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

    # ============================================================
    # 共通ユーティリティ: 資金管理 & ポジションサイズ計算
    # ============================================================
    def update_capital_with_exits(
        self, capital: float, active_positions: list, current_date
    ):
        """
        exit_date が current_date のポジションを決済して損益を反映。
        戻り値: (更新後capital, 未決済active_positions)
        """
        realized_pnl = sum(
            p["pnl"] for p in active_positions if p["exit_date"] == current_date
        )
        capital += realized_pnl
        # exit済みを除去
        active_positions = [
            p for p in active_positions if p["exit_date"] > current_date
        ]
        return capital, active_positions

    def calculate_position_size(
        self,
        capital: float,
        entry_price: float,
        stop_price: float,
        risk_pct: float = 0.02,
        max_pct: float = 0.10,
    ) -> int:
        """
        複利モードのポジションサイズ計算（System1〜6共通）
        - capital: 現在資金
        - entry_price: エントリー価格
        - stop_price: 損切り価格
        - risk_pct: 1トレードのリスク割合（デフォルト2%）
        - max_pct: 1トレードの最大資金割合（デフォルト10%）
        """
        risk_per_trade = risk_pct * capital
        max_position_value = max_pct * capital

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share <= 0:
            return 0

        shares = min(risk_per_trade / risk_per_share, max_position_value / entry_price)
        return int(shares)
