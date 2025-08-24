import time
import pandas as pd


def simulate_trades_with_risk(
    candidates_by_date: dict,
    data_dict: dict,
    capital: float,
    strategy,
    on_progress=None,
    on_log=None,
):
    """
    複利モード＋保有数ログ＋資金チェック付きバックテスト共通関数
    戻り値: (trades_df, logs_df)
    """
    results = []
    log_records = []
    active_positions = []
    current_capital = capital

    total_days = len(candidates_by_date)
    start_time = time.time()

    for i, (date, candidates) in enumerate(sorted(candidates_by_date.items()), start=1):
        # --- exit 済みポジションの損益反映 ---
        current_capital, active_positions = strategy.update_capital_with_exits(
            current_capital, active_positions, date
        )

        # --- 保有枠チェック ---
        active_positions = [p for p in active_positions if p["exit_date"] >= date]
        available_slots = 10 - len(active_positions)

        if available_slots > 0:
            day_candidates = [
                c
                for c in candidates
                if c["symbol"] not in {p["symbol"] for p in active_positions}
            ][:available_slots]

            for c in day_candidates:
                df = data_dict[c["symbol"]]
                try:
                    entry_idx = df.index.get_loc(c["entry_date"])
                except KeyError:
                    continue

                entry_price = df.iloc[entry_idx]["Open"]
                atr = df.iloc[entry_idx - 1]["ATR20"]
                stop_loss_price = entry_price - 5 * atr
                trail_pct = 0.25
                high_since_entry = entry_price
                exit_price, exit_date = entry_price, df.index[-1]

                # --- exitロジック ---
                for j in range(entry_idx + 1, len(df)):
                    high_since_entry = max(high_since_entry, df["High"].iloc[j])
                    trailing_stop = high_since_entry * (1 - trail_pct)
                    if df["Low"].iloc[j] < stop_loss_price:
                        exit_price, exit_date = stop_loss_price, df.index[j]
                        break
                    elif df["Low"].iloc[j] < trailing_stop:
                        exit_price, exit_date = trailing_stop, df.index[j]
                        break

                # --- ポジションサイズ計算 ---
                shares = strategy.calculate_position_size(
                    current_capital, entry_price, stop_loss_price
                )
                if shares <= 0:
                    continue

                # --- 資金不足チェック ---
                if shares * entry_price > current_capital:
                    continue

                pnl = (exit_price - entry_price) * shares
                results.append(
                    {
                        "symbol": c["symbol"],
                        "entry_date": c["entry_date"],
                        "exit_date": exit_date,
                        "entry_price": round(entry_price, 2),
                        "exit_price": round(exit_price, 2),
                        "shares": int(shares),
                        "pnl": round(pnl, 2),
                        "return_%": round((pnl / current_capital) * 100, 2),
                    }
                )

                active_positions.append(
                    {
                        "symbol": c["symbol"],
                        "exit_date": pd.Timestamp(exit_date),
                        "pnl": pnl,
                    }
                )

        # --- 資金・保有数ログ ---
        log_records.append(
            {
                "date": date,
                "capital": round(current_capital, 2),
                "active_count": len(active_positions),
            }
        )

        # --- 進捗ログ ---
        if on_progress:
            on_progress(i, total_days, start_time)
        if on_log and (i % 10 == 0 or i == total_days):
            elapsed = time.time() - start_time
            remain = elapsed / i * (total_days - i)
            on_log(
                f"💹 バックテスト: {i}/{total_days} 日処理完了"
                f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
                f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒"
            )

    return pd.DataFrame(results), pd.DataFrame(log_records)
