import streamlit as st
import common.ui_patch  # noqa: F401  # 共通ログ/サマリーへ委譲
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

# 外部翻訳を読み込む（任意・起動時に一度）
load_translations_from_dir(Path(__file__).parent / "translations")
# サイドバーに言語選択を表示
language_selector(in_sidebar=True)

# ✅ SPY関連は共通ユーティリティから
from common.utils_spy import get_spy_with_indicators

SYSTEM_NAME = "System1"
DISPLAY_NAME = "システム1"

# インスタンス生成
strategy = System1Strategy()


def run_tab(spy_df=None, ui_manager=None):
    # 例: 既存のヘッダを i18n で包む
    st.header(
        tr(
            f"{DISPLAY_NAME}：ロング・トレンド・ハイ・モメンタム（複数銘柄＋ランキング）"
        )
    )

    # SPY はフィルター判定で SMA100 を使用するため、必ずインジ付きで取得
    spy_df = spy_df if spy_df is not None else get_spy_with_indicators()
    if spy_df is None or spy_df.empty:
        st.error("SPYデータの取得に失敗しました。キャッシュを更新してください。")
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
        # キャッシュ保存後にも完了メッセージを再掲
        st.success("バックテスト完了")

    # フォールバック: リラン時にセッションから復元してランキング/サマリを表示
    elif results_df is None and merged_df is None:
        prev_res = st.session_state.get(f"{SYSTEM_NAME}_results_df")
        prev_merged = st.session_state.get(f"{SYSTEM_NAME}_merged_df")
        prev_cap = st.session_state.get(f"{SYSTEM_NAME}_capital")
        if prev_res is not None and prev_merged is not None:
            daily_df = clean_date_column(prev_merged, col_name="Date")
            display_roc200_ranking(
                daily_df, title=f"📊 {DISPLAY_NAME} 日別ROC200ランキング（保存済み）"
            )
            _ = show_signal_trade_summary(
                prev_merged, prev_res, SYSTEM_NAME, display_name=DISPLAY_NAME
            )

        # ✅ 同時保有銘柄数の最大値をチェック 0823デバッグ用
        # if not results_df.empty:
        #     results_df["entry_date"] = pd.to_datetime(results_df["entry_date"])
        #     results_df["exit_date"] = pd.to_datetime(results_df["exit_date"])

        #     # 各営業日に保有している銘柄数をカウント
        #     unique_dates = sorted(results_df["entry_date"].dt.normalize().unique())
        #     holding_counts = []
        #     for d in unique_dates:
        #         active = results_df[
        #             (results_df["entry_date"] <= d) & (results_df["exit_date"] >= d)
        #         ]
        #         holding_counts.append(len(active["symbol"].unique()))

        #     max_holdings = max(holding_counts) if holding_counts else 0
        #     st.info(f"📌 最大同時保有銘柄数: {max_holdings}")


# 単体実行用
if __name__ == "__main__":
    import sys

    if "streamlit" not in sys.argv[0]:
        run_tab()
