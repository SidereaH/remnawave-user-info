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


class _FakeMessage:
    def __init__(self, text):
        self.text = text
        self.answers = []

    async def answer(self, text, **kw):
        self.answers.append(text)


async def test_on_search_rejects_too_short_username_query():
    """Одна буква не должна сканировать всех — гард по длине."""
    from handlers.search import on_search

    c = _FakeClient()
    msg = _FakeMessage("z")
    await on_search(msg, c)
    assert c.calls == []  # поиск не запускался
    assert msg.answers and "минимум" in msg.answers[0].lower()


class _EmptyClient(_FakeClient):
    """Возвращает пустой результат, чтобы on_search не уходил в рендер."""

    async def get_by_email(self, v):
        self.calls.append(("email", v))
        return []

    async def get_by_telegram_id(self, v):
        self.calls.append(("tg", v))
        return []

    async def search_by_description(self, v):
        self.calls.append(("desc", v))
        return []


async def test_on_search_allows_query_at_min_length():
    from handlers.search import MIN_USERNAME_QUERY, on_search

    c = _EmptyClient()
    msg = _FakeMessage("z" * MIN_USERNAME_QUERY)
    await on_search(msg, c)
    assert c.calls == [("desc", "z" * MIN_USERNAME_QUERY)]


async def test_on_search_short_query_ok_for_telegram_id():
    """Короткий числовой ввод — это TG ID, гард не применяется."""
    from handlers.search import on_search

    c = _EmptyClient()
    msg = _FakeMessage("55")
    await on_search(msg, c)
    assert c.calls == [("tg", 55)]
