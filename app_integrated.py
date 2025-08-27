# app_integrated.py
import streamlit as st
import pandas as pd

# --- 蜷・す繧ｹ繝・Β縺ｮUI繧ｿ繝門他縺ｳ蜃ｺ縺・---
from app_system1_ui2 import run_tab as run_tab1, get_spy_data_cached
from app_system2_ui2 import run_tab as run_tab2
from app_system3_ui2 import run_tab as run_tab3
from app_system4_ui2 import run_tab as run_tab4
from app_system5_ui2 import run_tab as run_tab5
from app_system6_ui2 import run_tab as run_tab6
from app_system7_ui2 import run_tab as run_tab7

# --- 蜷・す繧ｹ繝・Β縺ｮ謌ｦ逡･繧ｯ繝ｩ繧ｹ・医ヰ繝・け繝・せ繝井ｸ諡ｬ逕ｨ・・---
from strategies.system1_strategy import System1Strategy
from strategies.system2_strategy import System2Strategy
from strategies.system3_strategy import System3Strategy
from strategies.system4_strategy import System4Strategy
from strategies.system5_strategy import System5Strategy
from strategies.system6_strategy import System6Strategy
from strategies.system7_strategy import System7Strategy

# --- 蜈ｱ騾壹く繝｣繝・す繝･髢｢謨ｰ ---
from cache_daily_data import get_cached_data


st.title("投 邨ｱ蜷医ヰ繝・け繝・せ繝・螳滄°逕ｨ・售ystem1縲・")
`r`nsettings = get_settings(create_dirs=True)`r`n_logger = setup_logging(settings)`r`n
# --- 陦ｨ遉ｺ繝｢繝ｼ繝蛾∈謚・---
display_mode = st.radio(
    "陦ｨ遉ｺ繝｢繝ｼ繝・, ["謌ｦ逡･蛻･繝・せ繝・, "荳諡ｬ螳溯｡・], key="display_mode_selector"
)

# =========================================================
# 謌ｦ逡･蛻･繝・せ繝医Δ繝ｼ繝・# =========================================================
if display_mode == "謌ｦ逡･蛻･繝・せ繝・:
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
# 荳諡ｬ螳溯｡後Δ繝ｼ繝・# =========================================================
if display_mode == "荳諡ｬ螳溯｡・:
    st.subheader("噫 荳諡ｬ繝舌ャ繧ｯ繝・せ繝・/ 螳滄°逕ｨ繧ｷ繧ｰ繝翫Ν逋ｺ逕・)

    # --- 蛻晄悄險ｭ螳・---
    capital = st.number_input("蛻晄悄雉・≡・・SD・・, value=settings.ui.default_capital, step=1000)
    run_mode = st.radio("繝｢繝ｼ繝蛾∈謚・, ["繝舌ャ繧ｯ繝・せ繝・, "繧ｷ繧ｰ繝翫Ν讀懷・"], horizontal=True)

    if st.button("笆ｶ 螳溯｡・):
        st.info("蜈ｨ繧ｷ繧ｹ繝・Β縺ｮ蜃ｦ逅・ｒ髢句ｧ九＠縺ｾ縺・..")
        progress = st.progress(0)
        log_area = st.empty()

        # --- 繝・・繧ｿ蜿門ｾ暦ｼ亥・騾壹く繝｣繝・す繝･・・---
        raw_data_dict = get_cached_data()  # 蜈ｨ驫俶氛縺ｾ縺ｨ繧√※蜿門ｾ・        spy_df = get_spy_data_cached()

        all_results = []
        total_systems = 7
        sys_done = 0

        # --- System1 ---
        s1 = System1Strategy()
        prepared = s1.prepare_data(
            raw_data_dict, log_callback=lambda m: log_area.text(m)
        )
        candidates, _ = s1.generate_candidates(prepared, spy_df)
        df1 = s1.run_backtest(
            prepared,
            candidates,
            capital,
            on_progress=lambda d, t, stt: progress.progress(
                (sys_done + d / t) / total_systems
            ),
        )
        all_results.append(df1)
        sys_done += 1

        # --- System2 ---
        s2 = System2Strategy()
        prepared = s2.prepare_data(
            raw_data_dict, log_callback=lambda m: log_area.text(m)
        )
        candidates = s2.generate_candidates(prepared)
        df2 = s2.run_backtest(prepared, candidates, capital)
        all_results.append(df2)
        sys_done += 1
        progress.progress(sys_done / total_systems)

        # --- System3 ---
        s3 = System3Strategy()
        prepared = s3.prepare_data(
            raw_data_dict, log_callback=lambda m: log_area.text(m)
        )
        candidates = s3.generate_candidates(prepared)
        df3 = s3.run_backtest(prepared, candidates, capital)
        all_results.append(df3)
        sys_done += 1
        progress.progress(sys_done / total_systems)

        # --- System4 ---
        s4 = System4Strategy()
        prepared = s4.prepare_data(
            raw_data_dict, log_callback=lambda m: log_area.text(m)
        )
        candidates = s4.generate_candidates(prepared)
        df4 = s4.run_backtest(prepared, candidates, capital)
        all_results.append(df4)
        sys_done += 1
        progress.progress(sys_done / total_systems)

        # --- System5 ---
        s5 = System5Strategy()
        prepared = s5.prepare_data(
            raw_data_dict, log_callback=lambda m: log_area.text(m)
        )
        candidates = s5.generate_candidates(prepared)
        df5 = s5.run_backtest(prepared, candidates, capital)
        all_results.append(df5)
        sys_done += 1
        progress.progress(sys_done / total_systems)

        # --- System6 ---
        s6 = System6Strategy()
        prepared = s6.prepare_data(
            raw_data_dict, log_callback=lambda m: log_area.text(m)
        )
        candidates = s6.generate_candidates(prepared)
        df6 = s6.run_backtest(prepared, candidates, capital)
        all_results.append(df6)
        sys_done += 1
        progress.progress(sys_done / total_systems)

        # --- System7 ---
        s7 = System7Strategy()
        prepared = s7.prepare_data({"SPY": spy_df})
        candidates = s7.generate_candidates(prepared)
        df7 = s7.run_backtest(prepared, candidates, capital)
        all_results.append(df7)
        sys_done += 1
        progress.progress(sys_done / total_systems)

        # --- 邨先棡縺ｾ縺ｨ繧・---
        final_df = pd.concat(all_results, ignore_index=True)
        st.success("蜈ｨ繧ｷ繧ｹ繝・Β蜃ｦ逅・ｮ御ｺ・笨・)
        st.dataframe(final_df)

