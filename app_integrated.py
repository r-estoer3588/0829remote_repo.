from __future__ import annotations

import streamlit as st
import common.ui_patch  # noqa: F401
from pathlib import Path
from common.i18n import tr, load_translations_from_dir, language_selector

from config.settings import get_settings
from common.logging_utils import setup_logging
from common.performance_summary import summarize as summarize_perf
from common.ui_bridge import (
    prepare_backtest_data_ui as _prepare_ui,
    run_backtest_with_logging_ui as _run_ui,
)
from common.utils_spy import get_spy_data_cached, get_spy_with_indicators
from tickers_loader import get_all_tickers
from common.ui_manager import UIManager

# 外部翻訳を読み込む（任意・起動時に一度）
load_translations_from_dir(Path(__file__).parent / "translations")
# サイドバーに言語選択を表示
language_selector(in_sidebar=True)

def _show_sys_result(df, capital):
    if df is None or getattr(df, "empty", True):
        st.info(tr("no trades"))
        return
    summary, _ = summarize_perf(df, capital)
    d = summary.to_dict()
    cols = st.columns(6)
    cols[0].metric(tr("trades"), d.get("trades"))
    cols[1].metric(tr("total pnl"), f"{d.get('total_return', 0):.2f}")
    cols[2].metric(tr("win rate (%)"), f"{d.get('win_rate', 0):.2f}")
    cols[3].metric("PF", f"{d.get('profit_factor', 0):.2f}")
    cols[4].metric("Sharpe", f"{d.get('sharpe', 0):.2f}")
    cols[5].metric(tr("max drawdown"), f"{d.get('max_drawdown', 0):.2f}")
    st.dataframe(df)


