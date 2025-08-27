import pandas as pd
import time
from ta.volatility import AverageTrueRange
from .base_strategy import StrategyBase
from common.backtest_utils import simulate_trades_with_risk


class System6Strategy(StrategyBase):
    """
    繧ｷ繧ｹ繝・Β6・壹す繝ｧ繝ｼ繝医・繝溘・繝ｳ繝ｻ繝ｪ繝舌・繧ｸ繝ｧ繝ｳ繝ｻ繝上う繝ｻ繧ｷ繝・け繧ｹ繝・う繧ｵ繝ｼ繧ｸ
    """
    SYSTEM_NAME = "system6"

    def __init__(self):
        super().__init__()

    # ===============================
    # 繧､繝ｳ繧ｸ繧ｱ繝ｼ繧ｿ繝ｼ險育ｮ・
    # ===============================
    def prepare_data(
        self,
        raw_data_dict,
        progress_callback=None,
        log_callback=None,
        skip_callback=None,
        batch_size=50,
    ):
        result_dict = {}
        total = len(raw_data_dict)
        start_time = time.time()
        processed, skipped = 0, 0
        buffer = []

        for sym, df in raw_data_dict.items():
            df = df.copy()
            if len(df) < 50:
                skipped += 1
                processed += 1
                continue

            try:
                # ---- 繧､繝ｳ繧ｸ繧ｱ繝ｼ繧ｿ繝ｼ險育ｮ・----
                df["ATR10"] = AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=10
                ).average_true_range()
                df["DollarVolume50"] = (df["Close"] * df["Volume"]).rolling(50).mean()
                df["Return6D"] = df["Close"].pct_change(6)
                df["UpTwoDays"] = (df["Close"] > df["Close"].shift(1)) & (
                    df["Close"].shift(1) > df["Close"].shift(2)
                )

                # ---- 繧ｻ繝・ヨ繧｢繝・・譚｡莉ｶ ----
                df["setup"] = (
                    (df["Close"] > 5)
                    & (df["DollarVolume50"] > 10_000_000)
                    & (df["Return6D"] > 0.20)
                    & (df["UpTwoDays"])
                ).astype(int)

                result_dict[sym] = df

            except Exception:
                skipped += 1

            processed += 1
            buffer.append(sym)

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
                    f"投 繧､繝ｳ繧ｸ繧ｱ繝ｼ繧ｿ繝ｼ險育ｮ・ {processed}/{total} 莉ｶ 螳御ｺ・
                    f" | 邨碁℃: {em}蛻・es}遘・/ 谿九ｊ: 邏・{rm}蛻・rs}遘・
                )
                if buffer:
                    msg += f"
驫俶氛: {', '.join(buffer)}"
                log_callback(msg)
                buffer.clear()

        if skipped > 0:
            msg = f"笞・・繝・・繧ｿ荳崎ｶｳ/險育ｮ怜､ｱ謨励〒繧ｹ繧ｭ繝・・: {skipped} 莉ｶ"
            if skip_callback:
                skip_callback(msg)
            elif log_callback:
                log_callback(msg)

        return result_dict

    # ===============================
    # 蛟呵｣憺釜譟・歓蜃ｺ
    # ===============================
    def generate_candidates(
        self,
        prepared_dict,
        progress_callback=None,
        log_callback=None,
        skip_callback=None,
        batch_size=50,
    ):
        candidates_by_date = {}
        total = len(prepared_dict)
        start_time = time.time()
        processed, skipped = 0, 0
        buffer = []

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
                        "Return6D": row["Return6D"],
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
                remain = (
                    (elapsed / processed) * (total - processed) if processed > 0 else 0
                )
                em, es = divmod(int(elapsed), 60)
                rm, rs = divmod(int(remain), 60)
                msg = (
                    f"投 繧ｻ繝・ヨ繧｢繝・・謚ｽ蜃ｺ: {processed}/{total} 莉ｶ 螳御ｺ・
                    f" | 邨碁℃: {em}蛻・es}遘・/ 谿九ｊ: 邏・{rm}蛻・rs}遘・
                )
                if buffer:
                    msg += f"
