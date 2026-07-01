from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from .models import RemnaUser

logger = logging.getLogger(__name__)


class RemnawaveError(Exception):
    """Понятная для пользователя ошибка обращения к панели."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class RemnawaveClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: int = 20,
        page_size: int = 250,
        transport: httpx.BaseTransport | None = None,
        revoke_body: bool = True,
    ) -> None:
        self._page_size = page_size
        self._revoke_body = revoke_body
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = await self._client.request(method, path, **kwargs)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.warning(
                "Remnawave %s %s -> %s: %s",
                method, path, e.response.status_code, e.response.text[:300],
            )
            raise RemnawaveError(
                f"Панель ответила {e.response.status_code}",
                status=e.response.status_code,
            ) from e
        except httpx.HTTPError as e:
            logger.warning("Remnawave %s %s failed: %s", method, path, e)
            raise RemnawaveError("Нет связи с панелью") from e
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json().get("response")

    @staticmethod
    def _as_users(response: Any) -> list[RemnaUser]:
        if response is None:
            return []
        if isinstance(response, dict) and "users" in response:
            response = response["users"] or []
        if isinstance(response, dict):
            response = [response]
        return [RemnaUser.from_dict(u) for u in response]

    async def get_by_telegram_id(self, tg_id: int) -> list[RemnaUser]:
        return self._as_users(
            await self._request("GET", f"/api/users/by-telegram-id/{tg_id}")
        )

    async def get_by_email(self, email: str) -> list[RemnaUser]:
        return self._as_users(
            await self._request("GET", f"/api/users/by-email/{email}")
        )

    async def get_user(self, uuid: str) -> RemnaUser:
        users = self._as_users(await self._request("GET", f"/api/users/{uuid}"))
        if not users:
            raise RemnawaveError("Пользователь не найден")
        return users[0]

    async def search_by_description(
        self, needle: str, max_pages: int = 100
    ) -> list[RemnaUser]:
        needle_l = needle.lower().lstrip("@")
        found: list[RemnaUser] = []
        start = 0
        for _ in range(max_pages):
            resp = await self._request(
                "GET", "/api/users",
                params={"size": self._page_size, "start": start},
            )
            total, raw_users = 0, []
            if isinstance(resp, dict):
                total = int(resp.get("total") or 0)
                raw_users = resp.get("users") or []
            elif isinstance(resp, list):
                raw_users = resp
            if not raw_users:
                break
            page = [RemnaUser.from_dict(u) for u in raw_users]
            found.extend(
                u for u in page if needle_l in (u.description or "").lower()
            )
            start += len(page)
            if total == 0 or start >= total:
                break
        return found

    async def _action(self, uuid: str, action: str) -> RemnaUser | None:
        users = self._as_users(
            await self._request("POST", f"/api/users/{uuid}/actions/{action}")
        )
        return users[0] if users else None

    async def enable_user(self, uuid: str) -> RemnaUser | None:
        return await self._action(uuid, "enable")

    async def disable_user(self, uuid: str) -> RemnaUser | None:
        return await self._action(uuid, "disable")

    async def reset_traffic(self, uuid: str) -> RemnaUser | None:
        return await self._action(uuid, "reset-traffic")

    async def reset_devices(self, uuid: str) -> Any:
        # Сброс всех HWID-устройств пользователя (Remnawave 2.7.x).
        return await self._request(
            "POST", "/api/hwid/devices/delete-all", json={"userUuid": uuid}
        )

    async def get_devices_count(self, uuid: str) -> int:
        # Число HWID-устройств пользователя: {response:{total, devices:[...]}}.
        resp = await self._request("GET", f"/api/hwid/devices/{uuid}")
        if isinstance(resp, dict):
            total = resp.get("total")
            if total is not None:
                try:
                    return int(total)
                except (TypeError, ValueError):
                    pass
            devices = resp.get("devices")
            if isinstance(devices, list):
                return len(devices)
        return 0

    async def revoke_subscription(self, uuid: str) -> RemnaUser:
        # Remnawave 2.8.0 требует тело (revokeOnlyPasswords=false — полный
        # перевыпуск подписки); 2.7.x тела не ждёт (revoke_body=False → без тела).
        body = {"revokeOnlyPasswords": False} if self._revoke_body else None
        users = self._as_users(
            await self._request(
                "POST", f"/api/users/{uuid}/actions/revoke", json=body
            )
        )
        return users[0] if users else await self.get_user(uuid)

    async def update_expire(self, uuid: str, expire_at: datetime) -> RemnaUser:
        body = {
            "uuid": uuid,
            "expireAt": expire_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
        users = self._as_users(await self._request("PATCH", "/api/users", json=body))
        return users[0] if users else await self.get_user(uuid)

    async def get_usage_by_range(
        self, uuid: str, start: datetime, end: datetime
    ) -> Any:
        """Потребление трафика пользователя за период [start, end].

        Основной `/api/bandwidth-stats/users/{uuid}` ждёт start/end в формате
        ДАТЫ (`YYYY-MM-DD`) + topNodesLimit; при 404/400 пробуем `/legacy`,
        где start/end — полный ISO date-time.
        """
        su = start.astimezone(timezone.utc)
        eu = end.astimezone(timezone.utc)
        try:
            return await self._request(
                "GET",
                f"/api/bandwidth-stats/users/{uuid}",
                params={
                    "start": su.strftime("%Y-%m-%d"),
                    "end": eu.strftime("%Y-%m-%d"),
                    "topNodesLimit": 10,
                },
            )
        except RemnawaveError as e:
            if e.status not in (400, 404):
                raise
            return await self._request(
                "GET",
                f"/api/bandwidth-stats/users/{uuid}/legacy",
                params={
                    "start": su.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "end": eu.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                },
            )
