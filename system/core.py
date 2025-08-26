"""
Shared core logic extracted from strategies/system1.py.

These functions keep their original names for compatibility
with existing call sites, while living under the shared
module path `system.core`.
"""

import time
import pandas as pd


def prepare_data_vectorized_system1(
    raw_data_dict,
    progress_callback=None,
    log_callback=None,
    skip_callback=None,
    batch_size=50,
    reuse_indicators=True,
    **kwargs,
):
    """
    System1: indicator computation (UI-agnostic)
    - reuse_indicators: reuse indicator columns from existing CSV if available
    - progress_callback: progress update function (done:int, total:int) -> None
    - log_callback: logging function (message:str) -> None
    - batch_size: interval for log updates
    Note: Does not perform I/O.
    """
    total_symbols = len(raw_data_dict)
    processed = 0
    symbol_buffer = []
    start_time = time.time()
    result_dict = {}

    for sym, df in raw_data_dict.items():
        required_cols = ["SMA25", "SMA50", "ROC200", "ATR20", "DollarVolume20"]

        if reuse_indicators and all(col in df.columns for col in required_cols):
            if not df[required_cols].isnull().any().any():
                result_dict[sym] = df
                symbol_buffer.append(sym)
                processed += 1
                continue
            else:
                df = df.copy()
        else:
            df = df.copy()

        # Indicators
        df["SMA25"] = df["Close"].rolling(25).mean()
        df["SMA50"] = df["Close"].rolling(50).mean()
        df["ROC200"] = df["Close"].pct_change(200) * 100
        tr = pd.concat(
            [
                df["High"] - df["Low"],
                (df["High"] - df["Close"].shift()).abs(),
                (df["Low"] - df["Close"].shift()).abs(),
            ],
            axis=1,
        ).max(axis=1)
        df["ATR20"] = tr.rolling(20).mean()
        df["DollarVolume20"] = (df["Close"] * df["Volume"]).rolling(20).mean()

        # Signal
        df["signal"] = (
            (df["SMA25"] > df["SMA50"])
            & (df["Close"] > 5)
            & (df["DollarVolume20"] > 50_000_000)
        ).astype(int)

        result_dict[sym] = df
        processed += 1
        symbol_buffer.append(sym)

        # Progress update
        if progress_callback:
            try:
                progress_callback(processed, total_symbols)
            except Exception:
                pass

        # Batched log updates
        if (processed % batch_size == 0 or processed == total_symbols) and log_callback:
            elapsed = time.time() - start_time
            remaining = (elapsed / processed) * (total_symbols - processed)
            elapsed_min, elapsed_sec = divmod(int(elapsed), 60)
            remain_min, remain_sec = divmod(int(remaining), 60)
            joined_syms = ", ".join(symbol_buffer)
            try:
                log_callback(
                    f"📊 指標計算: {processed}/{total_symbols} 件 完了"
                    f" | 経過: {elapsed_min}分{elapsed_sec}秒 / 残り: 約 {remain_min}分{remain_sec}秒\n"
                    f"銘柄: {joined_syms}"
                )
            except Exception:
                pass
            symbol_buffer.clear()

    return result_dict


def get_total_days_system1(data_dict):
    """
    System1: Return the total number of unique dates across prepared data.
    """
    all_dates = set()
    for df in data_dict.values():
        if df is None or df.empty:
            continue
        if "Date" in df.columns:
            date_series = pd.to_datetime(df["Date"]).dt.normalize()
        else:
            date_series = pd.to_datetime(df.index).normalize()
        all_dates.update(date_series)

    return len(sorted(all_dates))


def generate_roc200_ranking_system1(data_dict: dict, spy_df: pd.DataFrame, **kwargs):
    """
    Generate daily ROC200 ranking filtered by SPY trend; returns
    (candidates_by_date: dict[date -> list[candidate]], merged_df: pd.DataFrame)
    """
    all_signals = []
    for symbol, df in data_dict.items():
        if "signal" not in df.columns or df["signal"].sum() == 0:
            continue
        sig_df = df[df["signal"] == 1][["ROC200", "ATR20", "Open"]].copy()
        sig_df["symbol"] = symbol
        sig_df["entry_date"] = sig_df.index + pd.Timedelta(days=1)
        all_signals.append(sig_df.reset_index())

    if not all_signals:
        return {}, pd.DataFrame()

    all_signals_df = pd.concat(all_signals, ignore_index=True)

    # SPY filter expects SMA100 already computed on spy_df
    spy_df = spy_df[["Close", "SMA100"]].reset_index().rename(columns={"Date": "date"})

    merged = pd.merge_asof(
        all_signals_df.sort_values("Date"),
        spy_df.rename(
            columns={"Close": "Close_SPY", "SMA100": "SMA100_SPY"}
        ).sort_values("date"),
        left_on="Date",
        right_on="date",
    )
    merged = merged[merged["Close_SPY"] > merged["SMA100_SPY"]].copy()

    merged["entry_date_norm"] = merged["entry_date"].dt.normalize()
    grouped = merged.groupby("entry_date_norm")
    total_days = len(grouped)
    start_time = time.time()
    on_progress = kwargs.get("on_progress")
    on_log = kwargs.get("on_log")

    candidates_by_date = {}
    for i, (date, group) in enumerate(grouped, 1):
        top10 = group.nlargest(10, "ROC200")
        candidates_by_date[date] = top10.to_dict("records")

        if on_progress:
            on_progress(i, total_days, start_time)
        if on_log and (i % 10 == 0 or i == total_days):
            elapsed = time.time() - start_time
            remain = elapsed / i * (total_days - i)
            on_log(
                f"📊 ROC200ランキング: {i}/{total_days} 日処理完了"
                f" | 経過: {int(elapsed // 60)}分{int(elapsed % 60)}秒"
                f" / 残り: 約 {int(remain // 60)}分{int(remain % 60)}秒"
            )

    return candidates_by_date, merged

