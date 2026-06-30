"""Dispatch-level integration tests for FSM-aware routing.

Fix 1 (Critical): on_search must NOT fire when FSM state is
ExtendStates.waiting_for_date. Two assertions cover this:

(a) Direct filter inspection — on_search's filters must include
    StateFilter(None). This test fails immediately if Fix 1(a) is reverted,
    regardless of router order.

(b) Real feed_update round-trip — Dispatcher with MemoryStorage, routers
    included in the same order as bot.py (actions then search), FSM state
    pre-seeded to waiting_for_date. A valid date string must reach
    on_custom_date (update_expire called) and must NOT trigger on_search
    (search_by_description not called).
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.filters import StateFilter
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Message, Update, User

from handlers import actions, search
from remnawave.models import RemnaUser
from states import ExtendStates


# ---------------------------------------------------------------------------
# Fake client
# ---------------------------------------------------------------------------

def _make_remna_user() -> RemnaUser:
    return RemnaUser(
        uuid="test-uuid",
        username="testuser",
        status="ACTIVE",
        used_traffic_bytes=0,
        traffic_limit_bytes=0,
        expire_at=None,
        telegram_id=None,
        email=None,
        description="",
        subscription_url=None,
        short_uuid=None,
        raw={},
    )


class FakeClient:
    def __init__(self) -> None:
        self.search_calls: list = []
        self.update_expire_calls: list = []

    async def search_by_description(self, value: str) -> list:
        self.search_calls.append(value)
        return []

    async def get_by_email(self, value: str) -> list:
        return []

    async def get_by_telegram_id(self, value: int) -> list:
        return []

    async def update_expire(self, uuid: str, expire_at: datetime) -> RemnaUser:
        self.update_expire_calls.append((uuid, expire_at))
        return _make_remna_user()


# ---------------------------------------------------------------------------
# (a) Filter inspection — always catches a reverted Fix 1(a)
# ---------------------------------------------------------------------------

def test_on_search_has_state_filter_none() -> None:
    """on_search must carry StateFilter(None) so it is skipped when FSM is active.

    This test fails if Fix 1(a) is reverted, regardless of router order.
    """
    from handlers.search import on_search
    from handlers.search import router as search_router

    for handler in search_router.message.handlers:
        if handler.callback is on_search:
            state_filters = [
                f.callback
                for f in handler.filters
                if isinstance(f.callback, StateFilter)
            ]
            assert state_filters, (
                "on_search must have a StateFilter to avoid shadowing FSM handlers"
            )
            # StateFilter(None) means "only match when there is NO active state"
            assert None in state_filters[0].states, (
                "on_search StateFilter must include None (no active FSM state)"
            )
            return

    pytest.fail("on_search handler not found in search router — registration broken")


# ---------------------------------------------------------------------------
# (b) Real feed_update integration test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_date_input_in_waiting_state_routes_to_custom_date() -> None:
    """When FSM state is waiting_for_date a date string must reach on_custom_date.

    Asserts:
    - search_by_description is NOT called (on_search was skipped)
    - update_expire IS called (on_custom_date ran successfully)
    """
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    # Fixed router order: actions before search (matches bot.py after Fix 1b)
    dp.include_router(actions.router)
    dp.include_router(search.router)

    fake_client = FakeClient()

    # Minimal bot stub — any call to bot.send_message() etc. returns an AsyncMock
    bot: Bot = AsyncMock()
    bot.id = 42
    bot.send_message = AsyncMock(return_value=MagicMock())

    user_id = 100
    chat_id = 100

    # Pre-seed FSM state and data in storage
    key = StorageKey(bot_id=42, chat_id=chat_id, user_id=user_id)
    await storage.set_state(key=key, state=ExtendStates.waiting_for_date)
    await storage.set_data(key=key, data={"uuid": "test-uuid"})

    # Build a minimal Update containing a text message
    tg_user = User(id=user_id, is_bot=False, first_name="Test")
    tg_chat = Chat(id=chat_id, type="private")
    msg = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=tg_chat,
        from_user=tg_user,
        text="01.01.27",
    )
    update = Update(update_id=1, message=msg)

    # Process the update; inject our fake client as workflow data
    await dp.feed_update(bot, update, client=fake_client)

    assert fake_client.search_calls == [], (
        "on_search must NOT run when FSM state is ExtendStates.waiting_for_date"
    )
    assert len(fake_client.update_expire_calls) == 1, (
        "on_custom_date must have called client.update_expire exactly once"
    )
    called_uuid, called_expire = fake_client.update_expire_calls[0]
    assert called_uuid == "test-uuid"
    assert called_expire.year == 2027
