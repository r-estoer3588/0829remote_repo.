import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import StringIO
from ta.trend import SMAIndicator
from ta.momentum import ROCIndicator
from ta.volatility import AverageTrueRange
from tickers_loader import get_all_tickers, filter_symbols_by_system1
import os
from collections import defaultdict
import matplotlib
import matplotlib.pyplot as plt
import pandas_market_calendars as mcal
from holding_tracker import generate_holding_matrix, display_holding_heatmap, download_holding_csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import matplotlib.ticker as mticker
from indicators_common import add_indicators
from pathlib import Path
from datetime import time as dtime
import subprocess
from common.utils import safe_filename, clean_date_column, get_cached_data, get_manual_data
from strategies.system1_strategy import System1Strategy
import threading


# 戦略インスタンスを作成
strategy = System1Strategy()

#警告抑制
logging.getLogger('streamlit.runtime.scriptrunner.script_run_context').setLevel(logging.ERROR)

# 全体にメイリオフォントを設定（Windows用）
matplotlib.rcParams['font.family'] = 'Meiryo'

#キャッシュクリア
if st.button("⚠️ Streamlitキャッシュ全クリア"):
    st.cache_data.clear()
    st.success("Streamlit cache cleared.")

def is_last_trading_day(latest_date, today=None):
    # NYSEカレンダー取得
    nyse = mcal.get_calendar('NYSE')
    if today is None:
        today = pd.Timestamp.today().normalize()

    # 今週の直近の営業日リストを生成
    schedule = nyse.schedule(start_date=today - pd.Timedelta(days=7), end_date=today)
    valid_days = schedule.index.normalize()

    # SPYデータの最新日付が有効な営業日か判定
    return latest_date.normalize() == valid_days[-1]

def get_latest_nyse_trading_day(today=None):
    nyse = mcal.get_calendar('NYSE')
    if today is None:
        today = pd.Timestamp.today().normalize()
    # スケジュールは今日+1日もカバー（米国がまだ月曜朝になっていない場合用）
    sched = nyse.schedule(start_date=today - pd.Timedelta(days=7), end_date=today + pd.Timedelta(days=1))
    valid_days = sched.index.normalize()
    # 今日より前の直近の営業日（たいてい金曜か当日）
    last_trading_day = valid_days[valid_days <= today].max()
    return last_trading_day

# 例：SPY取得時
def get_spy_data_cached(folder="data_cache"):
    path = os.path.join(folder, "SPY.csv")
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, parse_dates=["Date"])
            if "Date" not in df.columns:
                print("❌ 'Date'列が存在しません。")
                return None
            df.set_index("Date", inplace=True)
            df = df.sort_index()
            st.write(f"✅ SPYキャッシュ最終日: {df.index[-1].date()}")

            # NYSEカレンダー
            nyse = mcal.get_calendar('NYSE')
            today = pd.Timestamp.today().normalize()
            latest_trading_day = get_latest_nyse_trading_day(today)
            st.write(f"🗓️ 直近のNYSE営業日: {latest_trading_day.date()}")

            prev_trading_day = nyse.schedule(
                start_date=today - pd.Timedelta(days=7),
                end_date=today
            ).index.normalize()[-2]

            # 米国時間を取得
            ny_time = pd.Timestamp.now(tz="America/New_York").time()

            # 判定: 古い場合 → 自動更新
            if df.index[-1].normalize() < prev_trading_day and ny_time >= dtime(18, 0):
                st.warning("⚠ SPYキャッシュが古いため自動更新します...")
                try:
                    result = subprocess.run(
                        ["python", "recover_spy_cache.py"],
                        capture_output=True,
                        text=True
                    )
                    st.text(result.stdout)
                    if result.stderr:
                        st.error(result.stderr)
                except Exception as e:
                    st.error(f"SPY自動更新失敗: {e}")
                    return None

                # 更新後再読み込み
                if os.path.exists(path):
                    df = pd.read_csv(path, parse_dates=["Date"])
                    df.set_index("Date", inplace=True)
                    df = df.sort_index()
                    st.success(f"✅ SPYキャッシュ更新後: {df.index[-1].date()}")
                    return df
                else:
                    st.error("❌ 更新後もSPY.csvが存在しません")
                    return None

            # 通常は現行データを返す
            st.write("✅ SPYキャッシュは有効")
            return df

        except Exception as e:
            st.error(f"❌ SPY読み込み失敗: {e}")
            return None
    else:
        st.error("❌ SPY.csv が存在しません")
        return None

