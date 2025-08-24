# app_system4_ui2.py
import streamlit as st
import pandas as pd
from strategies.system4_strategy import System4Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
    save_prepared_data_cache,
)
from common.utils_spy import get_spy_data_cached  # ✅ System1 と同じSPY取得方法


# ===============================
# 戦略インスタンス
# ===============================
strategy = System4Strategy()


# ===============================
# 固有UI: RSI4ランキング表示
# ===============================
def display_rsi4_ranking(
    candidates_by_date,
    years=5,
    top_n=100,
    title="📊 System4 日別RSI4ランキング（直近5年 / 上位100銘柄）",
):
    if not candidates_by_date:
        st.warning("RSI4ランキングが空です。")
        return

    all_candidates = []
    for date, candidates in candidates_by_date.items():
        for c in candidates:
            all_candidates.append(
                {"Date": date, "symbol": c["symbol"], "RSI4": c["RSI4"]}
            )
    df = pd.DataFrame(all_candidates)
    df["Date"] = pd.to_datetime(df["Date"])

    # 直近 years 年に絞る
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df["Date"] >= start_date]

    # 🔽 日別に RSI4 順位を付与（小さい方が上位）
    df["RSI4_Rank"] = df.groupby("Date")["RSI4"].rank(ascending=True, method="first")

    # 各日付の上位 top_n のみ表示
    df = df.sort_values(["Date", "RSI4_Rank"], ascending=[True, True])
    df = df.groupby("Date").head(top_n)

    with st.expander(title, expanded=False):
        st.dataframe(
            df.reset_index(drop=True)[["Date", "RSI4_Rank", "symbol", "RSI4"]],
            column_config={
                "Date": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                "RSI4_Rank": st.column_config.NumberColumn(width="small"),
                "symbol": st.column_config.TextColumn(width="small"),
                "RSI4": st.column_config.NumberColumn(width="small"),
            },
            hide_index=False,
        )


# ===============================
# Streamlitタブ呼び出し
# ===============================
def run_tab():
    st.header("System4：ロング・トレンド・ロー・ボラティリティ")

    # --- SPYデータ取得（フィルター用） ---
    spy_df = get_spy_data_cached()
    if spy_df is None or spy_df.empty:
        st.error("SPYデータの取得に失敗しました。キャッシュを更新してください。")
        return

    # --- バックテスト実行 ---
    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy,
        system_name="System4",
        limit_symbols=100,
        spy_df=spy_df,
    )

    if results_df is not None and candidates_by_date is not None:
        # 固有ランキング表示
        display_rsi4_ranking(candidates_by_date)

        # Signal件数とTrade件数の集計
        signal_summary_df = show_signal_trade_summary(data_dict, results_df, "System4")

        # 保存処理
        save_signal_and_trade_logs(signal_summary_df, results_df, "System4", capital)
        save_prepared_data_cache(data_dict, "System4")


# ===============================
# 単体実行用
# ===============================
if __name__ == "__main__":
    import sys

    if "streamlit" not in sys.argv[0]:
        run_tab()
