# app_system3.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from common.utils import safe_filename, get_cached_data, get_manual_data
from tickers_loader import get_all_tickers
from holding_tracker import generate_holding_matrix, display_holding_heatmap, download_holding_csv
from strategies.system3_strategy import System3Strategy
from datetime import datetime

# ===== 日本語フォント設定 =====
matplotlib.rcParams['font.family'] = 'Meiryo'  # or 'IPAGothic'

strategy = System3Strategy()

if st.button("⚠️ Streamlitキャッシュ全クリア"):
    st.cache_data.clear()
    st.success("Streamlit cache cleared.")


# ===== データ取得ヘルパー =====
def load_symbol(symbol):
    path = os.path.join("data_cache", f"{safe_filename(symbol)}.csv")
    if not os.path.exists(path):
        return symbol, None
    df = get_cached_data(symbol)
    return symbol, df

# ===== Streamlit 本体 =====
def app_body():
    st.title("システム3：ロング・ミーン・リバージョン・セルオフ")

    use_auto = st.checkbox("自動ティッカー取得（全銘柄）", value=True)
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=1000)

    symbols_input = None
    if not use_auto:
        symbols_input = st.text_input(
            "ティッカーをカンマ区切りで入力（例：AAPL,MSFT,NVDA）",
            "AAPL,MSFT,NVDA"
        )

    if st.button("バックテスト実行"):
        # ===== データ取得フェーズ =====
        if use_auto:
            select_tickers = get_all_tickers()[:100] 
            #select_tickers = get_all_tickers()
        else:
            if not symbols_input:
                st.error("銘柄を入力してください")
                return
            select_tickers = [s.strip().upper() for s in symbols_input.split(",")]

        raw_data_dict = {}
        total = len(select_tickers)
        data_log = st.empty()
        start_time = time.time()

        # データ取得開始メッセージ
        data_area = st.empty()
        data_area.info(f"📄 データ取得開始 | {total} 銘柄を処理中...")
        data_progress = st.progress(0)
        log_area = st.empty()

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(load_symbol, sym): sym for sym in select_tickers}
            for i, future in enumerate(as_completed(futures), 1):
                symbol, df = future.result()
                if df is not None and not df.empty:
                    raw_data_dict[symbol] = df

                elapsed = time.time() - start_time
                remain = (elapsed / i) * (total - i)
                elapsed_min, elapsed_sec = divmod(int(elapsed), 60)
                remain_min, remain_sec = divmod(int(remain), 60)

                if i % 50 == 0 or i == total:
                    joined_symbols = ", ".join(list(raw_data_dict.keys())[-50:])
                    log_area.text(
                        f"📄 データ取得: {i}/{total} 件 完了"
                        f" | 経過: {elapsed_min}分{elapsed_sec}秒"
                        f" / 残り: 約 {remain_min}分{remain_sec}秒\n"
                        f"銘柄: {joined_symbols}"
                    )
                data_progress.progress(i / total)
            data_progress.empty()

        if not raw_data_dict:
            st.error("有効な銘柄データがありません")
            return

        # ===== インジ計算 =====
        st.info("📊 インジケーター計算中...")
        ind_progress = st.progress(0)
        ind_log = st.empty()
        prepared_dict = strategy.prepare_data(
            raw_data_dict,
            progress_callback=lambda done, total: ind_progress.progress(done / total),
            log_callback=lambda msg: ind_log.text(msg),
        )
        ind_progress.empty()

        # ===== 候補生成 =====
        st.info("📊 セットアップ通過銘柄を抽出中...")
        cand_progress = st.progress(0)
        cand_log = st.empty()

        # session_state にログを蓄積
        if "system3_log" not in st.session_state:
            st.session_state["system3_log"] = ""

        def cand_log_callback(msg):
            st.session_state["system3_log"] += msg + "\n"
            cand_log.text_area("セットアップ抽出ログ", st.session_state["system3_log"], height=300)

        candidates_by_date = strategy.generate_candidates(
            prepared_dict,
            progress_callback=lambda done, total: cand_progress.progress(done / total),
            log_callback=cand_log_callback
        )

        if not candidates_by_date:
            st.warning("⚠️ セットアップ条件を満たす銘柄がありませんでした。")
            return

        st.write(f"📊 セットアップ抽出完了 | {len(prepared_dict)} 銘柄を処理しました")

        # ---- シグナル件数サマリー ----
        signal_days = len(candidates_by_date)
        signal_total = sum(len(v) for v in candidates_by_date.values())

        # 📌 シグナル集計
        st.subheader("📌 シグナル集計")
        col1, col2 = st.columns(2)
        col1.metric("Signal 発生日数", f"{signal_days}")
        col2.metric("Signal 総件数", f"{signal_total}")

        # ===== バックテスト =====
        st.info("💹 バックテスト実行中...")

        bt_progress = st.progress(0)
        bt_log = st.empty()

        def log_callback(i, total, start_time):
            elapsed = time.time() - start_time
            remain = (elapsed / i) * (total - i)
            bt_log.text(
                f"💹 バックテスト: {i}/{total} 日処理完了"
                f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
                f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒"
            )

        trades_df = strategy.run_backtest(
            prepared_dict,
            candidates_by_date,
            capital,
            on_progress=lambda i, total, start: bt_progress.progress(i / total),
            on_log=lambda i, total, start: log_callback(i, total, start)
        )
        bt_progress.empty()

        # ===== 銘柄別シグナル発生件数とトレード件数 =====
        signal_counts = {
            sym: int(df["setup"].sum())
            for sym, df in prepared_dict.items()
            if "setup" in df.columns
        }
        trade_counts = trades_df["symbol"].value_counts().to_dict()

        summary_data = []
        for sym in sorted(set(signal_counts.keys()) | set(trade_counts.keys())):
            summary_data.append({
                "Symbol": sym,
                "Signal_Count": signal_counts.get(sym, 0),
                "Trade_Count": trade_counts.get(sym, 0)
            })

        summary_df = pd.DataFrame(summary_data).sort_values("Signal_Count", ascending=False)

        with st.expander("📊 銘柄別シグナル発生件数とトレード件数（全期間）", expanded=False):
            st.dataframe(summary_df, height=400)

        if trades_df.empty:
            st.info("トレードは発生しませんでした。")
            return

        # ===== 集計 =====
        st.subheader("バックテスト結果")
        st.dataframe(trades_df)

        total_return = trades_df["pnl"].sum()
        win_rate = (trades_df["return_%"] > 0).mean() * 100

        # 累積損益とドローダウンを計算（System2準拠）
        trades_df = trades_df.sort_values("exit_date")
        trades_df["cumulative_pnl"] = trades_df["pnl"].cumsum()
        trades_df["cum_max"] = trades_df["cumulative_pnl"].cummax()
        trades_df["drawdown"] = trades_df["cumulative_pnl"] - trades_df["cum_max"]
        max_dd = trades_df["drawdown"].min()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("トレード回数", f"{len(trades_df)}")
        col2.metric("最終損益 (USD)", f"{total_return:,.2f}")
        col3.metric("勝率 (%)", f"{win_rate:.2f}")
        col4.metric("最大ドローダウン (USD)", f"{max_dd:,.2f}")

        # ===== グラフ =====
        trades_df["exit_date"] = pd.to_datetime(trades_df["exit_date"])
        trades_df = trades_df.sort_values("exit_date")
        trades_df["cumulative_pnl"] = trades_df["pnl"].cumsum()
        trades_df["cum_max"] = trades_df["cumulative_pnl"].cummax()
        trades_df["drawdown"] = trades_df["cumulative_pnl"] - trades_df["cum_max"]

        # ===== サマリー用カラム追加=====
        trades_df["year"] = trades_df["exit_date"].dt.year
        trades_df["month"] = trades_df["exit_date"].dt.to_period("M")
        trades_df["week"] = trades_df["exit_date"].dt.to_period("W")

        st.subheader("📈 累積損益グラフ")
        plt.figure(figsize=(10, 4))
        plt.plot(trades_df["exit_date"], trades_df["cumulative_pnl"], color="blue", label="累積損益")
        plt.fill_between(trades_df["exit_date"], trades_df["drawdown"], 0, color="red", alpha=0.2, label="ドローダウン")
        plt.xlabel("日付")
        plt.ylabel("損益 (USD)")
        plt.legend()
        plt.title("System3 累積損益とドローダウン", fontsize=12)
        st.pyplot(plt)

        # ===== R-multiple 分布 =====
        st.subheader("📊 R倍率ヒストグラム（-5R〜+5R）")
        trades_df["R_multiple"] = trades_df["pnl"] / trades_df["risk_amount"]
        plt.figure(figsize=(6, 3))
        plt.hist(
            trades_df["R_multiple"],
            bins=30, range=(-5, 5),
            color="blue", edgecolor="black", alpha=0.7
        )
        plt.xlabel("R倍率")
        plt.ylabel("頻度")
        plt.xlim(-5, 5)
        plt.title("R倍率の分布", fontsize=12)
        st.pyplot(plt)

        # ===== サマリー =====
        st.subheader("📅 年次サマリー")
        st.dataframe(trades_df.groupby("year")["pnl"].sum().reset_index())

        st.subheader("📆 月次サマリー")
        st.dataframe(trades_df.groupby("month")["pnl"].sum().reset_index())

        st.subheader("📊 週次サマリー")
        st.dataframe(trades_df.groupby("week")["pnl"].sum().reset_index())

        # ===== ヒートマップ =====
        st.subheader("📊 System3：日別保有銘柄ヒートマップ")
        heatmap_progress = st.progress(0)
        heatmap_status = st.empty()

        holding_matrix = generate_holding_matrix(
            trades_df,
            trade_progress_callback=lambda done, total: (
                heatmap_progress.progress(done / (2*total)),  # 全体の前半を使う
                heatmap_status.text(f"🔥 トレード処理中: {done}/{total} 件完了")
            ),
            matrix_progress_callback=lambda done, total: (
                heatmap_progress.progress(0.5 + done / (2*total)),  # 後半を使う
                heatmap_status.text(f"📊 マトリクス生成中: {done}/{total} 日完了")
            )
        )

        heatmap_progress.empty()
        heatmap_status.text("✅ ヒートマップ作成完了")

        display_holding_heatmap(holding_matrix, title="System3：日別保有銘柄ヒートマップ")
        download_holding_csv(holding_matrix, filename="holding_status_system3.csv")


        # ===== CSV自動保存 (System2準拠) =====
        today_str = pd.Timestamp.today().date().isoformat()
        save_dir = "results_csv"
        os.makedirs(save_dir, exist_ok=True)

        # 売買ログ保存
        trade_file = os.path.join(save_dir, f"system3_{today_str}_{int(capital)}.csv")
        trades_df.to_csv(trade_file, index=False)
        st.write(f"📂 売買ログを自動保存: {trade_file}")

        # signal件数保存（銘柄別集計）
        signal_counts = {
            sym: int(df["setup"].sum())
            for sym, df in prepared_dict.items()
            if "setup" in df.columns
        }
        signal_df = pd.DataFrame(signal_counts.items(), columns=["Symbol", "Signal_Count"])

        signal_dir = os.path.join(save_dir, "signals")
        os.makedirs(signal_dir, exist_ok=True)
        signal_path = os.path.join(signal_dir, f"system3_signals_{today_str}_{int(capital)}.csv")
        signal_df.to_csv(signal_path, index=False)
        st.write(f"✅ signal件数も保存済み: {signal_path}")

        # ===== キャッシュ保存メッセージ（System2準拠） =====
        st.info("💾 System3加工済日足データキャッシュ保存開始…")
        #0817 データ容量不足になるので後でキャッシュ共通化する
        cache_dir = os.path.join("data_cache", "systemX")
        os.makedirs(cache_dir, exist_ok=True)

        progress_bar = st.progress(0)
        status_text = st.empty()
        total = len(prepared_dict)

        for i, (sym, df) in enumerate(prepared_dict.items(), 1):
            path = os.path.join(cache_dir, f"{safe_filename(sym)}.csv")
            df.to_csv(path)
            progress_bar.progress(i / total)
            status_text.text(f"💾 System3キャッシュ保存中: {i}/{total} 件 完了")
        status_text.text(f"💾 System3キャッシュ保存完了 ({len(prepared_dict)} 件)")
        progress_bar.empty()

        # ===== 終了メッセージ =====
        st.success("🔚 バックテスト終了")

def run_tab():
    app_body()

if __name__ == "__main__":
    app_body()
