from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


def _parse_dt(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _to_int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


@dataclass
class RemnaUser:
    uuid: str
    username: str
    status: str
    used_traffic_bytes: int
    traffic_limit_bytes: int
    expire_at: datetime | None
    telegram_id: int | None
    email: str | None
    description: str
    subscription_url: str | None
    short_uuid: str | None
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RemnaUser":
        # Remnawave 2.8.0 вложил использованный трафик в userTraffic;
        # до 2.8 он лежал на верхнем уровне — поддерживаем оба варианта.
        traffic = d.get("userTraffic") or {}
        used = traffic.get("usedTrafficBytes")
        if used is None:
            used = d.get("usedTrafficBytes")
        return cls(
            uuid=d.get("uuid", ""),
            username=d.get("username", ""),
            status=d.get("status", ""),
            used_traffic_bytes=_to_int(used),
            traffic_limit_bytes=_to_int(d.get("trafficLimitBytes")),
            expire_at=_parse_dt(d.get("expireAt")),
            telegram_id=d.get("telegramId"),
            email=d.get("email"),
            description=d.get("description") or "",
            subscription_url=d.get("subscriptionUrl"),
            short_uuid=d.get("shortUuid"),
            raw=d,
        )
