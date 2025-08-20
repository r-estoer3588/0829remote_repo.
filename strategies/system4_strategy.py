# strategies/system4_strategy.py
import pandas as pd
import numpy as np
import time
from ta.trend import SMAIndicator
from ta.volatility import AverageTrueRange
from common.backtest_utils import log_progress   # ← 共通ユーティリティ呼び出し


class System4Strategy:
    """
    システム4：ロング・トレンド・ロー・ボラティリティ
    """

    # ===============================
    # インジケーター計算
    # ===============================
    def prepare_data(
            self,
            raw_data_dict,
            progress_callback=None,
            log_callback=None,
            batch_size=50):
        result_dict = {}
        total = len(raw_data_dict)
        start_time = time.time()
        processed, skipped = 0, 0
        buffer = []

        for sym, df in raw_data_dict.items():
            df = df.copy()
            if len(df) < 200:  # データ不足はスキップ
                skipped += 1
                processed += 1
                continue

            try:
                # ---- インジケーター計算 ----
                df["SMA200"] = SMAIndicator(
                    df["Close"], window=200).sma_indicator()
                df["ATR14"] = AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=14).average_true_range()
                df["ATR40"] = AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=40).average_true_range()
                df["HV20"] = (
                    np.log(
                        df["Close"] /
                        df["Close"].shift(1)).rolling(20).std() *
                    np.sqrt(252) *
                    100)
                df["AvgVolume50"] = df["Volume"].rolling(50).mean()
                df["ATR14_Ratio"] = df["ATR14"] / df["Close"]

                df["setup"] = (
                    (df["Close"] > 1) &
                    (df["AvgVolume50"] >= 1_000_000) &
                    (df["ATR14_Ratio"] > 0.05) &
                    (df["Close"] > df["SMA200"])
                ).astype(int)

                result_dict[sym] = df
            except Exception:
                skipped += 1

            processed += 1
            buffer.append(sym)

            # 進捗ログ
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

        if skipped > 0 and log_callback:
            log_callback(f"⚠️ データ不足/計算失敗でスキップ: {skipped} 件")

        return result_dict

    # ===============================
    # 候補銘柄抽出
    # ===============================
    def generate_candidates(
            self,
            prepared_dict,
            progress_callback=None,
            log_callback=None,
            batch_size=50):
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
                        "ATR14": row["ATR14"],
                        "ATR40": row["ATR40"],
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

        if skipped > 0 and log_callback:
            log_callback(f"⚠️ 候補抽出中にスキップ: {skipped} 件")

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
            # ---- 進捗更新 ----
            if on_progress:
                on_progress(i, total_days, start_time)
            if on_log and (i % 20 == 0 or i == total_days):
                on_log(i, total_days, start_time)

            # ---- 保有銘柄整理（10銘柄上限） ----
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

                entry_price = df.iloc[entry_idx]["Open"]
                atr = df.iloc[entry_idx - 1]["ATR14"]
                stop_price = entry_price - 3 * atr

                # ---- ポジションサイズ計算 ----
                shares = min(
                    risk_per_trade / max(entry_price - stop_price, 1e-6),
                    max_pos_value / entry_price
                )
                shares = int(shares)
                if shares <= 0:
                    continue

                entry_date = df.index[entry_idx]
                exit_date, exit_price = None, None

                # ---- 利確判定（+10%で翌日大引け決済） ----
                for offset in range(1, len(df) - entry_idx):
                    idx2 = entry_idx + offset
                    future_close = df.iloc[idx2]["Close"]
                    gain = (future_close - entry_price) / entry_price
                    if gain >= 0.10:
                        exit_date = df.index[min(
                            idx2 + 1, len(df) - 1)]  # 翌日大引け
                        exit_price = df.loc[exit_date, "Close"]
                        break

                if exit_price is None:
                    continue

                pnl = (exit_price - entry_price) * shares
                results.append({
                    "symbol": c["symbol"],
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "shares": shares,
                    "pnl": round(pnl, 2),
                    "return_%": round((pnl / capital) * 100, 2)
                })
                active_positions.append(
                    {"symbol": c["symbol"], "exit_date": exit_date})

        return pd.DataFrame(results)
