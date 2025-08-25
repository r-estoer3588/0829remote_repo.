# strategies/system2_strategy.py
import time
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange
from .base_strategy import StrategyBase
from common.backtest_utils import simulate_trades_with_risk
from common.config import load_config


class System2Strategy(StrategyBase):
    def __init__(self, config: dict | None = None):
        # Load merged config (defaults + System2 overrides)
        self.config = config or load_config("System2")
    """
    システム2：ショート RSIスラスト
    - フィルター: Close>5, DollarVolume20>25M, ATR10/Close>0.03
    - セットアップ: RSI3>90, 2連陽線
    - ランキング: ADX7 降順
    - 損切り: 売値 + 3ATR10
    - 利食い: 翌日4%以上利益で翌日大引け決済、未達なら2日後翌日決済
    - ポジションサイジング: リスク2%、最大サイズ10%、全期間最大10ポジション
    """

    def prepare_data(
        self, raw_data_dict, progress_callback=None, log_callback=None, batch_size=50
    ):
        total = len(raw_data_dict)
        processed = 0
        start_time = time.time()
        buffer = []
        result_dict = {}
        skipped_count = 0  # 追加: スキップ件数カウント

        for sym, df in raw_data_dict.items():
            df = df.copy()

            # --- データ不足チェック ---
            if len(df) < 20:
                skipped_count += 1  # ログは残さずカウントだけ
                processed += 1
                continue

            try:
                # --- インジケーター計算 ---
                df["RSI3"] = RSIIndicator(df["Close"], window=3).rsi()
                df["ADX7"] = ADXIndicator(
                    df["High"], df["Low"], df["Close"], window=7
                ).adx()
                df["ATR10"] = AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=10
                ).average_true_range()
            except Exception:
                skipped_count += 1  # 計算失敗もスキップ扱い
                processed += 1
                continue

            # --- その他の指標 ---
            df["DollarVolume20"] = (
                (df["Close"] * df["Volume"]).rolling(window=20).mean()
            )
            df["ATR_Ratio"] = df["ATR10"] / df["Close"]
            df["TwoDayUp"] = (df["Close"] > df["Close"].shift(1)) & (
                df["Close"].shift(1) > df["Close"].shift(2)
            )

            # --- セットアップ条件 ---
            df["setup"] = (
                (df["Close"] > 5)
                & (df["DollarVolume20"] > 25_000_000)
                & (df["ATR_Ratio"] > 0.03)
                & (df["RSI3"] > 90)
                & (df["TwoDayUp"])
            )

            result_dict[sym] = df
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
                    f"📊 指標計算: {processed}/{total} 件 完了"
                    f" | 経過: {em}分{es}秒 / 残り: 約 {rm}分{rs}秒"
                )
                if buffer:
                    msg += f"\n銘柄: {', '.join(buffer)}"

                log_callback(msg)  # ✅ 文字列だけ渡す
                buffer.clear()

        # --- 最後にスキップ件数をまとめて表示 ---
        if skipped_count > 0 and log_callback:
            log_callback(
                f"⚠️ データ不足・計算失敗でスキップされた銘柄: {skipped_count} 件"
            )

        return result_dict

    def generate_candidates(self, prepared_dict, **kwargs):
        """
        セットアップ条件通過銘柄を日別にADX7降順で返す
        - System1と同じインターフェースに統一（kwargs受け取り可）
        """
        all_signals = []
        for sym, df in prepared_dict.items():
            if "setup" not in df.columns or not df["setup"].any():
                continue
            setup_df = df[df["setup"]].copy()
            setup_df["symbol"] = sym
            setup_df["entry_date"] = setup_df.index + pd.Timedelta(days=1)
            all_signals.append(setup_df)

        if not all_signals:
            return {}, None

        all_df = pd.concat(all_signals)
        candidates_by_date = {
            date: group.sort_values("ADX7", ascending=False).to_dict("records")
            for date, group in all_df.groupby("entry_date")
        }
        return candidates_by_date, None

    def run_backtest(
        self, data_dict, candidates_by_date, capital, on_progress=None, on_log=None
    ):
        trades_df, _ = simulate_trades_with_risk(
            candidates_by_date,
            data_dict,
            capital,
            self,
            on_progress=on_progress,
            on_log=on_log,
        )
        return trades_df

    # ============================================================
    # 共通シミュレーター用フック（System2ルール）
    # ============================================================
    def compute_entry(self, df: pd.DataFrame, candidate: dict, current_capital: float):
        try:
            entry_idx = df.index.get_loc(candidate["entry_date"])
        except Exception:
            return None
        if entry_idx <= 0 or entry_idx >= len(df):
            return None
        prior_close = df.iloc[entry_idx - 1]["Close"]
        entry_price = df.iloc[entry_idx]["Open"]
        min_gap = float(self.config.get("entry_min_gap_pct", 0.04))
        if entry_price < prior_close * (1 + min_gap):
            return None
        try:
            atr = df.iloc[entry_idx - 1]["ATR10"]
        except Exception:
            return None
        stop_mult = float(self.config.get("stop_atr_multiple", 3.0))
        stop_price = entry_price + stop_mult * atr
        return entry_price, stop_price

    def compute_exit(
        self, df: pd.DataFrame, entry_idx: int, entry_price: float, stop_price: float
    ):
        exit_date, exit_price = None, None
        profit_take_pct = float(self.config.get("profit_take_pct", 0.04))
        max_days = int(self.config.get("profit_take_max_days", 3))
        for offset in range(1, max_days + 1):
            idx2 = entry_idx + offset
            if idx2 >= len(df):
                break
            row = df.iloc[idx2]
            if row["High"] >= stop_price:
                exit_date = df.index[idx2]
                exit_price = stop_price
                break
            gain = (entry_price - row["Close"]) / entry_price
            if gain >= profit_take_pct:
                next_idx = min(idx2 + 1, len(df) - 1)
                exit_date = df.index[next_idx]
                exit_price = df.iloc[next_idx]["Open"]
                break
        if exit_price is None:
            fallback_days = int(self.config.get("fallback_exit_after_days", 2))
            idx2 = min(entry_idx + fallback_days, len(df) - 1)
            next_idx = min(idx2 + 1, len(df) - 1)
            exit_date = df.index[next_idx]
            exit_price = df.iloc[next_idx]["Open"]
        return exit_price, exit_date

    def compute_pnl(self, entry_price: float, exit_price: float, shares: int) -> float:
        return (entry_price - exit_price) * shares
