# app_system2.py
import streamlit as st
import pandas as pd
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.utils import safe_filename, get_cached_data
from tickers_loader import get_all_tickers
from strategies.system2_strategy import System2Strategy
import matplotlib.pyplot as plt
import numpy as np
from holding_tracker import generate_holding_matrix, display_holding_heatmap, download_holding_csv

# ===============================
# 戦略インスタンス
# ===============================
strategy = System2Strategy()

# ===============================
# タイトル & キャッシュクリア
# ===============================
if st.button("⚠️ Streamlitキャッシュ全クリア"):
    st.cache_data.clear()
    st.success("Streamlit cache cleared.")

st.title("システム2：ショート RSIスラスト（複数銘柄）")


# ===============================
# バックテスト処理本体
# ===============================
def main_process(use_auto, capital, symbols_input):
    # 1. ティッカー取得
    if use_auto:
        #symbols = get_all_tickers()[:100]
        symbols = get_all_tickers()
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


    progress_bar.empty()
    if not data_dict:
        st.error("有効な銘柄データがありません")
        st.stop()

    # 3. インジケーター計算
    st.info("📊 インジケーター計算中...")
    ind_progress = st.progress(0)
    ind_log = st.empty()
    prepared_dict = strategy.prepare_data(
        data_dict,
        progress_callback=lambda done, total: ind_progress.progress(done / total),
        log_callback=lambda msg: ind_log.text(msg)
    )
    ind_progress.empty()

    # 4. 候補生成
    st.info("📊 セットアップ通過銘柄を抽出中...")
    candidates_by_date = strategy.generate_candidates(prepared_dict)
    if not candidates_by_date:
        st.warning("セットアップ条件を満たす銘柄がありませんでした。")
        st.stop()

    # 5. バックテスト
    st.info("💹 バックテスト実行中...")
    bt_progress = st.progress(0)
    bt_log = st.empty()
    results_df = strategy.run_backtest(
        prepared_dict,
        candidates_by_date,
        capital,
        progress_bar=bt_progress,
        log_area=bt_log
    )
    bt_progress.empty()

    # 6. 結果表示
    if results_df.empty:
        st.info("トレードは発生しませんでした。")
        return

    st.subheader("バックテスト結果")
    st.dataframe(results_df)

    total_return = results_df["pnl"].sum()
    win_rate = (results_df["return_%"] > 0).mean() * 100
    st.metric("トレード回数", len(results_df))
    st.metric("最終損益（USD）", f"{total_return:.2f}")
    st.metric("勝率（％）", f"{win_rate:.2f}")

    # Signal_Count + Trade_Count 表
    signal_counts = {sym: df["setup"].sum() for sym, df in prepared_dict.items() if "setup" in df.columns}
    signal_df = pd.DataFrame(signal_counts.items(), columns=["Symbol", "Signal_Count"])
    trade_counts = results_df.groupby("symbol").size().reset_index(name="Trade_Count")
    trade_counts.rename(columns={"symbol": "Symbol"}, inplace=True)
    summary_df = pd.merge(signal_df, trade_counts, on="Symbol", how="outer").fillna(0)
    summary_df["Signal_Count"] = summary_df["Signal_Count"].astype(int)
    summary_df["Trade_Count"] = summary_df["Trade_Count"].astype(int)

    with st.expander("📊 銘柄別シグナル発生件数とトレード件数（全期間）", expanded=False):
        st.dataframe(summary_df.sort_values("Signal_Count", ascending=False))

    # 損益曲線 & ドローダウン
    results_df["exit_date"] = pd.to_datetime(results_df["exit_date"])
    results_df = results_df.sort_values("exit_date")
    results_df["cumulative_pnl"] = results_df["pnl"].cumsum()
    results_df["cum_max"] = results_df["cumulative_pnl"].cummax()
    results_df["drawdown"] = results_df["cumulative_pnl"] - results_df["cum_max"]
    max_dd = results_df["drawdown"].min()
    st.metric("最大ドローダウン（USD）", f"{max_dd:.2f}")

    st.subheader("累積損益グラフ")
    plt.figure(figsize=(10, 4))
    plt.plot(results_df["exit_date"], results_df["cumulative_pnl"], label="Cumulative PnL")
    plt.xlabel("日付")
    plt.ylabel("PnL (USD)")
    plt.title("累積損益")
    plt.legend()
    st.pyplot(plt)

    # R 倍率計算（3ATR10基準）
    atr_lookup = []
    for sym, df in prepared_dict.items():
        atr_df = df[["ATR10"]].copy()
        atr_df["symbol"] = sym
        atr_df["entry_date"] = atr_df.index
        atr_lookup.append(atr_df)
    atr_lookup = pd.concat(atr_lookup)
    results_df = results_df.merge(atr_lookup, on=["symbol", "entry_date"], how="left")

    results_df["risk_per_share"] = 3 * results_df["ATR10"]
    results_df["r_multiple"] = results_df["pnl"] / (results_df["shares"] * results_df["risk_per_share"])
    r_values = results_df["r_multiple"].replace([np.inf, -np.inf], pd.NA).dropna()
    r_values = r_values[(r_values > -5) & (r_values < 20)]

    st.subheader("📊 R倍率ヒストグラム（-5R～+20R）")
    plt.figure(figsize=(8, 4))
    plt.hist(r_values, bins=20, edgecolor="black", range=(-5, 20))
    plt.xlabel("R倍率")
    plt.ylabel("件数")
    plt.title("R倍率の分布")
    st.pyplot(plt)

    # 年次・月次・週次サマリー
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

    # ヒートマップ生成
    st.info("📊 日別保有銘柄ヒートマップ生成中...")
    holding_matrix = generate_holding_matrix(results_df)
    display_holding_heatmap(holding_matrix, title="System2：日別保有銘柄ヒートマップ")
    download_holding_csv(holding_matrix, filename="holding_status_system2.csv")

    # 売買ログ保存
    today_str = pd.Timestamp.today().date().isoformat()
    save_dir = "results_csv"
    os.makedirs(save_dir, exist_ok=True)
    save_file = os.path.join(save_dir, f"system2_{today_str}_{int(capital)}.csv")
    results_df.to_csv(save_file, index=False)
    st.write(f"📂 売買ログを自動保存: {save_file}")

    # signal件数保存
    if not summary_df.empty:
        signal_dir = os.path.join(save_dir, "signals")
        os.makedirs(signal_dir, exist_ok=True)
        signal_path = os.path.join(signal_dir, f"system2_signals_{today_str}_{int(capital)}.csv")
        summary_df.to_csv(signal_path, index=False)
        st.write(f"✅ signal件数も保存済み: {signal_path}")

    # データキャッシュ保存（System2専用フォルダ）
    st.info("💾 System2 加工済日足データキャッシュ保存開始...")
    cache_dir = os.path.join("data_cache", "system2")
    os.makedirs(cache_dir, exist_ok=True)

    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(prepared_dict)

    for i, (sym, df) in enumerate(prepared_dict.items(), 1):
        path = os.path.join(cache_dir, f"{safe_filename(sym)}.csv")
        df.to_csv(path)
        progress_bar.progress(i / total)
        status_text.text(f"💾 System2キャッシュ保存中: {i}/{total} 件 完了")

    status_text.text(f"💾 System2キャッシュ保存完了 ({total} 件)")
    progress_bar.empty()
    st.success("🔚 バックテスト終了")

# ===============================
# 通常モード
# ===============================
use_auto = st.checkbox("自動ティッカー取得（全銘柄）", value=True, key="system2_auto_main")
capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="system2_capital_main")
symbols_input = None
if not use_auto:
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力", "AAPL,MSFT,TSLA,NVDA,META", key="system2_symbols_main")

if st.button("バックテスト実行", key="system2_run_main"):
    main_process(use_auto, capital, symbols_input)


# ===============================
# 統合モード用タブ呼び出し
# ===============================
def run_tab():
    st.header("System2：ショート RSIスラスト")
    use_auto = st.checkbox("自動ティッカー取得（全銘柄）", value=True, key="system2_auto_tab")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="system2_capital_tab")
    symbols_input = None
    if not use_auto:
        symbols_input = st.text_input("ティッカーをカンマ区切りで入力", "AAPL,MSFT,TSLA,NVDA,META", key="system2_symbols_tab")

    if st.button("バックテスト実行", key="system2_run_tab"):
        main_process(use_auto, capital, symbols_input)
