import os
import pandas as pd
import requests
from dotenv import load_dotenv

# .envからAPIキー取得
load_dotenv()
API_KEY = os.getenv("EODHD_API_KEY")

def fetch_and_cache_spy_from_eodhd(folder="data_cache"):
    symbol = "SPY"
    url = f"https://eodhistoricaldata.com/api/eod/{symbol}.US?api_token={API_KEY}&period=d&fmt=json"
    path = os.path.join(folder, f"{symbol}.csv")

    try:
        print(f"🔄 URL: {url}")
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            print("⚠ データが空です。APIキーまたはリクエスト制限を確認してください。")
            return
        df = pd.DataFrame(data)
        print(f"✅ データ件数: {len(df)}")
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
        print(f"✅ SPY.csv を保存しました: {path}")
    except Exception as e:
        print(f"❌ 例外が発生しました: {e}")

# 実行
fetch_and_cache_spy_from_eodhd()
