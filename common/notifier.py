"""通知機能のユーティリティ."""

# ruff: noqa: I001

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
import logging
import os
from pathlib import Path
import random
import time
from typing import Any
from zoneinfo import ZoneInfo

import requests

__all__ = [
    "Notifier",
    "now_jst_str",
    "mask_secret",
    "truncate",
    "format_table",
    "chunk_fields",
    "detect_default_platform",
    "get_notifiers_from_env",
]

SYSTEM_POSITION = {
    "system1": "long",
    "system2": "short",
    "system3": "long",
    "system4": "long",
    "system5": "long",
    "system6": "short",
    "system7": "short",
}

COLOR_LONG = 3066993
COLOR_SHORT = 15158332
COLOR_NEUTRAL = 15548997

_JST = ZoneInfo("Asia/Tokyo")


class _JSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):  # type: ignore[override]
        dt = datetime.fromtimestamp(record.created, tz=_JST)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M JST")


def _setup_logger() -> logging.Logger:
    logger = logging.getLogger("notifier")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = "[%(asctime)s] %(levelname)s Notifier: %(message)s"
    formatter = _JSTFormatter(fmt)

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    now = datetime.now(tz=_JST)
    log_file = logs_dir / f"notifier_{now:%Y-%m}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(sh)

    # cleanup old logs (>3 years)
    cutoff_year = now.year - 3
    cutoff_month = now.month
    for p in logs_dir.glob("notifier_*.log"):
        try:
            y, m = map(int, p.stem.split("_")[1].split("-"))
        except Exception:
            continue
        if (y < cutoff_year) or (y == cutoff_year and m < cutoff_month):
            try:
                p.unlink()
                logger.info("古いログを削除しました → %s", p.name)
            except Exception:
                pass
    return logger


def now_jst_str(minute: bool = True) -> str:
    fmt = "%Y-%m-%d %H:%M JST" if minute else "%Y-%m-%d %H:%M:%S JST"
    return datetime.now(tz=_JST).strftime(fmt)


def mask_secret(url: str) -> str:
    if not url:
        return ""
    try:
        head, tail = url.split("://", 1)
        domain, *rest = tail.split("/")
        token = "/".join(rest)
        if len(token) > 9:
            token = f"{token[:5]}...{token[-4:]}"
        else:
            token = "***"
        return f"{head}://{domain}/{token}"
    except Exception:
        return "***"


def truncate(text: str, max_len: int) -> str:
    if text is None:
        return ""
    s = str(text)
    return s if len(s) <= max_len else s[:max_len] + "… (truncated)"


def format_table(
    rows: list[Iterable[Any]], headers: list[str] | None = None, max_width: int = 80
) -> str:
    if not rows:
        return ""
    data = [list(map(str, r)) for r in rows]
    if headers:
        data.insert(0, list(map(str, headers)))
    cols = len(data[0])
    widths = [max(len(r[i]) for r in data) for i in range(cols)]
    total = sum(widths) + 3 * (cols - 1)
    if total > max_width:
        ratio = (max_width - 3 * (cols - 1)) / sum(widths)
        widths = [max(1, int(w * ratio)) for w in widths]

    def fmt_row(r: list[str]) -> str:
        return " | ".join(s[: widths[i]].ljust(widths[i]) for i, s in enumerate(r))

    lines: list[str] = []
    if headers:
        lines.append(fmt_row(data[0]))
        lines.append("-+-".join("-" * w for w in widths))
        body = data[1:]
    else:
        body = data
    for r in body:
        lines.append(fmt_row(r))
    return "```\n" + "\n".join(lines) + "\n```"


def chunk_fields(
    name: str, items: list[str], inline: bool = True, max_per_field: int = 15
) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for i in range(0, len(items), max_per_field):
        chunk = items[i : i + max_per_field]
        fields.append(
            {
                "name": name if i == 0 else f"{name} ({i // max_per_field + 1})",
                "value": "\n".join(chunk),
                "inline": inline,
            }
        )
    return fields


def detect_default_platform() -> str:
    """Return preferred notifier platform based on environment.

    - If ``SLACK_WEBHOOK_URL`` is set, prefer Slack.
    - Otherwise fall back to Discord.
    """
    try:
        return "slack" if os.getenv("SLACK_WEBHOOK_URL") else "discord"
    except Exception:
        return "discord"


