from __future__ import annotations

import streamlit as st

# 共通ログ/サマリーへ委譲（副作用で既存UI関数を置換）
import common.ui_patch  # noqa: F401

from config.settings import get_settings
from common.logging_utils import setup_logging
from common.performance_summary import summarize as summarize_perf
from common.ui_components import (
    prepare_backtest_data,
    run_backtest_with_logging,
    show_results,
)
from common.utils_spy import get_spy_data_cached
from tickers_loader import get_all_tickers


def _load_ui_modules():
    """各システムのUIモジュールを遅延読み込み。存在しない場合は None。"""
    mods = {}
    for i in range(1, 8):
        name = f"app_system{i}_ui2"
        try:
            mods[name] = __import__(name)
        except Exception:
            mods[name] = None
    return mods


def main():
    st.set_page_config(page_title="Trading Systems 1–7 (Integrated)", layout="wide")

    # 設定・ロギング初期化
    settings = get_settings(create_dirs=True)
    logger = setup_logging(settings)
    logger.info("app_integrated 起動")

    st.title("📈 Trading Systems 1–7 統合UI")
    with st.expander("⚙ 設定サマリー", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write("- RESULTS_DIR:", str(settings.RESULTS_DIR))
            st.write("- LOGS_DIR:", str(settings.LOGS_DIR))
        with col2:
            st.write("- DATA_CACHE_DIR:", str(settings.DATA_CACHE_DIR))
            st.write("- THREADS:", settings.THREADS_DEFAULT)
        with col3:
            st.write("- 初期資金:", settings.ui.default_capital)
            st.write("- ログレベル:", settings.logging.level)

    mods = _load_ui_modules()

    tabs = st.tabs(["一括実行"] + [f"System{i}" for i in range(1, 8)])

    # --- 一括実行タブ ---
    with tabs[0]:
        st.subheader("🚀 一括バックテスト / 集計")
        capital = st.number_input("初期資金 (USD)", min_value=1000, value=int(settings.ui.default_capital), step=1000)
        limit_symbols = st.number_input("取得銘柄上限", min_value=50, max_value=5000, value=min(500, get_all_tickers().__len__()), step=50)
        run_btn = st.button("▶ 一括実行")

        if run_btn:
            try:
                all_tickers = get_all_tickers()
                symbols = all_tickers[: int(limit_symbols)]
                spy_df = get_spy_data_cached()

                overall = []
                sys_progress = st.progress(0)
                sys_log = st.empty()
                total_sys = 7
                done_sys = 0

                for i in range(1, 8):
                    sys_name = f"System{i}"
                    sys_log.text(f"⏱ {sys_name}: 準備中...")
                    try:
                        mod = __import__(f"strategies.system{i}_strategy", fromlist=[f"System{i}Strategy"])  # type: ignore
                        cls = getattr(mod, f"System{i}Strategy")
                        strat = cls()

                        # データ準備
                        prepared, cands, merged = prepare_backtest_data(
                            strat,
                            symbols if sys_name != "System7" else ["SPY"],
                            system_name=sys_name,
                            spy_df=spy_df,
                        )
                        if cands is None:
                            sys_log.text(f"⚠ {sys_name}: 候補なし。スキップ")
                            done_sys += 1
                            sys_progress.progress(done_sys / total_sys)
                            continue

                        # バックテスト
                        sys_log.text(f"▶ {sys_name}: 実行中...")
                        res = run_backtest_with_logging(strat, prepared, cands, capital, sys_name)
                        if res is not None and not res.empty:
                            res["system"] = sys_name
                            overall.append(res)
                            # 個別結果を簡易表示（任意で折畳）
                            with st.expander(f"{sys_name} 結果", expanded=False):
                                show_results(res, capital, sys_name)
                        else:
                            st.info(f"{sys_name}: トレードなし")
                    except Exception as e:  # noqa: BLE001
                        logger.exception("%s 実行中に例外", sys_name)
                        st.exception(e)
                    finally:
                        done_sys += 1
                        sys_progress.progress(done_sys / total_sys)

                # 集計ビュー
                st.markdown("---")
                st.subheader("📊 全システム集計")
                if overall:
                    import pandas as pd

                    all_df = pd.concat(overall, ignore_index=True)
                    summary, all_df2 = summarize_perf(all_df, capital)
                    cols = st.columns(6)
                    d = summary.to_dict()
                    cols[0].metric("トレード回数", d["trades"])
                    cols[1].metric("合計損益", f"{d['total_return']:.2f}")
                    cols[2].metric("勝率(%)", f"{d['win_rate']:.2f}")
                    cols[3].metric("PF", f"{d['profit_factor']:.2f}")
                    cols[4].metric("Sharpe", f"{d['sharpe']:.2f}")
                    cols[5].metric("MDD", f"{d['max_drawdown']:.2f}")

                    st.dataframe(all_df2)
                else:
                    st.info("集計対象の結果がありません。")
            finally:
                pass

    # --- 個別タブ ---
    for idx, tab in enumerate(tabs[1:], start=1):
        with tab:
            mod = mods.get(f"app_system{idx}_ui2")
            if mod is None or not hasattr(mod, "run_tab"):
                st.warning(f"System{idx} UI が見つかりません。app_system{idx}_ui2.py を確認してください。")
                continue
            try:
                mod.run_tab()
            except Exception as e:  # noqa: BLE001
                logger.exception("System%d タブ実行中に例外", idx)
                st.exception(e)


if __name__ == "__main__":
    main()
