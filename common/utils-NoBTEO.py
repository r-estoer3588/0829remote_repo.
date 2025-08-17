# utils.py
import os
import pandas as pd

RESERVED_WORDS = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

def safe_filename(symbol: str) -> str:
    """
    Windows予約語を回避したファイル名を返す
    """
    if symbol.upper() in RESERVED_WORDS:
        return symbol + "_RESV"
    return symbol

def clean_date_column(df: pd.DataFrame, col_name="Date") -> pd.DataFrame:
    """
    DataFrame の Date 列を groupby 可能な形にクリーンアップする共通関数
    """
    df = df.copy()

    # MultiIndex カラムを解除
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 重複カラムを削除
    df = df.loc[:, ~df.columns.duplicated()]

    # Date列がDataFrameならSeries化
    if col_name in df.columns and isinstance(df[col_name], pd.DataFrame):
        df[col_name] = df[col_name].iloc[:, 0]

    # Date列を日付型に
    if col_name in df.columns:
        df[col_name] = pd.to_datetime(df[col_name])

    # インデックスがDateならreset_index()
    if df.index.name == col_name:
        df = df.reset_index()

    return df

def get_cached_data(symbol: str, folder="data_cache") -> pd.DataFrame | None:
    """
    キャッシュCSVを読み込み DataFrame を返す
    """
    filename = f"{safe_filename(symbol)}.csv"
    path = os.path.join(folder, filename)
    if os.path.exists(path):
        try:
            df = pd.read_csv(path, parse_dates=["Date"])
            df.set_index("Date", inplace=True)
            return df.sort_index()
        except Exception as e:
            print(f"{symbol}: キャッシュ読み込み失敗 - {e}")
            return None
    return None

def get_manual_data(symbol: str) -> pd.DataFrame | None:
    """
    data_cache にシンボルのキャッシュがある場合は読み込む
    """
    path = os.path.join("data_cache", f"{safe_filename(symbol)}.csv")
    if os.path.exists(path):
        return get_cached_data(symbol)
    else:
        print(f"{symbol} のキャッシュがありません。cache_daily_data.py を先に実行してください。")
        return None
