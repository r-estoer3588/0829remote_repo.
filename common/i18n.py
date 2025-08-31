from __future__ import annotations

import os
from typing import Dict

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None  # type: ignore


# 言語コード: "en" / "ja"
SUPPORTED = ("en", "ja")


def _get_session_state() -> Dict:
    if st is not None:
        return getattr(st, "session_state", {})
    return {}


def get_language() -> str:
    ss = _get_session_state()
    lang = ss.get("_lang") or os.getenv("APP_LANG", "ja")  # 既定: 日本語
    return lang if lang in SUPPORTED else "en"


def set_language(lang: str) -> None:
    if st is None:
        return
    st.session_state["_lang"] = lang if lang in SUPPORTED else "en"


# 既存の英語文言をキーとして日本語訳を提供
_JA_MAP: Dict[str, str] = {
    # common/ui_components.py 周辺
    "clear streamlit cache": "Streamlitキャッシュをクリア",
    "cache cleared": "キャッシュをクリアしました",
    "show debug logs": "デバッグログを表示",
    "auto symbols (all tickers)": "銘柄を自動選択（全ティッカー）",
    "capital (USD)": "資金（USD）",
    "symbol limit": "銘柄数の上限",
    "use all symbols": "全銘柄を使用",
    "symbols (comma separated)": "銘柄一覧（カンマ区切り）",
    "please input symbols": "銘柄を入力してください",
    "run": "実行",
    "no trades": "取引なし",
    "backtest finished": "バックテスト完了",
    "trade logs": "取引ログ",
    "download holdings csv": "保有状況CSVをダウンロード",

    # app_integrated.py 周辺（一部）
    "Trading Systems Integrated UI": "トレーディングシステム統合UI",
    "settings": "設定",
    "Integrated": "統合",
    "Batch": "バッチ",
    "Integrated Backtest (Systems 17)": "統合バックテスト（Systems 17）",
    "allow gross leverage (sum cost can exceed capital)": "総建玉レバレッジを許可（合計コストが資金を超える場合あり）",
    "long bucket share (%)": "ロング側の配分（%）",
    "short bucket share = 100% - long": "ショート側の配分 = 100% - ロング",
    "run integrated": "統合実行",
    "signals per system:": "各システムのシグナル数:",
    "simulate integrated": "統合シミュレーション",
    "Integrated Summary": "統合サマリー",
    "download integrated trades CSV": "統合トレードCSVをダウンロード",
    "no trades in integrated run": "統合実行での取引はありません",
    "Batch Backtest / Summary": "バッチ・バックテスト / サマリー",
    "mode": "モード",
    "Backtest": "バックテスト",
    "Future signals (coming soon)": "将来シグナル（近日対応）",
    "run batch": "バッチ実行",
    "max log lines shown per system": "各システムの表示ログ最大行数",
    "Saved Batch Results (persisted)": "保存済みバッチ結果（永続）",
    "download saved batch trades CSV": "保存済みバッチ取引CSVをダウンロード",
    "save saved batch CSV to disk": "保存済みバッチCSVをディスクへ保存",
    "clear saved batch results": "保存済みバッチ結果をクリア",
    "Saved Per-System Logs": "保存済みシステム別ログ",
    "Per-System Logs (latest)": "システム別ログ（最新）",
    "no saved logs yet": "保存済みのログはまだありません",
    "Signal detection mode will be added soon.": "シグナル検出モードは近日追加予定です。",
    "no results": "結果はありません",
    "All systems summary": "全システムのサマリー",
    "download batch trades CSV": "バッチ取引CSVをダウンロード",
    "save batch CSV to disk": "バッチCSVをディスクへ保存",
}


def tr(text: str) -> str:
    """簡易翻訳: 現在言語が日本語なら対応表から訳語を返す。未登録は原文のまま。"""
    if get_language() == "ja":
        return _JA_MAP.get(text, text)
    return text


def language_selector(in_sidebar: bool = True) -> None:
    """UIに言語セレクタを表示し、選択をセッションへ保持する。既定は日本語。"""
    if st is None:
        return
    options = {"日本語": "ja", "English": "en"}
    current = get_language()
    labels = list(options.keys())
    default_index = 0 if current == "ja" else 1
    label = "言語 / Language"
    if in_sidebar:
        choice = st.sidebar.selectbox(label, labels, index=default_index, key="_lang_select")
    else:
        choice = st.selectbox(label, labels, index=default_index, key="_lang_select")
    set_language(options.get(choice, "ja"))

