# app_system3_ui2.py
import streamlit as st
import pandas as pd
from strategies.system3_strategy import System3Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
    save_prepared_data_cache,
)

# ===== 戦略インスタンス =====
strategy = System3Strategy()


# ===== 固有UI: DropRate_3Dランキング =====
def display_drop3d_ranking(
    candidates_by_date,
    years=5,
    top_n=100,
    title="📊 System3 日別3日下落率ランキング（直近5年 / 上位100銘柄）",
):
    if not candidates_by_date:
        st.warning("DropRate_3Dランキングが空です。")
        return

    all_candidates = []
    for date, candidates in candidates_by_date.items():
        for c in candidates:
            all_candidates.append(
                {"Date": date, "symbol": c["symbol"], "DropRate_3D": c["DropRate_3D"]}
            )
    df = pd.DataFrame(all_candidates)
    df["Date"] = pd.to_datetime(df["Date"])

    # 直近 years 年に絞る
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df["Date"] >= start_date]

    # 🔽 ランキング列を付与（日別に DropRate_3D 昇順＝下落幅大きい順）
    df["DropRate_3D_Rank"] = df.groupby("Date")["DropRate_3D"].rank(
        ascending=False, method="first"
    )

    # 日付昇順、ランキング昇順にソート
    df = df.sort_values(["Date", "DropRate_3D_Rank"], ascending=[True, True])

    # 各日付の上位 top_n のみ表示
    df = df.groupby("Date").head(top_n)

    with st.expander(title, expanded=False):
        st.dataframe(
            df.reset_index(drop=True)[
                ["Date", "DropRate_3D_Rank", "symbol", "DropRate_3D"]
            ],
            column_config={
                "Date": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                "DropRate_3D_Rank": st.column_config.NumberColumn(width="small"),
                "symbol": st.column_config.TextColumn(width="small"),
                "DropRate_3D": st.column_config.NumberColumn(width="small"),
            },
            hide_index=False,
        )


# ===== Streamlitタブ呼び出し =====
def run_tab():
    st.header("System3：ロング・ミーン・リバージョン・セルオフ")

    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy, system_name="System3", limit_symbols=100
    )

    if results_df is not None and candidates_by_date is not None:
        display_drop3d_ranking(candidates_by_date)

        signal_summary_df = show_signal_trade_summary(data_dict, results_df, "System3")
        save_signal_and_trade_logs(signal_summary_df, results_df, "System3", capital)
        save_prepared_data_cache(data_dict, "System3")


# 単体実行用
if __name__ == "__main__":
    import sys

    if "streamlit" not in sys.argv[0]:
        run_tab()
