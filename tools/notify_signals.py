"""Simple signal notification utilities.

`notify_signals()` reads today's CSVs under ``settings.outputs.signals_dir``
and logs a summary. ``send_signal_notification`` posts a short text message to
webhooks defined by ``TEAMS_WEBHOOK_URL`` or ``SLACK_WEBHOOK_URL`` environment
variables.  The payload is compatible with Microsoft Teams and Slack incoming
webhooks. Discord webhooks are also supported via ``DISCORD_WEBHOOK_URL``.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from config.settings import get_settings


def notify_signals():
    settings = get_settings(create_dirs=True)
    sig_dir = Path(settings.outputs.signals_dir)
    if not sig_dir.exists():
        logging.info("signals ディレクトリが存在しません: %s", sig_dir)
        return

    today = datetime.today().strftime("%Y-%m-%d")
    files = list(sig_dir.glob(f"*{today}*.csv"))
    if not files:
        logging.info("本日の新規シグナルCSVは見つかりませんでした。")
        return

    total = 0
    frames = []
    for f in files:
        try:
            df = pd.read_csv(f)
            n = len(df)
            total += n
            frames.append(df)
            logging.info("シグナル: %s (%d 件)", f.name, n)
        except Exception:
            logging.exception("シグナルCSVの読み込みに失敗: %s", f)

    logging.info("本日の合計シグナル件数: %d", total)
    if frames:
        try:
            send_signal_notification(pd.concat(frames, ignore_index=True))
        except Exception:
            logging.exception("signal notification failed")


def _post_webhook(url: str, text: str) -> None:
    """Post a simple text payload to an incoming webhook.

    - Teams/Slack expect a JSON payload with "text" key.
    - Discord accepts both "content" and rich embeds; for simple text we use
      "content" to ensure the message appears as plain text.
    """
    try:
        # Heuristic: if URL contains 'discord.com/api/webhooks', send as Discord
        if "discord.com/api/webhooks" in (url or ""):
            requests.post(url, json={"content": text}, timeout=5)
        else:
            requests.post(url, json={"text": text}, timeout=5)
    except Exception:
        logging.exception("Webhook post failed: %s", url)


def send_signal_notification(df: pd.DataFrame) -> None:
    """Send a brief notification for the given signals DataFrame."""
    if df is None or df.empty:
        return
    syms = ", ".join(df["symbol"].astype(str).head(10))
    text = f"Today signals: {len(df)} picks\n{syms}"
    # Post to all configured destinations
    for env in ("TEAMS_WEBHOOK_URL", "SLACK_WEBHOOK_URL", "DISCORD_WEBHOOK_URL"):
        url = os.getenv(env)
        if url:
            _post_webhook(url, text)


if __name__ == "__main__":
    notify_signals()

