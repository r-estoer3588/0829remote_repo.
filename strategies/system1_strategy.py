# strategies/system1_strategy.py
import pandas as pd
from .base_strategy import StrategyBase
from .system1 import (
    prepare_data_vectorized_system1,
    generate_roc200_ranking_system1,
    execute_backtest_from_candidates,
    get_total_days_system1  # ← 追加
)

class System1Strategy(StrategyBase):
    """
    システム1（ロング・トレンド・ハイ・モメンタム）戦略クラス
    """

    def prepare_data(self, raw_data_dict: dict, **kwargs) -> dict:
        return prepare_data_vectorized_system1(raw_data_dict, **kwargs)

    def generate_candidates(self, data_dict: dict, market_df: pd.DataFrame, **kwargs):
        return generate_roc200_ranking_system1(data_dict, market_df, **kwargs)

    def run_backtest(self, data_dict: dict, candidates_by_date: dict, capital: float, **kwargs) -> pd.DataFrame:
        return execute_backtest_from_candidates(data_dict, candidates_by_date, capital, **kwargs)

    def get_total_days(self, data_dict: dict) -> int:
        """日別ROC200ランキングの総日数を返す"""
        return get_total_days_system1(data_dict)
