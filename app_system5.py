# app_system5.py
import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import StringIO
from ta.trend import SMAIndicator, ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
from alpha_vantage.timeseries import TimeSeries
import matplotlib.pyplot as plt
import time

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
    df["SMA100"] = SMAIndicator(close=df["Close"], window=100).sma_indicator()
    df["ATR10"] = AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=10).average_true_range()
    df["ADX7"] = ADXIndicator(high=df["High"], low=df["Low"], close=df["Close"], window=7).adx()
    df["RSI3"] = RSIIndicator(close=df["Close"], window=3).rsi()
    df["AvgVolume50"] = df["Volume"].rolling(50).mean()
    df["DollarVolume50"] = (df["Close"] * df["Volume"]).rolling(50).mean()
    df["ATR_Pct"] = df["ATR10"] / df["Close"]
    return df

# 必要
def backtest_symbol(symbol, df, capital):
    df = df.copy().dropna()
    trades = []

    df["Setup"] = (
        (df["Close"] > df["SMA100"] + df["ATR10"]) &
        (df["ADX7"] > 55) &
        (df["RSI3"] < 50) &
        (df["AvgVolume50"] > 500_000) &
        (df["DollarVolume50"] > 2_500_000) &
        (df["ATR_Pct"] > 0.04)
    )

    setup_df = df[df["Setup"]].copy()
    setup_df["symbol"] = symbol
    ranked_df = setup_df.sort_values("ADX7", ascending=False)

    risk_per_trade = 0.02 * capital
    max_position_value = 0.10 * capital

    active_until = None
    for idx, row in ranked_df.iterrows():
        entry_idx = df.index.get_loc(idx) + 1
        if entry_idx >= len(df) - 6:
            continue
        prev_close = df.iloc[entry_idx - 1]["Close"]
        entry_price = round(prev_close * 0.97, 2)
        date = idx
        if active_until and date <= active_until:
            continue
        if df.iloc[entry_idx]["Low"] > entry_price:
            continue

        atr = df.iloc[entry_idx - 1]["ATR10"]
        stop_price = entry_price - 3 * atr
        shares = risk_per_trade / (entry_price - stop_price)
        position_value = shares * entry_price
        if position_value > max_position_value:
            shares = max_position_value / entry_price
        shares = int(shares)
        entry_date = df.index[entry_idx]

        exit_price = None
        exit_date = None
        active_until = exit_date
        for offset in range(1, 7):
            idx2 = entry_idx + offset
            if idx2 >= len(df):
                break
            future_close = df.iloc[idx2]["Close"]
            if (future_close - entry_price) >= atr:
                exit_date = df.index[idx2 + 1] if idx2 + 1 < len(df) else df.index[idx2]
            active_until = exit_date
            exit_price = df.loc[exit_date]["Open"] if exit_date in df.index else future_close
            break
        if exit_price is None:
            idx2 = entry_idx + 6
            if idx2 < len(df):
                exit_date = df.index[idx2 + 1] if idx2 + 1 < len(df) else df.index[idx2]
            active_until = exit_date
            exit_price = df.loc[exit_date]["Open"] if exit_date in df.index else df.iloc[idx2]["Close"]

        pnl = (exit_price - entry_price) * shares
        return_pct = pnl / capital * 100

        trades.append({
            "symbol": symbol,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry": entry_price,
            "exit": round(exit_price, 2),
            "shares": shares,
            "pnl": round(pnl, 2),
            "return_%": round(return_pct, 2)
        })

    return trades, setup_df, ranked_df

#差し替え
if __name__ == "__main__":
    st.title("システム5：ロング・ミーン・リバージョン・ハイADX・リバーサル")

    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"], key="system5_data_source")
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力（例：AAPL,MSFT,NVDA）", "AAPL,MSFT,NVDA", key="system5_symbols_input")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100)

    if st.button("バックテスト実行", key="system5_backtest_button"):
        all_trades = []
        setup_df_list = []
        ranked_df_list = []
        symbols = [s.strip().upper() for s in symbols_input.split(",")]

        for symbol in symbols:
            st.write(f"▶ 処理中: {symbol}")
            try:
                df = get_stooq_data(symbol) if data_source == "Stooq" else get_alpha_data(symbol)
                if df is None or df.empty:
                    st.warning(f"{symbol}: データ取得に失敗しました。")
                    continue
                df = apply_indicators(df)
                trades, setup_df, ranked_df = backtest_symbol(symbol, df, capital)
                all_trades.extend(trades)
                setup_df_list.append(setup_df)
                ranked_df_list.append(ranked_df)
                if data_source == "Alpha Vantage":
                    time.sleep(12)
            except Exception as e:
                st.error(f"{symbol}: エラーが発生しました - {e}")

        if all_trades:
            st.subheader("仕掛け候補（ランキング順：ADX7）")
            if ranked_df_list:
                ranked_all = pd.concat(ranked_df_list)
                st.dataframe(ranked_all[["symbol", "Close", "ADX7", "RSI3"]].sort_values("ADX7", ascending=False))

            st.subheader("セットアップ条件を満たした銘柄")
            if setup_df_list:
                setup_all = pd.concat(setup_df_list)
                st.dataframe(setup_all[["symbol", "Close", "ADX7", "RSI3"]])

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
            st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system5.csv", mime="text/csv")
        else:
            st.info("トレードは発生しませんでした。")

#不要
def run_tab():
    st.header("System5：ロング・ミーン・リバージョン・ハイADX・リバーサル")
    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"], key="system5_data_source")
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力（例：AAPL,MSFT,NVDA）", "AAPL,MSFT,NVDA", key="system5_symbols")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="system5_capital")

    if st.button("バックテスト実行", key="system5_button"):
        all_trades = []
        setup_df_list = []
        ranked_df_list = []
        symbols = [s.strip().upper() for s in symbols_input.split(",")]

        for symbol in symbols:
            st.write(f"▶ 処理中: {symbol}")
            try:
                df = get_stooq_data(symbol) if data_source == "Stooq" else get_alpha_data(symbol)
                if df is None or df.empty:
                    st.warning(f"{symbol}: データ取得に失敗しました。")
                    continue
                df = apply_indicators(df)
                trades, setup_df, ranked_df = backtest_symbol(symbol, df, capital)
                all_trades.extend(trades)
                setup_df_list.append(setup_df)
                ranked_df_list.append(ranked_df)
                if data_source == "Alpha Vantage":
                    time.sleep(12)
            except Exception as e:
                st.error(f"{symbol}: エラーが発生しました - {e}")

        if all_trades:
            st.subheader("仕掛け候補（ランキング順：ADX7）")
            if ranked_df_list:
                ranked_all = pd.concat(ranked_df_list)
                st.dataframe(ranked_all[["symbol", "Close", "ADX7", "RSI3"]].sort_values("ADX7", ascending=False))

            st.subheader("セットアップ条件を満たした銘柄")
            if setup_df_list:
                setup_all = pd.concat(setup_df_list)
                st.dataframe(setup_all[["symbol", "Close", "ADX7", "RSI3"]])

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
            st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system5.csv", mime="text/csv")
        else:
            st.info("トレードは発生しませんでした。")
