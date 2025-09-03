import streamlit as st  
import common.ui_patch  # noqa: F401
import pandas as pd
from strategies.system1_strategy import System1Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
    display_roc200_ranking,
    clean_date_column,
)
from common.cache_utils import save_prepared_data_cache
from pathlib import Path
from common.i18n import tr, load_translations_from_dir, language_selector
from common.performance_summary import summarize as summarize_perf
from common.notifier import Notifier

# Load translations once
load_translations_from_dir(Path(__file__).parent / "translations")
# Skip local language selector when running inside integrated UI
if not st.session_state.get("_integrated_ui", False):
    language_selector()

from common.utils_spy import get_spy_with_indicators

SYSTEM_NAME = "System1"
DISPLAY_NAME = "システム1"

strategy = System1Strategy()
notifier = Notifier(platform="discord")


def run_tab(spy_df=None, ui_manager=None):
    st.header(
        tr(
            f"{DISPLAY_NAME} — ロング・トレンド × ハイ・モメンタム — 候補銘柄ランキング"
        )
    )

    spy_df = spy_df if spy_df is not None else get_spy_with_indicators()
    if spy_df is None or spy_df.empty:
        st.error("SPYデータの取得に失敗しました。キャッシュを更新してください")
        return

    results_df, merged_df, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy,
        system_name=SYSTEM_NAME,
        limit_symbols=10,
        spy_df=spy_df,
        ui_manager=ui_manager,
    )

    if results_df is not None and merged_df is not None:
        daily_df = clean_date_column(merged_df, col_name="Date")
        display_roc200_ranking(
            daily_df, title=f"📊 {DISPLAY_NAME} 日別ROC200ランキング"
        )

        signal_summary_df = show_signal_trade_summary(
            merged_df, results_df, SYSTEM_NAME, display_name=DISPLAY_NAME
        )
        save_signal_and_trade_logs(signal_summary_df, results_df, SYSTEM_NAME, capital)
        save_prepared_data_cache(data_dict, SYSTEM_NAME)
        st.success("バックテスト完了")
        summary, _ = summarize_perf(results_df, capital)
        stats = {
            "総リターン": f"{summary.total_return:.2f}",
            "最大DD": f"{summary.max_drawdown:.2f}",
            "Sharpe": f"{summary.sharpe:.2f}",
        }
        ranking = (
            [str(s) for s in results_df["symbol"].head(10)]
            if "symbol" in results_df.columns
            else []
        )
        period = ""
        if "entry_date" in results_df.columns and "exit_date" in results_df.columns:
            start = pd.to_datetime(results_df["entry_date"]).min()
            end = pd.to_datetime(results_df["exit_date"]).max()
            period = f"{start:%Y-%m-%d}〜{end:%Y-%m-%d}"
        # 通知ON/OFFトグル（既定はOFF）
        notify_key = f"{SYSTEM_NAME}_notify_backtest"
        if notify_key not in st.session_state:
            st.session_state[notify_key] = False
        try:
            use_toggle = hasattr(st, "toggle")
        except Exception:
            use_toggle = False
        label = tr("バックテスト結果を通知する（Webhook）")
        enabled = (
            st.toggle(label, key=notify_key) if use_toggle else st.checkbox(label, key=notify_key)
        )
        if not notifier.webhook_url:
            st.caption(tr("Webhook URL が未設定です（.env を確認）"))
        if enabled:
            try:
                notifier.send_backtest("system1", period, stats, ranking)
                st.success(tr("通知を送信しました"))
            except Exception:
                st.warning(tr("通知の送信に失敗しました"))
        else:
            st.info(tr("通知はOFFです"))

    elif results_df is None and merged_df is None:
        prev_res = st.session_state.get(f"{SYSTEM_NAME}_results_df")
        prev_merged = st.session_state.get(f"{SYSTEM_NAME}_merged_df")
        prev_cap = st.session_state.get(f"{SYSTEM_NAME}_capital_saved")
        if prev_res is not None and prev_merged is not None:
            daily_df = clean_date_column(prev_merged, col_name="Date")
            display_roc200_ranking(
                daily_df, title=f"📊 {DISPLAY_NAME} 日別ROC200ランキング（保存済み）"
            )
            _ = show_signal_trade_summary(
                prev_merged, prev_res, SYSTEM_NAME, display_name=DISPLAY_NAME
            )
            try:
                from common.ui_components import show_results
                show_results(prev_res, prev_cap or 0.0, SYSTEM_NAME, key_context="prev")
            except Exception:
                pass


if __name__ == "__main__":
    import sys
    if "streamlit" not in sys.argv[0]:
        run_tab()
