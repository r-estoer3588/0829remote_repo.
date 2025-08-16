# app_integrated.py
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time

# 戦略ごとのバックテスト関数（仮：別ファイルからimport予定）
from app_system1 import run_backtest as run_system1
from app_system2 import get_stooq_data as get_stooq_data_s2, get_alpha_data as get_alpha_data_s2, apply_indicators as apply_indicators_s2, backtest_symbol as backtest_symbol_s2
from app_system7 import backtest_spy as run_system7
from app_system3 import get_stooq_data as get_stooq_data_s3, get_alpha_data as get_alpha_data_s3, apply_indicators as apply_indicators_s3, backtest_symbol as backtest_symbol_s3
from app_system1 import get_stooq_data as get_stooq_data_s1, prepare_data as prepare_data_s1
from app_system7 import get_stooq_data as get_stooq_data_s7, get_alpha_data as get_alpha_data_s7, apply_indicators as apply_indicators_s7
from app_system4 import get_stooq_data as get_stooq_data_s4, get_alpha_data as get_alpha_data_s4, apply_indicators as apply_indicators_s4, backtest_symbol as backtest_symbol_s4

from app_system1 import run_tab as run_tab1
from app_system2 import run_tab as run_tab2
from app_system3 import run_tab as run_tab3
from app_system4 import run_tab as run_tab4
from app_system5 import run_tab as run_tab5
from app_system6 import run_tab as run_tab6
from app_system7 import run_tab as run_tab7
st.title("統合バックテストGUI：戦略1〜7")
display_mode = st.radio("表示モード", ["一括実行", "戦略別テスト"], key="display_mode_selector")
symbols = ["AAPL", "MSFT", "NVDA"]  # 仮のティッカーリスト（実際は入力フォームなどで取得）
capital = 1000  # 初期資金（仮）
data_source = "Stooq"  # または "Alpha Vantage"
df_all = pd.DataFrame()
results_all = []

# 共通設定

