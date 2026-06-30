"""Tests for handlers/actions.py — focused on the two important fixes."""
from __future__ import annotations

import pytest
from aiogram.exceptions import TelegramBadRequest

from handlers.actions import _show_card, on_custom_date
from remnawave.models import RemnaUser


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

def _make_user() -> RemnaUser:
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


def _not_modified_exc() -> TelegramBadRequest:
    return TelegramBadRequest(method=None, message="Bad Request: message is not modified")


def _other_bad_request_exc() -> TelegramBadRequest:
    return TelegramBadRequest(method=None, message="Bad Request: chat not found")


class FakeMessage:
    """Minimal fake for cq.message."""

    def __init__(self, edit_raises: Exception | None = None):
        self._edit_raises = edit_raises
        self.edit_calls: list[dict] = []

    async def edit_text(self, text: str, reply_markup=None):
        self.edit_calls.append({"text": text, "reply_markup": reply_markup})
        if self._edit_raises is not None:
            raise self._edit_raises


class FakeCQ:
    """Minimal fake for CallbackQuery."""

    def __init__(self, edit_raises: Exception | None = None):
        self.message = FakeMessage(edit_raises=edit_raises)

    async def answer(self, *args, **kwargs):
        pass


class FakeClient:
    """Minimal fake for RemnawaveClient."""

    def __init__(self, user: RemnaUser | None = None):
        self._user = user or _make_user()
        self.update_expire_called = False
        self.update_expire_args: tuple | None = None

    async def get_user(self, uuid: str) -> RemnaUser:
        return self._user

    async def update_expire(self, uuid, new_expire):
        self.update_expire_called = True
        self.update_expire_args = (uuid, new_expire)
        return self._user


class FakeState:
    """Minimal fake for FSMContext."""

    def __init__(self, data: dict):
        self._data = data
        self.cleared = False

    async def get_data(self) -> dict:
        return self._data

    async def clear(self):
        self.cleared = True


class FakeAnswerMessage:
    """Minimal fake for Message (on_custom_date path)."""

    def __init__(self, text: str):
        self.text = text
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs):
        self.answers.append(text)


# ---------------------------------------------------------------------------
# Fix 1: _show_card swallows "message is not modified" TelegramBadRequest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_show_card_swallows_not_modified():
    """_show_card must not raise when edit_text raises 'message is not modified'."""
    cq = FakeCQ(edit_raises=_not_modified_exc())
    client = FakeClient()
    # Should complete without raising
    await _show_card(cq, client, "some-uuid")


@pytest.mark.asyncio
async def test_show_card_reraises_other_bad_request():
    """_show_card must re-raise TelegramBadRequest for unrelated errors."""
    cq = FakeCQ(edit_raises=_other_bad_request_exc())
    client = FakeClient()
    with pytest.raises(TelegramBadRequest):
        await _show_card(cq, client, "some-uuid")


@pytest.mark.asyncio
async def test_show_card_succeeds_normally():
    """_show_card completes normally when edit_text does not raise."""
    cq = FakeCQ()
    client = FakeClient()
    await _show_card(cq, client, "some-uuid")
    assert len(cq.message.edit_calls) == 1


# ---------------------------------------------------------------------------
# Fix 2: on_custom_date guards missing uuid (expired FSM state)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_on_custom_date_missing_uuid_sends_expired_message():
    """When FSM data has no uuid, on_custom_date sends the expiry warning."""
    state = FakeState(data={})  # no "uuid" key
    message = FakeAnswerMessage(text="01.01.27")
    client = FakeClient()

    await on_custom_date(message, state, client)

    assert len(message.answers) == 1
    assert "Сессия истекла" in message.answers[0]
    assert state.cleared  # state.clear() was called before the guard


@pytest.mark.asyncio
async def test_on_custom_date_missing_uuid_does_not_call_update_expire():
    """When FSM data has no uuid, update_expire must NOT be called."""
    state = FakeState(data={})
    message = FakeAnswerMessage(text="01.01.27")
    client = FakeClient()

    await on_custom_date(message, state, client)

    assert not client.update_expire_called


@pytest.mark.asyncio
async def test_on_custom_date_with_uuid_calls_update_expire():
    """Sanity: when uuid is present, update_expire IS called."""
    state = FakeState(data={"uuid": "real-uuid"})
    message = FakeAnswerMessage(text="01.01.27")
    client = FakeClient()

    await on_custom_date(message, state, client)

    assert client.update_expire_called
    assert client.update_expire_args is not None
    assert client.update_expire_args[0] == "real-uuid"
