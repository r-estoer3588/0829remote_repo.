import pandas as pd
import time
from ta.volatility import AverageTrueRange
from common.backtest_utils import log_progress


class System6Strategy:
    """
    システム6：ショート・ミーン・リバージョン・ハイ・シックスデイサージ
    """

    # ===============================
    # インジケーター計算
    # ===============================
    def prepare_data(self, raw_data_dict, progress_callback=None,
                     log_callback=None, skip_callback=None, batch_size=50):
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
                # ---- インジケーター計算 ----
                df["ATR10"] = AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=10).average_true_range()
                df["DollarVolume50"] = (
                    df["Close"] * df["Volume"]).rolling(50).mean()
                df["Return6D"] = df["Close"].pct_change(6)
                df["UpTwoDays"] = (
                    (df["Close"] > df["Close"].shift(1)) &
                    (df["Close"].shift(1) > df["Close"].shift(2))
                )

                # ---- セットアップ条件 ----
                df["setup"] = (
                    (df["Close"] > 5) &
                    (df["DollarVolume50"] > 10_000_000) &
                    (df["Return6D"] > 0.20) &
                    (df["UpTwoDays"])
                ).astype(int)

                result_dict[sym] = df

            except Exception:
                skipped += 1

            processed += 1
            buffer.append(sym)

            if progress_callback:
                progress_callback(processed, total)
            if (processed %
                    batch_size == 0 or processed == total) and log_callback:
                log_progress(
                    processed,
                    total,
                    start_time,
                    buffer,
                    "📊 インジケーター計算",
                    log_callback)
                buffer.clear()

        if skipped > 0:
            msg = f"⚠️ データ不足/計算失敗でスキップ: {skipped} 件"
            if skip_callback:
                skip_callback(msg)
            elif log_callback:
                log_callback(msg)

        return result_dict

    # ===============================
    # 候補銘柄抽出
    # ===============================
    def generate_candidates(
            self,
            prepared_dict,
            progress_callback=None,
            log_callback=None,
            skip_callback=None,
            batch_size=50):
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
            if (processed %
                    batch_size == 0 or processed == total) and log_callback:
                log_progress(
                    processed,
                    total,
                    start_time,
                    buffer,
                    "📊 セットアップ抽出",
                    log_callback)
                buffer.clear()

        for date in candidates_by_date:
            candidates_by_date[date] = sorted(
                candidates_by_date[date],
                key=lambda x: x["Return6D"],
                reverse=True)

        if skipped > 0:
            msg = f"⚠️ 候補抽出中にスキップ: {skipped} 件"
            if skip_callback:
                skip_callback(msg)
            elif log_callback:
                log_callback(msg)

        return candidates_by_date

    # ===============================
    # バックテスト実行
    # ===============================
    def run_backtest(self, prepared_dict, candidates_by_date, capital,
                     on_progress=None, on_log=None):
        risk_per_trade = 0.02 * capital
        max_pos_value = 0.10 * capital

        results, active_positions = [], []
        total_days = len(candidates_by_date)
        start_time = time.time()

        for i, (date, candidates) in enumerate(
                sorted(candidates_by_date.items()), 1):
            if on_progress:
                on_progress(i, total_days, start_time)
            if on_log and (i % 20 == 0 or i == total_days):
                on_log(i, total_days, start_time)

            active_positions = [
                p for p in active_positions if p["exit_date"] >= date]
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

                prev_close = df.iloc[entry_idx - 1]["Close"]
                entry_price = round(prev_close * 1.05, 2)
                atr = df.iloc[entry_idx - 1]["ATR10"]
                stop_price = entry_price + 3 * atr

                shares = min(
                    risk_per_trade / max(stop_price - entry_price, 1e-6),
                    max_pos_value / entry_price
                )
                shares = int(shares)
                if shares <= 0:
                    continue

                entry_date = df.index[entry_idx]
                exit_date, exit_price = None, None

                # ---- 利確判定 ----
                for offset in range(1, 4):
                    idx2 = entry_idx + offset
                    if idx2 >= len(df):
                        break
                    future_close = df.iloc[idx2]["Close"]
                    gain = (entry_price - future_close) / entry_price
                    if gain >= 0.05:
                        exit_date = df.index[min(idx2 + 1, len(df) - 1)]
                        if "Open" in df.columns:
                            exit_price = df.loc[exit_date].get(
                                "Open", df.loc[exit_date]["Close"])
                        else:
                            exit_price = df.loc[exit_date]["Close"]
                        break

                # ---- 利確できなかった場合 ----
                if exit_price is None:
                    idx2 = min(entry_idx + 3, len(df) - 1)
                    exit_date = df.index[idx2]
                    if "Open" in df.columns:
                        exit_price = df.iloc[idx2].get(
                            "Open", df.iloc[idx2]["Close"])
                    else:
                        exit_price = df.iloc[idx2]["Close"]

                # ---- 最終安全チェック ----
                if exit_price is None or pd.isna(exit_price):
                    continue

                pnl = (entry_price - exit_price) * shares
                return_pct = pnl / capital * 100

                results.append({
                    "symbol": c["symbol"],
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_price": entry_price,
                    "exit_price": round(exit_price, 2),
                    "shares": shares,
                    "pnl": round(pnl, 2),
                    "return_%": round(return_pct, 2)
                })
                active_positions.append(
                    {"symbol": c["symbol"], "exit_date": exit_date})

        return pd.DataFrame(results)
