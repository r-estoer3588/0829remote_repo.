# strategies/system1_strategy.py
import time
import pandas as pd
from .base_strategy import StrategyBase
from .system1 import (
    prepare_data_vectorized_system1,
    generate_roc200_ranking_system1,
    execute_backtest_from_candidates,
    get_total_days_system1,
)

"""
システム1（ロング・トレンド・ハイ・モメンタム）戦略クラス
"""


class System1Strategy(StrategyBase):
    def prepare_data(self, raw_data_dict, **kwargs):
        progress_callback = kwargs.pop("progress_callback", None)
        log_callback = kwargs.pop("log_callback", None)
        skip_callback = kwargs.pop("skip_callback", None)

        return prepare_data_vectorized_system1(
            raw_data_dict,
            progress_callback=progress_callback,
            log_callback=log_callback,
            skip_callback=skip_callback,
            **kwargs,
        )

    def generate_candidates(self, prepared_dict, market_df=None, **kwargs):
        if market_df is None:
            market_df = prepared_dict.get("SPY")
            if market_df is None:
                raise ValueError("SPYデータが必要ですが見つかりませんでした。")
        return generate_roc200_ranking_system1(prepared_dict, market_df, **kwargs)

    # def run_backtest(self, data_dict: dict, candidates_by_date: dict, capital: float, **kwargs) -> pd.DataFrame:
    # return execute_backtest_from_candidates(data_dict, candidates_by_date,
    # capital, **kwargs)

    def run_backtest(
        self,
        prepared_dict,
        candidates_by_date,
        capital,
        on_progress=None,
        on_log=None,
    ):

        total_days = len(candidates_by_date)
        start_time = time.time()

        all_trades = []
        for i, (date, candidates) in enumerate(candidates_by_date.items(), 1):
            trades = execute_backtest_from_candidates(
                prepared_dict, {date: candidates}, capital
            )
            all_trades.extend(trades)

            # --- コールバックを呼ぶだけ（UIは知らない） ---
            if on_progress:
                on_progress(i, total_days, start_time)

            if on_log:
                on_log(i, total_days, start_time)

        return pd.DataFrame(all_trades)

    def get_total_days(self, data_dict: dict) -> int:
        """日別ROC200ランキングの総日数を返す"""
        return get_total_days_system1(data_dict)
