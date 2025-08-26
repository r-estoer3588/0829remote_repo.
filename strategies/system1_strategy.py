# strategies/system1_strategy.py
import time
import pandas as pd
from .base_strategy import StrategyBase
from system.core import (
    prepare_data_vectorized_system1,
    generate_roc200_ranking_system1,
    get_total_days_system1,
)
from common.backtest_utils import simulate_trades_with_risk

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

    def run_backtest(
        self, prepared_dict, candidates_by_date, capital, on_progress=None, on_log=None
    ):

        # --- バックテスト実行（trades_df, logs_df の2つを返す） ---
        trades_df, logs_df = simulate_trades_with_risk(
            candidates_by_date,
            prepared_dict,
            capital,
            self,  # ← strategy ではなく self を渡す
            on_progress=on_progress,
            on_log=on_log,
        )

        # --- ログ出力（資金推移ログをUIへ流す） ---
        if on_log and not logs_df.empty:
            for _, row in logs_df.iterrows():
                on_log(
                    f"💰 {row['date'].date()} | 資金: {row['capital']:.2f} USD "
                    f"| 保有: {row['active_count']}"
                )

        return trades_df

    def get_total_days(self, data_dict: dict) -> int:
        """日別ROC200ランキングの総日数を返す"""
        return get_total_days_system1(data_dict)
