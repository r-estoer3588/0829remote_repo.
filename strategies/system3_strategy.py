# strategies/system3_strategy.py
import pandas as pd
import time
from ta.trend import SMAIndicator
from ta.volatility import AverageTrueRange


class System3Strategy:
    """
    System3: ロング・ミーン・リバージョン・セルオフ
    """

    def prepare_data(
        self, data_dict, progress_callback=None, log_callback=None, batch_size=50
    ):
        result_dict = {}
        total = len(data_dict)
        start_time = time.time()
        processed = 0
        symbol_buffer = []
        skipped_count = 0  # データ不足や失敗をカウント

        for sym, df in data_dict.items():
            df = df.copy()

            # ---- インジケーター ----
            if len(df) < 150:  # データ不足チェック
                skipped_count += 1
                processed += 1
                continue

            try:
                df["SMA150"] = SMAIndicator(df["Close"], window=150).sma_indicator()
                df["ATR10"] = AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=10
                ).average_true_range()
                df["Return_3D"] = df["Close"].pct_change(3)
                df["AvgVolume50"] = df["Volume"].rolling(50).mean()
                df["ATR_Ratio"] = df["ATR10"] / df["Close"]

                df["setup"] = (
                    (df["Close"] > df["SMA150"])
                    & (df["Return_3D"] <= -0.125)
                    & (df["Close"] > 1)
                    & (df["AvgVolume50"] >= 1_000_000)
                    & (df["ATR_Ratio"] >= 0.05)
                ).astype(int)

                result_dict[sym] = df
            except Exception:
                skipped_count += 1
                processed += 1
                continue

            processed += 1
            symbol_buffer.append(sym)

            # ---- 進捗ログ ----
            if progress_callback:
                progress_callback(processed, total)
            if (processed % batch_size == 0 or processed == total) and log_callback:
                elapsed = time.time() - start_time
                remain = (elapsed / processed) * (total - processed)
                log_callback(
                    f"📊 指標計算: {processed}/{total} 件 完了"
                    f" | 経過: {int(elapsed // 60)}分{int(elapsed % 60)}秒"
                    f" / 残り: 約 {int(remain // 60)}分{int(remain % 60)}秒\n"
                    f"銘柄: {', '.join(symbol_buffer)}"
                )
                symbol_buffer.clear()

        # ---- スキップ件数を表示 ----
        if skipped_count > 0 and log_callback:
            log_callback(
                f"⚠️ データ不足・計算失敗でスキップされた銘柄: {skipped_count} 件"
            )

        # ---- 最後に完了メッセージ ----
        if log_callback:
            log_callback(f"📊 指標計算完了 | {total} 銘柄のデータを処理しました")

        return result_dict

    def generate_candidates(
        self, prepared_dict, progress_callback=None, log_callback=None, batch_size=50
    ):
        """
        Setup銘柄を抽出し、日別に Return_3D 昇順でランキング
        """
        candidates_by_date = {}
        total = len(prepared_dict)
        processed = 0
        symbol_buffer = []
        start_time = time.time()

        for sym, df in prepared_dict.items():
            setup_days = df[df["setup"] == 1]
            for date, row in setup_days.iterrows():
                entry_date = date + pd.Timedelta(days=1)
                if entry_date not in df.index:
                    continue
                rec = {
                    "symbol": sym,
                    "entry_date": entry_date,
                    "Return_3D": row["Return_3D"],
                    "ATR10": row["ATR10"],
                }
                candidates_by_date.setdefault(entry_date, []).append(rec)

            processed += 1
            symbol_buffer.append(sym)

            # ---- 進捗更新 ----
            if progress_callback:
                progress_callback(processed, total)
            if (processed % batch_size == 0 or processed == total) and log_callback:
                elapsed = time.time() - start_time
                remain = (elapsed / processed) * (total - processed) if processed else 0
                log_callback(
                    f"📊 セットアップ通過銘柄抽出中: {processed}/{total} 件 完了"
                    f" | 経過: {int(elapsed // 60)}分{int(elapsed % 60)}秒"
                    f" / 残り: 約 {int(remain // 60)}分{int(remain % 60)}秒\n"
                    f"銘柄: {', '.join(symbol_buffer)}"
                )
                symbol_buffer.clear()

        # ランキング（下落幅大きい順 = Return_3Dが小さい順）
        for date in candidates_by_date:
            candidates_by_date[date] = sorted(
                candidates_by_date[date], key=lambda x: x["Return_3D"]
            )

        return candidates_by_date

    def run_backtest(
        self, prepared_dict, candidates_by_date, capital, on_progress=None, on_log=None
    ):
        """
        System3 バックテスト
        - 前日終値の7%下で指値
        - 利食い: +4%以上
        - 損切り: -2.5ATR
        - 最大3日保持
        - 最大10銘柄、リスク2%、最大ポジション10%
        """
        risk_per_trade = 0.02 * capital
        max_position_value = 0.10 * capital

        results = []
        active_positions = []
        total_days = len(candidates_by_date)
        start_time = time.time()

        for i, (date, candidates) in enumerate(sorted(candidates_by_date.items()), 1):
            if on_progress:
                on_progress(i, total_days, start_time)
            if on_log and (i % 20 == 0 or i == total_days):
                on_log(i, total_days, start_time)

            # ---- 保有銘柄更新 ----
            active_positions = [p for p in active_positions if p["exit_date"] >= date]
            available_slots = 10 - len(active_positions)
            if available_slots <= 0:
                continue

            # ---- 候補から選択 ----
            day_candidates = candidates[:available_slots]

            for c in day_candidates:
                df = prepared_dict[c["symbol"]]
                try:
                    entry_idx = df.index.get_loc(c["entry_date"])
                except KeyError:
                    continue
                if entry_idx == 0:
                    continue

                prev_close = df.iloc[entry_idx - 1]["Close"]
                entry_price = round(prev_close * 0.93, 2)  # 前日終値の7%下
                atr = df.iloc[entry_idx - 1]["ATR10"]
                stop_price = entry_price - 2.5 * atr

                # ポジションサイズ
                shares = min(
                    risk_per_trade / (entry_price - stop_price),
                    max_position_value / entry_price,
                )
                shares = int(shares)
                if shares <= 0:
                    continue

                # ---- exitルール ----
                exit_price = entry_price
                exit_date = df.index[-1]

                for offset in range(1, 4):  # 最大3日保持
                    if entry_idx + offset >= len(df):
                        break
                    future_close = df.iloc[entry_idx + offset]["Close"]
                    gain = (future_close - entry_price) / entry_price
                    if gain >= 0.04:  # 利確
                        exit_date = df.index[min(entry_idx + offset + 1, len(df) - 1)]
                        exit_price = df.loc[exit_date, "Close"]
                        break
                else:
                    idx2 = min(entry_idx + 3, len(df) - 1)
                    exit_date = df.index[idx2]
                    exit_price = df.iloc[idx2]["Close"]

                pnl = (exit_price - entry_price) * shares
                risk_amount = (entry_price - stop_price) * shares
                if risk_amount <= 0:
                    continue

                results.append(
                    {
                        "symbol": c["symbol"],
                        "entry_date": c["entry_date"],
                        "exit_date": exit_date,
                        "entry_price": entry_price,
                        "exit_price": round(exit_price, 2),
                        "shares": shares,
                        "pnl": round(pnl, 2),
                        "return_%": round((pnl / capital) * 100, 2),
                        "risk_amount": risk_amount,
                    }
                )

                active_positions.append({"symbol": c["symbol"], "exit_date": exit_date})

        return pd.DataFrame(results)
