"""System6 core logic (Short mean-reversion momentum burst)。"""

from typing import Dict, Tuple
import time
import pandas as pd
from ta.volatility import AverageTrueRange


def prepare_data_vectorized_system6(
    raw_data_dict: Dict[str, pd.DataFrame],
    *,
    progress_callback=None,
    log_callback=None,
    skip_callback=None,
    batch_size: int = 50,
) -> Dict[str, pd.DataFrame]:
    result_dict: Dict[str, pd.DataFrame] = {}
    total = len(raw_data_dict)
    start_time = time.time()
    processed, skipped = 0, 0
    buffer = []

    for sym, df in raw_data_dict.items():
        x = df.copy()
        if len(x) < 50:
            skipped += 1
            processed += 1
            continue
        try:
            x["ATR10"] = AverageTrueRange(x["High"], x["Low"], x["Close"], window=10).average_true_range()
            x["DollarVolume50"] = (x["Close"] * x["Volume"]).rolling(50).mean()
            x["Return6D"] = x["Close"].pct_change(6)
            x["UpTwoDays"] = (x["Close"] > x["Close"].shift(1)) & (x["Close"].shift(1) > x["Close"].shift(2))
            x["setup"] = (
                (x["Close"] > 5) & (x["DollarVolume50"] > 10_000_000)
                & (x["Return6D"] > 0.20) & (x["UpTwoDays"])
            ).astype(int)
            result_dict[sym] = x
        except Exception:
            skipped += 1

        processed += 1
        buffer.append(sym)
        if progress_callback:
            try:
                progress_callback(processed, total)
            except Exception:
                pass
        if (processed % batch_size == 0 or processed == total) and log_callback:
            elapsed = time.time() - start_time
            remain = (elapsed / processed) * (total - processed) if processed else 0
            em, es = divmod(int(elapsed), 60)
            rm, rs = divmod(int(remain), 60)
            msg = f"📊 インジケーター計算 {processed}/{total} 件 完了 | 経過: {em}分{es}秒 / 残り: 約{rm}分{rs}秒\n"
            if buffer:
                msg += f"銘柄: {', '.join(buffer)}"
            try:
                log_callback(msg)
            except Exception:
                pass
            buffer.clear()

    if skipped > 0:
        msg = f"⚠ データ不足/計算失敗でスキップ: {skipped} 件"
        try:
            if skip_callback:
                skip_callback(msg)
            elif log_callback:
                log_callback(msg)
        except Exception:
            pass

    return result_dict


def generate_candidates_system6(
    prepared_dict: Dict[str, pd.DataFrame],
    *,
    top_n: int = 10,
    progress_callback=None,
    log_callback=None,
    skip_callback=None,
    batch_size: int = 50,
) -> Tuple[dict, pd.DataFrame | None]:
    candidates_by_date: Dict[pd.Timestamp, list] = {}
    total = len(prepared_dict)
    start_time = time.time()
    processed, skipped = 0, 0
    buffer = []

    for sym, df in prepared_dict.items():
        try:
            setup_days = df[df["setup"] == 1]
            for date, row in setup_days.iterrows():
                entry_date = date + pd.Timedelta(days=1)
                if entry_date not in df.index:
                    continue
                rec = {
                    "symbol": sym,
                    "entry_date": entry_date,
                    "Return6D": row["Return6D"],
                    "ATR10": row["ATR10"],
                }
                candidates_by_date.setdefault(entry_date, []).append(rec)
        except Exception:
            skipped += 1

        processed += 1
        buffer.append(sym)
        if progress_callback:
            try:
                progress_callback(processed, total)
            except Exception:
                pass
        if (processed % batch_size == 0 or processed == total) and log_callback:
            elapsed = time.time() - start_time
            remain = (elapsed / processed) * (total - processed) if processed else 0
            em, es = divmod(int(elapsed), 60)
            rm, rs = divmod(int(remain), 60)
            msg = f"📊 セットアップ抽出 {processed}/{total} 件 完了 | 経過: {em}分{es}秒 / 残り: 約{rm}分{rs}秒\n"
            if buffer:
                msg += f"銘柄: {', '.join(buffer)}"
            try:
                log_callback(msg)
            except Exception:
                pass
            buffer.clear()

    # Return6D 降順で日別 top_n
    for date in list(candidates_by_date.keys()):
        ranked = sorted(candidates_by_date[date], key=lambda x: x["Return6D"], reverse=True)
        candidates_by_date[date] = ranked[: int(top_n)]

    if skipped > 0:
        msg = f"⚠ 候補抽出中にスキップ: {skipped} 件"
        try:
            if skip_callback:
                skip_callback(msg)
            elif log_callback:
                log_callback(msg)
        except Exception:
            pass
    return candidates_by_date, None


def get_total_days_system6(data_dict: Dict[str, pd.DataFrame]) -> int:
    all_dates = set()
    for df in data_dict.values():
        if df is None or df.empty:
            continue
        if "Date" in df.columns:
            dates = pd.to_datetime(df["Date"]).dt.normalize()
        else:
            dates = pd.to_datetime(df.index).normalize()
        all_dates.update(dates)
    return len(all_dates)


__all__ = [
    "prepare_data_vectorized_system6",
    "generate_candidates_system6",
    "get_total_days_system6",
]
