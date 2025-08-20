# app_system5.py
from common.performance_summary import summarize_results
from holding_tracker import generate_holding_matrix, display_holding_heatmap, download_holding_csv
from strategies.system5_strategy import System5Strategy
from tickers_loader import get_all_tickers
from common.utils import safe_filename, get_cached_data
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
# 日本語フォントを設定（WindowsならMS GothicやMeiryoが確実）
plt.rcParams['font.family'] = 'Meiryo'


# ===============================
# 戦略インスタンス
# ===============================
strategy = System5Strategy()

# ===============================
# タイトル & キャッシュクリア
# ===============================
if st.button("⚠️ Streamlitキャッシュ全クリア", key="system5_clear_cache"):
    st.cache_data.clear()
    st.success("Streamlit cache cleared.")

st.title("システム5：ロング・ミーン・リバージョン・ハイADX・リバーサル")

# ===============================
# バックテスト処理本体
# ===============================


def main_process(use_auto, capital, symbols_input):
    # 1. ティッカー取得
    if use_auto:
        symbols = get_all_tickers()[:100]  # 上限100銘柄
        # symbols = get_all_tickers()
    else:
        if not symbols_input:
            st.error("銘柄を入力してください")
            st.stop()
        symbols = [s.strip().upper() for s in symbols_input.split(",")]

    # 2. データ取得
    start_time = time.time()
    data_dict = {}
    total = len(symbols)
    batch_size = 50
    symbol_buffer = []

    data_area = st.empty()
    data_area.info(f"📄 データ取得開始 | {total} 銘柄を処理中...")
    progress_bar = st.progress(0)
    log_area = st.empty()

    def load_symbol(symbol):
        path = os.path.join("data_cache", f"{safe_filename(symbol)}.csv")
        if not os.path.exists(path):
            return symbol, None
        return symbol, get_cached_data(symbol)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(load_symbol, sym): sym for sym in symbols}
        for i, future in enumerate(as_completed(futures), 1):
            sym, df = future.result()
            if df is not None and not df.empty:
                data_dict[sym] = df
                symbol_buffer.append(sym)

            if i % batch_size == 0 or i == total:
                elapsed = time.time() - start_time
                remaining = (elapsed / i) * (total - i)
                elapsed_min, elapsed_sec = divmod(int(elapsed), 60)
                remain_min, remain_sec = divmod(int(remaining), 60)
                joined_symbols = ", ".join(symbol_buffer)
                log_area.text(
                    f"📄 データ取得: {i}/{total} 件 完了"
                    f" | 経過: {elapsed_min}分{elapsed_sec}秒 / 残り: 約 {remain_min}分{remain_sec}秒\n"
                    f"銘柄: {joined_symbols}"
                )
                progress_bar.progress(i / total)
                symbol_buffer.clear()
    progress_bar.empty()

    if not data_dict:
        st.error("有効な銘柄データがありません")
        st.stop()

    # 3. インジケーター計算
    st.info("📊 インジケーター計算中...")
    ind_progress = st.progress(0)
    ind_log = st.empty()
    ind_skip_log = st.empty()

    prepared_dict = strategy.prepare_data(
        data_dict, progress_callback=lambda done, total: ind_progress.progress(
            done / total), log_callback=lambda msg: ind_log.text(msg))
    ind_progress.empty()

    # 4. 候補生成
    st.info("📊 セットアップ通過銘柄を抽出中...")

    cand_progress = st.progress(0)
    cand_log = st.empty()

    candidates_by_date = strategy.generate_candidates(
        prepared_dict, progress_callback=lambda done, total: cand_progress.progress(
            done / total), log_callback=lambda msg: cand_log.text(msg), )
    cand_progress.empty()

    if not candidates_by_date:
        st.warning("セットアップ条件を満たす銘柄がありませんでした。")
        st.stop()

    st.write(f"📊 セットアップ抽出完了 | {len(prepared_dict)} 銘柄を処理しました")

    # 5. バックテスト
    st.info("💹 バックテスト実行中...")
    bt_progress = st.progress(0)
    bt_log = st.empty()

    def progress_callback(i, total, start_time):
        bt_progress.progress(i / total)

    def log_callback(i, total, start_time):
        elapsed = time.time() - start_time
        remain = (elapsed / i) * (total - i)
        bt_log.text(
            f"💹 バックテスト: {i}/{total} 日処理完了"
            f" | 経過: {int(elapsed // 60)}分{int(elapsed % 60)}秒"
            f" / 残り: 約 {int(remain // 60)}分{int(remain % 60)}秒"
        )

    results_df = strategy.run_backtest(
        prepared_dict,
        candidates_by_date,
        capital,
        on_progress=progress_callback,
        on_log=log_callback
    )
    bt_progress.empty()

    # 6. 結果表示
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

    st.subheader("📈 累積損益グラフ")
    plt.figure(figsize=(10, 4))
    plt.plot(
        results_df["exit_date"],
        results_df["cumulative_pnl"],
        label="Cumulative PnL")
    plt.xlabel("日付")
    plt.ylabel("PnL (USD)")
    plt.title("累積損益")
    plt.legend()
    st.pyplot(plt)

    # 年次・月次・週次サマリー
    yearly = results_df.groupby(results_df["exit_date"].dt.to_period("Y"))[
        "pnl"].sum().reset_index()
    yearly["exit_date"] = yearly["exit_date"].astype(str)
    st.subheader("📅 年次サマリー")
    st.dataframe(yearly)

    monthly = results_df.groupby(results_df["exit_date"].dt.to_period("M"))[
        "pnl"].sum().reset_index()
    monthly["exit_date"] = monthly["exit_date"].astype(str)
    st.subheader("📅 月次サマリー")
    st.dataframe(monthly)

    weekly = results_df.groupby(results_df["exit_date"].dt.to_period("W"))[
        "pnl"].sum().reset_index()
    weekly["exit_date"] = weekly["exit_date"].astype(str)
    st.subheader("📆 週次サマリー")
    st.dataframe(weekly)

    # ===============================
    # 日別保有銘柄ヒートマップ
    # ===============================
    st.subheader("日別保有銘柄ヒートマップ")

    st.info("📊 日別保有銘柄ヒートマップ生成中...")
    progress_heatmap = st.progress(0)
    heatmap_log = st.empty()

    start_time = time.time()
    time.sleep(0.1)  # UI反映のため少し待機

    unique_dates = sorted(results_df["entry_date"].dt.normalize().unique())
    total_dates = len(unique_dates)

    for i, date in enumerate(unique_dates, 1):
        progress_heatmap.progress(i / total_dates)
        elapsed = time.time() - start_time
        remain = elapsed / i * (total_dates - i)

        # 🔽 10件ごとにログ更新
        if i % 10 == 0 or i == total_dates:
            heatmap_log.text(
                f"📊 日別保有銘柄ヒートマップ: {i}/{total_dates} 日処理完了"
                f" | 経過: {int(elapsed // 60)}分{int(elapsed % 60)}秒"
                f" / 残り: 約 {int(remain // 60)}分{int(remain % 60)}秒"
            )
        time.sleep(0.01)

    heatmap_log.text("✅ 日別保有銘柄データ処理完了。図を生成中...")
    time.sleep(1.0)
    heatmap_log.text("📊 ヒートマップ描画中...")

    holding_matrix = generate_holding_matrix(results_df)
    display_holding_heatmap(holding_matrix, title="System5：日別保有銘柄ヒートマップ")
    download_holding_csv(holding_matrix, filename="holding_status_system5.csv")
    heatmap_log.text("✅ ヒートマップ生成完了")
    progress_heatmap.empty()

    # 売買ログ保存
    today_str = pd.Timestamp.today().date().isoformat()
    save_dir = "results_csv"
    os.makedirs(save_dir, exist_ok=True)
    save_file = os.path.join(
        save_dir, f"system5_{today_str}_{
            int(capital)}.csv")
    results_df.to_csv(save_file, index=False)
    st.write(f"📂 売買ログを自動保存: {save_file}")

    # データキャッシュ保存（System5専用フォルダ）
    st.info("💾 System5 加工済日足データキャッシュ保存開始...")
    cache_dir = os.path.join("data_cache", "systemX")
    os.makedirs(cache_dir, exist_ok=True)
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(prepared_dict)
    for i, (sym, df) in enumerate(prepared_dict.items(), 1):
        path = os.path.join(cache_dir, f"{safe_filename(sym)}.csv")
        df.to_csv(path)
        progress_bar.progress(i / total)
        status_text.text(f"💾 System5キャッシュ保存中: {i}/{total} 件 完了")
    status_text.text(f"💾 System5キャッシュ保存完了 ({total} 件)")
    progress_bar.empty()
    st.success("🔚 バックテスト終了")


