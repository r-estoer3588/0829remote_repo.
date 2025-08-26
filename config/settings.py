from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


# プロジェクトルート推定（このファイルから2階層上: config/settings.py -> repo root）
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ルート直下の .env を読み込む（存在すれば）
load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    """アプリ全体で共有する設定値。

    - 優先順位: 環境変数(.env) > 既定値
    - create_dirs=True で主要ディレクトリを自動作成
    """

    # パス
    PROJECT_ROOT: Path
    DATA_CACHE_DIR: Path
    RESULTS_DIR: Path
    LOGS_DIR: Path

    # API/ネットワーク
    API_EODHD_BASE: str
    EODHD_API_KEY: Optional[str]
    REQUEST_TIMEOUT: int
    DOWNLOAD_RETRIES: int
    API_THROTTLE_SECONDS: float

    # 実行パラメータ
    THREADS_DEFAULT: int
    MARKET_CAL_TZ: str


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except Exception:
        return default


def get_settings(create_dirs: bool = False) -> Settings:
    """設定を生成して返す。必要に応じて出力系ディレクトリを作成。"""
    root = PROJECT_ROOT

    data_cache = Path(os.getenv("DATA_CACHE_DIR", root / "data_cache"))
    results_dir = Path(os.getenv("RESULTS_DIR", root / "results_csv"))
    logs_dir = Path(os.getenv("LOGS_DIR", root / "logs"))

    settings = Settings(
        PROJECT_ROOT=root,
        DATA_CACHE_DIR=data_cache,
        RESULTS_DIR=results_dir,
        LOGS_DIR=logs_dir,
        API_EODHD_BASE=os.getenv("API_EODHD_BASE", "https://eodhistoricaldata.com"),
        EODHD_API_KEY=os.getenv("EODHD_API_KEY"),
        REQUEST_TIMEOUT=_env_int("REQUEST_TIMEOUT", 10),
        DOWNLOAD_RETRIES=_env_int("DOWNLOAD_RETRIES", 3),
        API_THROTTLE_SECONDS=_env_float("API_THROTTLE_SECONDS", 1.5),
        THREADS_DEFAULT=_env_int("THREADS_DEFAULT", 8),
        MARKET_CAL_TZ=os.getenv("MARKET_CAL_TZ", "America/New_York"),
    )

    if create_dirs:
        for p in (settings.DATA_CACHE_DIR, settings.RESULTS_DIR, settings.LOGS_DIR):
            try:
                Path(p).mkdir(parents=True, exist_ok=True)
            except Exception:
                # 失敗しても致命的ではないため握りつぶす
                pass

    return settings


__all__ = ["Settings", "get_settings"]

