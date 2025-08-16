
# app_system2_backtest_multi.py
import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import StringIO
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange
from alpha_vantage.timeseries import TimeSeries
import matplotlib.pyplot as plt
import time

API_KEY = "L88B2SED3UWSYXGN"

#差し替え
@st.cache_data(ttl=86400)
def get_stooq_data(symbol):
    url = f"https://stooq.com/q/d/l/?s={symbol.lower()}.us&i=d"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    df = pd.read_csv(StringIO(response.text))
    df = df.rename(columns={
        "Date": "date",
        "Open": "Open",
        "High": "High",
        "Low": "Low",
        "Close": "Close",
        "Volume": "Volume"
    })
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
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

#　必要
def apply_indicators(df):
    df["RSI3"] = RSIIndicator(close=df["Close"], window=3).rsi()
    df["ADX7"] = ADXIndicator(high=df["High"], low=df["Low"], close=df["Close"], window=7).adx()
    df["ATR10"] = AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=10).average_true_range()
    df["DollarVolume20"] = (df["Close"] * df["Volume"]).rolling(window=20).mean()
    df["ATR_Ratio"] = df["ATR10"] / df["Close"]
    df["Filter_Pass"] = (df["Close"] > 5) & (df["DollarVolume20"] > 25_000_000) & (df["ATR_Ratio"] > 0.03)
    df["TwoDayUp"] = (df["Close"] > df["Close"].shift(1)) & (df["Close"].shift(1) > df["Close"].shift(2))
    df["Setup"] = (df["RSI3"] > 90) & (df["TwoDayUp"]) & (df["Filter_Pass"])
    return df

#　必要？
def backtest_symbol(symbol, df, capital, rank_limit=3):
    trades = []
    risk_per_trade = 0.02 * capital
    max_position_value = 0.10 * capital

    df = df.copy().dropna()
    setup_df = df[df["Setup"]].copy()
    setup_df["DateOnly"] = setup_df.index.date
    grouped_by_day = setup_df.groupby("DateOnly")

    for day, group in grouped_by_day:
        ranked = group.sort_values("ADX7", ascending=False).head(rank_limit)
        for date in ranked.index:
            if date not in df.index or date + pd.Timedelta(days=1) not in df.index:
                continue
            entry_idx = df.index.get_loc(date) + 1
            if entry_idx >= len(df) - 3:
                continue

            entry_day = df.iloc[entry_idx]
            prior_close = df.iloc[entry_idx - 1]["Close"]
            required_price = prior_close * 1.04

            if entry_day["Open"] < required_price:
                continue

            entry_price = entry_day["Open"]
            atr = df.iloc[entry_idx - 1]["ATR10"]
            stop_price = entry_price + 3 * atr
            shares = risk_per_trade / (stop_price - entry_price)
            position_value = shares * entry_price
            if position_value > max_position_value:
                shares = max_position_value / entry_price

            entry_date = entry_day.name

            exit_idx = entry_idx + 2
            if exit_idx >= len(df):
                continue
            for offset in [0, 1]:
                price_check = df.iloc[entry_idx + offset]["Close"]
                if (entry_price - price_check) / entry_price >= 0.04:
                    exit_idx = entry_idx + offset + 1
                    break

            exit_day = df.iloc[exit_idx]
            exit_price = exit_day["Close"]
            exit_date = exit_day.name

            pnl = (entry_price - exit_price) * shares
            pct_return = pnl / capital

            trades.append({
                "symbol": symbol,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry": round(entry_price, 2),
                "exit": round(exit_price, 2),
                "shares": int(shares),
                "pnl": round(pnl, 2),
                "return_%": round(pct_return * 100, 2)
            })

    return trades

