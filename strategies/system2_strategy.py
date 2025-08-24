# strategies/system2_strategy.py
import time
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange


class System2Strategy:
    """
    システム2：ショート RSIスラスト
    - フィルター: Close>5, DollarVolume20>25M, ATR10/Close>0.03
    - セットアップ: RSI3>90, 2連陽線
    - ランキング: ADX7 降順
    - 損切り: 売値 + 3ATR10
    - 利食い: 翌日4%以上利益で翌日大引け決済、未達なら2日後翌日決済
    - ポジションサイジング: リスク2%、最大サイズ10%、全期間最大10ポジション
    """

    def prepare_data(
        self, raw_data_dict, progress_callback=None, log_callback=None, batch_size=50
    ):
        total = len(raw_data_dict)
        processed = 0
        start_time = time.time()
        buffer = []
        result_dict = {}
        skipped_count = 0  # 追加: スキップ件数カウント

        for sym, df in raw_data_dict.items():
            df = df.copy()

            # --- データ不足チェック ---
            if len(df) < 20:
                skipped_count += 1  # ログは残さずカウントだけ
                processed += 1
                continue

            try:
                # --- インジケーター計算 ---
                df["RSI3"] = RSIIndicator(df["Close"], window=3).rsi()
                df["ADX7"] = ADXIndicator(
                    df["High"], df["Low"], df["Close"], window=7
                ).adx()
                df["ATR10"] = AverageTrueRange(
                    df["High"], df["Low"], df["Close"], window=10
                ).average_true_range()
            except Exception:
                skipped_count += 1  # 計算失敗もスキップ扱い
                processed += 1
                continue

            # --- その他の指標 ---
            df["DollarVolume20"] = (
                (df["Close"] * df["Volume"]).rolling(window=20).mean()
            )
            df["ATR_Ratio"] = df["ATR10"] / df["Close"]
            df["TwoDayUp"] = (df["Close"] > df["Close"].shift(1)) & (
                df["Close"].shift(1) > df["Close"].shift(2)
            )

            # --- セットアップ条件 ---
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

            # --- 進捗更新 ---
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
                    f"📊 指標計算: {processed}/{total} 件 完了"
                    f" | 経過: {em}分{es}秒 / 残り: 約 {rm}分{rs}秒"
                )
                if buffer:
                    msg += f"\n銘柄: {', '.join(buffer)}"

                log_callback(msg)  # ✅ 文字列だけ渡す
                buffer.clear()

        # --- 最後にスキップ件数をまとめて表示 ---
        if skipped_count > 0 and log_callback:
            log_callback(
                f"⚠️ データ不足・計算失敗でスキップされた銘柄: {skipped_count} 件"
            )

        return result_dict

    def generate_candidates(self, prepared_dict, **kwargs):
        """
        セットアップ条件通過銘柄を日別にADX7降順で返す
        - System1と同じインターフェースに統一（kwargs受け取り可）
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
        candidates_by_date = {
            date: group.sort_values("ADX7", ascending=False).to_dict("records")
            for date, group in all_df.groupby("entry_date")
        }
        return candidates_by_date, None

    def run_backtest(
        self, data_dict, candidates_by_date, capital, on_progress=None, on_log=None
    ):
        risk_per_trade = 0.02 * capital
        max_position_value = 0.10 * capital
        results = []
        active_positions = []

        total_days = len(candidates_by_date)
        start_time = time.time()

        for i, (date, candidates) in enumerate(
            sorted(candidates_by_date.items()), start=1
        ):
            # --- コールバックで進捗通知 ---
            if on_progress:
                on_progress(i, total_days, start_time)
            if on_log and (i % 10 == 0 or i == total_days):
                on_log(i, total_days, start_time)

            # 保有中リスト更新
            active_positions = [p for p in active_positions if p["exit_date"] >= date]
            available_slots = 10 - len(active_positions)
            if available_slots <= 0:
                continue

            # 新規エントリー候補（空きスロット分だけ）
            day_candidates = candidates[:available_slots]

            for c in day_candidates:
                df = data_dict[c["symbol"]]
                try:
                    entry_idx = df.index.get_loc(c["entry_date"])
                except KeyError:
                    continue
                if entry_idx >= len(df):
                    continue

                prior_close = df.iloc[entry_idx - 1]["Close"]
                entry_price = df.iloc[entry_idx]["Open"]

                # エントリー条件：寄り付きが前日終値×1.04以上
                if entry_price < prior_close * 1.04:
                    continue

                atr = df.iloc[entry_idx - 1]["ATR10"]
                stop_price = entry_price + 3 * atr
                shares = min(
                    risk_per_trade / (stop_price - entry_price),
                    max_position_value / entry_price,
                )
                shares = int(shares)
                if shares <= 0:
                    continue

                entry_date = df.index[entry_idx]
                exit_date = None
                exit_price = None

                # 利食い・損切り判定
                for offset in range(1, 4):  # 最大3営業日
                    idx2 = entry_idx + offset
                    if idx2 >= len(df):
                        break
                    high = df.iloc[idx2]["High"]
                    low = df.iloc[idx2]["Low"]
                    close = df.iloc[idx2]["Close"]

                    # 損切り
                    if high >= stop_price:
                        exit_date = df.index[idx2]
                        exit_price = stop_price
                        break
                    # 利食い（4%以上利益）
                    gain = (entry_price - close) / entry_price
                    if gain >= 0.04:
                        exit_date = (
                            df.index[idx2 + 1] if idx2 + 1 < len(df) else df.index[idx2]
                        )
                        exit_price = (
                            df.loc[exit_date]["Open"]
                            if exit_date in df.index
                            else close
                        )
                        break
                else:
                    # 2日後未達なら翌日決済
                    idx2 = entry_idx + 2
                    if idx2 < len(df):
                        exit_date = (
                            df.index[idx2 + 1] if idx2 + 1 < len(df) else df.index[idx2]
                        )
                        exit_price = (
                            df.loc[exit_date]["Open"]
                            if exit_date in df.index
                            else df.iloc[idx2]["Close"]
                        )

                if exit_price is None or exit_date is None:
                    continue

                pnl = (entry_price - exit_price) * shares
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

        return pd.DataFrame(results)
