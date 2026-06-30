# Remnawave Telegram Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telegram-бот для админов Remnawave: поиск юзера по TG ID / email / @username (username ищется в `description`) и управление им (вкл/выкл, продление, сброс трафика, ревок подписки, детализация трафика). Доступ ограничен белым списком TG ID, конфиг через `.env`.

**Architecture:** aiogram 3 (polling) + единый async `RemnawaveClient` на httpx. Доступ режется `AccessMiddleware`. Состояние действий — в `callback_data` (фабрики `CallbackData`), ввод даты продления — через FSM. БД нет.

**Tech Stack:** Python 3.11+, aiogram 3, httpx, pydantic-settings, pytest + pytest-asyncio. Тесты HTTP — через `httpx.MockTransport` (без доп. зависимостей).

## Global Constraints

- Python 3.11+ (используется синтаксис `X | None`, `set[int]`).
- Все обращения к API — только через `RemnawaveClient`; пути эндпоинтов нигде больше не хардкодятся.
- Ответы Remnawave обёрнуты в `{"response": ...}` — клиент разворачивает.
- `REMNAWAVE_URL` хранится без хвостового `/`.
- UI-тексты на русском, `parse_mode=HTML`, пользовательский ввод экранируется `html.escape`.
- ⚠️ Пути actions/usage-эндпоинтов — best-known для текущего Remnawave; при первом ручном прогоне против реальной панели сверить со swagger `{REMNAWAVE_URL}/api/docs`. Менять только в `remnawave/client.py`.

---

### Task 1: Скаффолд проекта, зависимости и конфиг

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `config.Settings` (pydantic BaseSettings) с полями `bot_token`, `remnawave_url`, `remnawave_token`, `allowed_admin_ids: str`, `users_page_size: int`, `request_timeout: int`, `log_level: str`; свойством `admin_ids -> set[int]`; функцией `get_settings() -> Settings`.

- [ ] **Step 1: git init + файлы окружения**

```bash
cd /home/siderea/vpn/kot
git init
```

`requirements.txt`:
```
aiogram>=3.4,<4
httpx>=0.27
pydantic-settings>=2.2
pytest>=8
pytest-asyncio>=0.23
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
.venv/
.pytest_cache/
```

`.env.example`:
```
BOT_TOKEN=
REMNAWAVE_URL=https://panel.example.com
REMNAWAVE_TOKEN=
ALLOWED_ADMIN_IDS=111111111,222222222
USERS_PAGE_SIZE=250
REQUEST_TIMEOUT=20
LOG_LEVEL=INFO
```

- [ ] **Step 2: Написать падающий тест** в `tests/test_config.py`

```python
from config import Settings


def _make(**over):
    base = dict(
        bot_token="x",
        remnawave_url="https://panel.example.com/",
        remnawave_token="t",
        allowed_admin_ids="111, 222 ,333",
    )
    base.update(over)
    return Settings(**base)


def test_admin_ids_parsed_to_set_of_ints():
    assert _make().admin_ids == {111, 222, 333}


def test_admin_ids_empty_string_is_empty_set():
    assert _make(allowed_admin_ids="").admin_ids == set()


def test_url_trailing_slash_stripped():
    assert _make().remnawave_url == "https://panel.example.com"


def test_defaults():
    s = _make()
    assert s.users_page_size == 250
    assert s.request_timeout == 20
```

Создать пустой `tests/__init__.py`.

