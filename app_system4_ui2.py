import streamlit as st
import common.ui_patch  # noqa: F401
import pandas as pd
from strategies.system4_strategy import System4Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
)
from common.cache_utils import save_prepared_data_cache
from common.utils_spy import get_spy_data_cached
from common.ui_manager import UIManager


strategy = System4Strategy()


def display_rsi4_ranking(
    candidates_by_date,
    years: int = 5,
    top_n: int = 100,
    title: str = "📊 System4 日別 RSI4 ランキング（直近{years}年 / 上位{top_n}銘柄）",
):
    if not candidates_by_date:
        st.warning("RSI4ランキングが空です")
        return

    rows = []
    for date, cands in candidates_by_date.items():
        for c in cands:
            rows.append({"Date": date, "symbol": c.get("symbol"), "RSI4": c.get("RSI4")})
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])  # type: ignore[arg-type]
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df["Date"] >= start_date]
    # RSIは小さいほど上位（買われ過ぎ反転狙いの想定）
    df["RSI4_Rank"] = df.groupby("Date")["RSI4"].rank(ascending=True, method="first")
    df = df.sort_values(["Date", "RSI4_Rank"], ascending=[True, True])
    df = df.groupby("Date").head(top_n)
    with st.expander(title.format(years=years, top_n=top_n), expanded=False):
        st.dataframe(
            df.reset_index(drop=True)[["Date", "RSI4_Rank", "symbol", "RSI4"]],
            hide_index=False,
        )


def run_tab():
    st.header("System4｜ロング・トレンドフォロー（RSI4ランク）")
    spy_df = get_spy_data_cached()
    if spy_df is None or spy_df.empty:
        st.error("SPYの取得に失敗しました。キャッシュの更新を確認してください。")
        return

    ui = UIManager()
    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy,
        system_name="System4",
        limit_symbols=100,
        spy_df=spy_df,
        ui_manager=ui,
    )
    if results_df is not None and candidates_by_date is not None:
        display_rsi4_ranking(candidates_by_date)
        summary_df = show_signal_trade_summary(data_dict, results_df, "System4")
        save_signal_and_trade_logs(summary_df, results_df, "System4", capital)
        save_prepared_data_cache(data_dict, "System4")


if __name__ == "__main__":
    import sys
    if "streamlit" not in sys.argv[0]:
        run_tab()

