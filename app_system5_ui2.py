import streamlit as st
import common.ui_patch  # noqa: F401
import pandas as pd
from strategies.system5_strategy import System5Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
)
from common.cache_utils import save_prepared_data_cache
from common.ui_manager import UIManager


strategy = System5Strategy()


def display_adx_ranking(
    candidates_by_date,
    years: int = 5,
    top_n: int = 100,
    title: str = "📊 System5 日別 ADX7 ランキング（直近{years}年 / 上位{top_n}銘柄）",
):
    if not candidates_by_date:
        st.warning("ADX7ランキングが空です")
        return
    rows = []
    for date, cands in candidates_by_date.items():
        for c in cands:
            rows.append({"Date": date, "symbol": c.get("symbol"), "ADX7": c.get("ADX7")})
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])  # type: ignore[arg-type]
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df["Date"] >= start_date]
    df["ADX7_Rank"] = df.groupby("Date")["ADX7"].rank(ascending=False, method="first")
    df = df.sort_values(["Date", "ADX7_Rank"], ascending=[True, True])
    df = df.groupby("Date").head(top_n)
    with st.expander(title.format(years=years, top_n=top_n), expanded=False):
        st.dataframe(
            df.reset_index(drop=True)[["Date", "ADX7_Rank", "symbol", "ADX7"]],
            hide_index=False,
        )


def run_tab(ui_manager=None):
    st.header("System5｜ロング・ミーンリバージョン（高ADXリバーサル）")
    ui = ui_manager or UIManager()
    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy, system_name="System5", limit_symbols=100, ui_manager=ui
    )
    if results_df is not None and candidates_by_date is not None:
        display_adx_ranking(candidates_by_date)
        summary_df = show_signal_trade_summary(data_dict, results_df, "System5")
        save_signal_and_trade_logs(summary_df, results_df, "System5", capital)
        save_prepared_data_cache(data_dict, "System5")


if __name__ == "__main__":
    import sys
    if "streamlit" not in sys.argv[0]:
        run_tab()
