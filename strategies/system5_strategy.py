import pandas as pd
import time
from ta.trend import SMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from .base_strategy import StrategyBase
from common.backtest_utils import simulate_trades_with_risk
from ui_components import log_with_progress


class System5Strategy(StrategyBase):
    SYSTEM_NAME = "system5"

    def __init__(self):
        super().__init__()
    """
    System5 (Long mean-reversion with ADX):
    - side: long（共通シミュレータはデフォルト long）
    - compute_* 未実装時は共通デフォルトに委譲。
    - 必須インジ: SMA100（テスト用軽量関数で生成）。
    """
    """
    繧ｷ繧ｹ繝・Β5・壹Ο繝ｳ繧ｰ繝ｻ繝溘・繝ｳ繝ｪ繝舌・繧ｸ繝ｧ繝ｳ繝ｻ繝上うADX繝ｪ繝舌・繧ｵ繝ｫ
    """

    # ===============================
    # 繧､繝ｳ繧ｸ繧ｱ繝ｼ繧ｿ繝ｼ險育ｮ・
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
                # ---- 繧､繝ｳ繧ｸ繧ｱ繝ｼ繧ｿ繝ｼ ----
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

                # ---- 繧ｻ繝・ヨ繧｢繝・・ ----
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

            # 騾ｲ謐玲峩譁ｰ
            if progress_callback:
                progress_callback(processed, total)
            if (processed % batch_size == 0 or processed == total):
                log_with_progress(
                    processed,
                    total,
                    start_time,
                    prefix="📊 インジケーター計算",
                    batch=batch_size,
                    log_func=log_callback,
                    extra_msg=(f"銘柄: {', '.join(buffer)}" if buffer else None),
                )
                buffer.clear()
            # 繝ｭ繧ｰ譖ｴ譁ｰ
            if False and log_callback:
                elapsed = time.time() - start_time
                remain = (elapsed / processed) * (total - processed) if processed else 0
                log_callback(
                    f"投 繧､繝ｳ繧ｸ繧ｱ繝ｼ繧ｿ繝ｼ險育ｮ・ {processed}/{total} 莉ｶ 螳御ｺ・
                    f" | 邨碁℃: {int(elapsed//60)}蛻・int(elapsed%60)}遘・
                    f" / 谿九ｊ: 邏・{int(remain//60)}蛻・int(remain%60)}遘箪n"
                    f"驫俶氛: {', '.join(buffer)}"
                )
                buffer.clear()

        if skipped > 0 and log_callback:
            log_callback(f"笞・・繝・・繧ｿ荳崎ｶｳ/險育ｮ怜､ｱ謨励〒繧ｹ繧ｭ繝・・: {skipped} 莉ｶ")

        return result_dict

    # ===============================
    # 蛟呵｣憺釜譟・歓蜃ｺ
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
            if (processed % batch_size == 0 or processed == total):
                log_with_progress(
                    processed,
                    total,
                    start_time,
                    prefix="📊 候補抽出",
                    batch=batch_size,
                    log_func=log_callback,
                    extra_msg=(f"銘柄: {', '.join(buffer)}" if buffer else None),
                )
                buffer.clear()
            if False and log_callback:
                elapsed = time.time() - start_time
                remaining = (elapsed / processed) * (total - processed)
                em, es = divmod(int(elapsed), 60)
                rm, rs = divmod(int(remaining), 60)
                log_callback(
                    f"投 繧ｻ繝・ヨ繧｢繝・・謚ｽ蜃ｺ: {processed}/{total} 莉ｶ 螳御ｺ・
                    f" | 邨碁℃: {em}蛻・es}遘・/ 谿九ｊ: 邏・{rm}蛻・rs}遘・
                    f"\n驫俶氛: {', '.join(buffer)}"
                )
                buffer.clear()

        if skipped > 0 and log_callback:
            log_callback(f"笞・・蛟呵｣懈歓蜃ｺ荳ｭ縺ｫ繧ｹ繧ｭ繝・・: {skipped} 莉ｶ")

                if skipped > 0 and log_callback:
            log_callback(f"⚠ 警告 候補抽出中にスキップ: {skipped} 件")

        # ADX7 降順の上位N件のみ（YAML: backtest.top_n_rank）
        try:
            from config.settings import get_settings
            top_n = int(get_settings(create_dirs=False).backtest.top_n_rank)
        except Exception:
            top_n = 10
        for date in list(candidates_by_date.keys()):
            ranked = sorted(
                candidates_by_date[date], key=lambda x: x["ADX7"], reverse=True
            )
            candidates_by_date[date] = ranked[:top_n]

        merged_df = None  # System5ではランキング用に結合DataFrameは不要
        return candidates_by_date, merged_df

    # ===============================
    # 繝舌ャ繧ｯ繝・せ繝亥ｮ溯｡・
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

    # 蜈ｱ騾壹す繝溘Η繝ｬ繝ｼ繧ｿ繝ｼ逕ｨ繝輔ャ繧ｯ・・ystem5・・
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
        # 菫晏ｭ・ 蛻晄悄ATR繧貞茜逶顔岼讓吶↓菴ｿ縺・
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
            # 蛻ｩ遒ｺ譚｡莉ｶ: 蠖捺律鬮伜､縺檎岼讓咎＃謌・竊・鄙悟霧讌ｭ譌･Open
            if row["High"] >= target_price:
                exit_idx = min(entry_idx + offset + 1, len(df) - 1)
                exit_date = df.index[exit_idx]
                exit_price = float(df.iloc[exit_idx]["Open"])
                return exit_price, exit_date
            # 謳榊・繧・ 蠖捺律螳牙､縺後せ繝医ャ繝怜牡繧・竊・蜊ｳ譌･繧ｹ繝医ャ繝嶺ｾ｡譬ｼ
            if row["Low"] <= stop_price:
                # 蜀堺ｻ墓寺縺・
                if entry_idx + offset < len(df) - 1:
                    prev_close2 = float(df.iloc[entry_idx + offset]["Close"])
                    ratio = float(getattr(self, "config", {}).get("entry_price_ratio_vs_prev_close", 0.97))
                    entry_price = round(prev_close2 * ratio, 2)
                    atr2 = float(df.iloc[entry_idx + offset]["ATR10"])
                    stop_mult = float(getattr(self, "config", {}).get("stop_atr_multiple", 3.0))
                    stop_price = entry_price - stop_mult * atr2
                    target_price = entry_price + target_mult * atr2
                    entry_idx = entry_idx + offset
                    offset = 0  # 鄙後Ν繝ｼ繝励〒 +1 縺輔ｌ繧・
                else:
                    exit_date = df.index[entry_idx + offset]
                    exit_price = float(stop_price)
                    return exit_price, exit_date
            offset += 1

        # 繝輔か繝ｼ繝ｫ繝舌ャ繧ｯ: fallback_days 蠕後・蟇・ｊ莉倥″
        idx2 = min(entry_idx + fallback_days, len(df) - 1)
        exit_date = df.index[idx2]
        exit_price = float(df.iloc[idx2]["Open"])
        return exit_price, exit_date

    def compute_pnl(self, entry_price: float, exit_price: float, shares: int) -> float:
        return (exit_price - entry_price) * shares

    # --- テスト用の軽量インジ生成（必須: SMA100） ---
    def prepare_minimal_for_test(self, raw_data_dict: dict) -> dict:
        out = {}
        for sym, df in raw_data_dict.items():
            x = df.copy()
            x["SMA100"] = x["Close"].rolling(100).mean()
            out[sym] = x
        return out
