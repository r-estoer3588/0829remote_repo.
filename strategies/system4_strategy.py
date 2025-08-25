# strategies/system4_strategy.py
import pandas as pd
import numpy as np
import time
from ta.trend import SMAIndicator
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
from .base_strategy import StrategyBase
from common.backtest_utils import simulate_trades_with_risk
from common.config import load_config


class System4Strategy(StrategyBase):
    """
    システム4：ロング・トレンド・ロー・ボラティリティ
    - フィルター:
        DollarVolume50 > 100M
        HV50 ∈ [10,40]
    - セットアップ:
        SPY Close > SPY SMA200
        銘柄 Close > SMA200
    - ランキング:
        RSI4 が小さい順
    - エントリー:
        翌日Openで成行
    - 損切り:
        Entry - 1.5 * ATR40
    - 再仕掛け:
        損切りに引っかかったら再度仕掛ける
    - 利益保護:
        20%のトレーリングストップ
    - 利食いなし
    - ポジションサイジング:
        リスク2%、最大サイズ10%、同時10銘柄
    """
    def __init__(self, config: dict | None = None):
        try:
            from common.config import load_config  # lazy to avoid import cycles
            self.config = config or load_config("System4")
        except Exception:
            self.config = config or {}

    # ===============================
    # インジケーター計算
    # ===============================
    def prepare_data(
        self, raw_data_dict, progress_callback=None, log_callback=None, batch_size=50
    ):
        result_dict = {}
        total = len(raw_data_dict)
        start_time = time.time()
        processed, skipped = 0, 0
        buffer = []

        for sym, df in raw_data_dict.items():
            df = df.copy()
            if len(df) < 200:
                skipped += 1
                processed += 1
                pass

            try:
                # ---- インジケーター ----
                df["SMA200"] = SMAIndicator(df["Close"], window=200).sma_indicator()
                df["ATR40"] = AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=40
                ).average_true_range()
                df["HV50"] = (
                    np.log(df["Close"] / df["Close"].shift(1)).rolling(50).std()
                    * np.sqrt(252)
                    * 100
                )
                df["RSI4"] = RSIIndicator(df["Close"], window=4).rsi()
                df["DollarVolume50"] = (df["Close"] * df["Volume"]).rolling(50).mean()

                result_dict[sym] = df
            except Exception:
                skipped += 1

            processed += 1
            buffer.append(sym)

            # --- 進捗更新 ---
            if progress_callback:
                progress_callback(processed, total)
            if (processed % batch_size == 0 or processed == total) and log_callback:
                elapsed = time.time() - start_time
                remain = (
                    (elapsed / processed) * (total - processed) if processed > 0 else 0
                )
                em, es = divmod(int(elapsed), 60)
                rm, rs = divmod(int(remain), 60)
                msg = (
                    f"📊 インジケーター計算: {processed}/{total} 件 完了"
                    f" | 経過: {em}分{es}秒 / 残り: 約 {rm}分{rs}秒"
                )
                if buffer:
                    msg += f"\n銘柄: {', '.join(buffer)}"
                log_callback(msg)
                buffer.clear()

        if skipped > 0 and log_callback:
            log_callback(f"⚠️ データ不足/計算失敗でスキップ: {skipped} 件")

        return result_dict

    # ===============================
    # 候補生成（SPYフィルター必須）
    # ===============================
    def generate_candidates(
        self,
        prepared_dict,
        market_df=None,
        progress_callback=None,
        log_callback=None,
        batch_size=50,
    ):
        if market_df is None:
            raise ValueError("System4 には SPYデータ (market_df) が必要です。")

        candidates_by_date = {}
        total = len(prepared_dict)
        processed, skipped = 0, 0
        buffer = []
        start_time = time.time()

        # 🔹 SPYフィルター
        spy_df = market_df.copy()
        spy_df["SMA200"] = SMAIndicator(spy_df["Close"], window=200).sma_indicator()
        spy_df["spy_filter"] = (spy_df["Close"] > spy_df["SMA200"]).astype(int)

        for sym, df in prepared_dict.items():
            try:
                df = df.copy()
                df["setup"] = (
                    (df["DollarVolume50"] > 100_000_000)
                    & (df["HV50"].between(10, 40))
                    & (df["Close"] > df["SMA200"])
                ).astype(int)

                setup_days = df[df["setup"] == 1]

                for date, row in setup_days.iterrows():
                    # 🔹 市場フィルター: SPYも200SMA上
                    if date not in spy_df.index:
                        pass
                    if spy_df.loc[date, "spy_filter"] == 0:
                        pass

                    entry_date = date + pd.Timedelta(days=1)
                    if entry_date not in df.index:
                        pass

                    rec = {
                        "symbol": sym,
                        "entry_date": entry_date,
                        "RSI4": row["RSI4"],
                        "ATR40": row["ATR40"],
                    }
                    candidates_by_date.setdefault(entry_date, []).append(rec)

            except Exception:
                skipped += 1

            processed += 1
            buffer.append(sym)

            # --- 進捗更新 ---
            if progress_callback:
                progress_callback(processed, total)
            if (processed % batch_size == 0 or processed == total) and log_callback:
                elapsed = time.time() - start_time
                remain = (
                    (elapsed / processed) * (total - processed) if processed > 0 else 0
                )
                em, es = divmod(int(elapsed), 60)
                rm, rs = divmod(int(remain), 60)
                msg = (
                    f"📊 セットアップ抽出: {processed}/{total} 件 完了"
                    f" | 経過: {em}分{es}秒 / 残り: 約 {rm}分{rs}秒"
                )
                if buffer:
                    msg += f"\n銘柄: {', '.join(buffer)}"
                log_callback(msg)
                buffer.clear()

        # 🔹 RSI4小さい順にソート
        for date in candidates_by_date:
            candidates_by_date[date] = sorted(
                candidates_by_date[date], key=lambda x: x["RSI4"]
            )

        if skipped > 0 and log_callback:
            log_callback(f"⚠️ 候補抽出中にスキップ: {skipped} 件")

        merged_df = None  # System4では結合DataFrame不要
        return candidates_by_date, merged_df

    # ===============================
    # バックテスト
    # ===============================
    def run_backtest(
        self, prepared_dict, candidates_by_date, capital, on_progress=None, on_log=None
    ):
        trades_df, _ = simulate_trades_with_risk(
            candidates_by_date,
            prepared_dict,
            capital,
            self,
            on_progress=on_progress,
            on_log=on_log,
        )
        return trades_df

            # 保有銘柄更新
            active_positions = [p for p in active_positions if p["exit_date"] >= date]
            slots = 10 - len(active_positions)
            if slots <= 0:
                pass

            for c in candidates[:slots]:
                df = prepared_dict[c["symbol"]]
                try:
                    entry_idx = df.index.get_loc(c["entry_date"])
                except KeyError:
                    pass
                if entry_idx == 0 or entry_idx >= len(df):
                    pass

                entry_price = df.iloc[entry_idx]["Open"]
                atr40 = df.iloc[entry_idx - 1]["ATR40"]
                stop_price = entry_price - 1.5 * atr40

                # ポジションサイズ
                shares = min(
                    risk_per_trade / max(entry_price - stop_price, 1e-6),
                    max_pos_value / entry_price,
                )
                shares = int(shares)
                if shares <= 0:
                    pass

                entry_date = df.index[entry_idx]
                highest = entry_price
                exit_date, exit_price = None, None

                for idx2 in range(entry_idx + 1, len(df)):
                    close = df.iloc[idx2]["Close"]

                    # トレーリングストップ更新
                    if close > highest:
                        highest = close
                    if close <= highest * 0.8:  # 20%下落
                        exit_date = df.index[idx2]
                        exit_price = close
                        break

                    # 損切り判定
                    if close <= stop_price:
                        exit_date = df.index[idx2]
                        exit_price = close
                        # 再仕掛けの実装余地あり
                        break

                if exit_date is None:
                    exit_date = df.index[-1]
                    exit_price = df.iloc[-1]["Close"]

                pnl = (exit_price - entry_price) * shares
                results.append(
                    {
                        "symbol": c["symbol"],
                        "entry_date": entry_date,
                        "exit_date": exit_date,
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "shares": shares,
                        "pnl": round(pnl, 2),
                        "return_%": round((pnl / capital) * 100, 2),
                    }
                )
                active_positions.append({"symbol": c["symbol"], "exit_date": exit_date})

        # 旧ロジックは共通シミュレーターへ統合済み（デッドコード削除）

    # 共通シミュレーター用フック（System4: ロング、1.5ATRストップ、20%トレーリング）
    def compute_entry(self, df: pd.DataFrame, candidate: dict, current_capital: float):
        try:
            entry_idx = df.index.get_loc(candidate["entry_date"])
        except Exception:
            return None
        if entry_idx <= 0 or entry_idx >= len(df):
            return None
        entry_price = float(df.iloc[entry_idx]["Open"])
        try:
            atr40 = float(df.iloc[entry_idx - 1]["ATR40"])
        except Exception:
            return None
        stop_mult = float(getattr(self, "config", {}).get("stop_atr_multiple", 1.5))
        stop_price = entry_price - stop_mult * atr40
        if entry_price - stop_price <= 0:
            return None
        return entry_price, stop_price

    def compute_exit(
        self, df: pd.DataFrame, entry_idx: int, entry_price: float, stop_price: float
    ):
        trail_pct = float(getattr(self, "config", {}).get("trailing_pct", 0.20))
        highest = entry_price
        for idx2 in range(entry_idx + 1, len(df)):
            close = float(df.iloc[idx2]["Close"])
            if close > highest:
                highest = close
            if close <= highest * (1 - trail_pct):
                return close, df.index[idx2]
            if close <= stop_price:
                return close, df.index[idx2]
        last_close = float(df.iloc[-1]["Close"])
        return last_close, df.index[-1]

    def compute_pnl(self, entry_price: float, exit_price: float, shares: int) -> float:
        return (exit_price - entry_price) * shares
