# app_integrated.py
import streamlit as st
import pandas as pd

# --- 各システムのUIタブ呼び出し ---
from app_system1 import run_tab as run_tab1, get_spy_data_cached
from app_system2 import run_tab as run_tab2
from app_system3 import run_tab as run_tab3
from app_system4 import run_tab as run_tab4
from app_system5 import run_tab as run_tab5
from app_system6 import run_tab as run_tab6
from app_system7 import run_tab as run_tab7

# --- 各システムの戦略クラス（バックテスト一括用） ---
from strategies.system1_strategy import System1Strategy
from strategies.system2_strategy import System2Strategy
from strategies.system3_strategy import System3Strategy
from strategies.system4_strategy import System4Strategy
from strategies.system5_strategy import System5Strategy
from strategies.system6_strategy import System6Strategy
from strategies.system7_strategy import System7Strategy

# --- 共通キャッシュ関数 ---
from cache_daily_data import get_cached_data


st.title("📊 統合バックテスト&実運用：System1〜7")

# --- 表示モード選択 ---
display_mode = st.radio("表示モード", ["戦略別テスト", "一括実行"], key="display_mode_selector")

# =========================================================
# 戦略別テストモード
# =========================================================
if display_mode == "戦略別テスト":
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        ["System1", "System2", "System3", "System4", "System5", "System6", "System7"]
    )

    with tab1:
        spy_df = get_spy_data_cached()
        run_tab1(spy_df)
    with tab2:
        run_tab2()
    with tab3:
        run_tab3()
    with tab4:
        run_tab4()
    with tab5:
        run_tab5()
    with tab6:
        run_tab6()
    with tab7:
        run_tab7()

# =========================================================
# 一括実行モード
# =========================================================
if display_mode == "一括実行":
    st.subheader("🚀 一括バックテスト / 実運用シグナル発生")

    # --- 初期設定 ---
    capital = st.number_input("初期資金（USD）", value=100000, step=1000)
    run_mode = st.radio("モード選択", ["バックテスト", "シグナル検出"], horizontal=True)

    if st.button("▶ 実行"):
        st.info("全システムの処理を開始します...")
        progress = st.progress(0)
        log_area = st.empty()

        # --- データ取得（共通キャッシュ） ---
        raw_data_dict = get_cached_data()  # 全銘柄まとめて取得
        spy_df = get_spy_data_cached()

        all_results = []
        total_systems = 7
        sys_done = 0

        # --- System1 ---
        s1 = System1Strategy()
        prepared = s1.prepare_data(raw_data_dict, log_callback=lambda m: log_area.text(m))
        candidates, _ = s1.generate_candidates(prepared, spy_df)
        df1 = s1.run_backtest(prepared, candidates, capital,
                              on_progress=lambda d, t, stt: progress.progress((sys_done + d/t)/total_systems))
        all_results.append(df1)
        sys_done += 1

        # --- System2 ---
        s2 = System2Strategy()
        prepared = s2.prepare_data(raw_data_dict, log_callback=lambda m: log_area.text(m))
        candidates = s2.generate_candidates(prepared)
        df2 = s2.run_backtest(prepared, candidates, capital)
        all_results.append(df2)
        sys_done += 1
        progress.progress(sys_done/total_systems)

        # --- System3 ---
        s3 = System3Strategy()
        prepared = s3.prepare_data(raw_data_dict, log_callback=lambda m: log_area.text(m))
        candidates = s3.generate_candidates(prepared)
        df3 = s3.run_backtest(prepared, candidates, capital)
        all_results.append(df3)
        sys_done += 1
        progress.progress(sys_done/total_systems)

        # --- System4 ---
        s4 = System4Strategy()
        prepared = s4.prepare_data(raw_data_dict, log_callback=lambda m: log_area.text(m))
        candidates = s4.generate_candidates(prepared)
        df4 = s4.run_backtest(prepared, candidates, capital)
        all_results.append(df4)
        sys_done += 1
        progress.progress(sys_done/total_systems)

        # --- System5 ---
        s5 = System5Strategy()
        prepared = s5.prepare_data(raw_data_dict, log_callback=lambda m: log_area.text(m))
        candidates = s5.generate_candidates(prepared)
        df5 = s5.run_backtest(prepared, candidates, capital)
        all_results.append(df5)
        sys_done += 1
        progress.progress(sys_done/total_systems)

        # --- System6 ---
        s6 = System6Strategy()
        prepared = s6.prepare_data(raw_data_dict, log_callback=lambda m: log_area.text(m))
        candidates = s6.generate_candidates(prepared)
        df6 = s6.run_backtest(prepared, candidates, capital)
        all_results.append(df6)
        sys_done += 1
        progress.progress(sys_done/total_systems)

        # --- System7 ---
        s7 = System7Strategy()
        prepared = s7.prepare_data({"SPY": spy_df})
        candidates = s7.generate_candidates(prepared)
        df7 = s7.run_backtest(prepared, candidates, capital)
        all_results.append(df7)
        sys_done += 1
        progress.progress(sys_done/total_systems)

        # --- 結果まとめ ---
        final_df = pd.concat(all_results, ignore_index=True)
        st.success("全システム処理完了 ✅")
        st.dataframe(final_df)
