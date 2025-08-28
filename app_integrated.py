from __future__ import annotations

import streamlit as st
import common.ui_patch  # noqa: F401

from config.settings import get_settings
from common.logging_utils import setup_logging
from common.performance_summary import summarize as summarize_perf
from common.ui_bridge import (
    prepare_backtest_data_ui as _prepare_ui,
    run_backtest_with_logging_ui as _run_ui,
)
from common.utils_spy import get_spy_data_cached
from tickers_loader import get_all_tickers
from common.ui_manager import UIManager


def _show_sys_result(df, capital):
    if df is None or getattr(df, "empty", True):
        st.info("no trades")
        return
    summary, _ = summarize_perf(df, capital)
    d = summary.to_dict()
    cols = st.columns(6)
    cols[0].metric("trades", d.get("trades"))
    cols[1].metric("total pnl", f"{d.get('total_return', 0):.2f}")
    cols[2].metric("win(%)", f"{d.get('win_rate', 0):.2f}")
    cols[3].metric("PF", f"{d.get('profit_factor', 0):.2f}")
    cols[4].metric("Sharpe", f"{d.get('sharpe', 0):.2f}")
    cols[5].metric("MDD", f"{d.get('max_drawdown', 0):.2f}")
    st.dataframe(df)


def main():
    st.set_page_config(page_title="Trading Systems 1-7 (Integrated)", layout="wide")

    settings = get_settings(create_dirs=True)
    logger = setup_logging(settings)
    logger.info("app_integrated start")

    st.title("Trading Systems Integrated UI")
    with st.expander("settings", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write("RESULTS_DIR:", str(settings.RESULTS_DIR))
            st.write("LOGS_DIR:", str(settings.LOGS_DIR))
        with col2:
            st.write("DATA_CACHE_DIR:", str(settings.DATA_CACHE_DIR))
            st.write("THREADS:", settings.THREADS_DEFAULT)
        with col3:
            st.write("DEFAULT CAPITAL:", settings.ui.default_capital)
            st.write("LOG LEVEL:", settings.logging.level)

    tabs = st.tabs(["Batch"] + [f"System{i}" for i in range(1, 8)])

    # Batch run tab
    with tabs[0]:
        st.subheader("Batch Backtest / Summary")
        mode = st.radio(
            "mode",
            ["Backtest", "Future signals (coming soon)"],
            index=0,
            horizontal=True,
            key="batch_mode",
        )
        capital = st.number_input("capital (USD)", min_value=1000, value=int(settings.ui.default_capital), step=1000)
        limit_symbols = st.number_input("symbol limit", min_value=50, max_value=5000, value=min(500, get_all_tickers().__len__()), step=50)
        run_btn = st.button("run batch", disabled=(mode != "Backtest"))

        if mode != "Backtest":
            st.info("Signal detection mode will be added soon.")

        if run_btn:
            all_tickers = get_all_tickers()
            symbols = all_tickers[: int(limit_symbols)]
            spy_df = get_spy_data_cached()

            overall = []
            sys_progress = st.progress(0)
            sys_log = st.empty()
            total_sys = 7
            done_sys = 0
            batch_ui = UIManager()

            for i in range(1, 8):
                sys_name = f"System{i}"
                sys_log.text(f"{sys_name}: starting...")
                try:
                    mod = __import__(f"strategies.system{i}_strategy", fromlist=[f"System{i}Strategy"])  # type: ignore
                    cls = getattr(mod, f"System{i}Strategy")
                    strat = cls()

                    sys_ui = batch_ui.system(sys_name, title=sys_name)
                    prepared, cands, merged = _prepare_ui(
                        strat,
                        symbols if sys_name != "System7" else ["SPY"],
                        system_name=sys_name,
                        spy_df=spy_df,
                        ui_manager=sys_ui,
                    )
                    if cands is None:
                        sys_log.text(f"{sys_name}: no candidates (skip)")
                        done_sys += 1
                        sys_progress.progress(done_sys / total_sys)
                        continue

                    sys_log.text(f"{sys_name}: running...")
                    res = _run_ui(
                        strat,
                        prepared,
                        cands,
                        capital,
                        system_name=sys_name,
                        ui_manager=sys_ui,
                    )
                    if res is not None and not res.empty:
                        res["system"] = sys_name
                        overall.append(res)
                        with sys_ui.container.expander(f"{sys_name} result", expanded=False):
                            _show_sys_result(res, capital)
                    else:
                        st.info(f"{sys_name}: no trades")
                except Exception as e:  # noqa: BLE001
                    logger.exception("%s error", sys_name)
                    st.exception(e)
                finally:
                    done_sys += 1
                    sys_progress.progress(done_sys / total_sys)

            st.markdown("---")
            st.subheader("All systems summary")
            if overall:
                import pandas as pd

                all_df = pd.concat(overall, ignore_index=True)
                summary, all_df2 = summarize_perf(all_df, capital)
                cols = st.columns(6)
                d = summary.to_dict()
                cols[0].metric("trades", d.get("trades"))
                cols[1].metric("total pnl", f"{d.get('total_return', 0):.2f}")
                cols[2].metric("win(%)", f"{d.get('win_rate', 0):.2f}")
                cols[3].metric("PF", f"{d.get('profit_factor', 0):.2f}")
                cols[4].metric("Sharpe", f"{d.get('sharpe', 0):.2f}")
                cols[5].metric("MDD", f"{d.get('max_drawdown', 0):.2f}")
                st.dataframe(all_df2)
            else:
                st.info("no results")

    # Individual tabs (reuse each system's UI assets via app_systemX.main_process)
    for idx, tab in enumerate(tabs[1:], start=1):
        with tab:
            sys_name = f"System{idx}"
            st.subheader(f"{sys_name} backtest")
            try:
                app_mod = __import__(f"app_system{idx}")
                if idx == 1:
                    # System1: reuse cached SPY from integrated layer
                    spy_df = get_spy_data_cached()
                    app_mod.main_process(spy_df=spy_df)
                else:
                    app_mod.main_process()
            except Exception as e:  # noqa: BLE001
                logger.exception("%s tab error", sys_name)
                st.exception(e)


if __name__ == "__main__":
    main()
