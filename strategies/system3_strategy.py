# strategies/system3_strategy.py
import pandas as pd
import time
from ta.trend import SMAIndicator
from ta.volatility import AverageTrueRange
from .base_strategy import StrategyBase
from common.backtest_utils import simulate_trades_with_risk
from common.config import load_config


class System3Strategy(StrategyBase):
    def __init__(self, config: dict | None = None):
        self.config = config or load_config("System3")
    """
    システム3：ロング・ミーン・リバージョン・セルオフ
    - セットアップ: Close > SMA150, DropRate_3D >= 12.5%, Volume > 100万, ATR比率 >= 5%
    - ランキング: DropRate_3D 降順（下落幅が大きい順）
    - 損切り: -2.5ATR, 利食い: +4%以上 or 最大3日保持
    - リスク2%、最大10%ポジション、同時保有最大10銘柄
    """

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
            if len(df) < 150:  # データ不足チェック
                skipped += 1
                processed += 1
                continue

            try:
                df["SMA150"] = SMAIndicator(df["Close"], window=150).sma_indicator()
                df["ATR10"] = AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=10
                ).average_true_range()
                df["DropRate_3D"] = -(df["Close"].pct_change(3))
                df["AvgVolume50"] = df["Volume"].rolling(50).mean()
                df["ATR_Ratio"] = df["ATR10"] / df["Close"]

                df["setup"] = (
                    (df["Close"] > df["SMA150"])
                    & (df["DropRate_3D"] >= 0.125)
                    & (df["Close"] > 1)
                    & (df["AvgVolume50"] >= 1_000_000)
                    & (df["ATR_Ratio"] >= 0.05)
                ).astype(int)

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
                remain = (elapsed / processed) * (total - processed)
                log_callback(
                    f"📊 指標計算: {processed}/{total} 件 完了"
                    f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
                    f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒\n"
                    f"銘柄: {', '.join(buffer)}"
                )
                buffer.clear()

        # --- スキップ件数 ---
        if skipped > 0 and log_callback:
            log_callback(f"⚠️ データ不足・計算失敗でスキップ: {skipped} 件")

        if log_callback:
            log_callback(f"📊 指標計算完了 | {total} 銘柄を処理しました")

        return result_dict

    def generate_candidates(
        self,
        prepared_dict,
        progress_callback=None,
        log_callback=None,
        batch_size=50,
        **kwargs,
    ):
        """
        セットアップ通過銘柄を日別に DropRate_3D 昇順でランキング
        """
        all_signals = []
        total = len(prepared_dict)
        processed = 0
        buffer = []
        start_time = time.time()

        for sym, df in prepared_dict.items():
            if "setup" not in df.columns or not df["setup"].any():
                continue
            setup_df = df[df["setup"] == 1].copy()
            setup_df["symbol"] = sym
            setup_df["entry_date"] = setup_df.index + pd.Timedelta(days=1)
            # 🔽 DropRate_3Dを残すため明示的に選択
            setup_df = setup_df[["symbol", "entry_date", "DropRate_3D", "ATR10"]]
            all_signals.append(setup_df)
            processed += 1
            buffer.append(sym)

            if progress_callback:
                progress_callback(processed, total)
            if (processed % batch_size == 0 or processed == total) and log_callback:
                elapsed = time.time() - start_time
                remain = (elapsed / processed) * (total - processed)
                log_callback(
                    f"📊 セットアップ抽出: {processed}/{total} 件 完了"
                    f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
                    f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒\n"
                    f"銘柄: {', '.join(buffer)}"
                )
                buffer.clear()

        if not all_signals:
            return {}, None

        all_df = pd.concat(all_signals)
        candidates_by_date = {
            date: group.sort_values("DropRate_3D", ascending=False).to_dict("records")
            for date, group in all_df.groupby("entry_date")
        }
        return candidates_by_date, None

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

    # ============================================================
    # 共通シミュレーター用フック（System3ルール）
    # ============================================================
    def compute_entry(self, df: pd.DataFrame, candidate: dict, current_capital: float):
        try:
            entry_idx = df.index.get_loc(candidate["entry_date"])
        except Exception:
            return None
        if entry_idx <= 0 or entry_idx >= len(df):
            return None
        prev_close = df.iloc[entry_idx - 1]["Close"]
        ratio = float(self.config.get("entry_price_ratio_vs_prev_close", 0.93))
        entry_price = round(prev_close * ratio, 2)
        try:
            atr = df.iloc[entry_idx - 1]["ATR10"]
        except Exception:
            return None
        stop_mult = float(self.config.get("stop_atr_multiple", 2.5))
        stop_price = entry_price - stop_mult * atr
        if entry_price - stop_price <= 0:
            return None
        return entry_price, stop_price

    def compute_exit(
        self, df: pd.DataFrame, entry_idx: int, entry_price: float, stop_price: float
    ):
        profit_take_pct = float(self.config.get("profit_take_pct", 0.04))
        max_days = int(self.config.get("profit_take_max_days", 3))
        # 1..max_days の間に利確達成なら翌営業日Closeで決済
        for offset in range(1, max_days + 1):
            idx2 = entry_idx + offset
            if idx2 >= len(df):
                break
            future_close = df.iloc[idx2]["Close"]
            gain = (future_close - entry_price) / entry_price
            if gain >= profit_take_pct:
                exit_idx = min(idx2 + 1, len(df) - 1)
                exit_date = df.index[exit_idx]
                exit_price = df.iloc[exit_idx]["Close"]
                return exit_price, exit_date
        # 未達なら max_days 後のClose
        idx2 = min(entry_idx + max_days, len(df) - 1)
        exit_date = df.index[idx2]
        exit_price = df.iloc[idx2]["Close"]
        return exit_price, exit_date

    def compute_pnl(self, entry_price: float, exit_price: float, shares: int) -> float:
        return (exit_price - entry_price) * shares
