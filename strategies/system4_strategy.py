# strategies/system4_strategy.py
import pandas as pd
import numpy as np
import time
from ta.trend import SMAIndicator
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
from .base_strategy import StrategyBase
from common.backtest_utils import simulate_trades_with_risk


class System4Strategy(StrategyBase):
    SYSTEM_NAME = "system4"
    """
    繧ｷ繧ｹ繝・Β4・壹Ο繝ｳ繧ｰ繝ｻ繝医Ξ繝ｳ繝峨・繝ｭ繝ｼ繝ｻ繝懊Λ繝・ぅ繝ｪ繝・ぅ
    - 繝輔ぅ繝ｫ繧ｿ繝ｼ:
        DollarVolume50 > 100M
        HV50 竏・[10,40]
    - 繧ｻ繝・ヨ繧｢繝・・:
        SPY Close > SPY SMA200
        驫俶氛 Close > SMA200
    - 繝ｩ繝ｳ繧ｭ繝ｳ繧ｰ:
        RSI4 縺悟ｰ上＆縺・・
    - 繧ｨ繝ｳ繝医Μ繝ｼ:
        鄙梧律Open縺ｧ謌占｡・
    - 謳榊・繧・
        Entry - 1.5 * ATR40
    - 蜀堺ｻ墓寺縺・
        謳榊・繧翫↓蠑輔▲縺九°縺｣縺溘ｉ蜀榊ｺｦ莉墓寺縺代ｋ
    - 蛻ｩ逶贋ｿ晁ｭｷ:
        20%縺ｮ繝医Ξ繝ｼ繝ｪ繝ｳ繧ｰ繧ｹ繝医ャ繝・
    - 蛻ｩ鬟溘＞縺ｪ縺・
    - 繝昴ず繧ｷ繝ｧ繝ｳ繧ｵ繧､繧ｸ繝ｳ繧ｰ:
        繝ｪ繧ｹ繧ｯ2%縲∵怙螟ｧ繧ｵ繧､繧ｺ10%縲∝酔譎・0驫俶氛
    """
    def __init__(self):
        super().__init__()

    # ===============================
    # 繧､繝ｳ繧ｸ繧ｱ繝ｼ繧ｿ繝ｼ險育ｮ・
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
                # ---- 繧､繝ｳ繧ｸ繧ｱ繝ｼ繧ｿ繝ｼ ----
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
                    f"投 繧､繝ｳ繧ｸ繧ｱ繝ｼ繧ｿ繝ｼ險育ｮ・ {processed}/{total} 莉ｶ 螳御ｺ・
                    f" | 邨碁℃: {em}蛻・es}遘・/ 谿九ｊ: 邏・{rm}蛻・rs}遘・
                )
                if buffer:
                    msg += f"\n驫俶氛: {', '.join(buffer)}"
                log_callback(msg)
                buffer.clear()

        if skipped > 0 and log_callback:
            log_callback(f"笞・・繝・・繧ｿ荳崎ｶｳ/險育ｮ怜､ｱ謨励〒繧ｹ繧ｭ繝・・: {skipped} 莉ｶ")

        return result_dict

    # ===============================
    # 蛟呵｣懃函謌撰ｼ・PY繝輔ぅ繝ｫ繧ｿ繝ｼ蠢・茨ｼ・
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
            raise ValueError("System4 縺ｫ縺ｯ SPY繝・・繧ｿ (market_df) 縺悟ｿ・ｦ√〒縺吶・)

        candidates_by_date = {}
        total = len(prepared_dict)
        processed, skipped = 0, 0
        buffer = []
        start_time = time.time()

        # 隼 SPY繝輔ぅ繝ｫ繧ｿ繝ｼ
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
                    # 隼 蟶ょｴ繝輔ぅ繝ｫ繧ｿ繝ｼ: SPY繧・00SMA荳・
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
                    f"投 繧ｻ繝・ヨ繧｢繝・・謚ｽ蜃ｺ: {processed}/{total} 莉ｶ 螳御ｺ・
                    f" | 邨碁℃: {em}蛻・es}遘・/ 谿九ｊ: 邏・{rm}蛻・rs}遘・
                )
                if buffer:
                    msg += f"\n驫俶氛: {', '.join(buffer)}"
                log_callback(msg)
                buffer.clear()

        # 隼 RSI4蟆上＆縺・・↓繧ｽ繝ｼ繝・
                # RSI4 昇順で上位N件のみ（YAML: backtest.top_n_rank）
        try:
            from config.settings import get_settings
            top_n = int(get_settings(create_dirs=False).backtest.top_n_rank)
        except Exception:
            top_n = 10
        for date in list(candidates_by_date.keys()):
            ranked = sorted(candidates_by_date[date], key=lambda x: x["RSI4"])
            candidates_by_date[date] = ranked[:top_n]
