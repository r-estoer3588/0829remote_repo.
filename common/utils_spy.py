# common/utils_spy.py
import os
import pandas as pd
import pandas_market_calendars as mcal
from datetime import time as dtime
from ta.trend import SMAIndicator
import subprocess
import streamlit as st


def get_latest_nyse_trading_day(today=None):
    nyse = mcal.get_calendar("NYSE")
    if today is None:
        today = pd.Timestamp.today().normalize()
    sched = nyse.schedule(
        start_date=today - pd.Timedelta(days=7),
        end_date=today + pd.Timedelta(days=1),
    )
    valid_days = sched.index.normalize()
    return valid_days[valid_days <= today].max()


def get_spy_data_cached(folder="data_cache"):
    """
    SPY.csv をキャッシュから読み込み、古ければ recover_spy_cache.py を呼んで更新。
    """
    path = os.path.join(folder, "SPY.csv")
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, parse_dates=["Date"])
            if "Date" not in df.columns:
                return None
            df.set_index("Date", inplace=True)
            df = df.sort_index()
            return df
        except Exception as e:
            st.error(f"❌ SPY読み込み失敗: {e}")
            return None
    else:
        st.error("❌ SPY.csv が存在しません")
        return None


def get_spy_with_indicators(spy_df=None):
    """
    SPY に SMA100 / SMA200 を付与（フィルターは戦略側で判定する）
    """
    if spy_df is None:
        spy_df = get_spy_data_cached()
    if spy_df is not None and not spy_df.empty:
        spy_df["SMA100"] = SMAIndicator(spy_df["Close"], window=100).sma_indicator()
        spy_df["SMA200"] = SMAIndicator(spy_df["Close"], window=200).sma_indicator()
    return spy_df
