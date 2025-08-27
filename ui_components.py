from __future__ import annotations

from typing import Callable

# 共通ログAPIの薄いラッパ。strategies からは本モジュール経由で呼び出す。
try:
    from common.logging_utils import log_with_progress as _core_log_with_progress  # type: ignore
except Exception:  # pragma: no cover
    _core_log_with_progress = None  # type: ignore


def log_with_progress(
    i: int,
    total: int,
    start_time: float,
    *,
    prefix: str = "処理",
    batch: int = 50,
    log_func: Callable[[str], None] | None = None,
    progress_func: Callable[[float], None] | None = None,
    extra_msg: str | None = None,
    unit: str = "件",
):
    if _core_log_with_progress is None:
        # フォールバック: 可能なら log_func のみで最低限出力
        if (i % batch == 0 or i == total) and log_func:
            try:
                log_func(f"{prefix}: {i}/{total} {unit}")
            except Exception:
                pass
        return
    _core_log_with_progress(
        i,
        total,
        start_time,
        prefix=prefix,
        batch=batch,
        log_func=log_func,
        progress_func=progress_func,
        extra_msg=extra_msg,
        unit=unit,
    )

