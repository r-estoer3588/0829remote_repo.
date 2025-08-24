# app_system5_ui2.py
import streamlit as st
import pandas as pd
from strategies.system5_strategy import System5Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
    save_prepared_data_cache,
)

# ===== 戦略インスタンス =====
strategy = System5Strategy()


# ===== 固有UI: ADX7ランキング =====
def display_adx_ranking(
    candidates_by_date,
    years=5,
    top_n=100,
    title="📊 System5 日別ADX7ランキング（直近5年 / 上位100銘柄）",
):
    if not candidates_by_date:
        st.warning("ADX7ランキングが空です。")
        return

    all_candidates = []
    for date, candidates in candidates_by_date.items():
        for c in candidates:
            all_candidates.append(
                {"Date": date, "symbol": c["symbol"], "ADX7": c.get("ADX7", None)}
            )
    df = pd.DataFrame(all_candidates)
    df["Date"] = pd.to_datetime(df["Date"])

    # 直近 years 年に絞る
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df["Date"] >= start_date]

    # 🔽 ランキング列を付与（日別に ADX7 降順）
    df["ADX7_Rank"] = df.groupby("Date")["ADX7"].rank(ascending=False, method="first")

    # 日付昇順、ランキング昇順にソート
    df = df.sort_values(["Date", "ADX7_Rank"], ascending=[True, True])

    # 各日付の上位 top_n のみ表示
    df = df.groupby("Date").head(top_n)

    with st.expander(title, expanded=False):
        st.dataframe(
            df.reset_index(drop=True)[["Date", "ADX7_Rank", "symbol", "ADX7"]],
            column_config={
                "Date": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                "ADX7_Rank": st.column_config.NumberColumn(width="small"),
                "symbol": st.column_config.TextColumn(width="small"),
                "ADX7": st.column_config.NumberColumn(width="small"),
            },
            hide_index=False,
        )


# ===== Streamlitタブ呼び出し =====
def run_tab():
    st.header("System5：ロング・ミーン・リバージョン・ハイADX・リバーサル")

    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy, system_name="System5", limit_symbols=100
    )

    if results_df is not None and candidates_by_date is not None:
        # ADX7ランキング表示
        display_adx_ranking(candidates_by_date)

        # signal件数サマリー + 保存
        signal_summary_df = show_signal_trade_summary(data_dict, results_df, "System5")
        save_signal_and_trade_logs(signal_summary_df, results_df, "System5", capital)

        # 加工済データキャッシュ保存
        save_prepared_data_cache(data_dict, "System5")


# 単体実行用
if __name__ == "__main__":
    import sys

    if "streamlit" not in sys.argv[0]:
        run_tab()
