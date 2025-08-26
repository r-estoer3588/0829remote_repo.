import streamlit as st
from strategies.system1_strategy import System1Strategy
import pandas as pd
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
    display_roc200_ranking,
    clean_date_column,
)
from common.cache_utils import save_prepared_data_cache

# ✅ SPY関連は共通ユーティリティから
from common.utils_spy import get_spy_data_cached, get_spy_with_indicators

# インスタンス生成
strategy = System1Strategy()


def run_tab():
    st.header("System1：ロング・トレンド・ハイ・モメンタム（複数銘柄＋ランキング）")

    spy_df = get_spy_data_cached()
    if spy_df is None or spy_df.empty:
        st.error("SPYデータの取得に失敗しました。キャッシュを更新してください。")
        return

    results_df, merged_df, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy,
        system_name="System1",
        limit_symbols=10,
        spy_df=spy_df,
    )

    if results_df is not None and merged_df is not None:
        daily_df = clean_date_column(merged_df, col_name="Date")
        display_roc200_ranking(daily_df, title="📊 System1 日別ROC200ランキング")

        signal_summary_df = show_signal_trade_summary(merged_df, results_df, "System1")
        save_signal_and_trade_logs(signal_summary_df, results_df, "System1", capital)
        save_prepared_data_cache(data_dict, "System1")

        # ✅ 同時保有銘柄数の最大値をチェック 0823デバッグ用
        # if not results_df.empty:
        #     results_df["entry_date"] = pd.to_datetime(results_df["entry_date"])
        #     results_df["exit_date"] = pd.to_datetime(results_df["exit_date"])

        #     # 各営業日に保有している銘柄数をカウント
        #     unique_dates = sorted(results_df["entry_date"].dt.normalize().unique())
        #     holding_counts = []
        #     for d in unique_dates:
        #         active = results_df[
        #             (results_df["entry_date"] <= d) & (results_df["exit_date"] >= d)
        #         ]
        #         holding_counts.append(len(active["symbol"].unique()))

        #     max_holdings = max(holding_counts) if holding_counts else 0
        #     st.info(f"📌 最大同時保有銘柄数: {max_holdings}")


# 単体実行用
if __name__ == "__main__":
    import sys

    if "streamlit" not in sys.argv[0]:
        run_tab()