if skipped > 0 and log_callback:
            log_callback(f"笞・・繝・・繧ｿ荳崎ｶｳ/險育ｮ怜､ｱ謨励〒繧ｹ繧ｭ繝・・: {skipped} 莉ｶ")

        return result_dict

    # ===============================
    # 蛟呵｣懃函謌撰ｼ・PY繝輔ぅ繝ｫ繧ｿ繝ｼ蠢・茨ｼ・
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
            raise ValueError("System4 縺ｫ縺ｯ SPY繝・・繧ｿ (market_df) 縺悟ｿ・ｦ√〒縺吶・)

        candidates_by_date = {}
        total = len(prepared_dict)
        processed, skipped = 0, 0
        buffer = []
        start_time = time.time()

        # 隼 SPY繝輔ぅ繝ｫ繧ｿ繝ｼ
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
                    # 隼 蟶ょｴ繝輔ぅ繝ｫ繧ｿ繝ｼ: SPY繧・00SMA荳・
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
                    f"投 繧ｻ繝・ヨ繧｢繝・・謚ｽ蜃ｺ: {processed}/{total} 莉ｶ 螳御ｺ・
                    f" | 邨碁℃: {em}蛻・es}遘・/ 谿九ｊ: 邏・{rm}蛻・rs}遘・
                )
                if buffer:
                    msg += f"\n驫俶氛: {', '.join(buffer)}"
                log_callback(msg)
                buffer.clear()

        # 隼 RSI4蟆上＆縺・・↓繧ｽ繝ｼ繝・
        # RSI4 譏・・〒荳贋ｽ康莉ｶ縺ｮ縺ｿ・・AML: backtest.top_n_rank・・        try:
            from config.settings import get_settings
            top_n = int(get_settings(create_dirs=False).backtest.top_n_rank)
        except Exception:
            top_n = 10
        for date in list(candidates_by_date.keys()):
            ranked = sorted(candidates_by_date[date], key=lambda x: x["RSI4"])
            candidates_by_date[date] = ranked[:top_n]

        if skipped > 0 and log_callback:
            log_callback(f"笞・・蛟呵｣懈歓蜃ｺ荳ｭ縺ｫ繧ｹ繧ｭ繝・・: {skipped} 莉ｶ")

        merged_df = None  # System4縺ｧ縺ｯ邨仙粋DataFrame荳崎ｦ・
        return candidates_by_date, merged_df

    # ===============================
    # 繝舌ャ繧ｯ繝・せ繝・
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

            # 菫晄怏驫俶氛譖ｴ譁ｰ
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

                # 繝昴ず繧ｷ繝ｧ繝ｳ繧ｵ繧､繧ｺ
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

                    # 繝医Ξ繝ｼ繝ｪ繝ｳ繧ｰ繧ｹ繝医ャ繝玲峩譁ｰ
                    if close > highest:
                        highest = close
                    if close <= highest * 0.8:  # 20%荳玖誠
                        exit_date = df.index[idx2]
                        exit_price = close
                        break

                    # 謳榊・繧雁愛螳・
                    if close <= stop_price:
                        exit_date = df.index[idx2]
                        exit_price = close
                        # 蜀堺ｻ墓寺縺代・螳溯｣・ｽ吝慍縺ゅｊ
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

        # 譌ｧ繝ｭ繧ｸ繝・け縺ｯ蜈ｱ騾壹す繝溘Η繝ｬ繝ｼ繧ｿ繝ｼ縺ｸ邨ｱ蜷域ｸ医∩・医ョ繝・ラ繧ｳ繝ｼ繝牙炎髯､・・

    # 蜈ｱ騾壹す繝溘Η繝ｬ繝ｼ繧ｿ繝ｼ逕ｨ繝輔ャ繧ｯ・・ystem4: 繝ｭ繝ｳ繧ｰ縲・.5ATR繧ｹ繝医ャ繝励・0%繝医Ξ繝ｼ繝ｪ繝ｳ繧ｰ・・
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

