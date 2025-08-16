import os
import pandas as pd
import requests
from dotenv import load_dotenv

# Streamlit がある場合だけインポート
try:
    import streamlit as st
    USE_STREAMLIT = True
except ImportError:
    USE_STREAMLIT = False

# 出力関数ラッパー
def log_info(msg):
    if USE_STREAMLIT:
        st.info(msg)
    else:
        print(f"[INFO] {msg}")

def log_success(msg):
    if USE_STREAMLIT:
        st.success(msg)
    else:
        print(f"[SUCCESS] {msg}")

def log_warning(msg):
    if USE_STREAMLIT:
        st.warning(msg)
    else:
        print(f"[WARN] {msg}")

def log_error(msg):
    if USE_STREAMLIT:
        st.error(msg)
    else:
        print(f"[ERROR] {msg}")

# .envからAPIキー取得
load_dotenv()
API_KEY = os.getenv("EODHD_API_KEY")

def fetch_and_cache_spy_from_eodhd(folder="data_cache"):
    symbol = "SPY"
    url = f"https://eodhistoricaldata.com/api/eod/{symbol}.US?api_token={API_KEY}&period=d&fmt=json"
    path = os.path.join(folder, f"{symbol}.csv")

    try:
        log_info(f"URL: {url}")
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            log_warning("データが空です。APIキーまたはリクエスト制限を確認してください。")
            return
        df = pd.DataFrame(data)
        log_info(f"データ件数: {len(df)}")
        df["date"] = pd.to_datetime(df["date"])
        df = df.rename(columns={
            "date": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "adjusted_close": "AdjClose",
            "volume": "Volume"
        })
        os.makedirs(folder, exist_ok=True)
        df.to_csv(path, index=False)
        log_success(f"SPY.csv を保存しました: {path}")
    except Exception as e:
        log_error(f"例外が発生しました: {e}")

# 実行
if __name__ == "__main__":
    fetch_and_cache_spy_from_eodhd()