# ===============================
# 通常モード
# ===============================
use_auto = st.checkbox("自動ティッカー取得（全銘柄）", value=True, key="system5_auto_main")
capital = st.number_input(
    "総資金（USD）",
    min_value=1000,
    value=1000,
    step=100,
    key="system5_capital_main")
symbols_input = None
if not use_auto:
    symbols_input = st.text_input(
        "ティッカーをカンマ区切りで入力",
        "AAPL,MSFT,TSLA,NVDA,META",
        key="system5_symbols_main")

if st.button("バックテスト実行", key="system5_run_main"):
    main_process(use_auto, capital, symbols_input)

# ===============================
# 統合モード用タブ呼び出し
# ===============================


def run_tab():
    st.header("System5：ロング・ミーン・リバージョン・ハイADX・リバーサル")
    use_auto = st.checkbox(
        "自動ティッカー取得（全銘柄）",
        value=True,
        key="system5_auto_tab")
    capital = st.number_input(
        "総資金（USD）",
        min_value=1000,
        value=1000,
        step=100,
        key="system5_capital_tab")
    symbols_input = None
    if not use_auto:
        symbols_input = st.text_input(
            "ティッカーをカンマ区切りで入力",
            "AAPL,MSFT,TSLA,NVDA,META",
            key="system5_symbols_tab")

    if st.button("バックテスト実行", key="system5_run_tab"):
        main_process(use_auto, capital, symbols_input)
