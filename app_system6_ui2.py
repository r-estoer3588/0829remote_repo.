import streamlit as st
import common.ui_patch  # noqa: F401
import pandas as pd
from strategies.system6_strategy import System6Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
)
from common.cache_utils import save_prepared_data_cache
from common.ui_manager import UIManager


strategy = System6Strategy()


def display_return6d_ranking(
    candidates_by_date,
    years: int = 5,
    top_n: int = 100,
    title: str = "📊 System6 日別 6日リターン ランキング（直近{years}年 / 上位{top_n}銘柄）",
):
    if not candidates_by_date:
        st.warning("Return6Dランキングが空です")
        return
    rows = []
    for date, cands in candidates_by_date.items():
        for c in cands:
            rows.append({"Date": date, "symbol": c.get("symbol"), "Return6D": c.get("Return6D")})
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])  # type: ignore[arg-type]
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df["Date"] >= start_date]
    df["Return6D_Rank"] = df.groupby("Date")["Return6D"].rank(ascending=False, method="first")
    df = df.sort_values(["Date", "Return6D_Rank"], ascending=[True, True])
    df = df.groupby("Date").head(top_n)
    with st.expander(title.format(years=years, top_n=top_n), expanded=False):
        st.dataframe(
            df.reset_index(drop=True)[["Date", "Return6D_Rank", "symbol", "Return6D"]],
            hide_index=False,
        )


def run_tab(ui_manager=None):
    st.header("System6｜ショート・ミーンリバージョン（ハイ・シェア・サージ）")
    ui = ui_manager or UIManager()
    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy, system_name="System6", limit_symbols=100, ui_manager=ui
    )
    if results_df is not None and candidates_by_date is not None:
        display_return6d_ranking(candidates_by_date)
        summary_df = show_signal_trade_summary(data_dict, results_df, "System6")
        save_signal_and_trade_logs(summary_df, results_df, "System6", capital)
        save_prepared_data_cache(data_dict, "System6")
    else:
        # フォールバック（リラン時にセッションから復元）
        prev_res = st.session_state.get("System6_results_df")
        prev_cands = st.session_state.get("System6_candidates_by_date")
        prev_data = st.session_state.get("System6_prepared_dict")
        prev_cap = st.session_state.get("System6_capital")
        if prev_res is not None and prev_cands is not None:
            display_return6d_ranking(prev_cands)
            _ = show_signal_trade_summary(prev_data, prev_res, "System6")


if __name__ == "__main__":
    import sys
    if "streamlit" not in sys.argv[0]:
        run_tab()
