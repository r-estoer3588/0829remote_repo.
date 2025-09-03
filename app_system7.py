import streamlit as st
import common.ui_patch  # noqa: F401
import pandas as pd
from strategies.system7_strategy import System7Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
)
from common.cache_utils import save_prepared_data_cache
from common.ui_manager import UIManager
from pathlib import Path
from common.i18n import tr, load_translations_from_dir, language_selector
from common.performance_summary import summarize as summarize_perf
from common.notifier import Notifier

# Load translations and (optionally) show language selector
load_translations_from_dir(Path(__file__).parent / "translations")
if not st.session_state.get("_integrated_ui", False):
    language_selector()

strategy = System7Strategy()
notifier = Notifier(platform="discord")


def run_tab(single_mode=None, ui_manager=None):
    st.header(tr("System7 バックテスト（カタストロフィー・ヘッジ / SPYのみ）"))
    single_mode = st.checkbox(tr("単体モード（資金100%を使用）"), value=False)

    ui = ui_manager or UIManager()
    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy,
        system_name="System7",
        limit_symbols=1,
        ui_manager=ui,
        single_mode=single_mode,
    )

    if st.checkbox(tr("チェック: インジケーターの確認"), value=False):
        if data_dict:
            for sym, df in data_dict.items():
                st.write(tr("例: 2020年02月〜03月"))
                st.dataframe(df.loc["2020-02-01":"2020-03-31"])  # 確認用
        else:
            st.info(tr("データが取得できていないため表示できません。バックテストを先に実行してください。"))

    if results_df is not None and candidates_by_date is not None:
        summary_df = show_signal_trade_summary(data_dict, results_df, "System7")
        save_signal_and_trade_logs(summary_df, results_df, "System7", capital)
        save_prepared_data_cache(data_dict, "System7")
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
        notifier.send_backtest("system7", period, stats, ranking)
    else:
        # Fallback view from session state
        prev_res = st.session_state.get("System7_results_df")
        prev_data = st.session_state.get("System7_prepared_dict")
        prev_cap = st.session_state.get("System7_capital_saved")
        if prev_res is not None:
            _ = show_signal_trade_summary(prev_data, prev_res, "System7")
            try:
                from common.ui_components import show_results
                show_results(prev_res, prev_cap or 0.0, "System7", key_context="prev")
            except Exception:
                pass


if __name__ == "__main__":
    import sys
    if "streamlit" not in sys.argv[0]:
        run_tab()

