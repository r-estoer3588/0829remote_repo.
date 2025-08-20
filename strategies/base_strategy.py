# strategies/base_strategy.py
from abc import ABC, abstractmethod
import pandas as pd


class StrategyBase(ABC):
    """
    全戦略共通の抽象基底クラス。
    各戦略はこのクラスを継承し、必須メソッドを実装する。
    """

    @abstractmethod
    def prepare_data(self, raw_data_dict: dict, **kwargs) -> dict:
        """生データからインジケーターやシグナルを計算"""
        pass

    @abstractmethod
    def generate_candidates(self, data_dict: dict, market_df: pd.DataFrame, **kwargs):
        """日別仕掛け候補を生成"""
        pass

    @abstractmethod
    def run_backtest(
        self, data_dict: dict, candidates_by_date: dict, capital: float, **kwargs
    ) -> pd.DataFrame:
        """仕掛け候補に基づいてバックテストを実行"""
        pass
