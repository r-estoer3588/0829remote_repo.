"""System1 Streamlitアプリ."""

# ruff: noqa: I001
# isort: skip_file

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from common.cache_utils import save_prepared_data_cache
from common.equity_curve import save_equity_curve
from common.i18n import language_selector, load_translations_from_dir, tr
from common.notifier import get_notifiers_from_env
from common.performance_summary import summarize as summarize_perf
from common.ui_components import (
    clean_date_column,
    display_roc200_ranking,
    run_backtest_app,
    save_signal_and_trade_logs,
    show_signal_trade_summary,
)
import common.ui_patch  # noqa: F401
from common.utils_spy import get_spy_with_indicators
from strategies.system1_strategy import System1Strategy

# Load translations once
load_translations_from_dir(Path(__file__).parent / "translations")
# Skip local language selector when running inside integrated UI
if not st.session_state.get("_integrated_ui", False):
    language_selector()

SYSTEM_NAME = "System1"
DISPLAY_NAME = "システム1"

strategy = System1Strategy()
# Auto-select Slack/Discord based on available webhook env
notifiers = get_notifiers_from_env()
notifier = notifiers[0]


def run_tab(spy_df=None, ui_manager=None):
    st.header(tr(f"{DISPLAY_NAME} — ロング・トレンド × ハイ・モメンタム — 候補銘柄ランキング"))
    st.header(tr(f"{DISPLAY_NAME} — ロング・トレンド × ハイ・モメンタム — 候補銘柄ランキング"))

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
        display_roc200_ranking(daily_df, title=f"📊 {DISPLAY_NAME} 日別ROC200ランキング")
        display_roc200_ranking(daily_df, title=f"📊 {DISPLAY_NAME} 日別ROC200ランキング")

        signal_summary_df = show_signal_trade_summary(
            merged_df, results_df, SYSTEM_NAME, display_name=DISPLAY_NAME
        )
        # 取引ログと保存ファイルはエクスパンダーにまとめて表示
        with st.expander(tr("取引ログ・保存ファイル"), expanded=False):
            save_signal_and_trade_logs(signal_summary_df, results_df, SYSTEM_NAME, capital)
        save_prepared_data_cache(data_dict, SYSTEM_NAME)
        st.success("バックテスト完了")
        summary, _ = summarize_perf(results_df, capital)
        max_dd = summary.max_drawdown
        if max_dd > 0:
            max_dd = -max_dd
        max_dd_pct = (max_dd / capital * 100) if capital else 0.0
        stats = {
            "総リターン": f"{summary.total_return:.2f}",
            "最大DD": f"{max_dd:.2f} ({max_dd_pct:.2f}%)",
            "Sharpe": f"{summary.sharpe:.2f}",
        }
        try:
            if hasattr(summary, "profit_factor"):
                stats["PF"] = f"{summary.profit_factor:.2f}"
            if hasattr(summary, "win_rate"):
                stats["勝率(%)"] = f"{summary.win_rate:.2f}"
        except Exception:
            pass

        ranking = []
        try:
            last_date = pd.to_datetime(daily_df["Date"]).max()
            cols = {c.lower(): c for c in daily_df.columns}
            roc_col = cols.get("roc200")
            vol_col = cols.get("volume") or cols.get("vol")
            if roc_col:
                today = daily_df[pd.to_datetime(daily_df["Date"]) == last_date]
                today = today.sort_values(roc_col, ascending=False).head(10)
                for _, r in today.iterrows():
                    item = {"symbol": str(r.get("symbol"))}
                    try:
                        item["roc"] = float(r.get(roc_col))
                    except Exception:
                        item["roc"] = r.get(roc_col)
                    if vol_col is not None:
                        item["volume"] = r.get(vol_col)
                    ranking.append(item)
            elif "symbol" in results_df.columns:
                ranking = [str(s) for s in results_df["symbol"].head(10)]
        except Exception:
            if "symbol" in results_df.columns:
                ranking = [str(s) for s in results_df["symbol"].head(10)]

        img_path, img_url = save_equity_curve(results_df, capital, SYSTEM_NAME)
        period = ""
        if "entry_date" in results_df.columns and "exit_date" in results_df.columns:
            start = pd.to_datetime(results_df["entry_date"]).min()
            end = pd.to_datetime(results_df["exit_date"]).max()
            period = f"{start:%Y-%m-%d}〜{end:%Y-%m-%d}"
        # トグルがONの場合のみ通知を送信
        notify_key = f"{SYSTEM_NAME}_notify_backtest"
        if st.session_state.get(notify_key, False):
            sent = False
            for n in notifiers:
                try:
                    mention = "channel" if n.platform == "slack" else None
                    if hasattr(n, "send_backtest_ex"):
                        n.send_backtest_ex(
                            "system1",
                            period,
                            stats,
                            ranking,
                            image_url=img_url,
                            mention=mention,
                        )
                    else:
                        n.send_backtest("system1", period, stats, ranking)
                    sent = True
                except Exception:
                    continue
            if sent:
                try:
                    mention = "channel" if os.getenv("SLACK_WEBHOOK_URL") else None
                    # use enhanced sender to include image and mention
                    if hasattr(notifier, "send_backtest_ex"):
                        notifier.send_backtest_ex(
                            "system1", period, stats, ranking, image_url=img_url, mention=mention
                        )
                    else:
                        notifier.send_backtest("system1", period, stats, ranking)
                    st.success(tr("通知を送信しました"))
                except Exception:
                    st.warning(tr("通知の送信に失敗しました"))
            else:
                st.warning(tr("通知の送信に失敗しました"))

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
