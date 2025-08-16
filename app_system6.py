# app_system6.py
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
    df["ATR10"] = AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=10).average_true_range()
    df["DollarVolume50"] = (df["Close"] * df["Volume"]).rolling(50).mean()
    df["6D_Return"] = df["Close"].pct_change(6)
    df["UpTwoDays"] = (df["Close"] > df["Close"].shift(1)) & (df["Close"].shift(1) > df["Close"].shift(2))
    return df

#必要
def backtest_symbol(symbol, df, capital, rank_limit):
    df = df.copy().dropna()
    trades = []

    df["Setup"] = (
        (df["Close"] > 5) &
        (df["DollarVolume50"] > 10_000_000) &
        (df["6D_Return"] > 0.20) &
        (df["UpTwoDays"])
    )

    setup_df = df[df["Setup"]].copy()
    setup_df["symbol"] = symbol
    ranked_df = setup_df.sort_values("6D_Return", ascending=False).head(rank_limit)

    risk_per_trade = 0.02 * capital
    max_position_value = 0.10 * capital

    active_until = None
    for idx, row in ranked_df.iterrows():
        entry_idx = df.index.get_loc(idx) + 1
        if entry_idx >= len(df) - 3:
            continue
        prev_close = df.iloc[entry_idx - 1]["Close"]
        entry_price = round(prev_close * 1.05, 2)
        date = idx
        if active_until and date <= active_until:
            continue
        if df.iloc[entry_idx]["High"] < entry_price:
            continue

        atr = df.iloc[entry_idx - 1]["ATR10"]
        stop_price = entry_price + 3 * atr
        shares = risk_per_trade / (stop_price - entry_price)
        position_value = shares * entry_price
        if position_value > max_position_value:
            shares = max_position_value / entry_price
        shares = int(shares)
        entry_date = df.index[entry_idx]

        exit_price = None
        exit_date = None
        active_until = exit_date
        exit_price = None
        exit_date = None
        for offset in range(1, 4):
            idx2 = entry_idx + offset
            if idx2 >= len(df):
                break
            future_close = df.iloc[idx2]["Close"]
            gain = (entry_price - future_close) / entry_price
            if gain >= 0.05:
                exit_date = df.index[idx2 + 1] if idx2 + 1 < len(df) else df.index[idx2]
                exit_price = df.loc[exit_date]["Open"] if exit_date in df.index else future_close
                break
        else:
            idx2 = entry_idx + 3
            if idx2 < len(df):
                exit_date = df.index[idx2 + 1] if idx2 + 1 < len(df) else df.index[idx2]
                exit_price = df.loc[exit_date]["Open"] if exit_date in df.index else df.iloc[idx2]["Close"]
        active_until = exit_date
        pnl = (entry_price - exit_price) * shares
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

#必要
if __name__ == "__main__":
    st.title("システム6：ショート・ミーン・リバージョン・ハイ・シックスデイサージ")

    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"])
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力（例：AAPL,MSFT,NVDA）", "AAPL,MSFT,NVDA")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100)
    rank_limit = st.number_input("同日エントリー銘柄上限（6日上昇率上位）", min_value=1, value=3, step=1)

    if st.button("バックテスト実行"):
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
                trades, setup_df, ranked_df = backtest_symbol(symbol, df, capital, rank_limit)
                all_trades.extend(trades)
                setup_df_list.append(setup_df)
                ranked_df_list.append(ranked_df)
                if data_source == "Alpha Vantage":
                    time.sleep(12)
            except Exception as e:
                st.error(f"{symbol}: エラーが発生しました - {e}")

        if all_trades:
            st.subheader("仕掛け候補（6日騰落率上位）")
            if ranked_df_list:
                ranked_all = pd.concat(ranked_df_list)
                st.dataframe(ranked_all[["symbol", "Close", "6D_Return"]].sort_values("6D_Return", ascending=False))

            st.subheader("セットアップ条件を満たした銘柄")
            if setup_df_list:
                setup_all = pd.concat(setup_df_list)
                st.dataframe(setup_all[["symbol", "Close", "6D_Return"]])

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
            st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system6.csv", mime="text/csv")
        else:
            st.info("トレードは発生しませんでした。")

#不要
def run_tab():
    st.header("System6：ショート・ミーン・リバージョン・シックスデイサージ")
    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"], key="system6_data_source")
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力（例：AAPL,MSFT,NVDA）", "AAPL,MSFT,NVDA", key="system6_symbols")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="system6_capital")
    rank_limit = st.slider("同日エントリー銘柄上限（6日上昇率上位）", min_value=1, max_value=10, value=3, key="system6_rank_limit")

    if st.button("バックテスト実行", key="system6_button"):
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
                trades, setup_df, ranked_df = backtest_symbol(symbol, df, capital, rank_limit)
                all_trades.extend(trades)
                setup_df_list.append(setup_df)
                ranked_df_list.append(ranked_df)
                if data_source == "Alpha Vantage":
                    time.sleep(12)
            except Exception as e:
                st.error(f"{symbol}: エラーが発生しました - {e}")

        if all_trades:
            st.subheader("仕掛け候補（6日騰落率上位）")
            if ranked_df_list:
                ranked_all = pd.concat(ranked_df_list)
                st.dataframe(ranked_all[["symbol", "Close", "6D_Return"]].sort_values("6D_Return", ascending=False))

            st.subheader("セットアップ条件を満たした銘柄")
            if setup_df_list:
                setup_all = pd.concat(setup_df_list)
                st.dataframe(setup_all[["symbol", "Close", "6D_Return"]])

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
            st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system6.csv", mime="text/csv")
        else:
            st.info("トレードは発生しませんでした。")
