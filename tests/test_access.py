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
    # Чужим не отвечаем — тишина.
    assert ev.answered is None
