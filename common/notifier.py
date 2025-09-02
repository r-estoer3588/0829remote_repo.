from __future__ import annotations

import logging
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List
from zoneinfo import ZoneInfo

import requests

__all__ = ["Notifier", "now_jst_str", "mask_secret", "truncate", "format_table", "chunk_fields"]

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


def format_table(rows: List[Iterable[Any]], headers: List[str] | None = None, max_width: int = 80) -> str:
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

    def fmt_row(r: List[str]) -> str:
        return " | ".join(s[:widths[i]].ljust(widths[i]) for i, s in enumerate(r))

    lines: List[str] = []
    if headers:
        lines.append(fmt_row(data[0]))
        lines.append("-+-".join("-" * w for w in widths))
        body = data[1:]
    else:
        body = data
    for r in body:
        lines.append(fmt_row(r))
    return "```\n" + "\n".join(lines) + "\n```"


def chunk_fields(name: str, items: List[str], inline: bool = True, max_per_field: int = 15) -> List[Dict[str, Any]]:
    fields: List[Dict[str, Any]] = []
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


class Notifier:
    def __init__(self, platform: str = "discord", webhook_url: str | None = None) -> None:
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
    def _post(self, payload: Dict[str, Any]) -> None:
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
                wait = (2 ** i) + random.uniform(-0.2, 0.2)
                time.sleep(wait)
        self.logger.error("送信に失敗しました: %s", masked)
        raise RuntimeError("notification failed")

    def send(
        self,
        title: str,
        message: str,
        fields: Dict[str, str] | List[Dict[str, Any]] | None = None,
        image_url: str | None = None,
        color: int | None = None,
    ) -> None:
        desc = f"実行日時: {now_jst_str()}"
        if message:
            desc += "\n" + message
        payload: Dict[str, Any]
        if self.platform == "discord":
            embed: Dict[str, Any] = {
                "title": truncate(title, 256),
                "description": truncate(desc, 4096),
            }
            if color is not None:
                embed["color"] = int(color)
            field_list: List[Dict[str, Any]] = []
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
            blocks: List[Dict[str, Any]] = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": truncate(f"*{title}*\n{desc}", 3000)},
                }
            ]
            if isinstance(fields, dict):
                text = "\n".join(f"*{k}*: {v}" for k, v in fields.items())
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": truncate(text, 3000)}})
            elif isinstance(fields, list):
                for f in fields:
                    text = f"*{f.get('name','')}*\n{f.get('value','')}"
                    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": truncate(text, 3000)}})
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

    def send_signals(self, system_name: str, signals: List[str]) -> None:
        direction = SYSTEM_POSITION.get(system_name.lower(), "")
        color = (
            COLOR_LONG if direction == "long" else COLOR_SHORT if direction == "short" else COLOR_NEUTRAL
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
        stats: Dict[str, Any],
        ranking: List[str],
    ) -> None:
        direction = SYSTEM_POSITION.get(system_name.lower(), "")
        color = (
            COLOR_LONG if direction == "long" else COLOR_SHORT if direction == "short" else COLOR_NEUTRAL
        )
        title = f"📊 {system_name} バックテスト（{period}, 実行: {now_jst_str()}）"
        fields = {k: str(v) for k, v in stats.items()}
        desc = ""
        if ranking:
            lines = [f"{i+1}. {s}" for i, s in enumerate(ranking[:10])]
            if len(ranking) > 10:
                lines.append("…")
            desc = "ROC200 TOP10\n" + "\n".join(lines)
        self.send(title, desc, fields=fields, color=color)
        summary = ", ".join(f"{k}={v}" for k, v in list(stats.items())[:3])
        self.logger.info(
            "backtest %s stats=%s top=%d", system_name, summary, min(len(ranking), 10)
        )

    def send_trade_report(self, system_name: str, trades: List[Dict[str, Any]]) -> None:
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
        self.logger.info(
            "trade report %s count=%d notional=%.2f", system_name, len(trades), total
        )

    def send_summary(
        self,
        system_name: str,
        period_type: str,
        period_label: str,
        summary: Dict[str, Any],
        image_url: str | None = None,
    ) -> None:
        title = f"📊 {system_name} {period_type} サマリー（{period_label}, 実行: {now_jst_str()}）"
        fields = {k: str(v) for k, v in summary.items()}
        self.send(title, "", fields=fields, image_url=image_url)
        self.logger.info(
            "summary %s %s keys=%d", system_name, period_type, len(summary)
        )
