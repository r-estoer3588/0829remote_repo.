"""
UI互換パッチローダー。
common.ui_components の関数を共通実装へ委譲するために動的差し替えする。
アプリ起動時に `import common.ui_patch` するだけで有効。
"""
from __future__ import annotations

try:
    from common.logging_utils import log_with_progress as _core_log_with_progress
    from common.performance_summary import summarize as _summarize_perf
    import common.ui_components as _ui
    import pandas as pd
    from config.settings import get_settings
    import streamlit as st
except Exception:  # pragma: no cover
    _core_log_with_progress = None  # type: ignore
    _summarize_perf = None  # type: ignore
    _ui = None  # type: ignore
    pd = None  # type: ignore


def _patched_log_with_progress(
    i,
    total,
    start_time,
    prefix="処理",
    batch=50,
    log_area=None,
    progress_bar=None,
    extra_msg=None,
    unit="件",
):
    if _core_log_with_progress is None:
        # 旧実装にフォールバック（安全側）
        import time as _t

        if i % batch == 0 or i == total:
            elapsed = _t.time() - start_time
            remain = (elapsed / i) * (total - i) if i > 0 else 0
            msg = (
                f"{prefix}: {i}/{total} {unit} 完了"
                f"| 経過: {int(elapsed // 60)}分{int(elapsed % 60)}秒"
                f"/ 残り: 約{int(remain // 60)}分{int(remain % 60)}秒"
            )
            if extra_msg:
                msg += f"\n{extra_msg}"
            if log_area:
                log_area.text(msg)
            if progress_bar:
                progress_bar.progress(i / total if total else 0)
        return

    _core_log_with_progress(
        i,
        total,
        start_time,
        prefix=prefix,
        batch=batch,
        log_func=(lambda m: log_area.text(m)) if log_area else None,
        progress_func=(lambda v: progress_bar.progress(v)) if progress_bar else None,
        extra_msg=extra_msg,
        unit=unit,
    )


def _patched_summarize_results(results_df, capital):
    if _summarize_perf is None or results_df is None or results_df.empty:
        return {}, results_df
    s, df2 = _summarize_perf(results_df, capital)
    return s.to_dict(), df2


if _ui is not None:
    # 関数を置き換え
    _ui.log_with_progress = _patched_log_with_progress  # type: ignore[attr-defined]
    _ui.summarize_results = _patched_summarize_results  # type: ignore[attr-defined]

# ダウンロードボタンの一括無効化（自動保存がある場合に隠す）
try:
    _settings = get_settings(create_dirs=True) if 'get_settings' in globals() else None
    if _settings is not None and 'st' in globals() and st is not None:
        _ui_cfg = getattr(_settings, 'ui', None)

        # 元の download_button を退避
        if not hasattr(st, '_orig_download_button') and hasattr(st, 'download_button'):
            st._orig_download_button = st.download_button  # type: ignore[attr-defined]

        def _patched_download_button(*args, **kwargs):  # noqa: D401
            """一部 CSV ダウンロードを非表示にし、その他は設定に従う。"""
            fname = kwargs.get('file_name')
            if fname is None and len(args) >= 3:
                fname = args[2]
            try:
                # シグナル/トレードの CSV は常に非表示（自動保存のため）
                if isinstance(fname, str) and ('_signals_' in fname or '_trades_' in fname):
                    return False
            except Exception:
                pass

            # それ以外は設定のフラグに従う
            if not getattr(_ui_cfg, 'show_download_buttons', True):
                return False
            try:
                return st._orig_download_button(*args, **kwargs)  # type: ignore[attr-defined]
            except Exception:
                return False

        st.download_button = _patched_download_button  # type: ignore[attr-defined]
except Exception:
    # 失敗時は従来動作のまま
    pass
