import streamlit as st
import pandas as pd
from strategies.system6_strategy import System6Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
    save_prepared_data_cache,
)

# ===== 戦略インスタンス =====
strategy = System6Strategy()


# ===== 固有UI: Return6Dランキング =====
def display_return6d_ranking(
    candidates_by_date,
    years=5,
    top_n=100,
    title="📊 System6 日別Return6Dランキング（直近5年 / 上位100銘柄）",
):
    if not candidates_by_date:
        st.warning("Return6Dランキングが空です。")
        return

    all_candidates = []
    for date, candidates in candidates_by_date.items():
        for c in candidates:
            all_candidates.append(
                {
                    "Date": date,
                    "symbol": c["symbol"],
                    "Return6D": c.get("Return6D", None),
                }
            )
    df = pd.DataFrame(all_candidates)
    df["Date"] = pd.to_datetime(df["Date"])

    # 直近 years 年に絞る
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df["Date"] >= start_date]

    # 🔽 ランキング列を付与（日別に Return6D 降順）
    df["Return6D_Rank"] = df.groupby("Date")["Return6D"].rank(
        ascending=False, method="first"
    )

    # 日付昇順、ランキング昇順にソート
    df = df.sort_values(["Date", "Return6D_Rank"], ascending=[True, True])

    # 各日付の上位 top_n のみ表示
    df = df.groupby("Date").head(top_n)

    with st.expander(title, expanded=False):
        st.dataframe(
            df.reset_index(drop=True)[["Date", "Return6D_Rank", "symbol", "Return6D"]],
            column_config={
                "Date": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                "Return6D_Rank": st.column_config.NumberColumn(width="small"),
                "symbol": st.column_config.TextColumn(width="small"),
                "Return6D": st.column_config.NumberColumn(width="small"),
            },
            hide_index=False,
        )


# ===== Streamlitタブ呼び出し =====
def run_tab():
    st.header("System6：ショート・ミーン・リバージョン・ハイ・シックスデイサージ")

    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy, system_name="System6", limit_symbols=100
    )

    if results_df is not None and candidates_by_date is not None:
        # Return6Dランキング表示
        display_return6d_ranking(candidates_by_date)

        # signal件数サマリー + 保存
        signal_summary_df = show_signal_trade_summary(data_dict, results_df, "System6")
        save_signal_and_trade_logs(signal_summary_df, results_df, "System6", capital)

        # 加工済データキャッシュ保存
        save_prepared_data_cache(data_dict, "System6")


# 単体実行用
if __name__ == "__main__":
    import sys

    if "streamlit" not in sys.argv[0]:
        run_tab()
