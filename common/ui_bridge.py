from __future__ import annotations
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict
import streamlit as st
import pandas as pd
from common.utils import safe_filename, get_cached_data
from utils.cache_manager import load_base_cache, base_cache_path
import os
from typing import Optional
from common.i18n import tr


class _FallbackPhase:
    """ui_manager が無い場合の簡易フェーズ代替。"""

    def __init__(self):
        # st は上で import 済み
        self.log_area = st.empty()
        self.progress_bar = st.progress(0)
        self.container = st.container()

    def info(self, *args, **kwargs):  # 互換 API
        try:
            st.info(*args, **kwargs)
        except Exception:
            pass


def _phase(ui_manager, name: str):
    """UIManager があればそのフェーズ、無ければフォールバック。"""
    try:
        return ui_manager.phase(name) if ui_manager else _FallbackPhase()
    except Exception:
        return _FallbackPhase()


def _mtime_or_zero(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0


@st.cache_data(show_spinner=False)
def _load_symbol_cached(
    symbol: str, *, base_path: str, base_mtime: float, raw_path: str, raw_mtime: float
):
    # base キャッシュ優先、無ければ raw を読む
    df = load_base_cache(symbol, rebuild_if_missing=True)
    if df is not None and not df.empty:
        return symbol, df
    import os

    if os.path.exists(raw_path):
        return symbol, get_cached_data(symbol)
    return symbol, None


def _load_symbol(symbol: str, cache_dir: str = "data_cache"):
    base_path = str(base_cache_path(symbol))
    raw_path = os.path.join(cache_dir, f"{safe_filename(symbol)}.csv")
    return _load_symbol_cached(
        symbol,
        base_path=base_path,
        base_mtime=_mtime_or_zero(base_path),
        raw_path=raw_path,
        raw_mtime=_mtime_or_zero(raw_path),
    )


def _fetch_data_ui(
    symbols, ui_manager=None, max_workers: int = 8
) -> Dict[str, pd.DataFrame]:
    data: Dict[str, pd.DataFrame] = {}
    total = len(symbols)
    phase = ui_manager.phase("fetch") if ui_manager else None
    progress = phase.progress_bar if phase else st.progress(0)
    log_area = phase.log_area if phase else st.empty()
    buffer, start = [], time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_load_symbol, s): s for s in symbols}
        for i, fut in enumerate(as_completed(futures), 1):
            sym, df = fut.result()
            if df is not None and not df.empty:
                data[sym] = df
                buffer.append(sym)
            if i % 50 == 0 or i == total:
                elapsed = time.time() - start
                msg = f"fetch: {i}/{total} items | elapsed {int(elapsed//60)}m{int(elapsed%60)}s"
                if buffer:
                    msg += "\n" + ", ".join(buffer)
                log_area.text(msg)
                progress.progress(i / total)
                buffer.clear()
    try:
        progress.empty()
    except Exception:
        pass
    return data


def prepare_backtest_data_ui(
    strategy,
    symbols,
    *,
    system_name: str,
    spy_df=None,
    ui_manager=None,
    **kwargs,
):
    # System1以降はui_componentsがui_manager対応済みなので委譲
    if system_name != "System2":
        from common.ui_components import prepare_backtest_data as _prepare

        return _prepare(
            strategy,
            symbols,
            system_name=system_name,
            spy_df=spy_df,
            ui_manager=ui_manager,
            **kwargs,
        )

    # --- System2: UIManagerでフェーズ分割 ---
    # 1) データ取得
    raw = _fetch_data_ui(symbols, ui_manager=ui_manager)
    if not raw:
        st.error(tr("有効なデータがありません"))
        return None, None, None

    # 2) インジケーター計算
    ind = _phase(ui_manager, "indicators")
    ind.info("📊 インジケーター計算中...")
    prepared = strategy.prepare_data(
        raw,
        progress_callback=lambda done, total: ind.progress_bar.progress(done / total),
        log_callback=lambda msg: ind.log_area.text(str(msg)),
        **kwargs,
    )
    try:
        ind.progress_bar.empty()
    except Exception:
        pass
    try:
        ind.log_area.text("インジケーター計算 完了")
    except Exception:
        pass

    # 3) 候補抽出
    cand = _phase(ui_manager, "candidates")
    cand.info("📊 候補抽出中...")
    try:
        candidates_by_date, merged_df = strategy.generate_candidates(
            prepared,
            progress_callback=lambda done, total: cand.progress_bar.progress(
                done / total
            ),
            **kwargs,
        )
    except TypeError:
        # 戻り値が dict のみ（System2仕様）
        candidates_by_date = strategy.generate_candidates(
            prepared,
            progress_callback=lambda done, total: cand.progress_bar.progress(
                done / total
            ),
            **kwargs,
        )
        merged_df = None
    try:
        cand.progress_bar.empty()
    except Exception:
        pass
    try:
        cand.log_area.text("候補抽出 完了")
    except Exception:
        pass

    if not candidates_by_date:
        st.warning(tr("候補がありません"))
        return prepared, None, None
    return prepared, candidates_by_date, merged_df


def run_backtest_with_logging_ui(
    strategy,
    prepared_dict,
    candidates_by_date,
    capital,
    *,
    system_name: str,
    ui_manager=None,
):
    # System1以降はui_components側へ委譲(ui_manager渡し)
    if system_name != "System2":
        from common.ui_components import run_backtest_with_logging as _run

        return _run(
            strategy,
            prepared_dict,
            candidates_by_date,
            capital,
            system_name,
            ui_manager=ui_manager,
        )

    bt = _phase(ui_manager, "backtest")
    bt.info("💹 バックテスト実行中...")
    debug_area = bt.container.empty()
    debug_logs = []

    results_df = strategy.run_backtest(
        prepared_dict,
        candidates_by_date,
        capital,
        on_progress=lambda i, total, start: bt.progress_bar.progress(
            0 if not total else i / total
        ),
        on_log=lambda msg: (
            debug_logs.append(str(msg))
            or (
                (getattr(bt, "trade_log_area", bt.log_area).text(str(msg)))
                if (isinstance(msg, str) and str(msg).startswith("💰"))
                else bt.log_area.text(str(msg))
            )
        ),
    )

    if debug_logs:
        with st.expander("💰 取引ログ", expanded=False):
            st.text("\n".join(debug_logs))
    # セッションへ永続化
    st.session_state[f"{system_name}_debug_logs"] = list(debug_logs)
    try:
        bt.progress_bar.empty()
    except Exception:
        pass
    st.session_state[f"{system_name}_results_df"] = results_df
    return results_df
