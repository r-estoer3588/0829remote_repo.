# app_system4.py
import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import StringIO
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from alpha_vantage.timeseries import TimeSeries
import matplotlib.pyplot as plt
import time

setup_df_list = []
ranked_df_list = []
all_trades = []

API_KEY = "L88B2SED3UWSYXGN"

#差し替え
@st.cache_data(ttl=86400)
def get_stooq_data(symbol):
    url = f"https://stooq.com/q/d/l/?s={symbol.lower()}.us&i=d"
    r = requests.get(url)
    if r.status_code != 200:
        return None
    df = pd.read_csv(StringIO(r.text))
    df.columns = [c.capitalize() for c in df.columns]
    df["Date"] = pd.to_datetime(df["Date"])
    df.set_index("Date", inplace=True)
    df = df.sort_index()
    return df

#差し替え
@st.cache_data(ttl=86400)
def get_alpha_data(symbol):
    ts = TimeSeries(key=API_KEY, output_format='pandas')
    df, _ = ts.get_daily(symbol=symbol, outputsize='full')
    df = df.rename(columns={
        "1. open": "Open",
        "2. high": "High",
        "3. low": "Low",
        "4. close": "Close",
        "5. volume": "Volume"
    })
    df = df.sort_index()
    return df

#必要
@st.cache_data
def apply_indicators(df):
    df = df.copy()
    df["SMA200"] = SMAIndicator(df["Close"], window=200).sma_indicator()
    df["ATR40"] = AverageTrueRange(df["High"], df["Low"], df["Close"], window=40).average_true_range()
    df["RSI4"] = RSIIndicator(df["Close"], window=4).rsi()
    df["HV20"] = np.log(df["Close"] / df["Close"].shift(1)).rolling(window=20).std() * np.sqrt(252) * 100
    df["DollarVolume50"] = (df["Close"] * df["Volume"]).rolling(window=50).mean()
    return df

#必要
def backtest_symbol(symbol, df, spy_df, capital):
    df = df.copy().dropna()
    spy_df = spy_df.copy().dropna()
    trades = []

    # Setup判定を先に追加
    df["Setup"] = (
        (df["Close"] > df["SMA200"]) &
        (df["DollarVolume50"] > 100_000_000) &
        (df["HV20"] >= 10) & (df["HV20"] <= 40)
    )

    setup_df = df[df["Setup"]].copy()
    setup_df["symbol"] = symbol
    ranked_df = setup_df.sort_values("RSI4")

    df = df.copy().dropna()
    spy_df = spy_df.copy().dropna()
    trades = []

    df["Setup"] = (
        (df["Close"] > df["SMA200"]) &
        (df["DollarVolume50"] > 100_000_000) &
        (df["HV20"] >= 10) & (df["HV20"] <= 40)
    )

    spy_df["SMA200"] = SMAIndicator(spy_df["Close"], window=200).sma_indicator()
    spy_condition = spy_df["Close"] > spy_df["SMA200"]

    risk_per_trade = 0.02 * capital
    max_position_value = 0.10 * capital

    active_until = None
    for i in range(1, len(df)):
        date = df.index[i]
        if active_until and date <= active_until:
            continue
        entry_price = df.at[date, "Open"]
        atr = df.at[date, "ATR40"]
        stop_price = entry_price - 1.5 * atr
        shares = risk_per_trade / (entry_price - stop_price)
        position_value = shares * entry_price
        if position_value > max_position_value:
            shares = max_position_value / entry_price
        shares = int(shares)

        # トレーリングストップ
        trail_stop = entry_price * 0.8

        # Exitルール
        exit_price = None
        exit_found = False
        exit_price = None
        exit_date = None
        for j in range(i+1, min(i+30, len(df))):  # 最大30営業日で終了
            next_close = df.iloc[j]["Close"]
            trail_stop = max(trail_stop, next_close * 0.8)
            if next_close < trail_stop:
                exit_price = df.iloc[j]["Close"]
                exit_date = df.index[j]
                break
        else:
            exit_price = df.iloc[-1]["Close"]
            exit_date = df.index[-1]
        active_until = exit_date

        pnl = (exit_price - entry_price) * shares
        return_pct = pnl / capital * 100

        trades.append({
            "symbol": symbol,
            "entry_date": date,
            "exit_date": exit_date,
            "entry": round(entry_price, 2),
            "exit": round(exit_price, 2),
            "shares": shares,
            "pnl": round(pnl, 2),
            "return_%": round(return_pct, 2)
        })

    return trades, setup_df, ranked_df


