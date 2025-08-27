import logging
import logging.handlers
from pathlib import Path
from typing import Optional

from config.settings import Settings


def setup_logging(settings: Settings) -> logging.Logger:
    """ロギング設定を標準 logging で初期化して root ロガーを返す。
    - 日次ローテーション: rotation == "daily"
    - それ以外: サイズローテーション（MB 指定の例: "10 MB" は 10*1024*1024）
    """
    level = getattr(logging, settings.logging.level.upper(), logging.INFO)
    log_dir = Path(settings.LOGS_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / settings.logging.filename

    logger = logging.getLogger()
    logger.setLevel(level)

    # 既存ハンドラをクリア
    for h in list(logger.handlers):
        logger.removeHandler(h)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    rotation = settings.logging.rotation.lower()
    if rotation == "daily":
        handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(log_path), when="midnight", backupCount=7, encoding="utf-8"
        )
    else:
        # 例: "10 MB" -> 10485760
        size_bytes: Optional[int] = None
        try:
            num = float(rotation.split()[0])
            unit = rotation.split()[1].lower() if len(rotation.split()) > 1 else "b"
            mult = 1
            if unit.startswith("k"):
                mult = 1024
            elif unit.startswith("m"):
                mult = 1024 * 1024
            elif unit.startswith("g"):
                mult = 1024 * 1024 * 1024
            size_bytes = int(num * mult)
        except Exception:
            size_bytes = 10 * 1024 * 1024
        handler = logging.handlers.RotatingFileHandler(
            filename=str(log_path), maxBytes=size_bytes, backupCount=5, encoding="utf-8"
        )

    handler.setFormatter(fmt)
    logger.addHandler(handler)

    # コンソールにも出す
    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    logger.debug("Logging initialized")
    return logger
