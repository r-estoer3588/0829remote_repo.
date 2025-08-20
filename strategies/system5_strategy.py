# strategies/system5_strategy.py
import pandas as pd
import time
from ta.trend import SMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange


class System5Strategy:
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
                remaining = (elapsed / processed) * (total - processed)
                em, es = divmod(int(elapsed), 60)
                rm, rs = divmod(int(remaining), 60)
                log_callback(
                    f"📊 インジケーター計算: {processed}/{total} 件 完了"
                    f" | 経過: {em}分{es}秒 / 残り: 約 {rm}分{rs}秒"
                    f"\n銘柄: {', '.join(buffer)}"
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

        return candidates_by_date

    # ===============================
    # バックテスト実行
    # ===============================
    def run_backtest(
        self, prepared_dict, candidates_by_date, capital, on_progress=None, on_log=None
    ):
        risk_per_trade = 0.02 * capital
        max_pos_value = 0.10 * capital
        results, active_positions = [], []
        total_days = len(candidates_by_date)
        start_time = time.time()

        for i, (date, candidates) in enumerate(sorted(candidates_by_date.items()), 1):
            # 進捗表示
            if on_progress:
                on_progress(i, total_days, start_time)
            if on_log and (i % 20 == 0 or i == total_days):
                on_log(i, total_days, start_time)

            # 同時保有管理（最大10銘柄）
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

                prev_close = df.iloc[entry_idx - 1]["Close"]
                entry_price = round(prev_close * 0.97, 2)  # 前日終値の3%下
                atr = df.iloc[entry_idx - 1]["ATR10"]
                stop_price = entry_price - 3 * atr

                # リスク管理
                shares = min(
                    risk_per_trade / max(entry_price - stop_price, 1e-6),
                    max_pos_value / entry_price,
                )
                shares = int(shares)
                if shares <= 0:
                    continue

                entry_date = df.index[entry_idx]
                exit_date, exit_price = None, None

                # 利確ルール（+1ATR or 6日後寄り付き）
                for offset in range(1, 7):
                    if entry_idx + offset >= len(df):
                        break
                    if (df.iloc[entry_idx + offset]["Close"] - entry_price) >= atr:
                        exit_date = df.index[min(entry_idx + offset + 1, len(df) - 1)]
                        exit_price = df.loc[exit_date, "Open"]
                        break
                if exit_price is None:
                    idx2 = min(entry_idx + 6, len(df) - 1)
                    exit_date = df.index[idx2]
                    exit_price = df.iloc[idx2]["Open"]

                pnl = (exit_price - entry_price) * shares
                results.append(
                    {
                        "symbol": c["symbol"],
                        "entry_date": entry_date,
                        "exit_date": exit_date,
                        "entry_price": entry_price,
                        "exit_price": round(exit_price, 2),
                        "shares": shares,
                        "pnl": round(pnl, 2),
                        "return_%": round((pnl / capital) * 100, 2),
                    }
                )
                active_positions.append({"symbol": c["symbol"], "exit_date": exit_date})

        return pd.DataFrame(results)
