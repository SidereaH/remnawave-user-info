from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from remnawave.models import RemnaUser

_STATUS_EMOJI = {
    "ACTIVE": "🟢",
    "DISABLED": "🔴",
    "LIMITED": "🟡",
    "EXPIRED": "⚪️",
}


def human_bytes(n: int) -> str:
    if n <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    f = float(n)
    i = 0
    while f >= 1024 and i < len(units) - 1:
        f /= 1024
        i += 1
    return f"{f:.2f} {units[i]}"


def _fmt_traffic(used: int, limit: int) -> str:
    if not limit:
        return f"{human_bytes(used)} / ∞"
    return f"{human_bytes(used)} / {human_bytes(limit)}"


def _fmt_expire(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "∞"


def render_card(u: RemnaUser) -> str:
    em = _STATUS_EMOJI.get(u.status, "▫️")
    lines = [
        f"<b>{em} {escape(u.username)}</b> ({escape(u.status)})",
        f"📶 Трафик: {_fmt_traffic(u.used_traffic_bytes, u.traffic_limit_bytes)}",
        f"⏳ Истекает: {_fmt_expire(u.expire_at)}",
        f"💬 Telegram ID: {u.telegram_id or '—'}",
        f"📧 Email: {escape(u.email) if u.email else '—'}",
        f"📝 Описание: {escape(u.description) if u.description else '—'}",
        f"🆔 <code>{escape(u.uuid)}</code>",
    ]
    if u.subscription_url:
        lines.append(f"🔗 {escape(u.subscription_url)}")
    return "\n".join(lines)


def render_usage(data: Any) -> str:
    """Детализация трафика по узлам. Формат ответа панели может отличаться —
    рендерим устойчиво к структуре."""
    if not data:
        return "Нет данных по трафику."
    rows: list[dict] = []
    if isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
    elif isinstance(data, dict):
        for key in ("nodes", "usage", "stats"):
            if isinstance(data.get(key), list):
                rows = [r for r in data[key] if isinstance(r, dict)]
                break
    if not rows:
        return "📊 Детализация недоступна (проверь формат usage-эндпоинта)."
    lines = ["📊 <b>Трафик по узлам:</b>"]
    for r in rows:
        name = escape(str(r.get("nodeName") or r.get("name") or r.get("node") or "?"))
        total = r.get("total") or r.get("totalBytes") or r.get("bytes") or 0
        try:
            total = int(total)
        except (TypeError, ValueError):
            total = 0
        lines.append(f"• {name}: {human_bytes(total)}")
    return "\n".join(lines)