- [ ] **Step 3: Запустить — убедиться, что падает**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'config'`).

- [ ] **Step 4: Реализовать `config.py`**

```python
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    bot_token: str
    remnawave_url: str
    remnawave_token: str
    allowed_admin_ids: str = ""
    users_page_size: int = 250
    request_timeout: int = 20
    log_level: str = "INFO"

    @field_validator("remnawave_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def admin_ids(self) -> set[int]:
        return {
            int(x.strip())
            for x in self.allowed_admin_ids.split(",")
            if x.strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 5: Запустить тесты — убедиться, что проходят**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: project scaffold and config"
```

---

### Task 2: Модель пользователя Remnawave

**Files:**
- Create: `remnawave/__init__.py`
- Create: `remnawave/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces: `remnawave.models.RemnaUser` (dataclass) с полями `uuid: str`, `username: str`, `status: str`, `used_traffic_bytes: int`, `traffic_limit_bytes: int`, `expire_at: datetime | None`, `telegram_id: int | None`, `email: str | None`, `description: str`, `subscription_url: str | None`, `short_uuid: str | None`, `raw: dict`; classmethod `from_dict(d: dict) -> RemnaUser`.

- [ ] **Step 1: Написать падающий тест** в `tests/test_models.py`

```python
from datetime import datetime

from remnawave.models import RemnaUser


def test_from_dict_maps_camelcase_fields():
    u = RemnaUser.from_dict(
        {
            "uuid": "abc",
            "username": "john",
            "status": "ACTIVE",
            "usedTrafficBytes": "1024",
            "trafficLimitBytes": 0,
            "expireAt": "2026-12-31T23:59:00.000Z",
            "telegramId": 555,
            "email": "j@e.com",
            "description": "tg @john_doe note",
            "subscriptionUrl": "https://s/abc",
            "shortUuid": "sh",
        }
    )
    assert u.uuid == "abc"
    assert u.used_traffic_bytes == 1024
    assert u.traffic_limit_bytes == 0
    assert isinstance(u.expire_at, datetime)
    assert u.telegram_id == 555
    assert u.description == "tg @john_doe note"


def test_from_dict_handles_missing_and_null():
    u = RemnaUser.from_dict({"uuid": "x"})
    assert u.username == ""
    assert u.used_traffic_bytes == 0
    assert u.expire_at is None
    assert u.telegram_id is None
    assert u.description == ""
    assert u.raw == {"uuid": "x"}
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'remnawave'`).

- [ ] **Step 3: Реализовать**

`remnawave/__init__.py` — пустой файл.

`remnawave/models.py`:
```python
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
        return cls(
            uuid=d.get("uuid", ""),
            username=d.get("username", ""),
            status=d.get("status", ""),
            used_traffic_bytes=_to_int(d.get("usedTrafficBytes")),
            traffic_limit_bytes=_to_int(d.get("trafficLimitBytes")),
            expire_at=_parse_dt(d.get("expireAt")),
            telegram_id=d.get("telegramId"),
            email=d.get("email"),
            description=d.get("description") or "",
            subscription_url=d.get("subscriptionUrl"),
            short_uuid=d.get("shortUuid"),
            raw=d,
        )
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: RemnaUser model"
```

---

### Task 3: RemnawaveClient (HTTP-слой)

**Files:**
- Create: `remnawave/client.py`
- Create: `tests/test_client.py`

**Interfaces:**
- Consumes: `remnawave.models.RemnaUser`.
- Produces: `remnawave.client.RemnawaveError(Exception)`; `remnawave.client.RemnawaveClient` с конструктором `(base_url, token, timeout=20, page_size=250, transport=None)` и async-методами:
  - `get_by_telegram_id(tg_id: int) -> list[RemnaUser]`
  - `get_by_email(email: str) -> list[RemnaUser]`
  - `get_user(uuid: str) -> RemnaUser`
  - `search_by_description(needle: str, max_pages: int = 100) -> list[RemnaUser]`
  - `enable_user(uuid) / disable_user(uuid) / reset_traffic(uuid) -> RemnaUser | None`
  - `revoke_subscription(uuid) -> RemnaUser`
  - `update_expire(uuid, expire_at: datetime) -> RemnaUser`
  - `get_usage(uuid) -> Any`
  - `aclose() -> None`

- [ ] **Step 1: Написать падающий тест** в `tests/test_client.py`

```python
import json

import httpx
import pytest

from remnawave.client import RemnawaveClient, RemnawaveError

pytestmark = pytest.mark.asyncio


def _client(handler):
    transport = httpx.MockTransport(handler)
    return RemnawaveClient(
        "https://panel.example.com", "tok", page_size=2, transport=transport
    )


async def test_get_by_telegram_id_unwraps_array():
    def handler(req):
        assert req.url.path == "/api/users/by-telegram-id/555"
        assert req.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, json={"response": [{"uuid": "a", "username": "john"}]})

    c = _client(handler)
    users = await c.get_by_telegram_id(555)
    assert len(users) == 1 and users[0].username == "john"
    await c.aclose()


async def test_search_by_description_filters_substring_case_insensitive():
    page0 = {"response": {"total": 3, "users": [
        {"uuid": "1", "description": "owner @JohnDoe"},
        {"uuid": "2", "description": "someone else"},
    ]}}
    page1 = {"response": {"total": 3, "users": [
        {"uuid": "3", "description": "ref: @johndoe again"},
    ]}}

    def handler(req):
        start = int(req.url.params.get("start", "0"))
        return httpx.Response(200, json=page0 if start == 0 else page1)

    c = _client(handler)
    users = await c.search_by_description("@johndoe")
    assert {u.uuid for u in users} == {"1", "3"}
    await c.aclose()


async def test_http_error_raises_remnawave_error():
    def handler(req):
        return httpx.Response(404, json={"message": "nope"})

    c = _client(handler)
    with pytest.raises(RemnawaveError):
        await c.get_user("missing")
    await c.aclose()


async def test_update_expire_sends_patch_with_uuid():
    captured = {}

    def handler(req):
        captured["method"] = req.method
        captured["path"] = req.url.path
        captured["body"] = json.loads(req.content)
        return httpx.Response(200, json={"response": {"uuid": "u1", "username": "x"}})

    from datetime import datetime, timezone

    c = _client(handler)
    u = await c.update_expire("u1", datetime(2026, 12, 31, tzinfo=timezone.utc))
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/api/users"
    assert captured["body"]["uuid"] == "u1"
    assert "expireAt" in captured["body"]
    assert u.uuid == "u1"
    await c.aclose()
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python -m pytest tests/test_client.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'remnawave.client'`).

