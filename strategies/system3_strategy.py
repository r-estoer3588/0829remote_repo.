# strategies/system3_strategy.py
import pandas as pd
import time
from ta.trend import SMAIndicator
from ta.volatility import AverageTrueRange
from .base_strategy import StrategyBase
from common.backtest_utils import simulate_trades_with_risk\nfrom ui_components import log_with_progress


class System3Strategy(StrategyBase):
    SYSTEM_NAME = "system3"

    def __init__(self):
        super().__init__()
    """
    System3 (Long mean-reversion):
    - side: long（共通シミュレータはデフォルト long）
    - compute_entry/exit が未実装時は共通デフォルト（ロング・トレーリング25%）に委譲。
    - 必須インジ: SMA150（テスト用軽量関数で生成）。
    """
    """
    繧ｷ繧ｹ繝・Β3・壹Ο繝ｳ繧ｰ繝ｻ繝溘・繝ｳ繝ｻ繝ｪ繝舌・繧ｸ繝ｧ繝ｳ繝ｻ繧ｻ繝ｫ繧ｪ繝・
    - 繧ｻ繝・ヨ繧｢繝・・: Close > SMA150, DropRate_3D >= 12.5%, Volume > 100荳・ ATR豈皮紫 >= 5%
    - 繝ｩ繝ｳ繧ｭ繝ｳ繧ｰ: DropRate_3D 髯埼・ｼ井ｸ玖誠蟷・′螟ｧ縺阪＞鬆・ｼ・
    - 謳榊・繧・ -2.5ATR, 蛻ｩ鬟溘＞: +4%莉･荳・or 譛螟ｧ3譌･菫晄戟
    - 繝ｪ繧ｹ繧ｯ2%縲∵怙螟ｧ10%繝昴ず繧ｷ繝ｧ繝ｳ縲∝酔譎ゆｿ晄怏譛螟ｧ10驫俶氛
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
            if len(df) < 150:  # 繝・・繧ｿ荳崎ｶｳ繝√ぉ繝・け
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

            # --- 騾ｲ謐玲峩譁ｰ ---
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
            if False and log_callback:
                elapsed = time.time() - start_time
                remain = (elapsed / processed) * (total - processed)
                log_callback(
                    f"投 謖・ｨ呵ｨ育ｮ・ {processed}/{total} 莉ｶ 螳御ｺ・
                    f" | 邨碁℃: {int(elapsed//60)}蛻・int(elapsed%60)}遘・
                    f" / 谿九ｊ: 邏・{int(remain//60)}蛻・int(remain%60)}遘箪n"
                    f"驫俶氛: {', '.join(buffer)}"
                )
                buffer.clear()

        # --- 繧ｹ繧ｭ繝・・莉ｶ謨ｰ ---
        if skipped > 0 and log_callback:
            log_callback(f"笞・・繝・・繧ｿ荳崎ｶｳ繝ｻ險育ｮ怜､ｱ謨励〒繧ｹ繧ｭ繝・・: {skipped} 莉ｶ")

        if log_callback:
            log_callback(f"投 謖・ｨ呵ｨ育ｮ怜ｮ御ｺ・| {total} 驫俶氛繧貞・逅・＠縺ｾ縺励◆")

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
        繧ｻ繝・ヨ繧｢繝・・騾夐℃驫俶氛繧呈律蛻･縺ｫ DropRate_3D 譏・・〒繝ｩ繝ｳ繧ｭ繝ｳ繧ｰ
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
            # 反 DropRate_3D繧呈ｮ九☆縺溘ａ譏守､ｺ逧・↓驕ｸ謚・
            setup_df = setup_df[["symbol", "entry_date", "DropRate_3D", "ATR10"]]
            all_signals.append(setup_df)
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
                remain = (elapsed / processed) * (total - processed)
                log_callback(
                    f"投 繧ｻ繝・ヨ繧｢繝・・謚ｽ蜃ｺ: {processed}/{total} 莉ｶ 螳御ｺ・
                    f" | 邨碁℃: {int(elapsed//60)}蛻・int(elapsed%60)}遘・
                    f" / 谿九ｊ: 邏・{int(remain//60)}蛻・int(remain%60)}遘箪n"
                    f"驫俶氛: {', '.join(buffer)}"
                )
                buffer.clear()

        if not all_signals:
            return {}, None

                all_df = pd.concat(all_signals)
        # DropRate_3D 降順で上位N件（YAML: backtest.top_n_rank）
        try:
            from config.settings import get_settings
            top_n = int(get_settings(create_dirs=False).backtest.top_n_rank)
        except Exception:
            top_n = 10
        candidates_by_date = {}
        for date, group in all_df.groupby("entry_date"):
            ranked = group.sort_values("DropRate_3D", ascending=False)
            candidates_by_date[date] = ranked.head(top_n).to_dict("records")
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
    # 蜈ｱ騾壹す繝溘Η繝ｬ繝ｼ繧ｿ繝ｼ逕ｨ繝輔ャ繧ｯ・・ystem3繝ｫ繝ｼ繝ｫ・・
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
        # 1..max_days 縺ｮ髢薙↓蛻ｩ遒ｺ驕疲・縺ｪ繧臥ｿ悟霧讌ｭ譌･Close縺ｧ豎ｺ貂・
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
        # 譛ｪ驕斐↑繧・max_days 蠕後・Close
        idx2 = min(entry_idx + max_days, len(df) - 1)
        exit_date = df.index[idx2]
        exit_price = df.iloc[idx2]["Close"]
        return exit_price, exit_date

    def compute_pnl(self, entry_price: float, exit_price: float, shares: int) -> float:
        return (exit_price - entry_price) * shares

    # --- テスト用の軽量インジ生成（必須: SMA150） ---
    def prepare_minimal_for_test(self, raw_data_dict: dict) -> dict:
        out = {}
        for sym, df in raw_data_dict.items():
            x = df.copy()
            x["SMA150"] = x["Close"].rolling(150).mean()
            out[sym] = x
        return out
