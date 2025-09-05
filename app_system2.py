import streamlit as st  
import common.ui_patch  # noqa: F401
import pandas as pd
from strategies.system2_strategy import System2Strategy
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
from common.notifier import get_notifiers_from_env
from common.equity_curve import save_equity_curve
import os

# 翻訳辞書ロードと言語選択
load_translations_from_dir(Path(__file__).parent / "translations")
if not st.session_state.get("_integrated_ui", False):
    language_selector()


# 戦略インスタンス
strategy = System2Strategy()
notifiers = get_notifiers_from_env()


def display_adx7_ranking(
    candidates_by_date,
    years: int = 5,
    top_n: int = 100,
    title: str = "📊 System2 日別 ADX7 ランキング（直近{years}年 / 上位{top_n}銘柄）",
):
    """System2 固有のADX7日別ランキングを表示する。"""
    if not candidates_by_date:
        st.warning("ADX7ランキングが空です")
        return

    rows = []
    for date, cands in candidates_by_date.items():
        for c in cands:
            rows.append({"Date": date, "symbol": c.get("symbol"), "ADX7": c.get("ADX7")})
    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])  # type: ignore[arg-type]

    start_date = pd.Timestamp.now() - pd.DateOffset(years=years)
    df = df[df["Date"] >= start_date]

    df["ADX7_Rank"] = df.groupby("Date")["ADX7"].rank(ascending=False, method="first")
    df = df.sort_values(["Date", "ADX7_Rank"], ascending=[True, True])
    df = df.groupby("Date").head(top_n)

    with st.expander(title.format(years=years, top_n=top_n), expanded=False):
        st.dataframe(
            df.reset_index(drop=True)[["Date", "ADX7_Rank", "symbol", "ADX7"]],
            hide_index=False,
        )


def run_tab(ui_manager=None):
    st.header("System2 バックテスト（ショートRSIスパイク + ADX傾きランキング）")
    ui = ui_manager or UIManager()
    # System1準拠: 通知トグル（Webhook）
    notify_key = "System2_notify_backtest"
    if notify_key not in st.session_state:
        st.session_state[notify_key] = True
    try:
        st.toggle(tr("バックテスト結果を通知する（Webhook）"), key=notify_key)
    except Exception:
        st.checkbox(tr("バックテスト結果を通知する（Webhook）"), key=notify_key)
    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy, system_name="System2", limit_symbols=100, ui_manager=ui
    )
    # 実行直後の表示・保存
    if results_df is not None and candidates_by_date is not None:
        display_adx7_ranking(candidates_by_date)
        summary_df = show_signal_trade_summary(data_dict, results_df, "System2")
        with st.expander(tr("取引ログ・保存ファイル"), expanded=False):
            save_signal_and_trade_logs(summary_df, results_df, "System2", capital)
        save_prepared_data_cache(data_dict, "System2")
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
        # equity image and mention for Slack
        _img_path, _img_url = save_equity_curve(results_df, capital, "System2")
        if st.session_state.get(notify_key, False):
            sent = False
            for n in notifiers:
                try:
                    _mention = "channel" if getattr(n, "platform", None) == "slack" else None
                    if hasattr(n, "send_backtest_ex"):
                        n.send_backtest_ex("system2", period, stats, ranking, image_url=_img_url, mention=_mention)
                    else:
                        n.send_backtest("system2", period, stats, ranking)
                    sent = True
                except Exception:
                    continue
            if sent:
                st.success(tr("通知を送信しました"))
            else:
                st.warning(tr("通知の送信に失敗しました"))
    # リラン時のフォールバック表示（セッションから復元）
    elif results_df is None and candidates_by_date is None:
        prev_res = st.session_state.get("System2_results_df")
        prev_cands = st.session_state.get("System2_candidates_by_date")
        prev_data = st.session_state.get("System2_prepared_dict")
        prev_cap = st.session_state.get("System2_capital_saved")
        if prev_res is not None and prev_cands is not None:
            display_adx7_ranking(prev_cands)
            _ = show_signal_trade_summary(prev_data, prev_res, "System2")
            try:
                from common.ui_components import show_results
                show_results(prev_res, prev_cap or 0.0, "System2", key_context="prev")
            except Exception:
                pass


if __name__ == "__main__":
    import sys
    if "streamlit" not in sys.argv[0]:
        run_tab()