- [ ] **Step 3: Реализовать `remnawave/client.py`**

```python
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from .models import RemnaUser

logger = logging.getLogger(__name__)


class RemnawaveError(Exception):
    """Понятная для пользователя ошибка обращения к панели."""


class RemnawaveClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: int = 20,
        page_size: int = 250,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._page_size = page_size
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
            raise RemnawaveError(f"Панель ответила {e.response.status_code}") from e
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
            response = response["users"]
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
            if total and start >= total:
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

    async def revoke_subscription(self, uuid: str) -> RemnaUser:
        users = self._as_users(
            await self._request("POST", f"/api/users/{uuid}/actions/revoke")
        )
        return users[0] if users else await self.get_user(uuid)

    async def update_expire(self, uuid: str, expire_at: datetime) -> RemnaUser:
        body = {
            "uuid": uuid,
            "expireAt": expire_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        }
        users = self._as_users(await self._request("PATCH", "/api/users", json=body))
        return users[0] if users else await self.get_user(uuid)

    async def get_usage(self, uuid: str) -> Any:
        # ⚠️ Сверить путь со swagger при ручном прогоне.
        return await self._request("GET", f"/api/users/stats/usage/{uuid}")
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `python -m pytest tests/test_client.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: RemnawaveClient with mock-transport tests"
```

---

### Task 4: Детект типа запроса

**Files:**
- Create: `detect.py`
- Create: `tests/test_detect.py`

**Interfaces:**
- Produces: `detect.detect_query(text: str) -> tuple[str, str]` — возвращает `(kind, value)`, где `kind ∈ {"email", "telegram_id", "username"}`, а `value` — нормализованное значение (для username — без ведущего `@`).

- [ ] **Step 1: Написать падающий тест** в `tests/test_detect.py`

```python
import pytest

from detect import detect_query


@pytest.mark.parametrize(
    "text,expected",
    [
        ("user@example.com", ("email", "user@example.com")),
        ("  user@example.com  ", ("email", "user@example.com")),
        ("@john_doe", ("username", "john_doe")),
        ("123456789", ("telegram_id", "123456789")),
        ("john_doe", ("username", "john_doe")),
        ("John Doe", ("username", "John Doe")),
    ],
)
def test_detect_query(text, expected):
    assert detect_query(text) == expected
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python -m pytest tests/test_detect.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'detect'`).

- [ ] **Step 3: Реализовать `detect.py`**

```python
import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def detect_query(text: str) -> tuple[str, str]:
    t = text.strip()
    if _EMAIL_RE.match(t):
        return "email", t
    if t.startswith("@"):
        return "username", t[1:].strip()
    if t.isdigit():
        return "telegram_id", t
    return "username", t
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `python -m pytest tests/test_detect.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: query type detection"
```

---

### Task 5: Форматирование карточки и трафика

**Files:**
- Create: `formatting.py`
- Create: `tests/test_formatting.py`

**Interfaces:**
- Consumes: `remnawave.models.RemnaUser`.
- Produces: `formatting.human_bytes(n: int) -> str`; `formatting.render_card(u: RemnaUser) -> str`; `formatting.render_usage(data) -> str`.

- [ ] **Step 1: Написать падающий тест** в `tests/test_formatting.py`

```python
from datetime import datetime, timezone

from formatting import human_bytes, render_card
from remnawave.models import RemnaUser


def test_human_bytes():
    assert human_bytes(0) == "0 B"
    assert human_bytes(1024) == "1.00 KB"
    assert human_bytes(1024 ** 3) == "1.00 GB"


def _user(**over):
    base = dict(
        uuid="u-1", username="john", status="ACTIVE",
        used_traffic_bytes=1024 ** 3, traffic_limit_bytes=0,
        expire_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        telegram_id=555, email="j@e.com",
        description="ref @john_doe", subscription_url="https://s/u-1",
        short_uuid="sh", raw={},
    )
    base.update(over)
    return RemnaUser(**base)


def test_render_card_contains_key_fields_and_unlimited_traffic():
    txt = render_card(_user())
    assert "john" in txt
    assert "ACTIVE" in txt
    assert "∞" in txt           # безлимит
    assert "555" in txt
    assert "u-1" in txt


def test_render_card_escapes_html():
    txt = render_card(_user(description="<b>x</b> @y"))
    assert "<b>x</b>" not in txt
    assert "&lt;b&gt;" in txt
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python -m pytest tests/test_formatting.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'formatting'`).

