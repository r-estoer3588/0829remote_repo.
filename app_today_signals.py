from __future__ import annotations

import io
import pandas as pd
import streamlit as st

from config.settings import get_settings
from run_all_systems_today import compute_today_signals
from utils.universe import build_universe_from_cache, save_universe_file, load_universe_file


st.set_page_config(page_title="Today Signals", layout="wide")
st.title("📈 Today Signals (All Systems)")

settings = get_settings(create_dirs=True)

with st.sidebar:
    st.header("Universe")
    if st.button("🔁 Rebuild Universe (cached)"):
        syms = build_universe_from_cache()
        path = save_universe_file(syms)
        st.success(f"Universe updated: {path} ({len(syms)} symbols)")

    universe = load_universe_file()
    default_syms = universe or list(settings.ui.auto_tickers) or []
    syms_text = st.text_area(
        "Symbols (comma/space separated)",
        value=", ".join(default_syms[:200]),
        height=100,
    )
    syms = [s.strip().upper() for s in syms_text.replace("\n", ",").replace(" ", ",").split(",") if s.strip()]

    st.header("Budgets")
    col1, col2 = st.columns(2)
    with col1:
        cap_long = st.number_input("Capital Long ($)", min_value=0.0, step=1000.0, value=float(settings.backtest.initial_capital))
    with col2:
        cap_short = st.number_input("Capital Short ($)", min_value=0.0, step=1000.0, value=float(settings.backtest.initial_capital))

    save_csv = st.checkbox("Save CSV to signals_dir", value=False)

if st.button("▶ Run Today Signals", type="primary"):
    with st.spinner("Running..."):
        final_df, per_system = compute_today_signals(
            syms,
            capital_long=cap_long,
            capital_short=cap_short,
            save_csv=save_csv,
        )

    st.subheader("Final Picks")
    if final_df is None or final_df.empty:
        st.info("No signals today.")
    else:
        st.dataframe(final_df, use_container_width=True)
        csv = final_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download Final CSV", data=csv, file_name="today_signals_final.csv")

    with st.expander("Per-system details"):
        for name, df in per_system.items():
            st.markdown(f"#### {name}")
            if df is None or df.empty:
                st.write("(empty)")
            else:
                st.dataframe(df, use_container_width=True)
                csv2 = df.to_csv(index=False).encode("utf-8")
                st.download_button(f"Download {name}", data=csv2, file_name=f"signals_{name}.csv")

