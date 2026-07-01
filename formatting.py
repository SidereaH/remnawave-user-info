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
    # Европейский формат: ДД.ММ.ГГ ЧЧ:ММ.
    return dt.strftime("%d.%m.%y %H:%M") if dt else "∞"


def render_user_list(
    entries: list[tuple[RemnaUser, int | None]], total: int
) -> str:
    """Список найденных подписок: username из Remnawave, трафик, число устройств.
    device_count = None → показываем '?' (не удалось получить)."""
    if total > len(entries):
        header = f"Найдено {total}, показаны первые {len(entries)}:"
    else:
        header = f"Найдено {total} — выбери:"
    lines = [header, ""]
    for i, (u, cnt) in enumerate(entries, 1):
        em = _STATUS_EMOJI.get(u.status, "▫️")
        dev = "?" if cnt is None else str(cnt)
        lines.append(f"{i}. {em} <b>{escape(u.username or u.uuid)}</b>")
        lines.append(
            f"   📶 {_fmt_traffic(u.used_traffic_bytes, u.traffic_limit_bytes)}"
            f"  ·  📵 {dev}"
        )
    return "\n".join(lines)


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


_BYTES_KEYS = (
    "total", "totalBytes", "bytes", "usedBytes", "used",
    "totalUsedBytes", "value",
)


def _row_bytes(r: dict) -> int:
    for key in _BYTES_KEYS:
        if key in r and r[key] is not None:
            try:
                return int(r[key])
            except (TypeError, ValueError):
                return 0
    return 0


def _row_name(r: dict) -> str:
    return str(
        r.get("nodeName") or r.get("name") or r.get("node")
        or r.get("date") or r.get("day") or "?"
    )


def _extract_rows(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("nodes", "usages", "usage", "stats"):
            if isinstance(data.get(key), list):
                return [r for r in data[key] if isinstance(r, dict)]
    return []


def render_usage(data: Any, period_label: str | None = None) -> str:
    """Потребление трафика за период / по узлам. Формат ответа панели может
    отличаться между версиями — рендерим устойчиво к структуре."""
    if not data:
        return "Нет данных по трафику."

    header = (
        f"📊 <b>Потребление за {escape(period_label)}:</b>"
        if period_label
        else "📊 <b>Трафик по узлам:</b>"
    )
    rows = _extract_rows(data)

    if not rows:
        # Плоский ответ с одним суммарным числом.
        if isinstance(data, dict):
            flat = _row_bytes(data)
            if flat:
                return f"{header}\nИтого: {human_bytes(flat)}"
        return "📊 Детализация недоступна (проверь формат usage-эндпоинта)."

    detail: list[str] = []
    total = 0
    for r in rows:
        b = _row_bytes(r)
        total += b
        detail.append(f"• {escape(_row_name(r))}: {human_bytes(b)}")
    return "\n".join([header, f"Итого: {human_bytes(total)}", *detail])