- [ ] **Step 3: Реализовать `formatting.py`**

```python
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
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `python -m pytest tests/test_formatting.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: card and usage formatting"
```

---

### Task 6: Клавиатуры и callback-фабрики

**Files:**
- Create: `keyboards.py`
- Create: `tests/test_keyboards.py`

**Interfaces:**
- Consumes: `remnawave.models.RemnaUser`.
- Produces:
  - `keyboards.UserCB(CallbackData, prefix="u")` с полями `action: str`, `uuid: str`.
  - `keyboards.ExtendCB(CallbackData, prefix="ext")` с полями `days: str`, `uuid: str`.
  - `keyboards.ConfirmCB(CallbackData, prefix="cf")` с полями `action: str`, `uuid: str`, `yes: int`.
  - `keyboards.card_keyboard(u: RemnaUser) -> InlineKeyboardMarkup`
  - `keyboards.extend_keyboard(uuid: str) -> InlineKeyboardMarkup`
  - `keyboards.confirm_keyboard(action: str, uuid: str) -> InlineKeyboardMarkup`
  - `keyboards.choice_keyboard(users: list[RemnaUser]) -> InlineKeyboardMarkup` (callback = `UserCB(action="open", uuid=...)`)

- [ ] **Step 1: Написать падающий тест** в `tests/test_keyboards.py`

```python
from keyboards import (
    ConfirmCB,
    UserCB,
    card_keyboard,
    choice_keyboard,
    confirm_keyboard,
    extend_keyboard,
)
from remnawave.models import RemnaUser


def _user(status="ACTIVE"):
    return RemnaUser(
        uuid="u-1", username="john", status=status,
        used_traffic_bytes=0, traffic_limit_bytes=0, expire_at=None,
        telegram_id=None, email=None, description="", subscription_url=None,
        short_uuid=None, raw={},
    )


def _all_cb(markup):
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


def test_card_keyboard_shows_enable_when_disabled():
    cbs = _all_cb(card_keyboard(_user(status="DISABLED")))
    assert any("enable" in c for c in cbs)
    assert not any(c.startswith("u:disable") for c in cbs)


def test_card_keyboard_shows_disable_when_active():
    cbs = _all_cb(card_keyboard(_user(status="ACTIVE")))
    assert any("disable" in c for c in cbs)


def test_extend_keyboard_has_preset_and_custom():
    cbs = _all_cb(extend_keyboard("u-1"))
    assert any(c == "ext:1:u-1" for c in cbs)
    assert any(c == "ext:30:u-1" for c in cbs)
    assert any(c == "ext:custom:u-1" for c in cbs)


def test_confirm_keyboard_yes_no():
    cbs = _all_cb(confirm_keyboard("revoke", "u-1"))
    assert "cf:revoke:u-1:1" in cbs
    assert "cf:revoke:u-1:0" in cbs


def test_choice_keyboard_one_button_per_user():
    markup = choice_keyboard([_user(), _user()])
    assert len(_all_cb(markup)) == 2
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python -m pytest tests/test_keyboards.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'keyboards'`).

- [ ] **Step 3: Реализовать `keyboards.py`**

```python
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from remnawave.models import RemnaUser


class UserCB(CallbackData, prefix="u"):
    action: str  # enable|disable|extend_menu|reset_ask|revoke_ask|usage|refresh|open
    uuid: str


class ExtendCB(CallbackData, prefix="ext"):
    days: str  # "30" | "90" | "180" | "custom"
    uuid: str


class ConfirmCB(CallbackData, prefix="cf"):
    action: str  # reset | revoke
    uuid: str
    yes: int


def card_keyboard(u: RemnaUser) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if u.status == "DISABLED":
        b.button(text="🟢 Включить", callback_data=UserCB(action="enable", uuid=u.uuid))
    else:
        b.button(text="🔴 Выключить", callback_data=UserCB(action="disable", uuid=u.uuid))
    b.button(text="➕ Продлить", callback_data=UserCB(action="extend_menu", uuid=u.uuid))
    b.button(text="🧹 Сброс трафика", callback_data=UserCB(action="reset_ask", uuid=u.uuid))
    b.button(text="🔁 Ревок подписки", callback_data=UserCB(action="revoke_ask", uuid=u.uuid))
    b.button(text="📊 Трафик по узлам", callback_data=UserCB(action="usage", uuid=u.uuid))
    b.button(text="🔄 Обновить", callback_data=UserCB(action="refresh", uuid=u.uuid))
    b.adjust(1, 1, 2, 1, 1)
    return b.as_markup()


