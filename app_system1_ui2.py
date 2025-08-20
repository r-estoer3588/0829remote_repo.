# app_system1_ui2.py
import streamlit as st
from strategies.system1_strategy import System1Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
    save_prepared_data_cache,
)


def run_tab():
    strategy = System1Strategy()
    results_df, merged_df, data_dict = run_backtest_app(
        strategy, system_name="System1", limit_symbols=10
    )

    if results_df is not None and merged_df is not None:
        signal_counts = merged_df["symbol"].value_counts().reset_index()
        signal_counts.columns = ["symbol", "Signal_Count"]

        # 件数表示
        show_signal_trade_summary(signal_counts, results_df, "System1")

        # CSV保存（signal件数 + 売買ログ）
        save_signal_and_trade_logs(signal_counts, results_df, "System1", 1000)

        # 加工済みキャッシュ保存
        save_prepared_data_cache(data_dict, "System1")


# 単体実行用
if __name__ == "__main__":
    run_tab()
