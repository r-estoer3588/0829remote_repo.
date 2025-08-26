import streamlit as st
from strategies.system7_strategy import System7Strategy
from common.ui_components import (
    run_backtest_app,
    show_signal_trade_summary,
    save_signal_and_trade_logs,
)
from common.cache_utils import save_prepared_data_cache

# ===== 戦略インスタンス =====
strategy = System7Strategy()


# ===== Streamlitタブ呼び出し =====
def run_tab():
    st.header("System7：ショート・カタストロフィーヘッジ（SPY専用）")

    single_mode = st.checkbox("単独運用モード（資金100%使用）", value=False)

    # 🔽 SPY専用に制御（symbolsは渡さない）
    results_df, _, data_dict, capital, candidates_by_date = run_backtest_app(
        strategy,
        system_name="System7",
        limit_symbols=1,
        single_mode=single_mode,
    )

    # ---- デバッグ確認 ----
    if st.checkbox("デバッグ: インジケーター確認", value=False):
        if data_dict is not None:
            for sym, df in data_dict.items():
                st.write("デバッグ: 2020年2月")
                st.dataframe(
                    df.loc["2020-02-01":"2020-03-31", ["Close", "min_50", "setup"]]
                )
                st.write("デバッグ: 2022年")
                st.dataframe(
                    df.loc["2022-01-01":"2022-12-31", ["Close", "min_50", "setup"]]
                )
        else:
            st.info(
                "データ未取得のためデバッグ表示はできません。バックテストを一度実行してください。"
            )

    if results_df is not None and candidates_by_date is not None:
        signal_summary_df = show_signal_trade_summary(data_dict, results_df, "System7")
        save_signal_and_trade_logs(signal_summary_df, results_df, "System7", capital)
        save_prepared_data_cache(data_dict, "System7")


# 単体実行用
if __name__ == "__main__":
    import sys

    if "streamlit" not in sys.argv[0]:
        run_tab()
