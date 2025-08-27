"""Daily data cache script (settings-driven).

- Uses YAML/.env via config.settings.get_settings
- Respects API base/key, cache dir, threads, throttle, retries, timeout
"""

from __future__ import annotations

import os
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, List

import pandas as pd
import requests

from config.settings import get_settings
from common.logging_utils import setup_logging
from indicators_common import add_indicators


FAILED_LIST = "eodhd_failed_symbols.csv"


SETTINGS = get_settings(create_dirs=True)
LOGGER = setup_logging(SETTINGS)
API_KEY = SETTINGS.EODHD_API_KEY
API_BASE = SETTINGS.API_EODHD_BASE.rstrip("/")
TIMEOUT = SETTINGS.REQUEST_TIMEOUT
RETRIES = SETTINGS.DOWNLOAD_RETRIES
THROTTLE = SETTINGS.API_THROTTLE_SECONDS


def load_failed_symbols() -> set[str]:
    if os.path.exists(FAILED_LIST):
        return set(pd.read_csv(FAILED_LIST, header=None)[0].astype(str).str.upper())
    return set()


def save_failed_symbols(new_failed: Iterable[str]) -> None:
    old_failed = load_failed_symbols()
    updated_failed = old_failed | {s.upper() for s in new_failed}
    pd.Series(sorted(updated_failed)).to_csv(FAILED_LIST, index=False, header=False)


def get_all_symbols() -> List[str]:
    urls = [
        "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
        "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
    ]
    symbols = set()
    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            lines = r.text.splitlines()
            for line in lines[1:]:
                if "|" in line:
                    parts = line.split("|")
                    if parts[0].isalpha():
                        symbols.add(parts[0])
        except Exception as e:
            logging.error(f"取得失敗 {url} - {e}")
    return sorted(symbols)


def get_with_retry(url: str, retries: int | None = None, delay: float | None = None, timeout: int | None = None):
    if retries is None:
        retries = RETRIES
    if delay is None:
        delay = THROTTLE
    if timeout is None:
        timeout = TIMEOUT
    for i in range(retries):
        try:
            r = requests.get(url, timeout=timeout)
            if r.status_code == 200:
                return r
            logging.warning(f"ステータスコード {r.status_code} - {url}")
        except Exception as e:
            logging.warning(f"試行{i + 1}回目のエラー: {e}")
        time.sleep(delay)
    return None


def get_eodhd_data(symbol: str) -> pd.DataFrame | None:
    url = f"{API_BASE}/api/eod/{symbol}.US?api_token={API_KEY}&period=d&fmt=json"
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


def safe_filename(symbol: str) -> str:
    if symbol.upper() in RESERVED_WORDS:
        return symbol + "_RESV"
    return symbol


def cache_single(symbol: str, output_dir: str):
    safe_symbol = safe_filename(symbol)
    filepath = os.path.join(output_dir, f"{safe_symbol}.csv")
    if os.path.exists(filepath):
        mod_time = datetime.fromtimestamp(os.path.getmtime(filepath))
        if mod_time.date() == datetime.today().date():
            return f"{symbol}: already cached", False  # False = no API call
    df = get_eodhd_data(symbol)
    if df is not None and not df.empty:
        df = add_indicators(df)
        df.to_csv(filepath)
        return f"{symbol}: saved", True  # True = API call used
    else:
        return f"{symbol}: failed to fetch", True


def cache_data(symbols: Iterable[str], output_dir: str | None = None, max_workers: int | None = None):
    if output_dir is None:
        output_dir = str(SETTINGS.DATA_CACHE_DIR)
    if max_workers is None:
        max_workers = SETTINGS.THREADS_DEFAULT
    os.makedirs(output_dir, exist_ok=True)
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(cache_single, symbol, output_dir): symbol for symbol in symbols}
        results_list = []
        for i, future in enumerate(as_completed(futures)):
            result, used_api = future.result()
            symbol = futures[future]
            results_list.append((symbol, result, used_api))
            logging.info(result)
            print(f"[{i}] {result}")
            if "failed" in result:
                failed.append(symbol)
            if used_api:
                time.sleep(THROTTLE)

    if failed:
        save_failed_symbols(failed)

    cached_count = sum(1 for _, _, used_api in results_list if not used_api)
    api_count = sum(1 for _, _, used_api in results_list if used_api)
    print(f"✅ キャッシュ済み: {cached_count}件, API使用: {api_count}件, 失敗 {len(failed)}件")


def warm_cache_default():
    """設定の auto_tickers を使って軽量ウォームアップを実施"""
    tickers = list(SETTINGS.ui.auto_tickers) or [
        "AAPL",
        "MSFT",
        "NVDA",
        "META",
        "AMZN",
        "GOOGL",
        "TSLA",
    ]
    cache_data(tickers)


if __name__ == "__main__":
    warm_cache_default()
    print("デイリーキャッシュ更新が完了しました。")

