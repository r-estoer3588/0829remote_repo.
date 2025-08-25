import pandas as pd
import time
from ta.trend import SMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from .base_strategy import StrategyBase
from common.backtest_utils import simulate_trades_with_risk
from common.config import load_config


class System5Strategy(StrategyBase):
    def __init__(self, config: dict | None = None):
        self.config = config or load_config("System5")
    """
    システム5：ロング・ミーンリバージョン・ハイADXリバーサル
    """

    # ===============================
    # インジケーター計算
    # ===============================
    def prepare_data(
        self, raw_data_dict, progress_callback=None, log_callback=None, batch_size=50
    ):
        result_dict = {}
        total = len(raw_data_dict)
        processed, skipped = 0, 0
        buffer = []
        start_time = time.time()

        for sym, df in raw_data_dict.items():
            df = df.copy()
            if len(df) < 100:
                skipped += 1
                processed += 1
                continue

            try:
                # ---- インジケーター ----
                df["SMA100"] = SMAIndicator(df["Close"], window=100).sma_indicator()
                df["ATR10"] = AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=10
                ).average_true_range()
                df["ADX7"] = ADXIndicator(
                    df["High"], df["Low"], df["Close"], window=7
                ).adx()
                df["RSI3"] = RSIIndicator(df["Close"], window=3).rsi()
                df["AvgVolume50"] = df["Volume"].rolling(50).mean()
                df["DollarVolume50"] = (df["Close"] * df["Volume"]).rolling(50).mean()
                df["ATR_Pct"] = df["ATR10"] / df["Close"]

                # ---- セットアップ ----
                df["setup"] = (
                    (df["Close"] > df["SMA100"] + df["ATR10"])
                    & (df["ADX7"] > 55)
                    & (df["RSI3"] < 50)
                    & (df["AvgVolume50"] > 500_000)
                    & (df["DollarVolume50"] > 2_500_000)
                    & (df["ATR_Pct"] > 0.04)
                ).astype(int)

                result_dict[sym] = df
            except Exception:
                skipped += 1

            processed += 1
            buffer.append(sym)

            # 進捗更新
            if progress_callback:
                progress_callback(processed, total)
            # ログ更新
            if (processed % batch_size == 0 or processed == total) and log_callback:
                elapsed = time.time() - start_time
                remain = (elapsed / processed) * (total - processed) if processed else 0
                log_callback(
                    f"📊 インジケーター計算: {processed}/{total} 件 完了"
                    f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
                    f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒\n"
                    f"銘柄: {', '.join(buffer)}"
                )
                buffer.clear()

        if skipped > 0 and log_callback:
            log_callback(f"⚠️ データ不足/計算失敗でスキップ: {skipped} 件")

        return result_dict

    # ===============================
    # 候補銘柄抽出
    # ===============================
    def generate_candidates(
        self, prepared_dict, progress_callback=None, log_callback=None, batch_size=50
    ):
        candidates_by_date = {}
        total = len(prepared_dict)
        processed, skipped = 0, 0
        buffer = []
        start_time = time.time()

        for sym, df in prepared_dict.items():
            try:
                setup_days = df[df["setup"] == 1]
                for date, row in setup_days.iterrows():
                    entry_date = date + pd.Timedelta(days=1)
                    if entry_date not in df.index:
                        continue
                    rec = {
                        "symbol": sym,
                        "entry_date": entry_date,
                        "ADX7": row["ADX7"],
                        "ATR10": row["ATR10"],
                    }
                    candidates_by_date.setdefault(entry_date, []).append(rec)
            except Exception:
                skipped += 1

            processed += 1
            buffer.append(sym)

            if progress_callback:
                progress_callback(processed, total)
            if (processed % batch_size == 0 or processed == total) and log_callback:
                elapsed = time.time() - start_time
                remaining = (elapsed / processed) * (total - processed)
                em, es = divmod(int(elapsed), 60)
                rm, rs = divmod(int(remaining), 60)
                log_callback(
                    f"📊 セットアップ抽出: {processed}/{total} 件 完了"
                    f" | 経過: {em}分{es}秒 / 残り: 約 {rm}分{rs}秒"
                    f"\n銘柄: {', '.join(buffer)}"
                )
                buffer.clear()

        if skipped > 0 and log_callback:
            log_callback(f"⚠️ 候補抽出中にスキップ: {skipped} 件")

        # ADX7 降順ランキング
        for date in candidates_by_date:
            candidates_by_date[date] = sorted(
                candidates_by_date[date], key=lambda x: x["ADX7"], reverse=True
            )

        merged_df = None  # System5ではランキング用に結合DataFrameは不要
        return candidates_by_date, merged_df

    # ===============================
    # バックテスト実行
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

    # 共通シミュレーター用フック（System5）
    def compute_entry(self, df: pd.DataFrame, candidate: dict, current_capital: float):
        try:
            entry_idx = df.index.get_loc(candidate["entry_date"])
        except Exception:
            return None
        if entry_idx <= 0 or entry_idx >= len(df):
            return None
        prev_close = float(df.iloc[entry_idx - 1]["Close"])
        ratio = float(getattr(self, "config", {}).get("entry_price_ratio_vs_prev_close", 0.97))
        entry_price = round(prev_close * ratio, 2)
        try:
            atr = float(df.iloc[entry_idx - 1]["ATR10"])
        except Exception:
            return None
        stop_mult = float(getattr(self, "config", {}).get("stop_atr_multiple", 3.0))
        stop_price = entry_price - stop_mult * atr
        if entry_price - stop_price <= 0:
            return None
        # 保存: 初期ATRを利益目標に使う
        self._last_entry_atr = atr
        return entry_price, stop_price

    def compute_exit(
        self, df: pd.DataFrame, entry_idx: int, entry_price: float, stop_price: float
    ):
        atr = getattr(self, "_last_entry_atr", None)
        if atr is None:
            try:
                atr = float(df.iloc[entry_idx - 1]["ATR10"])
            except Exception:
                atr = 0.0
        target_mult = float(getattr(self, "config", {}).get("target_atr_multiple", 1.0))
        target_price = entry_price + target_mult * atr
        fallback_days = int(getattr(self, "config", {}).get("fallback_exit_after_days", 6))

        offset = 1
        while offset <= fallback_days and entry_idx + offset < len(df):
            row = df.iloc[entry_idx + offset]
            # 利確条件: 当日高値が目標達成 → 翌営業日Open
            if row["High"] >= target_price:
                exit_idx = min(entry_idx + offset + 1, len(df) - 1)
                exit_date = df.index[exit_idx]
                exit_price = float(df.iloc[exit_idx]["Open"])
                return exit_price, exit_date
            # 損切り: 当日安値がストップ割れ → 即日ストップ価格
            if row["Low"] <= stop_price:
                # 再仕掛け
                if entry_idx + offset < len(df) - 1:
                    prev_close2 = float(df.iloc[entry_idx + offset]["Close"])
                    ratio = float(getattr(self, "config", {}).get("entry_price_ratio_vs_prev_close", 0.97))
                    entry_price = round(prev_close2 * ratio, 2)
                    atr2 = float(df.iloc[entry_idx + offset]["ATR10"])
                    stop_mult = float(getattr(self, "config", {}).get("stop_atr_multiple", 3.0))
                    stop_price = entry_price - stop_mult * atr2
                    target_price = entry_price + target_mult * atr2
                    entry_idx = entry_idx + offset
                    offset = 0  # 翌ループで +1 される
                else:
                    exit_date = df.index[entry_idx + offset]
                    exit_price = float(stop_price)
                    return exit_price, exit_date
            offset += 1

        # フォールバック: fallback_days 後の寄り付き
        idx2 = min(entry_idx + fallback_days, len(df) - 1)
        exit_date = df.index[idx2]
        exit_price = float(df.iloc[idx2]["Open"])
        return exit_price, exit_date

    def compute_pnl(self, entry_price: float, exit_price: float, shares: int) -> float:
        return (exit_price - entry_price) * shares
