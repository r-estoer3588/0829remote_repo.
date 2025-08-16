
# app_system3_v2.py
import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import StringIO
from ta.trend import SMAIndicator
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

#　必要
@st.cache_data
def apply_indicators(df):
    df = df.copy()
    df["SMA150"] = SMAIndicator(close=df["Close"], window=150).sma_indicator()
    df["ATR10"] = AverageTrueRange(df["High"], df["Low"], df["Close"], window=10).average_true_range()
    df["Return_3D"] = df["Close"].pct_change(3)
    df["AvgVolume50"] = df["Volume"].rolling(50).mean()
    df["ATR_Ratio"] = df["ATR10"] / df["Close"]
    return df

#　必要？
def backtest_symbol(symbol, df, capital):
    df = df.copy().dropna()
    trades = []

    df["Setup"] = (df["Close"] > df["SMA150"]) & (df["Return_3D"] <= -0.125) &                   (df["Close"] > 1) & (df["AvgVolume50"] >= 1_000_000) & (df["ATR_Ratio"] >= 0.05)

    setup_df = df[df["Setup"]].copy()
    setup_df["symbol"] = symbol
    ranked_df = setup_df.sort_values("Return_3D")

    risk_per_trade = 0.02 * capital
    max_position_value = 0.10 * capital

    active_until = None
    for idx, row in ranked_df.iterrows():
        entry_idx = df.index.get_loc(idx) + 1
        if entry_idx >= len(df) - 3:
            continue
        prev_close = df.iloc[entry_idx - 1]["Close"]
        entry_price = round(prev_close * 0.93, 2)
        date = idx
        if active_until and date <= active_until:
            continue
        atr = df.iloc[entry_idx - 1]["ATR10"]
        stop_price = entry_price - 2.5 * atr
        shares = risk_per_trade / (entry_price - stop_price)
        position_value = shares * entry_price
        if position_value > max_position_value:
            shares = max_position_value / entry_price

        shares = int(shares)
        entry_date = df.index[entry_idx]

        exit_date = None
        active_until = exit_date
        exit_price = None
        exit_price = None
        exit_date = None
        for offset in range(1, 4):
            idx2 = entry_idx + offset
            if idx2 >= len(df):
                break
            future_close = df.iloc[idx2]["Close"]
            gain = (future_close - entry_price) / entry_price
            if gain >= 0.04:
                exit_date = df.index[idx2 + 1] if idx2 + 1 < len(df) else df.index[idx2]
                exit_price = df.loc[exit_date]["Close"] if exit_date in df.index else future_close
                break
        else:
            idx2 = entry_idx + 3
            if idx2 < len(df):
                exit_date = df.index[idx2 + 1] if idx2 + 1 < len(df) else df.index[idx2]
                exit_price = df.loc[exit_date]["Close"] if exit_date in df.index else df.iloc[idx2]["Close"]
        active_until = exit_date
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
    st.title("システム3：ロング・ミーン・リバージョン・セルオフ（複数銘柄）")
    
    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"])
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力（例：AAPL,MSFT,NVDA）", "AAPL,MSFT,NVDA")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100)

    if st.button("バックテスト実行"):
        all_trades = []
        all_setups = []
        all_ranked = []
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
                all_setups.append(setup_df)
                all_ranked.append(ranked_df)
                if data_source == "Alpha Vantage":
                    time.sleep(12)
            except Exception as e:
                st.error(f"{symbol}: エラーが発生しました - {e}")

        if all_trades:
            st.subheader("仕掛け候補一覧（ランキング順）")
            if all_ranked:
                ranked_concat = pd.concat(all_ranked)
                ranked_concat = ranked_concat[["symbol", "Close", "Return_3D", "ATR_Ratio"]]
                st.dataframe(ranked_concat.sort_values("Return_3D"))

            st.subheader("セットアップ条件を満たした銘柄（Setup=True）")
            if all_setups:
                setup_concat = pd.concat(all_setups)
                setup_concat = setup_concat[["symbol", "Close", "Return_3D", "ATR_Ratio"]]
                st.dataframe(setup_concat)

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
            st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system3.csv", mime="text/csv")

        else:
            st.info("トレードは発生しませんでした。")

#不要
def run_tab():
    st.header("System3：ロング・ミーン・リバージョン・セルオフ")
    data_source = st.radio("データソース", ["Stooq", "Alpha Vantage"], key="system3_data_source")
    symbols_input = st.text_input("ティッカーをカンマ区切りで入力", "AAPL,MSFT,NVDA", key="system3_symbols")
    capital = st.number_input("総資金（USD）", min_value=1000, value=1000, step=100, key="system3_capital")

    if st.button("バックテスト実行", key="system3_button"):
        all_trades = []
        all_setups = []
        all_ranked = []
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
                all_setups.append(setup_df)
                all_ranked.append(ranked_df)
                if data_source == "Alpha Vantage":
                    time.sleep(12)
            except Exception as e:
                st.error(f"{symbol}: エラーが発生しました - {e}")

        if all_trades:
            ranked_concat = pd.concat(all_ranked)
            st.subheader("仕掛け候補一覧（ランキング順）")
            st.dataframe(ranked_concat[["symbol", "Close", "Return_3D", "ATR_Ratio"]].sort_values("Return_3D"))

            setup_concat = pd.concat(all_setups)
            st.subheader("セットアップ条件を満たした銘柄")
            st.dataframe(setup_concat[["symbol", "Close", "Return_3D", "ATR_Ratio"]])

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
            st.download_button("売買ログをCSVで保存", data=csv, file_name="trade_log_system3.csv", mime="text/csv")
        else:
            st.info("トレードは発生しませんでした。")
