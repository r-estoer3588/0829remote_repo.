import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
# 日本語フォントを設定（WindowsならMS GothicやMeiryoが確実）
plt.rcParams['font.family'] = 'Meiryo'

import streamlit as st
import pandas as pd
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.utils import safe_filename, get_cached_data
from tickers_loader import get_all_tickers
from strategies.system7_strategy import System7Strategy
from common.performance_summary import summarize_results

# ===============================
# 戦略インスタンス
# ===============================
strategy = System7Strategy()

# ===============================
# タイトル & キャッシュクリア
# ===============================
if st.button("⚠️ Streamlitキャッシュ全クリア", key="system7_clear_cache"):
    st.cache_data.clear()
    st.success("Streamlit cache cleared.")

st.title("システム7：ショート・カタストロフィーヘッジ（SPY専用）")

# ===============================
# バックテスト処理本体
# ===============================
def main_process(use_auto, capital, symbols_input, single_mode=False):
    # ---- 1. ティッカー取得 ----
    if use_auto:
        symbols = ["SPY"]  # System7はSPY専用
    else:
        if not symbols_input:
            st.error("銘柄を入力してください")
            st.stop()
        symbols = [s.strip().upper() for s in symbols_input.split(",")]

    # ---- 2. データ取得 ----
    st.info(f"📄 データ取得開始 | {len(symbols)} 銘柄を処理中...")
    data_dict = {}
    start_time = time.time()
    buffer = []
    log_area = st.empty()
    progress_bar = st.progress(0)

    def load_symbol(symbol):
        path = os.path.join("data_cache", f"{safe_filename(symbol)}.csv")
        if not os.path.exists(path):
            return symbol, None
        return symbol, get_cached_data(symbol)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(load_symbol, sym): sym for sym in symbols}
        total = len(symbols)
        for i, future in enumerate(as_completed(futures), 1):
            sym, df = future.result()
            if df is not None and not df.empty:
                data_dict[sym] = df
                buffer.append(sym)

            if i % 20 == 0 or i == total:
                elapsed = time.time() - start_time
                remain = (elapsed / i) * (total - i)
                em, es = divmod(int(elapsed), 60)
                rm, rs = divmod(int(remain), 60)
                joined = ", ".join(buffer)
                log_area.text(
                    f"📄 データ取得: {i}/{total} 件 完了"
                    f" | 経過: {em}分{es}秒 / 残り: 約 {rm}分{rs}秒\n"
                    f"銘柄: {joined}"
                )
                buffer.clear()
                progress_bar.progress(i / total)
    progress_bar.empty()

    if not data_dict:
        st.error("有効なデータがありません。")
        st.stop()

    # ---- 3. インジケーター計算 ----
    st.info("📊 インジケーター計算中...")
    ind_progress = st.progress(0)
    ind_log = st.empty()
    ind_skip = st.empty()

    prepared_dict = strategy.prepare_data(
        data_dict,
        progress_callback=lambda done, total: ind_progress.progress(done / total),
        log_callback=lambda msg: ind_log.text(msg),
        skip_callback=lambda msg: ind_skip.warning(msg)
    )
    ind_progress.empty()

    # ---- デバッグ確認 ----
    # for sym, df in prepared_dict.items():
    #     st.write("デバッグ: 2020年2月")
    #     st.dataframe(df.loc["2020-02-01":"2020-03-31", ["Close", "min_50", "setup"]])
    #     st.write("デバッグ: 2022年")
    #     st.dataframe(df.loc["2022-01-01":"2022-12-31", ["Close", "min_50", "setup"]])
    
    # ---- 4. 候補生成 ----
    st.info("📊 セットアップ抽出中...")
    cand_progress = st.progress(0)
    cand_log = st.empty()
    cand_skip = st.empty()

    candidates_by_date = strategy.generate_candidates(
        prepared_dict,
        progress_callback=lambda done, total: cand_progress.progress(done / total),
        log_callback=lambda msg: cand_log.text(msg),
        skip_callback=lambda msg: cand_skip.warning(msg)
    )
    cand_progress.empty()

    if not candidates_by_date:
        st.warning("セットアップ条件を満たす銘柄がありません。")
        st.stop()

    # ---- 5. バックテスト ----
    st.info("💹 バックテスト実行中...")
    bt_progress = st.progress(0)
    bt_log = st.empty()

    def progress_callback(i, total, start_time):
        bt_progress.progress(i / total)

    def log_callback(i, total, start_time):
        elapsed = time.time() - start_time
        remain = elapsed / i * (total - i)
        bt_log.text(
            f"💹 バックテスト: {i}/{total} 日完了"
            f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
            f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒"
        )

    results_df = strategy.run_backtest(
        prepared_dict,
        candidates_by_date,
        capital,
        on_progress=progress_callback,
        on_log=log_callback,
        single_mode=single_mode
    )
    bt_progress.empty()

    # ---- 6. 結果表示 ----
    if results_df.empty:
        st.info("トレードは発生しませんでした。")
        return

    st.subheader("バックテスト結果")
    st.dataframe(results_df)

    summary, results_df = summarize_results(results_df, capital)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("トレード回数", summary["trades"])
    col2.metric("最終損益 (USD)", f"{summary['total_return']:.2f}")
    col3.metric("勝率 (%)", f"{summary['win_rate']:.2f}")
    col4.metric("最大ドローダウン (USD)", f"{summary['max_dd']:.2f}")

    # ---- 累積損益グラフ ----
    st.subheader("📈 累積損益")
    plt.figure(figsize=(10, 4))
    plt.plot(results_df["exit_date"], results_df["cumulative_pnl"], label="Cumulative PnL")
    plt.xlabel("日付")
    plt.ylabel("PnL (USD)")
    plt.title("累積損益")
    plt.legend()
    st.pyplot(plt)

    # ---- 年次・月次・週次サマリー ----
    yearly = results_df.groupby(results_df["exit_date"].dt.to_period("Y"))["pnl"].sum().reset_index()
    yearly["exit_date"] = yearly["exit_date"].astype(str)
    st.subheader("📅 年次サマリー")
    st.dataframe(yearly)

    monthly = results_df.groupby(results_df["exit_date"].dt.to_period("M"))["pnl"].sum().reset_index()
    monthly["exit_date"] = monthly["exit_date"].astype(str)
    st.subheader("📅 月次サマリー")
    st.dataframe(monthly)

    weekly = results_df.groupby(results_df["exit_date"].dt.to_period("W"))["pnl"].sum().reset_index()
    weekly["exit_date"] = weekly["exit_date"].astype(str)
    st.subheader("📆 週次サマリー")
    st.dataframe(weekly)

    # ---- 売買ログ保存 ----
    today_str = pd.Timestamp.today().date().isoformat()
    save_dir = "results_csv"
    os.makedirs(save_dir, exist_ok=True)
    save_file = os.path.join(save_dir, f"system7_{today_str}_{int(capital)}.csv")
    results_df.to_csv(save_file, index=False)
    st.write(f"📂 売買ログを自動保存: {save_file}")

    # ---- データキャッシュ保存 ----
    st.info("💾 System7 加工済日足データキャッシュ保存中...")
    cache_dir = os.path.join("data_cache", "system7")
    os.makedirs(cache_dir, exist_ok=True)
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(prepared_dict)

    for i, (sym, df) in enumerate(prepared_dict.items(), 1):
        path = os.path.join(cache_dir, f"{safe_filename(sym)}.csv")
        df.to_csv(path)
        progress_bar.progress(i / total)
        status_text.text(f"💾 System7キャッシュ保存中: {i}/{total} 件 完了")

    status_text.text(f"💾 System7キャッシュ保存完了 ({total} 件)")
    progress_bar.empty()
    st.success(f"🔚 バックテスト終了 | {len(prepared_dict)} 銘柄キャッシュ保存済")

# ===============================
# 単独モード
# ===============================
use_auto = st.checkbox("自動ティッカー取得（SPY専用）", value=True, key="system7_auto_main")
capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="system7_capital_main")
single_mode = st.checkbox("単独運用モード（資金100%使用）", value=False, key="system7_single_mode_main")

if st.button("バックテスト実行", key="system7_run_main"):
    main_process(use_auto, capital, None, single_mode=single_mode)

# ===============================
# 統合タブモード
# ===============================
def run_tab():
    st.header("System7：ショート・カタストロフィーヘッジ（SPY専用）")
    use_auto = st.checkbox("自動ティッカー取得（SPY専用）", value=True, key="system7_auto_tab")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="system7_capital_tab")
    single_mode = st.checkbox("単独運用モード（資金100%使用）", value=False, key="system7_single_mode_tab")

    if st.button("バックテスト実行", key="system7_run_tab"):
        main_process(use_auto, capital, None, single_mode=single_mode)