@st.cache_data
def get_spy_with_indicators(spy_df=None):
    if spy_df is None:
        spy_df = get_spy_data_cached()
    if spy_df is not None and not spy_df.empty:
        spy_df["SMA100"] = SMAIndicator(spy_df["Close"], window=100).sma_indicator()
        spy_df["SMA200"] = SMAIndicator(spy_df["Close"], window=200).sma_indicator()
        spy_df["spy_filter"] = (spy_df["Close"] > spy_df["SMA200"]).astype(int)
    return spy_df

# 並列処理でデータを取得
def load_symbol(symbol):
    path = os.path.join("data_cache", f"{safe_filename(symbol)}.csv")
    if not os.path.exists(path):
        return symbol, None
    df = get_cached_data(symbol)
    return symbol, df

def summarize_signals(trades_df):
    """trades_dfをSymbolとsignalで集計しDataFrameを返す"""
    if trades_df is None or trades_df.empty:
        return pd.DataFrame(columns=["Symbol", "signal", "count"])
    return (
        trades_df.groupby(["Symbol", "signal"])
        .size()
        .reset_index(name="count")
        .sort_values(["signal", "count"], ascending=[True, False])
    )

#統合実施用
if __name__ == "__main__":
    st.title("システム1：ロング・トレンド・ハイ・モメンタム（複数銘柄＋ランキング）")
    debug_mode = st.checkbox("詳細ログを表示（System1）", value=False, key="system1_debug")

    use_auto = st.checkbox("自動ティッカー取得（System1フィルター適用）", value=True)
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100)

    # 🔽 ここを追加：手動入力UIは use_auto=False のときだけ描画
    Symbols_input = None
    if not use_auto:
        Symbols_input = st.text_input(
            "ティッカーをカンマ区切りで入力（例：AAPL,MSFT,META）",
            "AAPL,MSFT,META,AMZN,GOOGL"
    )
    spy_df = None  # 初期化
    if st.button("バックテスト実行"):
        spy_df = get_spy_data_cached()
        if spy_df is None or spy_df.empty:
            st.error("SPYデータの取得に失敗しました。キャッシュを更新してください。")
            st.stop()
        max_workers = 8  # 調整可
        all_tickers = get_all_tickers()
        # バックテスト実行ボタン押下後の処理開始直後に追加
        st.info(f"🔁 run_backtest 開始 | {len(all_tickers)} 銘柄を取得しました")
        # データ取得ログを先に作る（画面の上に表示）
        data_log_area = st.empty()
        # 指標計算ログをその下に作る
        ind_log_area = st.empty()

        if use_auto:
            # 🔽 (0809実装用)ここで銘柄数上限100に制限
            select_tickers = get_all_tickers()[:100]  
            data_dict = {}
            log_container = st.container()  # 複数行保持用
            start_time = time.time()

            if spy_df is None or spy_df.empty:
                st.error("SPYデータの取得に失敗しました。キャッシュを更新してください。")
                st.stop()
            spy_df["SMA200"] = SMAIndicator(spy_df["Close"], window=200).sma_indicator()
            spy_df["spy_filter"] = (spy_df["Close"] > spy_df["SMA200"]).astype(int)

            # 1. データ取得フェーズ
            # 設定
            start_time = time.time()
            raw_data_dict = {}
            total = len(select_tickers)
            batch_size = 50
            symbol_buffer = []
            # 進捗バー、進捗ログ作成
            data_area = st.empty()
            data_area.info(f"📄 データ取得開始 | {total} 銘柄を処理中...")

            data_progress_bar = st.progress(0)
            data_log_area = st.empty()

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(load_symbol, sym): sym for sym in select_tickers}
                for i, future in enumerate(as_completed(futures), 1):
                    Symbol, df = future.result()
                    if df is not None and not df.empty:
                        raw_data_dict[Symbol] = df
                        symbol_buffer.append(Symbol)

                    if i % batch_size == 0 or i == total:
                        elapsed = time.time() - start_time
                        remaining = (elapsed / i) * (total - i)
                        elapsed_min, elapsed_sec = divmod(int(elapsed), 60)
                        remain_min, remain_sec = divmod(int(remaining), 60)
                        joined_symbols = ", ".join(symbol_buffer)
                        data_log_area.text(
                            f"📄 データ取得: {i}/{total} 件 完了"
                            f" | 経過: {elapsed_min}分{elapsed_sec}秒 / 残り: 約 {remain_min}分{remain_sec}秒\n"
                            f"銘柄: {joined_symbols}"
                        )
                        data_progress_bar.progress(i / total)
                        symbol_buffer.clear()
            data_progress_bar.empty()  # データ取得フェーズ終了

            # 2. 加工処理フェーズ　(指標計算)
            # 設定
            start_time = time.time()
            batch_size = 50    
            # 進捗バー、進捗ログ作成
            ind_area = st.empty()
            ind_area.info(f"📊 指標計算開始 | {len(raw_data_dict)} 銘柄を処理中...")
            ind_progress_bar = st.progress(0)
            ind_log_area = st.empty()
        
            data_dict = strategy.prepare_data(
                raw_data_dict,
                progress_callback=lambda done, total: ind_progress_bar.progress(done / total),
                log_callback=lambda msg: ind_log_area.text(msg),
                batch_size=batch_size
            )
            ind_progress_bar.empty()

            st.write("📊 指標計算完了"
                     f" | {len(data_dict)} 銘柄のデータを処理しました")
            if not data_dict:
                st.error("有効な銘柄データがありません。")
                st.stop()
            
            # 3. ROC200ランキング作成フェーズ
            # 設定
            start_time = time.time()
            # 進捗バー、進捗ログ作成
            roc_area = st.empty()
            roc_area.info("📊 ROC200ランキング生成中...")
            roc_progress = st.progress(0)
            roc_log = st.empty()

            # total_days を先に計算して初期表示
            total_days = strategy.get_total_days(data_dict)


            roc_log.text(f"📊 ROC200ランキング: 0/{total_days} 日処理開始... | 残り: 計算中...")

            def progress_callback_roc(i, total, start_time):
                roc_progress.progress(i / total)

            def log_callback_roc(i, total, start_time):
                elapsed = time.time() - start_time
                remain = (elapsed / i) * (total - i)
                roc_log.text(
                    f"📊 ROC200計算: {i}/{total} 銘柄処理完了"
                    f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
                    f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒"
                )

            candidates_by_date, merged_df = strategy.generate_candidates(
                data_dict, spy_df,
                on_progress=progress_callback_roc,
                on_log=log_callback_roc
            )
            daily_df = clean_date_column(merged_df, col_name="Date")

            # ここで true_signal_summary を作る
            merged_df.rename(columns={"symbol": "Symbol"}, inplace=True)
            true_signal_summary = merged_df["Symbol"].value_counts().to_dict()

            roc_progress.empty()
            roc_log.empty()

            # 📊 ROC200ランキング進捗付き生成 (処理)
            daily_df = clean_date_column(daily_df, col_name="Date")
            unique_dates = sorted(daily_df["Date"].unique())
            total_days = len(unique_dates)

            # ROC200ランク列を追加
            daily_df["ROC200_Rank"] = daily_df.groupby("Date")["ROC200"].rank(ascending=False, method="first")

            ranking_list = []
            for i, date in enumerate(unique_dates, start=1):
                top100 = daily_df[daily_df["Date"] == date].sort_values("ROC200", ascending=False).head(100)
                # Symbolカラム統一
                if "symbol" in top100.columns:
                    top100 = top100.rename(columns={"symbol": "Symbol"})
                ranking_list.append(top100[["Date", "Symbol", "ROC200_Rank"]])

                roc_progress.progress(i / total_days)
                if i % 10 == 0 or i == total_days:
                    elapsed = time.time() - start_time
                    remain = elapsed / i * (total_days - i)
                    roc_log.text(
                        f"📊 ROC200ランキング: {i}/{total_days} 日処理完了"
                        f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒 / 残り: 約 {int(remain//60)}分{int(remain%60)}秒"
                    )
                    time.sleep(0.01) # ← 表示のための小さな遅延

            roc_progress.empty()
            roc200_ranking_df = pd.concat(ranking_list, ignore_index=True)

            # === ここから5年フィルタ＆表示 ===
            five_years_ago = pd.Timestamp.now() - pd.DateOffset(years=5)
            roc200_display_df = roc200_ranking_df[roc200_ranking_df["Date"] >= five_years_ago]

            with st.expander("📊 日別ROC200ランキング（直近5年 / 上位100銘柄）"):
                st.dataframe(
                    roc200_display_df.reset_index(drop=True)[["Date", "ROC200_Rank", "Symbol"]],
                    column_config={
                        "Date": st.column_config.DatetimeColumn(format="YYYY-MM-DD"),
                        "ROC200_Rank": st.column_config.NumberColumn(width="small"),
                        "Symbol": st.column_config.TextColumn(width="small")
                    },
                    hide_index=False
                )

            roc_progress.empty()
            roc_log.empty()


            # CSVエクスポート
            csv = roc200_ranking_df.to_csv(index=False).encode("utf-8")
            st.download_button("全期間データをCSVで保存", data=csv, file_name="roc200_ranking_all.csv", mime="text/csv")

            # 固定メッセージを表示
            bt_area = st.empty()
            bt_area.info("💹 バックテスト実行中...")

            bt_progress = st.progress(0)
            bt_log_area = st.empty()

            # --- コールバック定義 ---
            def progress_callback(i, total, start_time):
                bt_progress.progress(i / total)

            def log_callback(i, total, start_time):
                elapsed = time.time() - start_time
                remain = (elapsed / i) * (total - i)
                bt_log_area.text(
                    f"💹 バックテスト: {i}/{total} 日処理完了"
                    f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
                    f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒"
                )

            # --- バックテスト実行 ---
            trades_df = strategy.run_backtest(
                data_dict,
                candidates_by_date,
                capital,
                on_progress=progress_callback,
                on_log=log_callback
            )

            # 固定メッセージを消す
            bt_area.empty()

            # 銘柄別 Signal_Count + Trade_Count 表
            # Signal_Count: merged_dfから作成
            signal_counts = merged_df["Symbol"].value_counts().reset_index()
            signal_counts.columns = ["Symbol", "Signal_Count"]

            # Trade_Count: trades_dfから作成
            if "symbol" in trades_df.columns:
                trades_df = trades_df.rename(columns={"symbol": "Symbol"})
            trade_counts = trades_df.groupby("Symbol").size().reset_index(name="Trade_Count")

            # マージ
            summary_df = pd.merge(signal_counts, trade_counts, on="Symbol", how="outer").fillna(0)
            summary_df["Signal_Count"] = summary_df["Signal_Count"].astype(int)
            summary_df["Trade_Count"] = summary_df["Trade_Count"].astype(int)

            with st.expander("📊 銘柄別シグナル発生件数とトレード件数（全期間）", expanded=False):
                st.dataframe(summary_df.sort_values("Signal_Count", ascending=False))

        else:
            if not Symbols_input:
                st.error("銘柄を入力してください")
                st.stop()
            Symbols = [s.strip().upper() for s in Symbols_input.split(",")]

            # 手動入力モード
            data_dict = {}
            ind_progress_bar = st.progress(0)  
            ind_log_area = st.empty()
            for Symbol in Symbols:
                path = os.path.join("data_cache", f"{safe_filename(Symbol)}.csv")
                if not os.path.exists(path):
                    st.warning(f"{Symbol}: キャッシュなし（data_cache/{Symbol}.csv）")
                    continue
                df = get_cached_data(Symbol)
                if df is None or df.empty:
                    continue
                prepared = strategy.prepare_data(
                    {Symbol: df},
                    progress_callback=lambda done, total: ind_progress_bar.progress(done / total),
                    log_callback=lambda msg: ind_log_area.text(msg)
                )
                df = prepared[Symbol]
                if not df.empty:
                    data_dict[Symbol] = df

            ind_progress_bar.empty()

            spy_df = get_spy_data_cached()
            if spy_df is None or spy_df.empty:
                st.error("SPYデータの取得に失敗しました。")
                st.stop()
            spy_df["SMA100"] = SMAIndicator(spy_df["Close"], window=100).sma_indicator()

            if not data_dict:
                st.error("有効な銘柄データがありません。")
                st.stop()

        # 3. バックテストフェーズ（run_backtest内部で日付単位の進捗を表示）
        # 再表示
        bt_area.info("💹 バックテスト実行中...")

        bt_progress.empty()
        bt_log_area.empty()

        # 全部trades_dfに変更
        # 4-2. バックテスト結果の表示
        if trades_df.empty:
            st.warning("SPYの条件を満たさないか、仕掛け候補がありません。")
        else:
            st.subheader("バックテスト結果")
            st.dataframe(trades_df)

            total_return = trades_df["pnl"].sum()
            win_rate = (trades_df["return_%"] > 0).mean() * 100

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("トレード回数", f"{len(trades_df)}")
            col2.metric("最終損益 (USD)", f"{total_return:,.2f}")
            col3.metric("勝率 (%)", f"{win_rate:.2f}")

            trades_df["exit_date"] = pd.to_datetime(trades_df["exit_date"])
            results = trades_df.sort_values("exit_date")
            results["cumulative_pnl"] = results["pnl"].cumsum()
            results["cum_max"] = results["cumulative_pnl"].cummax()
            results["drawdown"] = results["cumulative_pnl"] - results["cum_max"]
            max_dd = results["drawdown"].min()
            col4.metric("最大ドローダウン (USD)", f"{max_dd:,.2f}")

            st.subheader("累積損益グラフ")
            plt.figure(figsize=(10, 4))
            plt.plot(results["exit_date"], results["cumulative_pnl"], label="Cumulative PnL")

            min_pnl = results["cumulative_pnl"].min()
            max_pnl = results["cumulative_pnl"].max()
            margin = (max_pnl - min_pnl) * 0.1
            plt.ylim(min_pnl - margin, max_pnl + margin)

            ax = plt.gca()

            # 先に目盛り間隔を設定
            ax.yaxis.set_major_locator(mticker.MultipleLocator(500))

            # 次にフォーマットを設定（K表記）
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x*1e-3:.0f}K"))

            plt.xlabel("日付")
            plt.ylabel("損益 (USD)")
            plt.title("累積損益")
            plt.legend()
            st.pyplot(plt)

            # ✅ 追加：R倍率計算（5ATRをリスク基準とする）
            results["r_multiple"] = results["pnl"] / (results["shares"] * 5 * results["entry_price"] * 0.02)

            # ✅ 年次・月次・週次パフォーマンス
            yearly = results.groupby(results["exit_date"].dt.to_period("Y"))["pnl"].sum().reset_index()
            yearly["exit_date"] = yearly["exit_date"].astype(str)
            st.subheader("📅 年次サマリー")
            st.dataframe(yearly)

            monthly = results.groupby(results["exit_date"].dt.to_period("M"))["pnl"].sum().reset_index()
            monthly["exit_date"] = monthly["exit_date"].astype(str)
            st.subheader("📅 月次サマリー")
            st.dataframe(monthly)

            weekly = results.groupby(results["exit_date"].dt.to_period("W"))["pnl"].sum().reset_index()
            weekly["exit_date"] = weekly["exit_date"].astype(str)
            st.subheader("📆 週次サマリー")
            st.dataframe(weekly)

            # 📊 R倍率ヒストグラム（-5R〜+20Rに制限）
            st.subheader("📊 R倍率ヒストグラム（-5R～+20R）")
            r_values = results["r_multiple"].replace([np.inf, -np.inf], np.nan).dropna()
            r_values = r_values[(r_values > -5) & (r_values < 20)]

            plt.figure(figsize=(8, 4))
            plt.hist(r_values, bins=20, edgecolor='black', range=(-5, 20))
            plt.xlabel("R倍率")
            plt.ylabel("件数")
            plt.title("R倍率の分布")
            st.pyplot(plt)

            # 4. バックテスト結果の表示
            # 📊 日別保有銘柄ヒートマップ生成
            st.subheader("📊 System1：日別保有銘柄ヒートマップ")
            heatmap_progress = st.progress(0)
            heatmap_status = st.empty()

            holding_matrix = generate_holding_matrix(
                results,
                progress_callback=lambda done, total: (
                    heatmap_progress.progress(done / total),
                    heatmap_status.text(
                        f"🔥 ヒートマップ作成中: {done}/{total} 件完了"
                    )
                )
            )

            heatmap_progress.empty()
            heatmap_status.text("✅ ヒートマップ作成完了")

            # ✅ 自動保存用ディレクトリとファイル名を定義
            today_str = pd.Timestamp.today().date().isoformat()
            save_dir = "results_csv"
            os.makedirs(save_dir, exist_ok=True)
            save_file = os.path.join(save_dir, f"system1_{today_str}_{int(capital)}.csv")

            # ✅ 売買ログを自動保存
            results.to_csv(save_file, index=False)
            st.write(f"📂 売買ログを自動保存: {save_file}")

            # ✅ signal_summaryの自動保存（存在する場合）
            if true_signal_summary:
                signal_df = pd.DataFrame(sorted(true_signal_summary.items()), columns=["Symbol", "signal_count"])
                signal_dir = os.path.join(save_dir, "signals")
                os.makedirs(signal_dir, exist_ok=True)
                signal_path = os.path.join(signal_dir, f"system1_signals_{today_str}_{int(capital)}.csv")
                signal_df.to_csv(signal_path, index=False)
                st.write(f"✅ signal件数も保存済み: {signal_path}")

            # -------------------------------
            # 加工済日足データキャッシュの保存（System1）
            # -------------------------------
            st.info("💾 System1 加工済日足データキャッシュ保存開始...")

            os.makedirs("data_cache", exist_ok=True)
            total = len(data_dict)
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, (sym, df) in enumerate(data_dict.items(), 1):
                path = os.path.join("data_cache", f"{safe_filename(sym)}.csv")
                df.to_csv(path)
                progress_bar.progress(i / total)
                status_text.text(f"💾 加工済日足データキャッシュ保存中: {i}/{total} 件 完了")

            status_text.text(f"💾 加工済日足データキャッシュ保存完了 ({total} 件)")
            progress_bar.empty()
            st.success("🔚 バックテスト終了")

#単体実施
def run_tab(spy_df):
    st.header("System1：ロング・トレンド・ハイ・モメンタム（複数銘柄＋ランキング）") 
    Symbols_input = st.text_input(
    "ティッカーをカンマ区切りで入力（例：AAPL,MSFT,META）",
    "AAPL,MSFT,META,AMZN,GOOGL",
    key="system1_input"
    )
    Symbols = [s.strip().upper() for s in Symbols_input.split(",")]
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="system1_capital")

    if st.button("バックテスト実行", key="system1_button"):
        data_dict = {}

        # 🔽 追加：進捗バーとログ領域を定義
        ind_progress_bar = st.progress(0)
        ind_log_area = st.empty()

        with st.spinner("データ取得中..."):
            for Symbol in Symbols:
                st.write(f"▶ 処理中: {Symbol}")
                df = get_manual_data(Symbol)
                if df is not None:
                    prepared = strategy.prepare_data(
                        {Symbol: df},
                        progress_callback=lambda done, total: ind_progress_bar.progress(done / total),
                        log_callback=lambda msg: ind_log_area.text(msg)
                    )
                    df = prepared[Symbol]
                    data_dict[Symbol] = df
        ind_progress_bar.empty()
        
        if spy_df is None or spy_df.empty:
            st.error("SPYデータの取得に失敗しました。")
            return

        bt_log_area = st.empty()
        bt_progress = st.progress(0)

        def progress_callback_roc(i, total, start_time):
            roc_progress.progress(i / total)

        def log_callback_roc(i, total, start_time):
            elapsed = time.time() - start_time
            remain = (elapsed / i) * (total - i)
            roc_log.text(
                f"📊 ROC200計算: {i}/{total} 銘柄処理完了"
                f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
                f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒"
            )

        candidates_by_date, merged_df = strategy.generate_candidates(
            data_dict, spy_df,
            on_progress=progress_callback_roc,
            on_log=log_callback_roc
        )

        # ② true_signal_summary を merged_df から作成
        if "symbol" in merged_df.columns:
            merged_df.rename(columns={"symbol": "Symbol"}, inplace=True)
        true_signal_summary = merged_df["Symbol"].value_counts().to_dict()

        # ③ バックテスト実行
        def progress_callback(i, total, start_time):
            bt_progress.progress(i / total)

        def log_callback(i, total, start_time):
            elapsed = time.time() - start_time
            remain = (elapsed / i) * (total - i)
            bt_log_area.text(
                f"💹 バックテスト: {i}/{total} 日処理完了"
                f" | 経過: {int(elapsed//60)}分{int(elapsed%60)}秒"
                f" / 残り: 約 {int(remain//60)}分{int(remain%60)}秒"
            )

        trades_df = strategy.run_backtest(
            data_dict,
            candidates_by_date,
            capital,
            on_progress=progress_callback,
            on_log=log_callback
        )
        bt_progress.empty()

        # ④ Signal_Count + Trade_Count 表
        signal_counts = pd.DataFrame(sorted(true_signal_summary.items()), columns=["Symbol", "Signal_Count"])
        if "symbol" in trades_df.columns:
            trades_df = trades_df.rename(columns={"symbol": "Symbol"})
        trade_counts = trades_df.groupby("Symbol").size().reset_index(name="Trade_Count")
        summary_df = pd.merge(signal_counts, trade_counts, on="Symbol", how="outer").fillna(0)
        summary_df["Signal_Count"] = summary_df["Signal_Count"].astype(int)
        summary_df["Trade_Count"] = summary_df["Trade_Count"].astype(int)
        st.dataframe(summary_df.sort_values("Signal_Count", ascending=False))

        # バックテスト結果表示
        if trades_df.empty:
            st.warning("仕掛け候補なし")
        else:
            st.dataframe(trades_df)

            # results に trades_df をセット
            results = trades_df.sort_values("exit_date").copy()

            total_return = results["pnl"].sum()
            win_rate = (results["return_%"] > 0).mean() * 100
            st.metric("トレード回数", len(results))
            st.metric("最終損益（USD）", f"{total_return:.2f}")
            st.metric("勝率（％）", f"{win_rate:.2f}")

            results["exit_date"] = pd.to_datetime(results["exit_date"])
            results = results.sort_values("exit_date")
            results["cumulative_pnl"] = results["pnl"].cumsum()
            results["cum_max"] = results["cumulative_pnl"].cummax()
            results["drawdown"] = results["cumulative_pnl"] - results["cum_max"]
            max_dd = results["drawdown"].min()
            st.metric("最大ドローダウン（USD）", f"{max_dd:.2f}")

            st.subheader("累積損益グラフ")
            plt.figure(figsize=(10, 4))
            plt.plot(results["exit_date"], results["cumulative_pnl"], label="Cumulative PnL")
            plt.xlabel("日付")
            plt.ylabel("損益 (USD)")
            plt.title("累積損益")
            plt.legend()
            st.pyplot(plt)

            # バックテスト実行後の Streamlit セクション内に追記
            holding_matrix = generate_holding_matrix(results)
            display_holding_heatmap(holding_matrix, title="System1：日別保有銘柄ヒートマップ")
            download_holding_csv(holding_matrix, filename="holding_status_system1.csv")

            csv = results.to_csv(index=False).encode("utf-8")
            st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system1.csv", mime="text/csv")