def main():
    st.set_page_config(page_title="Trading Systems 1-7 (Integrated)", layout="wide")

    settings = get_settings(create_dirs=True)
    logger = setup_logging(settings)
    logger.info("app_integrated start")

    st.title(tr("Trading Systems Integrated UI"))
    with st.expander(tr("settings"), expanded=False):
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

    tabs = st.tabs([tr("Integrated"), tr("Batch")] + [f"System{i}" for i in range(1, 8)])

    # Integrated Engine tab
    with tabs[0]:
        st.subheader(tr("Integrated Backtest (Systems 1-7)"))
        from common.integrated_backtest import (
            build_system_states,
            run_integrated_backtest,
            DEFAULT_ALLOCATIONS,
        )
        from common.ui_bridge import prepare_backtest_data_ui as _prepare_ui
        from common.utils_spy import get_spy_with_indicators
        from common.holding_tracker import generate_holding_matrix, display_holding_heatmap

        capital_i = st.number_input(
            tr("capital (USD)"),
            min_value=1000,
            value=int(settings.ui.default_capital),
            step=1000,
            key="integrated_capital",
        )
        limit_i = st.number_input(
            tr("symbol limit"),
            min_value=50,
            max_value=5000,
            value=min(500, get_all_tickers().__len__()),
            step=50,
            key="integrated_limit",
        )
        colA, colB = st.columns(2)
        with colA:
            allow_gross = st.checkbox(
                tr("allow gross leverage (sum cost can exceed capital)"),
                value=False,
                key="integrated_gross",
            )
        with colB:
            st.caption(
                tr(
                    "allocation is fixed: long 1/3/4/5: each 25%, short 2:40%,6:40%,7:20%"
                )
            )
        colL, colS = st.columns(2)
        with colL:
            long_share = st.slider(
                tr("long bucket share (%)"),
                min_value=0,
                max_value=100,
                value=50,
                step=5,
                key="integrated_long_share",
            )
        with colS:
            st.caption(tr("short bucket share = 100% - long"))
        short_share = 100 - int(long_share)
        run_btn_i = st.button(tr("run integrated"))

        if run_btn_i:
            all_tickers = get_all_tickers()
            symbols = all_tickers[: int(limit_i)]
            spy_base = get_spy_with_indicators(get_spy_data_cached())

            ui = UIManager().system("Integrated", title=tr("Integrated"))
            prep_phase = ui.phase("prepare", title=tr("prepare all systems"))
            prep_phase.info(tr("preparing per-system data / candidates..."))

            # states 構築（UI連携）
            # UIManager を build_system_states に渡して各システムのフェーズUIを利用
            states = build_system_states(
                symbols,
                spy_df=spy_base,
                ui_bridge_prepare=_prepare_ui,
                ui_manager=ui,
            )

            # シグナル件数表示
            import pandas as _pd
            sig_counts = {s.name: int(sum(len(v) for v in s.candidates_by_date.values())) for s in states}
            st.write(tr("signals per system:"))
            st.dataframe(_pd.DataFrame([sig_counts]))

            sim = ui.phase("simulate", title=tr("simulate integrated"))
            sim.info(tr("running integrated engine..."))
            trades_df, _sig = run_integrated_backtest(
                states,
                capital_i,
                allocations=DEFAULT_ALLOCATIONS,
                long_share=float(long_share) / 100.0,
                short_share=float(short_share) / 100.0,
                allow_gross_leverage=allow_gross,
            )

            st.markdown("---")
            st.subheader(tr("Integrated Summary"))
            if trades_df is not None and not trades_df.empty:
                summary, df2 = summarize_perf(trades_df, capital_i)
                d = summary.to_dict()
                cols = st.columns(6)
                cols[0].metric(tr("trades"), d.get("trades"))
                cols[1].metric(tr("total pnl"), f"{d.get('total_return', 0):.2f}")
                cols[2].metric(tr("win rate (%)"), f"{d.get('win_rate', 0):.2f}")
                cols[3].metric("PF", f"{d.get('profit_factor', 0):.2f}")
                cols[4].metric("Sharpe", f"{d.get('sharpe', 0):.2f}")
                cols[5].metric(tr("max drawdown"), f"{d.get('max_drawdown', 0):.2f}")
                st.dataframe(df2)

                # Holdings heatmap (optional)
                with st.expander("holdings heatmap", expanded=False):
                    matrix = generate_holding_matrix(df2)
                    display_holding_heatmap(matrix, title="Integrated - holdings heatmap")

                # Download
                _ts_i = _pd.Timestamp.now().strftime("%Y-%m-%d_%H%M")
                st.download_button(
                    label=tr("download integrated trades CSV"),
                    data=df2.to_csv(index=False).encode("utf-8"),
                    file_name=f"integrated_trades_{_ts_i}_{int(capital_i)}.csv",
                    mime="text/csv",
                    key="download_integrated_csv",
                )
            else:
                st.info(tr("no trades in integrated run"))

    # Batch run tab
    with tabs[1]:
        st.subheader(tr("Batch Backtest / Summary"))
        _mode_options = {
            "Backtest": tr("Backtest"),
            "Future": tr("Future signals (coming soon)"),
        }
        _mode_label = st.radio(
            tr("mode"),
            list(_mode_options.values()),
            index=0,
            horizontal=True,
            key="batch_mode",
        )
        mode = "Backtest" if _mode_label == _mode_options["Backtest"] else "Future"
        capital = st.number_input(
            tr("capital (USD)"),
            min_value=1000,
            value=int(settings.ui.default_capital),
            step=1000,
        )
        limit_symbols = st.number_input(
            tr("symbol limit"),
            min_value=50,
            max_value=5000,
            value=min(500, get_all_tickers().__len__()),
            step=50,
        )
        run_btn = st.button(tr("run batch"), disabled=(mode != "Backtest"))

        # Log display option
        log_tail_lines = st.number_input(
            tr("max log lines shown per system"),
            min_value=10,
            max_value=10000,
            value=500,
            step=50,
            key="batch_log_tail_n",
        )

        # Saved results (persist across reruns)
        saved_df = st.session_state.get("Batch_all_trades_df")
        saved_summary = st.session_state.get("Batch_summary_dict")
        saved_capital = st.session_state.get("Batch_capital")
        if saved_df is not None:
            st.markdown("---")
            st.subheader(tr("Saved Batch Results (persisted)"))
            if isinstance(saved_summary, dict):
                cols = st.columns(6)
                cols[0].metric(tr("trades"), saved_summary.get("trades"))
                cols[1].metric(tr("total pnl"), f"{saved_summary.get('total_return', 0):.2f}")
                cols[2].metric(tr("win rate (%)"), f"{saved_summary.get('win_rate', 0):.2f}")
                cols[3].metric("PF", f"{saved_summary.get('profit_factor', 0):.2f}")
                cols[4].metric("Sharpe", f"{saved_summary.get('sharpe', 0):.2f}")
                cols[5].metric(tr("max drawdown"), f"{saved_summary.get('max_drawdown', 0):.2f}")
            st.dataframe(saved_df)
            # Download / Save buttons for saved batch
            import pandas as _pd
            import os as _os
            _ts = _pd.Timestamp.now().strftime("%Y-%m-%d_%H%M")
            st.download_button(
                label=tr("download saved batch trades CSV"),
                data=saved_df.to_csv(index=False).encode("utf-8"),
                file_name=f"batch_trades_saved_{_ts}_{int(saved_capital or 0)}.csv",
                mime="text/csv",
                key="download_saved_batch_csv",
            )
            if st.button(tr("save saved batch CSV to disk"), key="save_saved_batch_to_disk"):
                out_dir = _os.path.join("results_csv", "batch"); _os.makedirs(out_dir, exist_ok=True)
                trades_path = _os.path.join(out_dir, f"batch_trades_saved_{_ts}_{int(saved_capital or 0)}.csv")
                saved_df.to_csv(trades_path, index=False)
                # summary
                if isinstance(saved_summary, dict):
                    sum_df = _pd.DataFrame([saved_summary])
                    sum_path = _os.path.join(out_dir, f"batch_summary_saved_{_ts}_{int(saved_capital or 0)}.csv")
                    sum_df.to_csv(sum_path, index=False)
                st.success(tr("saved to {out_dir}", out_dir=out_dir))
            if st.button(tr("clear saved batch results"), key="clear_saved_batch"):
                for k in ["Batch_all_trades_df", "Batch_summary_dict", "Batch_capital"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.experimental_rerun()

        # Saved per-system logs
        st.markdown("---")
        with st.expander(tr("Saved Per-System Logs"), expanded=False):
            any_logs = False
            for i in range(1, 8):
                sys_name = f"System{i}"
                logs = st.session_state.get(f"{sys_name}_debug_logs")
                if logs:
                    any_logs = True
                    with st.expander(f"{sys_name} logs", expanded=False):
                        tail = list(map(str, logs))[-int(log_tail_lines):]
                        st.text("\n".join(tail))
            if not any_logs:
                st.info(tr("no saved logs yet"))

        if mode != "Backtest":
            st.info(tr("Signal detection mode will be added soon."))

        if run_btn:
            all_tickers = get_all_tickers()
            symbols = all_tickers[: int(limit_symbols)]
            # Batch 実行でも SPY に SMA100/200 を付与しておく（System1/4 フィルタ用）
            spy_df = get_spy_with_indicators(get_spy_data_cached())

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
            st.subheader(tr("All systems summary"))
            if overall:
                import pandas as pd

                all_df = pd.concat(overall, ignore_index=True)
                summary, all_df2 = summarize_perf(all_df, capital)
                cols = st.columns(6)
                d = summary.to_dict()
                cols[0].metric(tr("trades"), d.get("trades"))
                cols[1].metric(tr("total pnl"), f"{d.get('total_return', 0):.2f}")
                cols[2].metric(tr("win rate (%)"), f"{d.get('win_rate', 0):.2f}")
                cols[3].metric("PF", f"{d.get('profit_factor', 0):.2f}")
                cols[4].metric("Sharpe", f"{d.get('sharpe', 0):.2f}")
                cols[5].metric(tr("max drawdown"), f"{d.get('max_drawdown', 0):.2f}")
                st.dataframe(all_df2)

                # Download / Save buttons for current batch output
                _ts2 = pd.Timestamp.now().strftime("%Y-%m-%d_%H%M")
                st.download_button(
                    label=tr("download batch trades CSV"),
                    data=all_df2.to_csv(index=False).encode("utf-8"),
                    file_name=f"batch_trades_{_ts2}_{int(capital)}.csv",
                    mime="text/csv",
                    key="download_batch_csv_current",
                )
                if st.button(tr("save batch CSV to disk"), key="save_batch_to_disk_current"):
                    import os as _os
                    out_dir = _os.path.join("results_csv", "batch"); _os.makedirs(out_dir, exist_ok=True)
                    trades_path = _os.path.join(out_dir, f"batch_trades_{_ts2}_{int(capital)}.csv")
                    all_df2.to_csv(trades_path, index=False)
                    sum_df = pd.DataFrame([d])
                    sum_path = _os.path.join(out_dir, f"batch_summary_{_ts2}_{int(capital)}.csv")
                    sum_df.to_csv(sum_path, index=False)
                    st.success(tr("saved to {out_dir}", out_dir=out_dir))

                # Save to session (persist across reruns)
                st.session_state["Batch_all_trades_df"] = all_df2
                st.session_state["Batch_summary_dict"] = d
                st.session_state["Batch_capital"] = capital
            else:
                st.info(tr("no results"))

            # Show latest per-system logs after batch run
            st.markdown("---")
            with st.expander(tr("Per-System Logs (latest)"), expanded=False):
                any_logs2 = False
                for i in range(1, 8):
                    sys_name = f"System{i}"
                    logs = st.session_state.get(f"{sys_name}_debug_logs")
                    if logs:
                        any_logs2 = True
                        with st.expander(f"{sys_name} logs", expanded=False):
                            tail2 = list(map(str, logs))[-int(log_tail_lines):]
                            st.text("\n".join(tail2))
                if not any_logs2:
                    st.info(tr("no logs to show"))

    # Individual tabs (skip Integrated and Batch tabs)
    system_tabs = tabs[2:]
    for sys_idx, tab in enumerate(system_tabs, start=1):
        with tab:
            sys_name = f"System{sys_idx}"
            st.subheader(f"{sys_name} backtest")
            try:
                app_mod = __import__(f"app_system{sys_idx}")
                if sys_idx == 1:
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
