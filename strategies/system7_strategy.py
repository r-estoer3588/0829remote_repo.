# strategies/system7_strategy.py
import pandas as pd
import time
from ta.volatility import AverageTrueRange
from .base_strategy import StrategyBase
from common.config import load_config


class System7Strategy(StrategyBase):
    """
    System7：ショート・カタストロフィーヘッジ（SPY専用）
    - エントリー: SPYが直近50日安値を更新した翌日の寄付でショート
    - 損切り: エントリー価格 + 3 * ATR50
    - 利確: SPYが直近70日高値を更新した翌日の寄付で決済
    """

    def __init__(self, config: dict | None = None):
        self.config = config or load_config("System7")

    def prepare_data(self, raw_data_dict, **kwargs):
        progress_callback = kwargs.pop("progress_callback", None)
        log_callback = kwargs.pop("log_callback", None)
        skip_callback = kwargs.pop("skip_callback", None)

        prepared_dict = {}
        try:
            # 🔽 SPY専用（必ず dict 内に SPY を期待する）
            df = raw_data_dict.get("SPY").copy()
            df["ATR50"] = AverageTrueRange(
                df["High"], df["Low"], df["Close"], window=50
            ).average_true_range()
            df["min_50"] = df["Close"].rolling(window=50).min().round(4)  # 当日を含む
            df["setup"] = (df["Low"] <= df["min_50"]).astype(int)  # Lowベース判定
            df["max_70"] = df["Close"].rolling(window=70).max()
            prepared_dict["SPY"] = df
        except Exception as e:
            if skip_callback:
                skip_callback(f"SPY の処理をスキップしました: {e}")

        if log_callback:
            log_callback("SPY インジケーター計算完了 (ATR50, min_50, max_70, setup)")
        if progress_callback:
            progress_callback(1, 1)

        return prepared_dict

    def generate_candidates(self, prepared_dict, **kwargs):
        progress_callback = kwargs.pop("progress_callback", None)
        log_callback = kwargs.pop("log_callback", None)

        candidates_by_date = {}
        if "SPY" not in prepared_dict:
            return {}, None

        df = prepared_dict["SPY"]
        setup_days = df[df["setup"] == 1]

        for date, row in setup_days.iterrows():
            entry_idx = df.index.get_loc(date)
            if entry_idx + 1 >= len(df):
                continue
            entry_date = df.index[entry_idx + 1]
            rec = {"symbol": "SPY", "entry_date": entry_date, "ATR50": row["ATR50"]}
            candidates_by_date.setdefault(entry_date, []).append(rec)

        if log_callback:
            log_callback(f"候補日数: {len(candidates_by_date)}")
        if progress_callback:
            progress_callback(1, 1)

        # 🔽 System7はランキング不要 → merged_df=None を返す
        return candidates_by_date, None

    def run_backtest(
        self,
        prepared_dict,
        candidates_by_date,
        capital,
        on_progress=None,
        on_log=None,
        single_mode=False,
    ):
        results = []
        if "SPY" not in prepared_dict:
            return pd.DataFrame()

        df = prepared_dict["SPY"]
        total_days = len(candidates_by_date)
        start_time = time.time()

        # 🔽 ポジション状態と exit_date を追跡
        capital_current = capital
        position_open = False
        current_exit_date = None

        risk_pct = float(self.config.get("risk_pct", 0.02))
        max_pct = float(self.config.get("max_pct", 0.20))
        if "single_mode" in self.config:
            single_mode = bool(self.config.get("single_mode", False))

        stop_mult = float(self.config.get("stop_atr_multiple", 3.0))

        for i, (entry_date, candidates) in enumerate(
            sorted(candidates_by_date.items()), 1
        ):
            # もし exit_date に到達していればスロット解放
            if position_open and entry_date >= current_exit_date:
                position_open = False
                current_exit_date = None

            if position_open:
                continue  # 保有中は新規エントリーしない

            for c in candidates:
                entry_price = df.loc[entry_date, "Open"]
                atr = c["ATR50"]

                stop_price = entry_price + stop_mult * atr

                risk_per_trade = risk_pct * capital_current
                max_position_value = capital_current if single_mode else capital_current * max_pct

                shares_by_risk = risk_per_trade / (stop_price - entry_price)
                shares_by_cap = max_position_value // entry_price
                shares = int(min(shares_by_risk, shares_by_cap))
                if shares <= 0:
                    continue

                # --- exit探索 ---
                exit_date, exit_price = None, None
                entry_idx = df.index.get_loc(entry_date)
                for idx2 in range(entry_idx + 1, len(df)):
                    if df.iloc[idx2]["High"] >= stop_price:
                        exit_date = df.index[idx2]
                        exit_price = stop_price
                        break
                    if df.iloc[idx2]["High"] >= df.iloc[idx2]["max_70"]:
                        exit_date = df.index[min(idx2 + 1, len(df) - 1)]
                        exit_price = df.loc[exit_date, "Open"]
                        break
                if exit_date is None:
                    exit_date = df.index[-1]
                    exit_price = df.iloc[-1]["Close"]

                pnl = (entry_price - exit_price) * shares
                return_pct = pnl / capital_current * 100

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

                # 資金更新
                capital_current += pnl

                # 🔽 exit_date に達するまで保有中とする
                position_open = True
                current_exit_date = exit_date

            # 進捗ログ
            if on_progress:
                on_progress(i, total_days, start_time)
            if on_log and (i % 10 == 0 or i == total_days):
                on_log(i, total_days, start_time)

        return pd.DataFrame(results)