#　必要
if __name__ == "__main__":
    st.title("システム2：複数銘柄バックテスト（RSIショート）")

    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"])
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力（例：AAPL,MSFT,NVDA）", "AAPL,MSFT,NVDA")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100)
    rank_limit = st.number_input("同日エントリー銘柄上限（ADX上位）", min_value=1, value=3, step=1)

    if st.button("バックテスト実行"):
        all_trades = []
        symbols = [s.strip().upper() for s in symbols_input.split(",")]
        for i, symbol in enumerate(symbols):
            st.write(f"▶ 処理中: {symbol}")
            try:
                df = get_stooq_data(symbol) if data_source == "Stooq" else get_alpha_data(symbol)
                if df is None or df.empty:
                    st.warning(f"{symbol}: データ取得に失敗しました。")
                    continue
                @st.cache_data
                def apply_indicators(df):
                    df = df.copy()
                symbol_trades = backtest_symbol(symbol, df, capital)
                all_trades.extend(symbol_trades)
                if data_source == "Alpha Vantage":
                    time.sleep(12)  # レート制限対策
            except Exception as e:
                st.error(f"{symbol}: エラーが発生しました - {e}")

        if all_trades:
            results = pd.DataFrame(all_trades)
            st.subheader("バックテスト結果")
            st.dataframe(results)

            total_return = results["pnl"].sum()
            win_rate = (results["return_%"] > 0).mean() * 100
            st.metric("トレード回数", len(results))
            st.metric("最終損益（USD）", f"{total_return:.2f}")
            st.metric("勝率（％）", f"{win_rate:.2f}")

            st.subheader("累積損益グラフ")
        
            results["exit_date"] = pd.to_datetime(results["exit_date"])
            results = results.sort_values("exit_date")
            results["cumulative_pnl"] = results["pnl"].cumsum()
            results["cum_max"] = results["cumulative_pnl"].cummax()
            results["drawdown"] = results["cumulative_pnl"] - results["cum_max"]
            max_dd = results["drawdown"].min()
            st.metric("最大ドローダウン（USD）", f"{max_dd:.2f}")

            plt.figure(figsize=(10, 4))
            plt.plot(results["exit_date"], results["cumulative_pnl"], label="Cumulative PnL")
            plt.xlabel("Date")
            plt.ylabel("PnL (USD)")
            plt.title("累積損益")
            plt.legend()
            st.pyplot(plt)

            csv = results.to_csv(index=False).encode("utf-8")
            st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log.csv", mime="text/csv")

        else:
            st.info("トレードは発生しませんでした。")

#不要（手動単体テスト）
def run_tab():
    st.header("System2：ショート RSIスラスト（複数銘柄）")
    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"], key="system2_data_source")
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力", "AAPL,MSFT,NVDA", key="system2_symbols")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="system2_capital")
    rank_limit = st.slider("同日最大仕掛け数（ADX上位）", 1, 10, 3, key="system2_rank_limit")

    if st.button("バックテスト実行", key="system2_button"):
        all_trades = []
        symbols = [s.strip().upper() for s in symbols_input.split(",")]
        for symbol in symbols:
            st.write(f"▶ 処理中: {symbol}")
            try:
                df = get_stooq_data(symbol) if data_source == "Stooq" else get_alpha_data(symbol)
                if df is None or df.empty:
                    st.warning(f"{symbol}: データ取得に失敗しました。")
                    continue
                df = apply_indicators(df)
                trades = backtest_symbol(symbol, df, capital, rank_limit)
                all_trades.extend(trades)
                if data_source == "Alpha Vantage":
                    time.sleep(12)
            except Exception as e:
                st.error(f"{symbol}: エラーが発生しました - {e}")

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
            plt.figure(figsize=(10, 4))
            plt.plot(results["exit_date"], results["cumulative_pnl"], label="Cumulative PnL")
            plt.xlabel("Date")
            plt.ylabel("PnL (USD)")
            plt.title("累積損益")
            plt.legend()
            st.pyplot(plt)
            csv = results.to_csv(index=False).encode("utf-8")
            st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system2.csv", mime="text/csv")
        else:
            st.info("トレードは発生しませんでした。")
