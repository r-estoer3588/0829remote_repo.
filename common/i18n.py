from __future__ import annotations

import os
import json
from typing import Dict, Optional
from pathlib import Path

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None  # type: ignore


# 言語コード: "en" / "ja"
SUPPORTED = ("en", "ja")

# モジュール内での言語設定（streamlit が無い場合に利用）
_module_lang: Optional[str] = None

# 外部から読み込んだ翻訳辞書
_TRANSLATIONS: Dict[str, Dict[str, str]] = {}


def _get_session_state() -> Dict:
    if st is not None:
        return getattr(st, "session_state", {})
    return {}


def get_language() -> str:
    """現在の言語コードを返す。優先順: モジュール設定 -> セッション -> 環境変数 -> 既定(ja)"""
    global _module_lang
    if _module_lang and _module_lang in SUPPORTED:
        return _module_lang
    ss = _get_session_state()
    lang = ss.get("_lang") or os.getenv("APP_LANG", "ja")
    return lang if lang in SUPPORTED else "ja"


def set_language(lang: str) -> None:
    """言語を設定。streamlit がある場合はセッションへ、ない場合はモジュール変数へ保存。"""
    global _module_lang
    code = lang if lang in SUPPORTED else "en"
    if st is None:
        _module_lang = code
        return
    st.session_state["_lang"] = code


# 既存の英語文言をキーとして日本語訳を提供（フォールバック用）
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


def load_translations_from_dir(translations_dir: str | os.PathLike) -> None:
    """
    translations_dir 配下の <lang>.json を読み込む。形式: {"原文 English": "翻訳"} の辞書。
    呼び出しはアプリ起点で一度行えば良い（streamlit なら起動時）。
    """
    p = Path(translations_dir)
    if not p.exists() or not p.is_dir():
        return
    for child in p.iterdir():
        if child.suffix.lower() == ".json":
            code = child.stem
            if code not in SUPPORTED:
                continue
            try:
                with child.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, dict):
                        _TRANSLATIONS[code] = {str(k): str(v) for k, v in data.items()}
            except Exception:
                # ロード失敗は無視（フォールバックあり）
                continue


def _lookup_translation(text: str, lang: str) -> Optional[str]:
    """ロード済み辞書や組み込みの _JA_MAP から翻訳を取得"""
    if lang in _TRANSLATIONS and text in _TRANSLATIONS[lang]:
        return _TRANSLATIONS[lang][text]
    if lang == "ja" and text in _JA_MAP:
        return _JA_MAP[text]
    return None


def tr(text: str, **kwargs) -> str:
    """
    翻訳を返す。現在言語が日本語なら対応表から訳語を返す。未登録は原文のまま。
    kwargs を渡すと Python の format で埋め込みを行う（例: tr("hello {name}", name="A")）。
    """
    lang = get_language()
    if lang == "en":
        out = text
    else:
        found = _lookup_translation(text, lang)
        out = found if found is not None else text
    try:
        return out.format(**kwargs) if kwargs else out
    except Exception:
        return out


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
        choice = st.sidebar.selectbox(
            label, labels, index=default_index, key="_lang_select"
        )
    else:
        choice = st.selectbox(label, labels, index=default_index, key="_lang_select")
    set_language(options.get(choice, "ja"))
