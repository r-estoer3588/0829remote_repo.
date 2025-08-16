# app_system7.py
import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import StringIO
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
    df["ATR50"] = AverageTrueRange(df["High"], df["Low"], df["Close"], window=50).average_true_range()
    df["min_50"] = df["Close"].rolling(window=50).min()
    df["max_70"] = df["Close"].rolling(window=70).max()
    return df

#必要
def backtest_spy(df, capital):
    df = df.copy().dropna()
    trades = []
    risk_per_trade = 0.02 * capital
    max_position_value = 0.20 * capital
    position_open = False

    for i in range(1, len(df) - 1):
        today = df.index[i]
        row = df.iloc[i]

        if not position_open and row["Close"] <= row["min_50"]:
            entry_price = df.iloc[i + 1]["Open"]
            atr = row["ATR50"]
            stop_price = entry_price + 3 * atr
            shares = risk_per_trade / (stop_price - entry_price)
            position_value = shares * entry_price
            if position_value > max_position_value:
                shares = max_position_value / entry_price
            shares = int(shares)
            entry_date = df.index[i + 1]
            position_open = True
            trades.append({
                "symbol": "SPY",
                "entry_date": entry_date,
                "entry": round(entry_price, 2),
                "shares": shares,
                "stop": round(stop_price, 2),
                "exit": None,
                "exit_date": None,
                "pnl": None
            })

        elif position_open:
            last_trade = trades[-1]
            if row["Close"] >= row["max_70"]:
                exit_price = df.iloc[i + 1]["Open"]
                exit_date = df.index[i + 1]
                pnl = (last_trade["entry"] - exit_price) * last_trade["shares"]
                last_trade.update({
                    "exit": round(exit_price, 2),
                    "exit_date": exit_date,
                    "pnl": round(pnl, 2)
                })
                position_open = False

    trades = [t for t in trades if t["exit"] is not None]
    return pd.DataFrame(trades)


#必要
if __name__ == "__main__":
    st.title("システム7：カタストロフィーヘッジ（SPY）")

    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"])
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100)

    if st.button("バックテスト実行"):
        try:
            df = get_stooq_data("SPY") if data_source == "Stooq" else get_alpha_data("SPY")
            if df is None or df.empty:
                st.error("SPYデータの取得に失敗しました。")
            else:
                df = apply_indicators(df)
                results = backtest_spy(df, capital)
                if results.empty:
                    st.info("トレードは発生しませんでした。")
                else:
                    st.subheader("バックテスト結果")
                    st.dataframe(results)
                    total_return = results["pnl"].sum()
                    win_rate = (results["pnl"] > 0).mean() * 100
                    st.metric("トレード回数", len(results))
                    st.metric("最終損益（USD）", f"{total_return:.2f}")
                    st.metric("勝率（％）", f"{win_rate:.2f}")

                    results = results.copy()
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
                    st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system7.csv", mime="text/csv")
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")

#不要
def run_tab():
    st.header("System7：カタストロフィーヘッジ（SPY）")
    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"], key="system7_data_source")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="system7_capital")

    if st.button("バックテスト実行", key="system7_button"):
        try:
            df = get_stooq_data("SPY") if data_source == "Stooq" else get_alpha_data("SPY")
            if df is None or df.empty:
                st.error("SPYデータの取得に失敗しました。")
            else:
                df = apply_indicators(df)
                results = backtest_spy(df, capital)
                if results.empty:
                    st.info("トレードは発生しませんでした。")
                else:
                    st.subheader("バックテスト結果")
                    st.dataframe(results)

                    total_return = results["pnl"].sum()
                    win_rate = (results["pnl"] > 0).mean() * 100
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
                    st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system7.csv", mime="text/csv")
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
