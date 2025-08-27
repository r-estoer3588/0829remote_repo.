# strategies/system2_strategy.py
import time
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange
from .base_strategy import StrategyBase
from common.backtest_utils import simulate_trades_with_risk


class System2Strategy(StrategyBase):
    SYSTEM_NAME = "system2"

    def __init__(self):
        super().__init__()
    """
    繧ｷ繧ｹ繝・Β2・壹す繝ｧ繝ｼ繝・RSI繧ｹ繝ｩ繧ｹ繝・
    - 繝輔ぅ繝ｫ繧ｿ繝ｼ: Close>5, DollarVolume20>25M, ATR10/Close>0.03
    - 繧ｻ繝・ヨ繧｢繝・・: RSI3>90, 2騾｣髯ｽ邱・
    - 繝ｩ繝ｳ繧ｭ繝ｳ繧ｰ: ADX7 髯埼・
    - 謳榊・繧・ 螢ｲ蛟､ + 3ATR10
    - 蛻ｩ鬟溘＞: 鄙梧律4%莉･荳雁茜逶翫〒鄙梧律螟ｧ蠑輔￠豎ｺ貂医∵悴驕斐↑繧・譌･蠕檎ｿ梧律豎ｺ貂・
    - 繝昴ず繧ｷ繝ｧ繝ｳ繧ｵ繧､繧ｸ繝ｳ繧ｰ: 繝ｪ繧ｹ繧ｯ2%縲∵怙螟ｧ繧ｵ繧､繧ｺ10%縲∝・譛滄俣譛螟ｧ10繝昴ず繧ｷ繝ｧ繝ｳ
    """

    def prepare_data(
        self, raw_data_dict, progress_callback=None, log_callback=None, batch_size=50
    ):
        total = len(raw_data_dict)
        processed = 0
        start_time = time.time()
        buffer = []
        result_dict = {}
        skipped_count = 0  # 霑ｽ蜉: 繧ｹ繧ｭ繝・・莉ｶ謨ｰ繧ｫ繧ｦ繝ｳ繝・

        for sym, df in raw_data_dict.items():
            df = df.copy()

            # --- 繝・・繧ｿ荳崎ｶｳ繝√ぉ繝・け ---
            if len(df) < 20:
                skipped_count += 1  # 繝ｭ繧ｰ縺ｯ谿九＆縺壹き繧ｦ繝ｳ繝医□縺・
                processed += 1
                continue

            try:
                # --- 繧､繝ｳ繧ｸ繧ｱ繝ｼ繧ｿ繝ｼ險育ｮ・---
                df["RSI3"] = RSIIndicator(df["Close"], window=3).rsi()
                df["ADX7"] = ADXIndicator(
                    df["High"], df["Low"], df["Close"], window=7
                ).adx()
                df["ATR10"] = AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=10
                ).average_true_range()
            except Exception:
                skipped_count += 1  # 險育ｮ怜､ｱ謨励ｂ繧ｹ繧ｭ繝・・謇ｱ縺・
                processed += 1
                continue

            # --- 縺昴・莉悶・謖・ｨ・---
            df["DollarVolume20"] = (
                (df["Close"] * df["Volume"]).rolling(window=20).mean()
            )
            df["ATR_Ratio"] = df["ATR10"] / df["Close"]
            df["TwoDayUp"] = (df["Close"] > df["Close"].shift(1)) & (
                df["Close"].shift(1) > df["Close"].shift(2)
            )

            # --- 繧ｻ繝・ヨ繧｢繝・・譚｡莉ｶ ---
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

            # --- 騾ｲ謐玲峩譁ｰ ---
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
                    f"投 謖・ｨ呵ｨ育ｮ・ {processed}/{total} 莉ｶ 螳御ｺ・
                    f" | 邨碁℃: {em}蛻・es}遘・/ 谿九ｊ: 邏・{rm}蛻・rs}遘・
                )
                if buffer:
                    msg += f"\n驫俶氛: {', '.join(buffer)}"

                log_callback(msg)  # 笨・譁・ｭ怜・縺縺第ｸ｡縺・
                buffer.clear()

        # --- 譛蠕後↓繧ｹ繧ｭ繝・・莉ｶ謨ｰ繧偵∪縺ｨ繧√※陦ｨ遉ｺ ---
        if skipped_count > 0 and log_callback:
            log_callback(
                f"笞・・繝・・繧ｿ荳崎ｶｳ繝ｻ險育ｮ怜､ｱ謨励〒繧ｹ繧ｭ繝・・縺輔ｌ縺滄釜譟・ {skipped_count} 莉ｶ"
            )

        return result_dict

    def generate_candidates(self, prepared_dict, **kwargs):
        """
        繧ｻ繝・ヨ繧｢繝・・譚｡莉ｶ騾夐℃驫俶氛繧呈律蛻･縺ｫADX7髯埼・〒霑斐☆
        - System1縺ｨ蜷後§繧､繝ｳ繧ｿ繝ｼ繝輔ぉ繝ｼ繧ｹ縺ｫ邨ｱ荳・・wargs蜿励￠蜿悶ｊ蜿ｯ・・
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
        # ADX7降順で日別ランキングし、上位N件に絞る（YAML: backtest.top_n_rank）
        try:
            from config.settings import get_settings
            top_n = int(get_settings(create_dirs=False).backtest.top_n_rank)
        except Exception:
            top_n = 10
        candidates_by_date = {}
        for date, group in all_df.groupby("entry_date"):
            ranked = group.sort_values("ADX7", ascending=False)
            candidates_by_date[date] = ranked.head(top_n).to_dict("records")
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
    # 蜈ｱ騾壹す繝溘Η繝ｬ繝ｼ繧ｿ繝ｼ逕ｨ繝輔ャ繧ｯ・・ystem2繝ｫ繝ｼ繝ｫ・・
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

