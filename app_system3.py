import streamlit as st  
import common.ui_patch  # noqa: F401
import pandas as pd
from strategies.system3_strategy import System3Strategy
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
from common.equity_curve import save_equity_curve
import os

# 翻訳辞書ロードと言語選択
load_translations_from_dir(Path(__file__).parent / "translations")
if not st.session_state.get("_integrated_ui", False):
    language_selector()


strategy = System3Strategy()
notifier = Notifier(platform="auto")


def display_drop3d_ranking(
    candidates_by_date,
    years: int = 5,
    top_n: int = 100,
    title: str = "📊 System3 日別 3日下落率 ランキング（直近{years}年 / 上位{top_n}銘柄）",
):
    if not candidates_by_date:
        st.warning("3日下落率ランキングが空です")
        return
    rows = []
    for date, cands in candidates_by_date.items():
        for c in cands:
            rows.append({"Date": date, "symbol": c.get("symbol"), "DropRate_3D": c.get("DropRate_3D")})
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])  # type: ignore[arg-type]
    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df["Date"] >= start_date]
    df["DropRate_3D_Rank"] = df.groupby("Date")["DropRate_3D"].rank(ascending=False, method="first")
    df = df.sort_values(["Date", "DropRate_3D_Rank"], ascending=[True, True])
    df = df.groupby("Date").head(top_n)
    with st.expander(title.format(years=years, top_n=top_n), expanded=False):
        st.dataframe(
            df.reset_index(drop=True)[["Date", "DropRate_3D_Rank", "symbol", "DropRate_3D"]],
            hide_index=False,
        )


def run_tab(ui_manager=None):
    st.header("System3 バックテスト（ロング・ミーンリバージョン：急落の反発狙い）")
    ui = ui_manager or UIManager()
    # System1準拠: 通知トグル（Webhook）
    notify_key = "System3_notify_backtest"
    if notify_key not in st.session_state:
        st.session_state[notify_key] = True
    try:
        st.toggle(tr("バックテスト結果を通知する（Webhook）"), key=notify_key)
    except Exception:
        st.checkbox(tr("バックテスト結果を通知する（Webhook）"), key=notify_key)
    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy, system_name="System3", limit_symbols=100, ui_manager=ui
    )
    if results_df is not None and candidates_by_date is not None:
        display_drop3d_ranking(candidates_by_date)
        summary_df = show_signal_trade_summary(data_dict, results_df, "System3")
        with st.expander(tr("取引ログ・保存ファイル"), expanded=False):
            save_signal_and_trade_logs(summary_df, results_df, "System3", capital)
        save_prepared_data_cache(data_dict, "System3")
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
        _img_path, _img_url = save_equity_curve(results_df, capital, "System3")
        if st.session_state.get(notify_key, False):
            _mention = "channel" if os.getenv("SLACK_WEBHOOK_URL") else None
            if hasattr(notifier, "send_backtest_ex"):
                notifier.send_backtest_ex("system3", period, stats, ranking, image_url=_img_url, mention=_mention)
            else:
                notifier.send_backtest("system3", period, stats, ranking)
    else:
        # フォールバック（リラン時にセッションから復元）
        prev_res = st.session_state.get("System3_results_df")
        prev_cands = st.session_state.get("System3_candidates_by_date")
        prev_data = st.session_state.get("System3_prepared_dict")
        prev_cap = st.session_state.get("System3_capital_saved")
        if prev_res is not None and prev_cands is not None:
            display_drop3d_ranking(prev_cands)
            _ = show_signal_trade_summary(prev_data, prev_res, "System3")
            try:
                from common.ui_components import show_results
                show_results(prev_res, prev_cap or 0.0, "System3", key_context="prev")
            except Exception:
                pass


if __name__ == "__main__":
    import sys
    if "streamlit" not in sys.argv[0]:
        run_tab()
