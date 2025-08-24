# strategies/system3_strategy.py
import pandas as pd
import time
from ta.trend import SMAIndicator
from ta.volatility import AverageTrueRange


class System3Strategy:
    """
    システム3：ロング・ミーン・リバージョン・セルオフ
    - セットアップ: Close > SMA150, DropRate_3D >= 12.5%, Volume > 100万, ATR比率 >= 5%
    - ランキング: DropRate_3D 降順（下落幅が大きい順）
    - 損切り: -2.5ATR, 利食い: +4%以上 or 最大3日保持
    - リスク2%、最大10%ポジション、同時保有最大10銘柄
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
            if len(df) < 150:  # データ不足チェック
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

            # --- 進捗更新 ---
            if progress_callback:
                progress_callback(processed, total)
            if (processed % batch_size == 0 or processed == total) and log_callback:
                elapsed = time.time() - start_time
                remain = (elapsed / processed) * (total - processed)
                log_callback(
                    f"📊 指標計算: {processed}/{total} 件 完了"
                    f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
                    f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒\n"
                    f"銘柄: {', '.join(buffer)}"
                )
                buffer.clear()

        # --- スキップ件数 ---
        if skipped > 0 and log_callback:
            log_callback(f"⚠️ データ不足・計算失敗でスキップ: {skipped} 件")

        if log_callback:
            log_callback(f"📊 指標計算完了 | {total} 銘柄を処理しました")

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
        セットアップ通過銘柄を日別に DropRate_3D 昇順でランキング
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
            # 🔽 DropRate_3Dを残すため明示的に選択
            setup_df = setup_df[["symbol", "entry_date", "DropRate_3D", "ATR10"]]
            all_signals.append(setup_df)
            processed += 1
            buffer.append(sym)

            if progress_callback:
                progress_callback(processed, total)
            if (processed % batch_size == 0 or processed == total) and log_callback:
                elapsed = time.time() - start_time
                remain = (elapsed / processed) * (total - processed)
                log_callback(
                    f"📊 セットアップ抽出: {processed}/{total} 件 完了"
                    f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
                    f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒\n"
                    f"銘柄: {', '.join(buffer)}"
                )
                buffer.clear()

        if not all_signals:
            return {}, None

        all_df = pd.concat(all_signals)
        candidates_by_date = {
            date: group.sort_values("DropRate_3D", ascending=False).to_dict("records")
            for date, group in all_df.groupby("entry_date")
        }
        return candidates_by_date, None

    def run_backtest(
        self, prepared_dict, candidates_by_date, capital, on_progress=None, on_log=None
    ):
        risk_per_trade = 0.02 * capital
        max_position_value = 0.10 * capital
        results, active_positions = [], []
        total_days = len(candidates_by_date)
        start_time = time.time()

        for i, (date, candidates) in enumerate(sorted(candidates_by_date.items()), 1):
            if on_progress:
                on_progress(i, total_days, start_time)
            if on_log and (i % 20 == 0 or i == total_days):
                on_log(i, total_days, start_time)

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
                if entry_idx == 0:
                    continue

                prev_close = df.iloc[entry_idx - 1]["Close"]
                entry_price = round(prev_close * 0.93, 2)  # 前日終値の7%下
                atr = df.iloc[entry_idx - 1]["ATR10"]
                stop_price = entry_price - 2.5 * atr

                shares = min(
                    risk_per_trade / max(entry_price - stop_price, 1e-6),
                    max_position_value / entry_price,
                )
                shares = int(shares)
                if shares <= 0:
                    continue

                # ---- exitルール ----
                exit_date, exit_price = df.index[-1], entry_price
                for offset in range(1, 4):
                    if entry_idx + offset >= len(df):
                        break
                    future_close = df.iloc[entry_idx + offset]["Close"]
                    gain = (future_close - entry_price) / entry_price
                    if gain >= 0.04:
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