if display_mode == "一括実行":
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力（例：AAPL,MSFT,NVDA）", "AAPL,MSFT,NVDA")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="capital_input")
    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"], key="data_source_input")
    rank_limit = st.slider("同日最大仕掛け数（System2/6用）", min_value=1, max_value=10, value=3)

    if st.button("バックテスト実行"):
        results_all = []
        symbols = [s.strip().upper() for s in symbols_input.split(",")]
        
        st.subheader("▶ System1")
        st.write("System1 を実行中です（トレンド銘柄をチェック中）")
        data_dict = {}
        for symbol in symbols:
            st.write(f"▶ 処理中: {symbol}")
            try:
                df = get_stooq_data_s1(symbol)
                if df is not None:
                    df = prepare_data_s1(df)
                    data_dict[symbol] = df
            except Exception as e:
                st.error(f"{symbol}: エラーが発生しました: {e}")
            
        spy_df = get_stooq_data_s1("SPY")
        spy_df = prepare_data_s1(spy_df)
        
        res1 = run_system1(data_dict, spy_df, capital)
        if not res1.empty:
            for symbol in symbols:
                count = res1[res1["symbol"] == symbol].shape[0]
                st.write(f"　{symbol}: {count}件のトレード")
            st.write(f"{len(res1)}件のトレード発生")
            res1["system"] = "System1"
            results_all.append(res1)
        else:
            st.write("トレードは発生しませんでした。")
        
        st.subheader("▶ System2")
        st.write("System2 を実行中です（仕掛け候補をチェック中）")
        system2_has_trades = False
        for symbol in symbols:
            st.write(f"▶ 処理中: {symbol}")
            try:
                pass
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                df = get_stooq_data_s2(symbol) if data_source == "Stooq" else get_alpha_data_s2(symbol)
            if df is None or df.empty:
                st.warning(f"{symbol}: データ取得に失敗しました。")
            continue
        df = apply_indicators_s2(df)
        trades = backtest_symbol_s2(symbol, df, capital, rank_limit)
        for trade in trades:
            trade["system"] = "System2"
        if trades:
            st.write(f"{len(trades)}件のトレード発生")
            df_trades = pd.DataFrame(trades)
            df_trades["system"] = "System2"
            results_all.append(df_trades)
            system2_has_trades = True
        else:
            st.write("トレードは発生しませんでした。")
        if data_source == "Alpha Vantage":
            time.sleep(12)
        try:
            pass
        except Exception as e:
            st.error(f"{symbol}: エラーが発生しました - {e}")

        st.subheader("▶ System3")
        st.write("System3 を実行中です（急落銘柄をチェック中）")
        system3_has_trades = False
        for symbol in symbols:
            st.write(f"▶ 処理中: {symbol}")
            try:
                pass
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
            df = get_stooq_data_s3(symbol) if data_source == "Stooq" else get_alpha_data_s3(symbol)
            if df is None or df.empty:
                st.warning(f"{symbol}: データ取得に失敗しました。")
            continue
        df = apply_indicators_s3(df)
        trades, _, _ = backtest_symbol_s3(symbol, df, capital)
        for trade in trades:
            trade["system"] = "System3"
        if trades:
            st.write(f"{len(trades)}件のトレード発生")
            results_all.append(pd.DataFrame(trades))
            system3_has_trades = True
            system3_has_trades = True
        else:
            st.write("トレードは発生しませんでした。")
        if data_source == "Alpha Vantage":
            time.sleep(12)
        try:
            pass
        except Exception as e:
            st.error(f"{symbol}: エラーが発生しました - {e}")

        st.subheader("▶ System4")
        st.write("System4 を実行中です（低ボラ銘柄をチェック中）")
        spy_df = get_stooq_data_s4("SPY") if data_source == "Stooq" else get_alpha_data_s4("SPY")
        spy_df = apply_indicators_s4(spy_df)
        for symbol in symbols:
            st.write(f"▶ 処理中: {symbol}")
            try:
                pass
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                df = get_stooq_data_s4(symbol) if data_source == "Stooq" else get_alpha_data_s4(symbol)
            if df is None or df.empty:
                st.warning(f"{symbol}: データ取得に失敗しました。")
            continue
        df = apply_indicators_s4(df)
        trades, _, _ = backtest_symbol_s4(symbol, df, spy_df, capital)
        for trade in trades:
            trade["system"] = "System4"
        if trades:
            st.write(f"{len(trades)}件のトレード発生")
            results_all.append(pd.DataFrame(trades))
        else:
            st.write("トレードは発生しませんでした。")
        if data_source == "Alpha Vantage":
            time.sleep(12)
        try:
            pass
        except Exception as e:
            st.error(f"{symbol}: エラーが発生しました - {e}")

        system5_has_trades = False
        st.subheader("▶ System5")
        st.write("System5 を実行中です（ADXリバーサルをチェック中）")
        from app_system5 import get_stooq_data as get_stooq_data_s5, get_alpha_data as get_alpha_data_s5, apply_indicators as apply_indicators_s5, backtest_symbol as backtest_symbol_s5
        for symbol in symbols:
            st.write(f"▶ 処理中: {symbol}")
            try:
                pass
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                df = get_stooq_data_s5(symbol) if data_source == "Stooq" else get_alpha_data_s5(symbol)
            if df is None or df.empty:
                st.warning(f"{symbol}: データ取得に失敗しました。")
            continue
        df = apply_indicators_s5(df)
        trades, _, _ = backtest_symbol_s5(symbol, df, capital)
        for trade in trades:
            trade["system"] = "System5"
        if trades:
            st.write(f"{len(trades)}件のトレード発生")
            results_all.append(pd.DataFrame(trades))
            system3_has_trades = True
        else:
            st.write("トレードは発生しませんでした。")
        if data_source == "Alpha Vantage":
            time.sleep(12)
        try:
            pass
        except Exception as e:
            st.error(f"{symbol}: エラーが発生しました - {e}")

        system6_has_trades = False
        st.subheader("▶ System6")
        st.write("System6 を実行中です（6日急騰＋2連陽線をチェック中）")
        from app_system6 import get_stooq_data as get_stooq_data_s6, get_alpha_data as get_alpha_data_s6, apply_indicators as apply_indicators_s6, backtest_symbol as backtest_symbol_s6
        for symbol in symbols:
            st.write(f"▶ 処理中: {symbol}")
            try:
                pass
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                df = get_stooq_data_s6(symbol) if data_source == "Stooq" else get_alpha_data_s6(symbol)
            if df is None or df.empty:
                st.warning(f"{symbol}: データ取得に失敗しました。")
            continue
        df = apply_indicators_s6(df)
        trades, _, _ = backtest_symbol_s6(symbol, df, capital, rank_limit)
        for trade in trades:
            trade["system"] = "System6"
        if trades:
            st.write(f"{len(trades)}件のトレード発生")
            results_all.append(pd.DataFrame(trades))
            system6_has_trades = True
        else:
            st.write("トレードは発生しませんでした。")
        if data_source == "Alpha Vantage":
                time.sleep(12)
        try:
            pass
        except Exception as e:
            st.error(f"{symbol}: エラーが発生しました - {e}")
            st.error(f"{symbol}: エラーが発生しました - {e}")
            st.error(f"{symbol}: エラーが発生しました - {e}")

        system7_has_trades = False
        st.subheader("▶ System7")
        df = get_stooq_data_s7("SPY") if data_source == "Stooq" else get_alpha_data_s7("SPY")
        df = apply_indicators_s7(df)
        res7 = run_system7(df, capital)
        if not res7.empty:
            st.write(f"{len(res7)}件のトレード発生")
            res7["system"] = "System7"
            results_all.append(res7)
            system7_has_trades = True
        else:
            st.write("トレードは発生しませんでした。")

        if results_all:
            df_all = pd.concat(results_all, ignore_index=True)
            df_all["exit_date"] = pd.to_datetime(df_all["exit_date"])
            df_all = df_all.sort_values("exit_date")
            df_all["cumulative_pnl"] = df_all["pnl"].cumsum()
            st.subheader("統合バックテスト結果")
            st.dataframe(df_all)

            st.metric("総トレード数", len(df_all))
            st.metric("最終損益", f"{df_all['pnl'].sum():.2f} USD")

            win_rate = (df_all['pnl'] > 0).mean() * 100
            df_all["cum_max"] = df_all["cumulative_pnl"].cummax()
            df_all["drawdown"] = df_all["cumulative_pnl"] - df_all["cum_max"]
            max_dd = df_all["drawdown"].min()

            st.metric("勝率（％）", f"{win_rate:.2f}")
            st.metric("最大ドローダウン（USD）", f"{max_dd:.2f}")
        
            fig, ax = plt.subplots(figsize=(10,4))
            for system in df_all["system"].unique():
                sub = df_all[df_all["system"] == system]
                ax.plot(sub["exit_date"], sub["cumulative_pnl"], label=system)
            ax.set_title("累積損益（システム別）")
            ax.set_xlabel("Date")
            ax.set_ylabel("PnL (USD)")
            ax.legend()
            st.pyplot(fig)
        else:
            st.warning("System6：全銘柄でトレードは発生しませんでした。")
            st.warning("System5：全銘柄でトレードは発生しませんでした。")
            st.warning("System3：全銘柄でトレードは発生しませんでした。")
            st.warning("System2：全銘柄でトレードは発生しませんでした。")
            st.warning("System1：SPY条件が満たされず、トレードは発生しませんでした。")
            st.warning("System7：トレードは発生しませんでした。")
        if not results_all:
            st.warning("選択された戦略すべてにおいてトレードは発生しませんでした。")
        

        st.subheader("システム別サマリー（棒グラフ）")
        # システム別のトレード数、勝率、総損益、最大ドローダウンを計算
        # トレード数
        trade_counts = df_all["system"].value_counts().sort_index()

        # 勝率（％）
        win_rates = df_all[df_all["pnl"].notna()].groupby("system")["pnl"].apply(lambda x: (x > 0).mean() * 100)

        # 総損益
        total_pnl = df_all.groupby("system")["pnl"].sum()

        # 最大ドローダウン
        max_drawdown = df_all.groupby("system")["drawdown"].min()

        # グラフ描画関数
        def plot_bar(series, title, ylabel):
            import matplotlib
            matplotlib.rcParams['font.family'] = 'MS Gothic'  # または 'Yu Gothic'
            fig, ax = plt.subplots()
            series.plot(kind="bar", ax=ax)
            ax.set_title(title)
            ax.set_ylabel(ylabel)
            st.pyplot(fig)

        plot_bar(trade_counts, "システム別トレード数", "件数")
        plot_bar(win_rates, "システム別勝率", "勝率（％）")
        plot_bar(total_pnl, "システム別最終損益", "損益（USD）")
        plot_bar(max_drawdown, "システム別最大ドローダウン", "ドローダウン（USD）")


elif display_mode == "戦略別テスト":
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "System1", "System2", "System3", "System4", "System5", "System6", "System7"
    ])
    with tab1:
        run_tab1()
    with tab2:
        run_tab2()
    with tab3:
        run_tab3()
    with tab4:
        run_tab4()
    with tab5:
        run_tab5()
    with tab6:
        run_tab6()
    with tab7:
        run_tab7()

elif display_mode == "一括実行":
    st.subheader("全戦略の一括バックテスト")
    # 既存の一括処理をここに維持