#差し替え
if __name__ == "__main__":
    st.title("システム4：ロング・トレンド・ロー・ボラティリティ")

    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"])
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力（例：AAPL,MSFT,NVDA）", "AAPL,MSFT,NVDA")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100)

    if st.button("バックテスト実行"):
        setup_df_list = []
        ranked_df_list = []
        all_trades = []
        symbols = [s.strip().upper() for s in symbols_input.split(",")]

        with st.spinner("データ取得中..."):
            spy_df = get_stooq_data("SPY") if data_source == "Stooq" else get_alpha_data("SPY")
            spy_df = apply_indicators(spy_df)

            for symbol in symbols:
                st.write(f"▶ 処理中: {symbol}")
                try:
                    df = get_stooq_data(symbol) if data_source == "Stooq" else get_alpha_data(symbol)
                    if df is None or df.empty:
                        st.warning(f"{symbol}: データ取得に失敗しました。")
                        continue
                    df = apply_indicators(df)
                    trades, setup_df, ranked_df = backtest_symbol(symbol, df, spy_df, capital)
                    setup_df_list.append(setup_df)
                    ranked_df_list.append(ranked_df)
                    all_trades.extend(trades)
                    if data_source == "Alpha Vantage":
                        time.sleep(12)
                except Exception as e:
                    st.error(f"{symbol}: エラーが発生しました - {e}")

    
    if setup_df_list:
        st.subheader("セットアップ条件を満たした銘柄（Setup=True）")
        setup_all = pd.concat(setup_df_list)
        st.dataframe(setup_all[["symbol", "Close", "RSI4", "HV20", "DollarVolume50"]])

    if ranked_df_list:
        st.subheader("仕掛け候補（RSI4が低い順）")
        ranked_all = pd.concat(ranked_df_list)
        ranked_sorted = ranked_all.sort_values("RSI4")
        st.dataframe(ranked_sorted[["symbol", "Close", "RSI4", "HV20"]])

    if all_trades:

            results = pd.DataFrame(all_trades)
            st.subheader("バックテスト結果")
            st.dataframe(results)

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
            plt.xlabel("Date")
            plt.ylabel("PnL (USD)")
            plt.title("累積損益")
            plt.legend()
            st.pyplot(plt)

            csv = results.to_csv(index=False).encode("utf-8")
            st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system4.csv", mime="text/csv")
    else:
        st.info("トレードは発生しませんでした。")
#不要
def run_tab():
    st.header("System4：ロング・トレンド・ロー・ボラティリティ")
    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"], key="system4_data_source")
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力（例：AAPL,MSFT,NVDA）", "AAPL,MSFT,NVDA", key="system4_symbols")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="system4_capital")

    if st.button("バックテスト実行", key="system4_button"):
        setup_df_list = []
        ranked_df_list = []
        all_trades = []
        symbols = [s.strip().upper() for s in symbols_input.split(",")]

        with st.spinner("データ取得中..."):
            spy_df = get_stooq_data("SPY") if data_source == "Stooq" else get_alpha_data("SPY")
            spy_df = apply_indicators(spy_df)

            for symbol in symbols:
                st.write(f"▶ 処理中: {symbol}")
                try:
                    df = get_stooq_data(symbol) if data_source == "Stooq" else get_alpha_data(symbol)
                    if df is None or df.empty:
                        st.warning(f"{symbol}: データ取得に失敗しました。")
                        continue
                    df = apply_indicators(df)
                    trades, setup_df, ranked_df = backtest_symbol(symbol, df, spy_df, capital)
                    setup_df_list.append(setup_df)
                    ranked_df_list.append(ranked_df)
                    all_trades.extend(trades)
                    if data_source == "Alpha Vantage":
                        time.sleep(12)
                except Exception as e:
                    st.error(f"{symbol}: エラーが発生しました - {e}")

        if setup_df_list:
            st.subheader("セットアップ条件を満たした銘柄（Setup=True）")
            setup_all = pd.concat(setup_df_list)
            st.dataframe(setup_all[["symbol", "Close", "RSI4", "HV20", "DollarVolume50"]])

        if ranked_df_list:
            st.subheader("仕掛け候補（RSI4が低い順）")
            ranked_all = pd.concat(ranked_df_list)
            ranked_sorted = ranked_all.sort_values("RSI4")
            st.dataframe(ranked_sorted[["symbol", "Close", "RSI4", "HV20"]])

        if all_trades:
            results = pd.DataFrame(all_trades)
            st.subheader("バックテスト結果")
            st.dataframe(results)

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
            plt.xlabel("Date")
            plt.ylabel("PnL (USD)")
            plt.title("累積損益")
            plt.legend()
            st.pyplot(plt)

            csv = results.to_csv(index=False).encode("utf-8")
            st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system4.csv", mime="text/csv")
        else:
            st.info("トレードは発生しませんでした。")