驫俶氛: {', '.join(buffer)}"
                log_callback(msg)
                buffer.clear()

        # Return6D 降順の上位N件（YAML: backtest.top_n_rank）
        try:
            from config.settings import get_settings
            top_n = int(get_settings(create_dirs=False).backtest.top_n_rank)
        except Exception:
            top_n = 10
        for date in list(candidates_by_date.keys()):
            ranked = sorted(
                candidates_by_date[date], key=lambda x: x["Return6D"], reverse=True
            )
            candidates_by_date[date] = ranked[:top_n]

        if skipped > 0:
            msg = f"笞・・蛟呵｣懈歓蜃ｺ荳ｭ縺ｫ繧ｹ繧ｭ繝・・: {skipped} 莉ｶ"
            if skip_callback:
                skip_callback(msg)
            elif log_callback:
                log_callback(msg)

        merged_df = None  # System6縺ｧ縺ｯ繝ｩ繝ｳ繧ｭ繝ｳ繧ｰ逕ｨ邨仙粋DataFrame荳崎ｦ・
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

    # 蜈ｱ騾壹す繝溘Η繝ｬ繝ｼ繧ｿ繝ｼ逕ｨ繝輔ャ繧ｯ・・ystem6: 繧ｷ繝ｧ繝ｼ繝茨ｼ・
    def compute_entry(self, df: pd.DataFrame, candidate: dict, current_capital: float):
        try:
            entry_idx = df.index.get_loc(candidate["entry_date"])
        except Exception:
            return None
        if entry_idx <= 0 or entry_idx >= len(df):
            return None
        prev_close = float(df.iloc[entry_idx - 1]["Close"])
        ratio = float(self.config.get("entry_price_ratio_vs_prev_close", 1.05))
        entry_price = round(prev_close * ratio, 2)
        try:
            atr = float(df.iloc[entry_idx - 1]["ATR10"])
        except Exception:
            return None
        stop_mult = float(self.config.get("stop_atr_multiple", 3.0))
        stop_price = entry_price + stop_mult * atr
        if stop_price - entry_price <= 0:
            return None
        return entry_price, stop_price

    def compute_exit(
        self, df: pd.DataFrame, entry_idx: int, entry_price: float, stop_price: float
    ):
        profit_take_pct = float(self.config.get("profit_take_pct", 0.05))
        max_days = int(self.config.get("profit_take_max_days", 3))
        offset = 1
        while offset <= max_days and entry_idx + offset < len(df):
            row = df.iloc[entry_idx + offset]
            gain = (entry_price - row["Close"]) / entry_price
            if gain >= profit_take_pct:
                exit_idx = min(entry_idx + offset + 1, len(df) - 1)
                exit_date = df.index[exit_idx]
                exit_price = float(df.iloc[exit_idx]["Close"])
                return exit_price, exit_date
            if row["High"] >= stop_price:
                if entry_idx + offset < len(df) - 1:
                    prev_close2 = float(df.iloc[entry_idx + offset]["Close"])
                    ratio = float(self.config.get("entry_price_ratio_vs_prev_close", 1.05))
                    entry_price = round(prev_close2 * ratio, 2)
                    atr2 = float(df.iloc[entry_idx + offset]["ATR10"])
                    stop_mult = float(self.config.get("stop_atr_multiple", 3.0))
                    stop_price = entry_price + stop_mult * atr2
                    entry_idx = entry_idx + offset + 1
                    offset = 0
                else:
                    exit_date = df.index[entry_idx + offset]
                    exit_price = float(stop_price)
                    return exit_price, exit_date
            offset += 1
        idx2 = min(entry_idx + max_days, len(df) - 1)
        exit_date = df.index[idx2]
        exit_price = float(df.iloc[idx2]["Close"])
        return exit_price, exit_date

    def compute_pnl(self, entry_price: float, exit_price: float, shares: int) -> float:
        return (entry_price - exit_price) * shares
        risk_per_trade = 0.02 * capital
        max_pos_value = 0.10 * capital

        results, active_positions = [], []
        total_days = len(candidates_by_date)
        start_time = time.time()

        for i, (date, candidates) in enumerate(sorted(candidates_by_date.items()), 1):
            if on_progress:
                on_progress(i, total_days, start_time)
            if on_log and (i % 20 == 0 or i == total_days):
                on_log(i, total_days, start_time)

            # 菫晄怏驫俶氛謨ｴ逅・ｼ域怙螟ｧ10驫俶氛・・
            active_positions = [p for p in active_positions if p["exit_date"] >= date]
            slots = 10 - len(active_positions)
            if slots <= 0:
                continue

            for c in candidates[:slots]:
                df = prepared_dict[c["symbol"]]
                try:
                    entry_idx = df.index.get_loc(c["entry_date"])
                except KeyError:
                    continue
                if entry_idx == 0 or entry_idx >= len(df):
                    continue

                # === 蛻晏屓繧ｨ繝ｳ繝医Μ繝ｼ ===
                prev_close = df.iloc[entry_idx - 1]["Close"]
                entry_price = round(prev_close * 1.05, 2)  # 蜑肴律邨ょ､縺ｮ5%荳翫〒繧ｷ繝ｧ繝ｼ繝・
                atr = df.iloc[entry_idx - 1]["ATR10"]
                stop_price = entry_price + 3 * atr

                shares = min(
                    risk_per_trade / max(stop_price - entry_price, 1e-6),
                    max_pos_value / entry_price,
                )
                shares = int(shares)
                if shares <= 0:
                    continue

                entry_date = df.index[entry_idx]
                exit_date, exit_price = None, None

                # === 蛻ｩ遒ｺ繝ｻ謳榊・繧翫・蜀堺ｻ墓寺縺大愛螳・===
                offset = 1
                while offset <= 3 and entry_idx + offset < len(df):
                    row = df.iloc[entry_idx + offset]

                    # 蛻ｩ遒ｺ (+5%驕疲・ 竊・鄙悟霧讌ｭ譌･螟ｧ蠑輔￠ Close)
                    gain = (entry_price - row["Close"]) / entry_price
                    if gain >= 0.05:
                        exit_date = df.index[min(entry_idx + offset + 1, len(df) - 1)]
                        exit_price = df.loc[exit_date, "Close"]
                        break

                    # 謳榊・繧・(High 縺・stop_price 莉･荳・
                    if row["High"] >= stop_price:
                        exit_date = df.index[entry_idx + offset]
                        exit_price = stop_price

                        # === 蜀堺ｻ墓寺縺・===
                        if entry_idx + offset < len(df) - 1:
                            prev_close2 = df.iloc[entry_idx + offset]["Close"]
                            entry_price = round(prev_close2 * 1.05, 2)
                            atr2 = df.iloc[entry_idx + offset]["ATR10"]
                            stop_price = entry_price + 3 * atr2
                            entry_date = df.index[entry_idx + offset + 1]
                            offset = 1  # 鄙悟霧讌ｭ譌･縺九ｉ蜀榊愛螳夲ｼ育┌髯舌Ν繝ｼ繝鈴亟豁｢・・
                        else:
                            break
                    offset += 1

                # === 譎る俣繝吶・繧ｹ縺ｮ蛻ｩ鬟溘＞・・蝟ｶ讌ｭ譌･蠕後・螟ｧ蠑輔￠・・===
                if exit_price is None:
                    idx2 = min(entry_idx + 3, len(df) - 1)
                    exit_date = df.index[idx2]
                    exit_price = df.iloc[idx2]["Close"]

                if exit_price is None or pd.isna(exit_price):
                    continue

                pnl = (entry_price - exit_price) * shares
                return_pct = pnl / capital * 100

                results.append(
                    {
                        "symbol": c["symbol"],
                        "entry_date": entry_date,
                        "exit_date": exit_date,
                        "entry_price": entry_price,
                        "exit_price": round(exit_price, 2),
                        "shares": shares,
                        "pnl": round(pnl, 2),
                        "return_%": round(return_pct, 2),
                    }
                )
                active_positions.append({"symbol": c["symbol"], "exit_date": exit_date})

        return pd.DataFrame(results)






