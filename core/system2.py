"""System2 core logic (Short RSI spike) を共通化。

- インジケーター: RSI3, ADX7, ATR10, DollarVolume20, ATR_Ratio, TwoDayUp
- セットアップ条件: Close>5, DollarVolume20>25M, ATR_Ratio>0.03, RSI3>90, TwoDayUp
- 候補生成: ADX7 降順で top_n を日別抽出
"""

from typing import Dict, Tuple
import time
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange


def prepare_data_vectorized_system2(
    raw_data_dict: Dict[str, pd.DataFrame],
    *,
    progress_callback=None,
    log_callback=None,
    batch_size: int = 50,
) -> Dict[str, pd.DataFrame]:
    total = len(raw_data_dict)
    processed = 0
    start_time = time.time()
    buffer = []
    result_dict: Dict[str, pd.DataFrame] = {}
    skipped_count = 0

    for sym, df in raw_data_dict.items():
        x = df.copy()

        # データ行不足
        if len(x) < 20:
            skipped_count += 1
            processed += 1
            continue

        try:
            x["RSI3"] = RSIIndicator(x["Close"], window=3).rsi()
            x["ADX7"] = ADXIndicator(x["High"], x["Low"], x["Close"], window=7).adx()
            x["ATR10"] = AverageTrueRange(x["High"], x["Low"], x["Close"], window=10).average_true_range()
        except Exception:
            skipped_count += 1
            processed += 1
            continue

        x["DollarVolume20"] = (x["Close"] * x["Volume"]).rolling(window=20).mean()
        x["ATR_Ratio"] = x["ATR10"] / x["Close"]
        x["TwoDayUp"] = (x["Close"] > x["Close"].shift(1)) & (x["Close"].shift(1) > x["Close"].shift(2))

        x["setup"] = (
            (x["Close"] > 5)
            & (x["DollarVolume20"] > 25_000_000)
            & (x["ATR_Ratio"] > 0.03)
            & (x["RSI3"] > 90)
            & (x["TwoDayUp"])
        )

        result_dict[sym] = x
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
            msg = (
                f"📊 インジケーター計算 {processed}/{total} 件 完了 | "
                f"経過: {em}分{es}秒 / 残り: 約{rm}分{rs}秒\n"
            )
            if buffer:
                msg += f"銘柄: {', '.join(buffer)}"
            try:
                log_callback(msg)
            except Exception:
                pass
            buffer.clear()

    if skipped_count > 0 and log_callback:
        try:
            log_callback(f"⚠️ データ不足/計算失敗でスキップ: {skipped_count} 件")
        except Exception:
            pass

    return result_dict


def generate_candidates_system2(
    prepared_dict: Dict[str, pd.DataFrame],
    *,
    top_n: int = 10,
) -> Tuple[dict, pd.DataFrame | None]:
    """セットアップ通過銘柄を日別に ADX7 降順で抽出。
    返却: (candidates_by_date, merged_df=None)
    """
    all_signals = []
    for sym, df in prepared_dict.items():
        if "setup" not in df.columns or not df["setup"].any():
            continue
        setup_df = df[df["setup"]].copy()
        setup_df["symbol"] = sym
        setup_df["entry_date"] = setup_df.index + pd.Timedelta(days=1)
        all_signals.append(setup_df)

    if not all_signals:
        return {}, None

    all_df = pd.concat(all_signals)

    candidates_by_date = {}
    for date, group in all_df.groupby("entry_date"):
        ranked = group.sort_values("ADX7", ascending=False)
        candidates_by_date[date] = ranked.head(int(top_n)).to_dict("records")
    return candidates_by_date, None


def get_total_days_system2(data_dict: Dict[str, pd.DataFrame]) -> int:
    """データ中の日数ユニーク数。"""
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
    "prepare_data_vectorized_system2",
    "generate_candidates_system2",
    "get_total_days_system2",
]