class Notifier:
    def __init__(self, platform: str = "discord", webhook_url: str | None = None) -> None:
        # Allow callers that pass "auto" or an empty string to rely on env detection
        if not platform or platform.lower() == "auto":
            platform = detect_default_platform()
        self.platform = platform.lower()
        if self.platform not in {"discord", "slack"}:
            raise ValueError(f"未知のplatform: {platform}")
        env = "DISCORD_WEBHOOK_URL" if self.platform == "discord" else "SLACK_WEBHOOK_URL"
        self.logger = _setup_logger()
        self.webhook_url = webhook_url or os.getenv(env)
        if not self.webhook_url:
            self.logger.warning("Webhook URLが設定されていません: %s", env)
        else:
            self.logger.info(
                "Notifier 初期化 platform=%s webhook=%s",
                self.platform,
                mask_secret(self.webhook_url),
            )

    # internal send with retry
    def _post(self, payload: dict[str, Any]) -> None:
        if not self.webhook_url:
            self.logger.debug("Webhook未設定のため通知をスキップしました")
            return
        url = self.webhook_url
        masked = mask_secret(url)
        for i in range(3):
            try:
                r = requests.post(url, json=payload, timeout=10)
                if 200 <= r.status_code < 300:
                    return
                self.logger.warning(
                    "送信失敗[%d] status=%s body=%s",
                    i + 1,
                    r.status_code,
                    truncate(r.text, 100),
                )
            except Exception as e:  # pragma: no cover - network errors
                self.logger.warning("送信エラー[%d] %s", i + 1, e)
            if i < 2:
                wait = (2**i) + random.uniform(-0.2, 0.2)
                time.sleep(wait)
        self.logger.error("送信に失敗しました: %s", masked)
        raise RuntimeError("notification failed")

    def send(
        self,
        title: str,
        message: str,
        fields: dict[str, str] | list[dict[str, Any]] | None = None,
        image_url: str | None = None,
        color: int | None = None,
    ) -> None:
        desc = f"実行日時: {now_jst_str()}"
        if message:
            desc += "\n" + message
        payload: dict[str, Any]
        if self.platform == "discord":
            embed: dict[str, Any] = {
                "title": truncate(title, 256),
                "description": truncate(desc, 4096),
            }
            if color is not None:
                embed["color"] = int(color)
            field_list: list[dict[str, Any]] = []
            if isinstance(fields, dict):
                for k, v in fields.items():
                    field_list.append(
                        {
                            "name": truncate(k, 256),
                            "value": truncate(str(v), 1024),
                            "inline": True,
                        }
                    )
            elif isinstance(fields, list):
                for f in fields:
                    field_list.append(
                        {
                            "name": truncate(f.get("name", ""), 256),
                            "value": truncate(str(f.get("value", "")), 1024),
                            "inline": bool(f.get("inline", True)),
                        }
                    )
            if field_list:
                embed["fields"] = field_list[:25]
            if image_url:
                embed["image"] = {"url": image_url}
            payload = {"embeds": [embed]}
        else:  # slack
            blocks: list[dict[str, Any]] = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": truncate(f"*{title}*\n{desc}", 3000)},
                }
            ]
            if isinstance(fields, dict):
                text = "\n".join(f"*{k}*: {v}" for k, v in fields.items())
                blocks.append(
                    {"type": "section", "text": {"type": "mrkdwn", "text": truncate(text, 3000)}}
                )
            elif isinstance(fields, list):
                for f in fields:
                    text = f"*{f.get('name', '')}*\n{f.get('value', '')}"
                    blocks.append(
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": truncate(text, 3000)},
                        }
                    )
            if image_url:
                blocks.append({"type": "image", "image_url": image_url, "alt_text": title})
            payload = {"blocks": blocks}
        self.logger.info(
            "send title=%s fields=%d image=%s",
            truncate(title, 50),
            0 if not fields else (len(fields) if isinstance(fields, list) else len(fields)),
            bool(image_url),
        )
        self._post(payload)

    # unified send with optional mention support
    def send_with_mention(
        self,
        title: str,
        message: str,
        fields: dict[str, str] | list[dict[str, Any]] | None = None,
        image_url: str | None = None,
        color: int | None = None,
        mention: str | bool | None = None,
    ) -> None:
        desc = f"実行日時: {now_jst_str()}"
        if message:
            desc += "\n" + message
        content: str | None = None
        if mention is None:
            _m = os.getenv("NOTIFY_MENTION", "").strip().lower()
            if _m in {"channel", "here", "@everyone", "@here"}:
                mention = _m
        if mention:
            if self.platform == "slack":
                tag = (
                    "<!channel>" if str(mention).lower() in {"channel", "@everyone"} else "<!here>"
                )
                desc = f"{tag}\n" + desc
            else:
                content = (
                    "@everyone" if str(mention).lower() in {"channel", "@everyone"} else "@here"
                )

        payload: dict[str, Any]
        if self.platform == "discord":
            embed: dict[str, Any] = {
                "title": truncate(title, 256),
                "description": truncate(desc, 4096),
            }
            if color is not None:
                embed["color"] = int(color)
            field_list: list[dict[str, Any]] = []
            if isinstance(fields, dict):
                for k, v in fields.items():
                    field_list.append(
                        {"name": truncate(k, 256), "value": truncate(str(v), 1024), "inline": True}
                    )
            elif isinstance(fields, list):
                for f in fields:
                    field_list.append(
                        {
                            "name": truncate(f.get("name", ""), 256),
                            "value": truncate(str(f.get("value", "")), 1024),
                            "inline": bool(f.get("inline", True)),
                        }
                    )
            if field_list:
                embed["fields"] = field_list[:25]
            if image_url:
                embed["image"] = {"url": image_url}
            payload = {"embeds": [embed]}
            if content:
                payload["content"] = content
        else:
            blocks: list[dict[str, Any]] = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": truncate(f"*{title}*\n{desc}", 3000)},
                }
            ]
            if isinstance(fields, dict):
                text = "\n".join(f"*{k}*: {v}" for k, v in fields.items())
                blocks.append(
                    {"type": "section", "text": {"type": "mrkdwn", "text": truncate(text, 3000)}}
                )
            elif isinstance(fields, list):
                for f in fields:
                    text = f"*{f.get('name', '')}*\n{f.get('value', '')}"
                    blocks.append(
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": truncate(text, 3000)},
                        }
                    )
            if image_url:
                blocks.append({"type": "image", "image_url": image_url, "alt_text": title})
            payload = {"blocks": blocks}
        self.logger.info(
            "send+mention title=%s fields=%d image=%s",
            truncate(title, 50),
            0 if not fields else (len(fields) if isinstance(fields, list) else len(fields)),
            bool(image_url),
        )
        self._post(payload)

    def send_signals(self, system_name: str, signals: list[str]) -> None:
        direction = SYSTEM_POSITION.get(system_name.lower(), "")
        color = (
            COLOR_LONG
            if direction == "long"
            else COLOR_SHORT if direction == "short" else COLOR_NEUTRAL
        )
        title = f"📢 {system_name} 日次シグナル（{now_jst_str()}）"
        if not signals:
            self.send(title, "本日のシグナルはありません。", color=color)
            self.logger.info("signals %s direction=%s count=0", system_name, direction or "none")
            return
        emoji = "✅" if direction == "long" else "❌" if direction == "short" else ""
        items = [f"{emoji} {s}" if emoji else s for s in signals]
        fields = chunk_fields("銘柄", items, inline=False)
        self.send(title, "", fields=fields, color=color)
        self.logger.info(
            "signals %s direction=%s count=%d", system_name, direction or "none", len(signals)
        )

    def send_backtest(
        self,
        system_name: str,
        period: str,
        stats: dict[str, Any],
        ranking: list[str],
    ) -> None:
        direction = SYSTEM_POSITION.get(system_name.lower(), "")
        color = (
            COLOR_LONG
            if direction == "long"
            else COLOR_SHORT if direction == "short" else COLOR_NEUTRAL
        )
        title = f"📊 {system_name} バックテスト（{period}, 実行: {now_jst_str()}）"
        fields = {k: str(v) for k, v in stats.items()}
        desc = ""
        if ranking:
            lines = [f"{i + 1}. {s}" for i, s in enumerate(ranking[:10])]
            if len(ranking) > 10:
                lines.append("…")
            desc = "ROC200 TOP10\n" + "\n".join(lines)
        self.send(title, desc, fields=fields, color=color)
        summary = ", ".join(f"{k}={v}" for k, v in list(stats.items())[:3])
        self.logger.info("backtest %s stats=%s top=%d", system_name, summary, min(len(ranking), 10))

    def send_trade_report(self, system_name: str, trades: list[dict[str, Any]]) -> None:
        title = f"✅ {system_name} 売買完了（{now_jst_str()}）"
        if not trades:
            self.send(title, "本日の売買はありません。")
            self.logger.info("trade report %s count=0", system_name)
            return
        rows = []
        total = 0.0
        for t in trades:
            sym = str(t.get("symbol"))
            action = str(t.get("action", "")).upper()
            qty = t.get("qty", 0)
            price = float(t.get("price", 0.0))
            total += float(qty) * price
            rows.append([sym, action, f"{qty}", f"@{price:.4f}"])
        table = format_table(rows, headers=["SYMBOL", "ACTION", "QTY", "PRICE"])
        self.send(title, table)
        self.logger.info("trade report %s count=%d notional=%.2f", system_name, len(trades), total)

    def send_summary(
        self,
        system_name: str,
        period_type: str,
        period_label: str,
        summary: dict[str, Any],
        image_url: str | None = None,
    ) -> None:
        title = f"📊 {system_name} {period_type} サマリー（{period_label}, 実行: {now_jst_str()}）"
        fields = {k: str(v) for k, v in summary.items()}
        self.send(title, "", fields=fields, image_url=image_url)
        self.logger.info("summary %s %s keys=%d", system_name, period_type, len(summary))

    def send_backtest_ex(
        self,
        system_name: str,
        period: str,
        stats: dict[str, Any],
        ranking: list[Any],
        image_url: str | None = None,
        mention: str | bool | None = None,
    ) -> None:
        """Enhanced backtest notification with optional image and mentions.

        - ranking can be list of str or dicts with keys: symbol, roc, volume.
        - When platform is Slack and mention is truthy ("channel"/"here"),
          a tag is prefixed to the message so that a sound/notification bar appears.
        """
        direction = SYSTEM_POSITION.get(system_name.lower(), "")
        color = (
            COLOR_LONG
            if direction == "long"
            else COLOR_SHORT if direction == "short" else COLOR_NEUTRAL
        )
        title = f"📊 {system_name} バックテスト（{period}）"
        fields = {k: str(v) for k, v in stats.items()}
        desc = ""
        if ranking:
            lines: list[str] = []
            for i, item in enumerate(ranking[:10], start=1):
                try:
                    if isinstance(item, dict):
                        sym = item.get("symbol") or item.get("sym") or item.get("ticker") or "?"
                        roc = item.get("roc")
                        vol = item.get("volume") or item.get("vol")
                        part = f"{sym}"
                        if roc is not None:
                            part += f"  ROC200:{float(roc):.2f}"
                        if vol is not None:
                            part += f"  Vol:{int(float(vol)):,}"
                        lines.append(f"{i}. {part}")
                    else:
                        lines.append(f"{i}. {item}")
                except Exception:
                    lines.append(f"{i}. {item}")
            if len(ranking) > 10:
                lines.append("…")
            desc = "ROC200 TOP10\n" + "\n".join(lines)
        # Slack mention: add tag at the top of the message
        if mention and getattr(self, "platform", "") == "slack":
            tag = "<!channel>" if str(mention).lower() in {"channel", "@everyone"} else "<!here>"
            desc = f"{tag}\n" + desc
        self.send(title, desc, fields=fields, color=color, image_url=image_url)
        summary = ", ".join(f"{k}={v}" for k, v in list(stats.items())[:3])
        self.logger.info(
            "backtest_ex %s stats=%s top=%d", system_name, summary, min(len(ranking), 10)
        )


def get_notifiers_from_env() -> list[Notifier]:
    """環境変数から利用可能な Notifier のリストを生成する。"""
    notifiers: list[Notifier] = []
    try:
        slack_url = os.getenv("SLACK_WEBHOOK_URL")
        if slack_url:
            notifiers.append(Notifier(platform="slack", webhook_url=slack_url))
    except Exception:
        pass
    try:
        discord_url = os.getenv("DISCORD_WEBHOOK_URL")
        if discord_url:
            notifiers.append(Notifier(platform="discord", webhook_url=discord_url))
    except Exception:
        pass
    if not notifiers:
        notifiers.append(Notifier(platform="auto"))
    return notifiers
