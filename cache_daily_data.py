import pandas as pd
import requests
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import os
from ta.trend import SMAIndicator
from ta.momentum import ROCIndicator
from ta.volatility import AverageTrueRange
from indicators_common import add_indicators

FAILED_LIST = "eodhd_failed_symbols.csv"


def load_failed_symbols():
    if os.path.exists(FAILED_LIST):
        return set(pd.read_csv(FAILED_LIST, header=None)[0].astype(str).str.upper())
    return set()


def save_failed_symbols(new_failed):
    old_failed = load_failed_symbols()
    updated_failed = old_failed | set([s.upper() for s in new_failed])
    pd.Series(list(updated_failed)).to_csv(FAILED_LIST, index=False, header=False)


# .envからAPIキーを読み込み（相対的なパス）
load_dotenv(dotenv_path=r".env")
API_KEY = os.getenv("EODHD_API_KEY")

# ロギング設定
logging.basicConfig(
    filename="cache_log.txt",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_all_symbols():
    urls = [
        "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
        "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
    ]
    symbols = set()
    for url in urls:
        try:
            r = requests.get(url)
            lines = r.text.splitlines()
            for line in lines[1:]:
                if "|" in line:
                    parts = line.split("|")
                    if parts[0].isalpha():
                        symbols.add(parts[0])
        except Exception as e:
            logging.error(f"取得失敗: {url} - {e}")
    return sorted(symbols)


def get_with_retry(url, retries=3, delay=2):
    for i in range(retries):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return r
            logging.warning(f"ステータスコード {r.status_code} - {url}")
        except Exception as e:
            logging.warning(f"試行{i + 1}回目のエラー: {e}")
        time.sleep(delay)
    return None


def get_eodhd_data(symbol):
    url = f"https://eodhistoricaldata.com/api/eod/{symbol}.US?api_token={API_KEY}&period=d&fmt=json"
    r = get_with_retry(url)
    if r is None:
        return None
    try:
        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            logging.warning(f"{symbol}: 空または無効なJSON応答")
            return None
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.rename(
            columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "adjusted_close": "AdjClose",
                "volume": "Volume",
            }
        )
        df.set_index("Date", inplace=True)
        df = df.sort_index()
        return df
    except Exception as e:
        logging.error(f"{symbol}: データ整形中のエラー - {e}")
        return None


RESERVED_WORDS = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def safe_filename(symbol):
    # Windows予約語を避ける（大文字小文字無視）
    if symbol.upper() in RESERVED_WORDS:
        return symbol + "_RESV"
    return symbol


def cache_single(symbol, output_dir):
    safe_symbol = safe_filename(symbol)
    filepath = os.path.join(output_dir, f"{safe_symbol}.csv")
    if os.path.exists(filepath):
        mod_time = datetime.fromtimestamp(os.path.getmtime(filepath))
        if mod_time.date() == datetime.today().date():
            return f"{symbol}: already cached", False  # False = no API call
    df = get_eodhd_data(symbol)
    if df is not None and not df.empty:
        df = add_indicators(df)  # ← ここで指標を追加
        df.to_csv(filepath)
        return f"{symbol}: saved", True  # True = API call used
    else:
        return f"{symbol}: failed to fetch", True


def cache_data(symbols, output_dir="data_cache", max_workers=5):
    os.makedirs(output_dir, exist_ok=True)
    failed = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(cache_single, symbol, output_dir): symbol
            for symbol in symbols
        }
        results_list = []
        for i, future in enumerate(as_completed(futures)):
            result, used_api = future.result()
            symbol = futures[future]
            results_list.append((symbol, result, used_api))
            logging.info(result)
            print(f"[{i}] {result}")
            if "failed" in result:
                failed.append(futures[future])
            if used_api:
                time.sleep(1.5)  # API使用時のみスロットリング

    # ブラックリストへ追記
    if failed:
        save_failed_symbols(failed)

    # 処理件数のログ（results_listから集計）
    cached_count = sum(1 for _, _, used_api in results_list if not used_api)
    api_count = sum(1 for _, _, used_api in results_list if used_api)
    print(
        f"✅ キャッシュ済み: {cached_count}件, API使用: {api_count}件, 失敗: {
            len(failed)}件"
    )


if __name__ == "__main__":
    # symbols = get_all_symbols()[:3]  # 無料プラン対策（テスト用）
    symbols = get_all_symbols()
    # ブラックリスト除外
    failed_symbols = load_failed_symbols()
    symbols = [s for s in symbols if s.upper() not in failed_symbols]
    print(f"{len(symbols)}銘柄を取得します（ブラックリスト除外後）")
    cache_data(symbols, output_dir="data_cache")
    print("データのキャッシュが完了しました。")
