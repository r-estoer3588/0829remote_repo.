"""
UI要素の一元管理ヘルパ。

- `UIManager`: コンテナ階層（root→system→phase）を管理し、
  ログ表示用`st.empty()`と進捗用`st.progress()`を提供。
- 既存コードは `log_area.text(...)` / `progress_bar.progress(v)` に依存しているため、
  互換オブジェクト（StreamlitのElementそのもの）を返すだけの薄い実装にしている。

将来的に並列実行へ拡張する際も、各System/Phase専用の領域を確保して干渉を避けられる。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import streamlit as st


@dataclass
class PhaseContext:
    """フェーズ単位のUIハンドル。"""

    container: "st.delta_generator.DeltaGenerator"
    title: Optional[str] = None

    def __post_init__(self) -> None:
        if self.title:
            try:
                self.container.caption(self.title)
            except Exception:
                pass
        # 必要な要素を先に確保（互換API）
        self._log = self.container.empty()
        self._progress = self.container.progress(0)

    @property
    def log_area(self):
        return self._log

    @property
    def progress_bar(self):
        return self._progress

    # 便利メソッド
    def info(self, msg: str) -> None:
        try:
            self.container.info(msg)
        except Exception:
            pass


class UIManager:
    """UI階層を管理する薄いマネージャ。"""

    def __init__(self, *, root: "st.delta_generator.DeltaGenerator" | None = None):
        self._root = root or st.container()
        self._systems: Dict[str, UIManager] = {}
        self._phases: Dict[str, PhaseContext] = {}

    # --- 階層管理 ---
    def system(self, name: str, *, title: Optional[str] = None) -> "UIManager":
        if name not in self._systems:
            c = self._root.container()
            if title:
                try:
                    c.subheader(title)
                except Exception:
                    pass
            self._systems[name] = UIManager(root=c)
        return self._systems[name]

    def phase(self, name: str, *, title: Optional[str] = None) -> PhaseContext:
        if name not in self._phases:
            c = self._root.container()
            self._phases[name] = PhaseContext(container=c, title=title)
        return self._phases[name]

    # --- シンプル便宜API（後方互換想定） ---
    def get_log_area(self, name: str = "log"):
        return self.phase(name).log_area

    def get_progress_bar(self, name: str = "progress"):
        return self.phase(name).progress_bar

    # 外部で `with ui.container:` と使えるよう公開
    @property
    def container(self):
        return self._root