def extend_keyboard(uuid: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="+1 день", callback_data=ExtendCB(days="1", uuid=uuid))
    for d in ("30", "90", "180"):
        b.button(text=f"+{d} дней", callback_data=ExtendCB(days=d, uuid=uuid))
    b.button(text="📅 Ввести дату", callback_data=ExtendCB(days="custom", uuid=uuid))
    b.button(text="⬅️ Назад", callback_data=UserCB(action="refresh", uuid=uuid))
    b.adjust(1, 3, 1, 1)
    return b.as_markup()


def confirm_keyboard(action: str, uuid: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да", callback_data=ConfirmCB(action=action, uuid=uuid, yes=1))
    b.button(text="❌ Нет", callback_data=ConfirmCB(action=action, uuid=uuid, yes=0))
    b.adjust(2)
    return b.as_markup()


def choice_keyboard(users: list[RemnaUser]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for u in users:
        label = u.username or u.uuid
        if u.email:
            label = f"{label} · {u.email}"
        b.button(text=label[:60], callback_data=UserCB(action="open", uuid=u.uuid))
    b.adjust(1)
    return b.as_markup()
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `python -m pytest tests/test_keyboards.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: inline keyboards and callback factories"
```

---

### Task 7: Middleware контроля доступа

**Files:**
- Create: `middlewares/__init__.py`
- Create: `middlewares/access.py`
- Create: `tests/test_access.py`

**Interfaces:**
- Produces: `middlewares.access.AccessMiddleware(allowed: set[int])` — `BaseMiddleware`; пропускает событие в handler только если `event.from_user.id in allowed`, иначе отвечает отказом и не вызывает handler.

- [ ] **Step 1: Написать падающий тест** в `tests/test_access.py`

```python
import pytest

from middlewares.access import AccessMiddleware

pytestmark = pytest.mark.asyncio


class _User:
    def __init__(self, uid):
        self.id = uid


class _Event:
    def __init__(self, uid):
        self.from_user = _User(uid)
        self.answered = None

    async def answer(self, text, **kw):
        self.answered = text


async def test_allowed_user_calls_handler():
    mw = AccessMiddleware({111})
    called = {}

    async def handler(event, data):
        called["ok"] = True
        return "done"

    res = await mw(handler, _Event(111), {})
    assert called.get("ok") is True
    assert res == "done"


async def test_blocked_user_does_not_call_handler():
    mw = AccessMiddleware({111})
    called = {}

    async def handler(event, data):
        called["ok"] = True

    ev = _Event(999)
    await mw(handler, ev, {})
    assert "ok" not in called
    assert ev.answered is not None
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python -m pytest tests/test_access.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'middlewares'`).

- [ ] **Step 3: Реализовать**

`middlewares/__init__.py` — пустой файл.

`middlewares/access.py`:
```python
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class AccessMiddleware(BaseMiddleware):
    def __init__(self, allowed: set[int]) -> None:
        self._allowed = allowed

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        uid = getattr(user, "id", None)
        if uid not in self._allowed:
            logger.warning("Доступ запрещён: telegram_id=%s", uid)
            answer = getattr(event, "answer", None)
            if answer is not None:
                await answer("⛔️ Нет доступа.")
            return None
        return await handler(event, data)
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `python -m pytest tests/test_access.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: access-control middleware"
```

---

### Task 8: FSM-состояния и хендлер поиска

**Files:**
- Create: `states.py`
- Create: `handlers/__init__.py`
- Create: `handlers/search.py`
- Create: `tests/test_search_logic.py`

**Interfaces:**
- Consumes: `detect.detect_query`, `remnawave.client.RemnawaveClient`, `formatting.render_card`, `keyboards.card_keyboard / choice_keyboard`.
- Produces:
  - `states.ExtendStates(StatesGroup)` с состоянием `waiting_for_date`.
  - `handlers.search.lookup(client, kind, value) -> list[RemnaUser]` (чистая корутина, маршрутизирует тип → метод клиента).
  - `handlers.search.router` (aiogram `Router`) c хендлером на текстовые сообщения.

- [ ] **Step 1: Написать падающий тест** в `tests/test_search_logic.py`

```python
import pytest

from handlers.search import lookup

pytestmark = pytest.mark.asyncio


class _FakeClient:
    def __init__(self):
        self.calls = []

    async def get_by_email(self, v):
        self.calls.append(("email", v))
        return ["E"]

    async def get_by_telegram_id(self, v):
        self.calls.append(("tg", v))
        return ["T"]

    async def search_by_description(self, v):
        self.calls.append(("desc", v))
        return ["D"]


async def test_lookup_routes_email():
    c = _FakeClient()
    assert await lookup(c, "email", "a@b.com") == ["E"]
    assert c.calls == [("email", "a@b.com")]


async def test_lookup_routes_telegram_id_as_int():
    c = _FakeClient()
    await lookup(c, "telegram_id", "555")
    assert c.calls == [("tg", 555)]


async def test_lookup_routes_username_to_description():
    c = _FakeClient()
    await lookup(c, "username", "john")
    assert c.calls == [("desc", "john")]
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python -m pytest tests/test_search_logic.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'handlers'`).

- [ ] **Step 3: Реализовать**

`states.py`:
```python
from aiogram.fsm.state import State, StatesGroup


class ExtendStates(StatesGroup):
    waiting_for_date = State()
```

`handlers/__init__.py` — пустой файл.

`handlers/search.py`:
```python
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from detect import detect_query
from formatting import render_card
from keyboards import card_keyboard, choice_keyboard
from remnawave.client import RemnawaveClient, RemnawaveError
from remnawave.models import RemnaUser

logger = logging.getLogger(__name__)
router = Router(name="search")

_HELP = (
    "🔎 Пришли для поиска:\n"
    "• <b>Telegram ID</b> — например <code>123456789</code>\n"
    "• <b>Email</b> — например <code>user@example.com</code>\n"
    "• <b>@username</b> — ищется в описании пользователя"
)


async def lookup(
    client: RemnawaveClient, kind: str, value: str
) -> list[RemnaUser]:
    if kind == "email":
        return await client.get_by_email(value)
    if kind == "telegram_id":
        return await client.get_by_telegram_id(int(value))
    return await client.search_by_description(value)


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(_HELP)


@router.message(F.text)
async def on_search(message: Message, client: RemnawaveClient) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer(_HELP)
        return
    kind, value = detect_query(text)
    try:
        users = await lookup(client, kind, value)
    except RemnawaveError as e:
        await message.answer(f"⚠️ {e}")
        return
    if not users:
        await message.answer("🤷 Ничего не найдено.")
        return
    if len(users) == 1:
        u = users[0]
        await message.answer(render_card(u), reply_markup=card_keyboard(u))
        return
    await message.answer(
        f"Найдено {len(users)}. Выбери:",
        reply_markup=choice_keyboard(users[:20]),
    )
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `python -m pytest tests/test_search_logic.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: search handler and lookup routing"
```

---

### Task 9: Хендлеры действий (callbacks + FSM продления)

**Files:**
- Create: `handlers/actions.py`
- Create: `tests/test_extend_date.py`

**Interfaces:**
- Consumes: `keyboards.UserCB / ExtendCB / ConfirmCB`, `keyboards.card_keyboard / extend_keyboard / confirm_keyboard`, `formatting.render_card / render_usage`, `states.ExtendStates`, `remnawave.client.RemnawaveClient`.
- Produces:
  - `handlers.actions.parse_date(text: str) -> datetime` (raises `ValueError` на неверном формате; формат `YYYY-MM-DD`, UTC).
  - `handlers.actions.router` (aiogram `Router`).

- [ ] **Step 1: Написать падающий тест** в `tests/test_extend_date.py`

```python
from datetime import timezone

import pytest

from handlers.actions import parse_date


def test_parse_date_ok():
    d = parse_date("2026-12-31")
    assert (d.year, d.month, d.day) == (2026, 12, 31)
    assert d.tzinfo == timezone.utc


@pytest.mark.parametrize("bad", ["31-12-2026", "2026/12/31", "хрень", ""])
def test_parse_date_invalid_raises(bad):
    with pytest.raises(ValueError):
        parse_date(bad)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python -m pytest tests/test_extend_date.py -v`
Expected: FAIL (`ModuleNotFoundError` / `ImportError: cannot import name 'parse_date'`).

- [ ] **Step 3: Реализовать `handlers/actions.py`**

```python
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from formatting import render_card, render_usage
from keyboards import (
    ConfirmCB,
    ExtendCB,
    UserCB,
    card_keyboard,
    confirm_keyboard,
    extend_keyboard,
)
from remnawave.client import RemnawaveClient, RemnawaveError
from states import ExtendStates

logger = logging.getLogger(__name__)
router = Router(name="actions")


def parse_date(text: str) -> datetime:
    dt = datetime.strptime(text.strip(), "%Y-%m-%d")
    return dt.replace(tzinfo=timezone.utc)


async def _show_card(cq: CallbackQuery, client: RemnawaveClient, uuid: str) -> None:
    user = await client.get_user(uuid)
    await cq.message.edit_text(render_card(user), reply_markup=card_keyboard(user))


@router.callback_query(UserCB.filter(F.action == "open"))
@router.callback_query(UserCB.filter(F.action == "refresh"))
async def cb_open(cq: CallbackQuery, callback_data: UserCB, client: RemnawaveClient):
    try:
        await _show_card(cq, client, callback_data.uuid)
    except RemnawaveError as e:
        await cq.answer(str(e), show_alert=True)
        return
    await cq.answer()


@router.callback_query(UserCB.filter(F.action == "enable"))
async def cb_enable(cq: CallbackQuery, callback_data: UserCB, client: RemnawaveClient):
    await _do_simple(cq, client, callback_data.uuid, client.enable_user, "Включён")


@router.callback_query(UserCB.filter(F.action == "disable"))
async def cb_disable(cq: CallbackQuery, callback_data: UserCB, client: RemnawaveClient):
    await _do_simple(cq, client, callback_data.uuid, client.disable_user, "Выключен")


async def _do_simple(cq, client, uuid, method, ok_text):
    try:
        await method(uuid)
        await _show_card(cq, client, uuid)
    except RemnawaveError as e:
        await cq.answer(str(e), show_alert=True)
        return
    await cq.answer(ok_text)


@router.callback_query(UserCB.filter(F.action == "usage"))
async def cb_usage(cq: CallbackQuery, callback_data: UserCB, client: RemnawaveClient):
    try:
        data = await client.get_usage(callback_data.uuid)
    except RemnawaveError as e:
        await cq.answer(str(e), show_alert=True)
        return
    await cq.message.answer(render_usage(data))
    await cq.answer()


@router.callback_query(UserCB.filter(F.action == "extend_menu"))
async def cb_extend_menu(cq: CallbackQuery, callback_data: UserCB):
    await cq.message.edit_reply_markup(
        reply_markup=extend_keyboard(callback_data.uuid)
    )
    await cq.answer()


@router.callback_query(ExtendCB.filter(F.days != "custom"))
async def cb_extend_preset(cq: CallbackQuery, callback_data: ExtendCB, client: RemnawaveClient):
    days = int(callback_data.days)
    new_expire = datetime.now(timezone.utc) + timedelta(days=days)
    try:
        await client.update_expire(callback_data.uuid, new_expire)
        await _show_card(cq, client, callback_data.uuid)
    except RemnawaveError as e:
        await cq.answer(str(e), show_alert=True)
        return
    await cq.answer(f"Продлено на {days} дней")


@router.callback_query(ExtendCB.filter(F.days == "custom"))
async def cb_extend_custom(cq: CallbackQuery, callback_data: ExtendCB, state: FSMContext):
    await state.update_data(uuid=callback_data.uuid)
    await state.set_state(ExtendStates.waiting_for_date)
    await cq.message.answer("📅 Пришли дату окончания в формате <b>YYYY-MM-DD</b>:")
    await cq.answer()


@router.message(ExtendStates.waiting_for_date, F.text)
async def on_custom_date(message: Message, state: FSMContext, client: RemnawaveClient):
    try:
        new_expire = parse_date(message.text or "")
    except ValueError:
        await message.answer("❌ Неверный формат. Нужно <b>YYYY-MM-DD</b>, например 2026-12-31.")
        return
    data = await state.get_data()
    uuid = data.get("uuid")
    await state.clear()
    try:
        user = await client.update_expire(uuid, new_expire)
    except RemnawaveError as e:
        await message.answer(f"⚠️ {e}")
        return
    await message.answer(render_card(user), reply_markup=card_keyboard(user))


@router.callback_query(UserCB.filter(F.action == "reset_ask"))
async def cb_reset_ask(cq: CallbackQuery, callback_data: UserCB):
    await cq.message.edit_reply_markup(
        reply_markup=confirm_keyboard("reset", callback_data.uuid)
    )
    await cq.answer("Подтвердите сброс трафика")


@router.callback_query(UserCB.filter(F.action == "revoke_ask"))
async def cb_revoke_ask(cq: CallbackQuery, callback_data: UserCB):
    await cq.message.edit_reply_markup(
        reply_markup=confirm_keyboard("revoke", callback_data.uuid)
    )
    await cq.answer("Подтвердите ревок подписки")


@router.callback_query(ConfirmCB.filter())
async def cb_confirm(cq: CallbackQuery, callback_data: ConfirmCB, client: RemnawaveClient):
    if not callback_data.yes:
        await _safe_show(cq, client, callback_data.uuid)
        await cq.answer("Отменено")
        return
    try:
        if callback_data.action == "reset":
            await client.reset_traffic(callback_data.uuid)
            done = "Трафик сброшен"
        else:
            await client.revoke_subscription(callback_data.uuid)
            done = "Подписка перевыпущена"
        await _show_card(cq, client, callback_data.uuid)
    except RemnawaveError as e:
        await cq.answer(str(e), show_alert=True)
        return
    await cq.answer(done)


async def _safe_show(cq, client, uuid):
    try:
        await _show_card(cq, client, uuid)
    except RemnawaveError:
        pass
```

- [ ] **Step 4: Запустить тесты — убедиться, что проходят**

Run: `python -m pytest tests/test_extend_date.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Прогнать весь тест-сьют**

Run: `python -m pytest -v`
Expected: PASS (все тесты зелёные).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: action callbacks and FSM extend flow"
```

---

### Task 10: Точка входа, DI клиента и README

**Files:**
- Create: `bot.py`
- Create: `README.md`

**Interfaces:**
- Consumes: `config.get_settings`, `remnawave.client.RemnawaveClient`, `middlewares.access.AccessMiddleware`, `handlers.search.router`, `handlers.actions.router`.
- Produces: исполняемый `bot.py` (polling); `RemnawaveClient` прокидывается в хендлеры через `workflow_data` (DI aiogram), middleware доступа навешан на message и callback_query.

- [ ] **Step 1: Реализовать `bot.py`**

```python
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import get_settings
from handlers import actions, search
from middlewares.access import AccessMiddleware
from remnawave.client import RemnawaveClient


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    client = RemnawaveClient(
        base_url=settings.remnawave_url,
        token=settings.remnawave_token,
        timeout=settings.request_timeout,
        page_size=settings.users_page_size,
    )

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp["client"] = client

    access = AccessMiddleware(settings.admin_ids)
    dp.message.middleware(access)
    dp.callback_query.middleware(access)

    dp.include_router(search.router)
    dp.include_router(actions.router)

    logging.getLogger(__name__).info(
        "Бот запущен. Админов: %d", len(settings.admin_ids)
    )
    try:
        await dp.start_polling(bot)
    finally:
        await client.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Проверить импорт без запуска polling**

Run: `python -c "import bot; print('ok')"`
Expected: печатает `ok` без ошибок (наличие `.env` не требуется для импорта модуля).

- [ ] **Step 3: Smoke-проверка конфигом**

Создать временный `.env` из `.env.example` с фиктивными значениями, затем:

Run: `python -c "from config import get_settings; s=get_settings(); print(sorted(s.admin_ids))"`
Expected: печатает `[111111111, 222222222]`.

- [ ] **Step 4: Написать `README.md`**

````markdown
# Remnawave Telegram Bot

Бот для админов: поиск и управление пользователями Remnawave.

## Возможности
- Поиск по Telegram ID, email или `@username` (username ищется в `description`).
- Карточка юзера: статус, трафик, срок, контакты, UUID, подписка.
- Действия: вкл/выкл, продление (+30/+90/+180 или дата), сброс трафика,
  ревок подписки, детализация трафика по узлам.
- Доступ только для Telegram ID из белого списка.

## Установка
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить значения
python bot.py
```

## Переменные .env
| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | токен бота от @BotFather |
| `REMNAWAVE_URL` | адрес панели, напр. `https://panel.example.com` |
| `REMNAWAVE_TOKEN` | API-токен Remnawave (Bearer) |
| `ALLOWED_ADMIN_IDS` | TG ID админов через запятую |
| `USERS_PAGE_SIZE` | размер страницы при поиске по описанию (по умолч. 250) |
| `REQUEST_TIMEOUT` | таймаут запросов к API, сек (по умолч. 20) |
| `LOG_LEVEL` | уровень логов (по умолч. INFO) |

## Тесты
```bash
python -m pytest -v
```

## Заметка по API
Пути actions/usage-эндпоинтов заданы под текущий Remnawave в
`remnawave/client.py`. Если панель отвечает 404 на действие или «📊 Детализация
недоступна», сверь путь со swagger `{REMNAWAVE_URL}/api/docs` и поправь в клиенте.
````

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: bot entrypoint, DI wiring and README"
```

---

## Self-Review

**Spec coverage:**
- Доступ по ID → Task 7 (AccessMiddleware) + Task 10 (навеска). ✅
- Поиск по TG ID / email / username-в-description → Task 3 (client) + Task 4 (detect) + Task 8 (lookup/handler). ✅
- Авто-детект типа по тексту → Task 4. ✅
- Карточка с полными полями → Task 5. ✅
- Действия вкл/выкл/продлить(FSM)/сброс/ревок/детализация → Task 6 (кнопки) + Task 9 (хендлеры). ✅
- Конфиг через .env → Task 1. ✅
- Обработка ошибок API → Task 3 (`RemnawaveError`) + хендлеры ловят. ✅
- Тестирование → юнит-тесты в каждой задаче. ✅

**Placeholder scan:** код приведён полностью в каждом шаге; «TODO/TBD» нет. Помечен только риск путей API (Global Constraints + README) — это осознанная верификация против реальной панели, не плейсхолдер.

**Type consistency:** имена методов клиента (`get_by_telegram_id`, `get_by_email`, `search_by_description`, `get_user`, `enable_user`, `disable_user`, `reset_traffic`, `revoke_subscription`, `update_expire`, `get_usage`) совпадают между Task 3, 8, 9. Callback-фабрики `UserCB/ExtendCB/ConfirmCB` и их поля совпадают между Task 6 и 9. `RemnaUser`-поля совпадают между Task 2, 5, 6.
```
