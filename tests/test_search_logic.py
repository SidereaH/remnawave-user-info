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
