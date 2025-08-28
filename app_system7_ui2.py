import streamlit as st
import common.ui_patch  # noqa: F401
from strategies.system7_strategy import System7Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
)
from common.cache_utils import save_prepared_data_cache
from common.ui_manager import UIManager


strategy = System7Strategy()


def run_tab(single_mode=None, ui_manager=None):
    st.header("System7｜ショート・カタストロフィーヘッジ（SPY専用）")
    single_mode = st.checkbox("単独運用モード（資金100%を使用）", value=False)

    ui = UIManager()
    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy,
        system_name="System7",
        limit_symbols=1,
        ui_manager=ui,
        single_mode=single_mode,
    )

    if st.checkbox("チェック: インジケーターの確認", value=False):
        if data_dict:
            for sym, df in data_dict.items():
                st.write("例: 2020年2〜3月")
                st.dataframe(df.loc["2020-02-01":"2020-03-31"])  # 確認用
        else:
            st.info("データ未取得のため表示できません。バックテストを一度実行してください。")

    if results_df is not None and candidates_by_date is not None:
        summary_df = show_signal_trade_summary(data_dict, results_df, "System7")
        save_signal_and_trade_logs(summary_df, results_df, "System7", capital)
        save_prepared_data_cache(data_dict, "System7")


if __name__ == "__main__":
    import sys
    if "streamlit" not in sys.argv[0]:
        run_tab()
