"""通知機能のユーティリティ.

- Slack / Discord Webhook に対応
- ユーザー向け日本語文言は正規化済み
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
import logging
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

__all__ = [
    "Notifier",
    "BroadcastNotifier",
    "create_notifier",
    "now_jst_str",
    "mask_secret",
    "truncate",
    "format_table",
    "chunk_fields",
    "detect_default_platform",
    "get_notifiers_from_env",
]


# System と売買方向（色指定に使用）
SYSTEM_POSITION: dict[str, str] = {
    "system1": "long",
    "system2": "short",
    "system3": "long",
    "system4": "long",
    "system5": "long",
    "system6": "short",
    "system7": "short",
}

COLOR_LONG = 0x2ECC71   # Discord embed color (緑)
COLOR_SHORT = 0xE74C3C  # 赤
COLOR_NEUTRAL = 0xF1C40F # 黄

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

    # 古いログをローテーション（> 3年）
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
                logger.info("古いログを削除しました %s", p.name)
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


def truncate(text: Any, max_len: int) -> str:
    s = "" if text is None else str(text)
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


def chunk_fields(title: str, items: list[str], inline: bool = True, per_row: int = 2) -> list[dict[str, Any]]:
    """Slack/Discord 共通の fields 形式へ整形する簡易ユーティリティ."""
    fields: list[dict[str, Any]] = []
    if not items:
        return fields
    if inline:
        # 2列などで並べる
        row: list[str] = []
        for i, it in enumerate(items, 1):
            row.append(str(it))
            if i % per_row == 0:
                fields.append({"name": title, "value": "  |  ".join(row), "inline": True})
                row = []
        if row:
            fields.append({"name": title, "value": "  |  ".join(row), "inline": True})
    else:
        for it in items:
            fields.append({"name": title, "value": str(it), "inline": False})
    return fields


def detect_default_platform() -> str:
    if os.getenv("SLACK_WEBHOOK_URL"):
        return "slack"
    if os.getenv("DISCORD_WEBHOOK_URL"):
        return "discord"
    return "none"


class Notifier:
    """Slack / Discord 送信を抽象化する通知クラス."""

    def __init__(self, platform: str = "auto", webhook_url: str | None = None):
        if platform == "auto":
            platform = detect_default_platform()
        self.platform = platform
        self.webhook_url = webhook_url or (
            os.getenv("SLACK_WEBHOOK_URL") if platform == "slack" else os.getenv("DISCORD_WEBHOOK_URL")
        )
        self.logger = _setup_logger()

    # 低レベル送信
    def _post(self, payload: dict[str, Any]) -> None:  # pragma: no cover - 実送信は通常テストしない
        if not self.webhook_url:
            self.logger.warning("webhook が未設定のため送信をスキップします platform=%s", self.platform)
            return
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code >= 300:
                self.logger.warning("notify failed status=%s text=%s", resp.status_code, resp.text[:200])
        except Exception as e:
            self.logger.warning("notify exception %s", e)

    # 共通 send（簡易）
    def send(
        self,
        title: str,
        message: str,
        fields: dict[str, str] | list[dict[str, Any]] | None = None,
        image_url: str | None = None,
        color: int | None = None,
    ) -> None:
        payload: dict[str, Any]
        if self.platform == "discord":
            embed: dict[str, Any] = {
                "title": truncate(title, 256),
                "description": truncate(message, 4096),
            }
            if color is not None:
                embed["color"] = int(color)
            field_list: list[dict[str, Any]] = []
            if isinstance(fields, dict):
                for k, v in fields.items():
                    field_list.append({"name": truncate(k, 256), "value": truncate(str(v), 1024), "inline": True})
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
        else:  # slack / none
            blocks: list[dict[str, Any]] = [
                {"type": "section", "text": {"type": "mrkdwn", "text": truncate(f"*{title}*\n{message}", 3000)}}
            ]
            if isinstance(fields, dict):
                text = "\n".join(f"*{k}*: {v}" for k, v in fields.items())
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": truncate(text, 3000)}})
            elif isinstance(fields, list):
                for f in fields:
                    text = f"*{f.get('name', '')}*\n{f.get('value', '')}"
                    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": truncate(text, 3000)}})
            if image_url:
                blocks.append({"type": "image", "image_url": image_url, "alt_text": title})
            # Slack Webhookでは fallback 用の text があると安全
            fallback = truncate(f"{title}\n{message}", 3000)
            payload = {"text": fallback, "blocks": blocks}
        self.logger.info(
            "send title=%s fields=%d image=%s",
            truncate(title, 50),
            0 if not fields else (len(fields) if isinstance(fields, list) else len(fields)),
            bool(image_url),
        )
        self._post(payload)

    # 以降は高レベル API（ユーザー向け日本語文言を整形）
    def send_signals(self, system_name: str, signals: list[str]) -> None:
        direction = SYSTEM_POSITION.get(system_name.lower(), "")
        color = COLOR_LONG if direction == "long" else (COLOR_SHORT if direction == "short" else COLOR_NEUTRAL)
        title = f"📢 {system_name} 日次シグナル（{now_jst_str()}）"
        if not signals:
            self.send(title, "本日のシグナルはありません。", color=color)
            self.logger.info("signals %s direction=%s count=0", system_name, direction or "none")
            return
        emoji = "↑" if direction == "long" else ("↓" if direction == "short" else "")
        items = [f"{emoji} {s}" if emoji else s for s in signals]
        fields = chunk_fields("銘柄", items, inline=False)
        self.send(title, "", fields=fields, color=color)
        self.logger.info("signals %s direction=%s count=%d", system_name, direction or "none", len(signals))

    def send_backtest(self, system_name: str, period: str, stats: dict[str, Any], ranking: list[str]) -> None:
        direction = SYSTEM_POSITION.get(system_name.lower(), "")
        color = COLOR_LONG if direction == "long" else (COLOR_SHORT if direction == "short" else COLOR_NEUTRAL)
        title = f"📊 {system_name} バックテスト（{period}、実行日時 {now_jst_str()}）"
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
        title = f"📊 {system_name} {period_type} サマリー（{period_label}、実行日時 {now_jst_str()}）"
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
        """拡張バックテスト通知（画像 URL、メンション対応）."""
        direction = SYSTEM_POSITION.get(system_name.lower(), "")
        color = COLOR_LONG if direction == "long" else (COLOR_SHORT if direction == "short" else COLOR_NEUTRAL)
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
        # Slack へは先頭にメンションタグ
        if mention and getattr(self, "platform", "") == "slack":
            tag = "<!channel>" if str(mention).lower() in {"channel", "@everyone"} else "<!here>"
            desc = f"{tag}\n" + desc
        self.send(title, desc, fields=fields, color=color, image_url=image_url)
        summary = ", ".join(f"{k}={v}" for k, v in list(stats.items())[:3])
        self.logger.info("backtest_ex %s stats=%s top=%d", system_name, summary, min(len(ranking), 10))


# ---------------------------------
# Broadcast support (Slack + Discord)
# ---------------------------------
class BroadcastNotifier:
    """複数プラットフォームへ同時通知するラッパー.

    子として `Notifier(platform="slack")` や `Notifier(platform="discord")`
    を保持し、各メソッド呼び出しを内部で委譲する。
    """

    def __init__(self, notifiers: list[Notifier]) -> None:
        self._notifiers = [n for n in notifiers if getattr(n, "webhook_url", None)]
        self.logger = _setup_logger()

    def _each(self, fn_name: str, *args, **kwargs) -> None:
        for n in self._notifiers:
            try:
                getattr(n, fn_name)(*args, **kwargs)
            except Exception as e:  # pragma: no cover - network/IO
                self.logger.warning(
                    "broadcast %s failed platform=%s %s", fn_name, getattr(n, "platform", "?"), e
                )

    # Notifier API を委譲
    def send(self, *args, **kwargs) -> None:
        self._each("send", *args, **kwargs)

    def send_signals(self, *args, **kwargs) -> None:
        self._each("send_signals", *args, **kwargs)

    def send_backtest(self, *args, **kwargs) -> None:
        self._each("send_backtest", *args, **kwargs)

    def send_backtest_ex(self, *args, **kwargs) -> None:
        self._each("send_backtest_ex", *args, **kwargs)

    def send_trade_report(self, *args, **kwargs) -> None:
        self._each("send_trade_report", *args, **kwargs)

    def send_summary(self, *args, **kwargs) -> None:
        self._each("send_summary", *args, **kwargs)


def create_notifier(platform: str = "auto", broadcast: bool | None = None):
    """Notifier を生成するファクトリ.

    - broadcast=True の場合、Slack/Discord の両方が設定されていれば
      BroadcastNotifier を返し、片方のみなら通常の Notifier を返す
    - broadcast が None の場合、環境変数 `NOTIFY_BROADCAST` を参照する
    - platform="auto" は既存動作（Slack 優先）を維持
    """
    if broadcast is None:
        flag = os.getenv("NOTIFY_BROADCAST", "").strip().lower()
        broadcast = flag in {"1", "true", "yes", "on", "both", "all"}

    if broadcast:
        notifiers: list[Notifier] = []
        slack_url = os.getenv("SLACK_WEBHOOK_URL")
        discord_url = os.getenv("DISCORD_WEBHOOK_URL")
        # auto/both: 可能なものを全部採用
        if platform in {"auto", "both", "broadcast", "all"}:
            if slack_url:
                notifiers.append(Notifier(platform="slack", webhook_url=slack_url))
            if discord_url:
                notifiers.append(Notifier(platform="discord", webhook_url=discord_url))
        else:
            # 明示指定時は一致する方のみ
            if platform == "slack" and slack_url:
                notifiers.append(Notifier(platform="slack", webhook_url=slack_url))
            if platform == "discord" and discord_url:
                notifiers.append(Notifier(platform="discord", webhook_url=discord_url))
        if len(notifiers) >= 2:
            return BroadcastNotifier(notifiers)
        if len(notifiers) == 1:
            return notifiers[0]
        # フォールバック
        return Notifier(platform=platform)

    # broadcast 無効時はそのまま
    return Notifier(platform=platform)


def get_notifiers_from_env() -> list[Notifier]:
    """環境変数から利用可能な Notifier のリストを生成する."""
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

