import pandas as pd
from ta.volatility import AverageTrueRange
import time
import pandas as pd


class System7Strategy:
    """
    System7：カタストロフィーヘッジ（SPY専用）
    - ショート戦略
    - エントリー: SPYが直近50日安値を更新した翌日の寄付でショート
    - 損切り: エントリー価格 + 3 * ATR50
    - 利確: SPYが直近70日高値を更新した翌日の寄付で決済
    """

    def prepare_data(
        self, data_dict, progress_callback=None, log_callback=None, skip_callback=None
    ):
        """
        SPY専用なので data_dict から1銘柄だけ処理する。
        app_system7.py が system6 と同じ呼び出し方をしてもエラーにならないよう、
        progress_callback / skip_callback も受け取れる形にしている。
        """
        prepared_dict = {}
        try:
            df = list(data_dict.values())[0].copy()  # SPYのみ対象
            df["ATR50"] = AverageTrueRange(
                df["High"], df["Low"], df["Close"], window=50
            ).average_true_range()
            df["min_50"] = df["Close"].shift(1).rolling(window=50).min().round(4)
            df["Close_r"] = df["Close"].round(4)
            df["setup"] = (df["Close_r"] <= df["min_50"]).astype(int)
            df["max_70"] = df["Close"].rolling(window=70).max()
            prepared_dict["SPY"] = df
        except Exception as e:
            if skip_callback:
                skip_callback(f"SPY の処理をスキップしました: {e}")

        if log_callback:
            log_callback("SPY インジケーター計算完了 (ATR50, min_50, max_70, setup)")

        if progress_callback:
            progress_callback(1, 1)  # SPY 1銘柄なので進捗100%

        return prepared_dict

    def generate_candidates(
        self,
        prepared_dict,
        progress_callback=None,
        log_callback=None,
        skip_callback=None,
    ):
        """
        セットアップ条件を満たした日の翌営業日を候補日として抽出
        """
        candidates_by_date = {}
        df = prepared_dict["SPY"]

        setup_days = df[df["setup"] == 1]
        for date, row in setup_days.iterrows():
            entry_idx = df.index.get_loc(date)
            if entry_idx + 1 >= len(df):
                continue
            entry_date = df.index[entry_idx + 1]
            rec = {
                "symbol": "SPY",
                "entry_date": entry_date,
                "ATR50": row["ATR50"],
            }
            candidates_by_date.setdefault(entry_date, []).append(rec)

        if log_callback:
            log_callback(f"候補日数: {len(candidates_by_date)}")

        if progress_callback:
            progress_callback(1, 1)  # SPY専用なので常に100%

        return candidates_by_date

    def run_backtest(
        self,
        prepared_dict,
        candidates_by_date,
        capital,
        on_progress=None,
        on_log=None,
        single_mode=False,
    ):
        """
        SPYショート戦略のバックテスト
        - 単独モード: 資金全額を使用
        - 通常モード: リスクベース (2%)、最大20%制限
        """
        results = []
        df = prepared_dict["SPY"]

        total_days = len(candidates_by_date)
        start_time = time.time()

        for i, (entry_date, candidates) in enumerate(
            sorted(candidates_by_date.items()), 1
        ):
            for c in candidates:
                entry_price = df.loc[entry_date, "Open"]
                atr = c["ATR50"]
                stop_price = entry_price + 3 * atr  # ショートなので損切りは上方向

                # --- 資金管理 ---
                if single_mode:
                    shares = int(capital // entry_price)
                else:
                    risk_per_trade = 0.02 * capital
                    position_value = (
                        risk_per_trade / (stop_price - entry_price) * entry_price
                    )
                    max_position_value = 0.20 * capital
                    if position_value > max_position_value:
                        shares = int(max_position_value // entry_price)
                    else:
                        shares = int(risk_per_trade / (stop_price - entry_price))

                if shares <= 0:
                    continue

                # --- exitロジック ---
                entry_idx = df.index.get_loc(entry_date)
                exit_date, exit_price = None, None

                for idx2 in range(entry_idx + 1, len(df)):
                    # 損切り
                    if df.iloc[idx2]["High"] >= stop_price:
                        exit_date = df.index[idx2]
                        exit_price = stop_price
                        break
                    # 利確（70日高値ブレイク）
                    if df.iloc[idx2]["High"] >= df.iloc[idx2]["max_70"]:
                        exit_date = df.index[min(idx2 + 1, len(df) - 1)]
                        exit_price = df.loc[exit_date, "Open"]
                        break

                if exit_date is None:
                    exit_date = df.index[-1]
                    exit_price = df.iloc[-1]["Close"]

                pnl = (entry_price - exit_price) * shares  # ショートなので entry - exit
                return_pct = pnl / capital * 100

                results.append(
                    {
                        "symbol": "SPY",
                        "entry_date": entry_date,
                        "exit_date": exit_date,
                        "entry_price": entry_price,
                        "exit_price": round(exit_price, 2),
                        "shares": shares,
                        "pnl": round(pnl, 2),
                        "return_%": round(return_pct, 2),
                    }
                )

            # --- 進捗更新（日単位） ---
            if on_progress:
                on_progress(i, total_days, start_time)
            if on_log and (i % 10 == 0 or i == total_days):
                on_log(i, total_days, start_time)

        return pd.DataFrame(results)
