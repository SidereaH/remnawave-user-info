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


async def test_get_usage_by_range_primary_plural_path_and_params():
    from datetime import datetime, timezone

    captured = {}

    def handler(req):
        captured["path"] = req.url.path
        captured["start"] = req.url.params.get("start")
        captured["end"] = req.url.params.get("end")
        captured["topNodesLimit"] = req.url.params.get("topNodesLimit")
        return httpx.Response(200, json={"response": [{"nodeName": "A", "total": 10}]})

    c = _client(handler)
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 8, tzinfo=timezone.utc)
    data = await c.get_usage_by_range("u1", start, end)
    assert captured["path"] == "/api/bandwidth-stats/users/u1"  # plural primary
    assert captured["start"] == "2026-06-01T00:00:00.000Z"
    assert captured["end"] == "2026-06-08T00:00:00.000Z"
    assert captured["topNodesLimit"] == "10"
    assert data == [{"nodeName": "A", "total": 10}]
    await c.aclose()


async def test_get_usage_by_range_falls_back_to_singular_on_404():
    from datetime import datetime, timezone

    seen = []

    def handler(req):
        seen.append(req.url.path)
        if req.url.path == "/api/bandwidth-stats/users/u1":
            return httpx.Response(404, json={"message": "not found"})
        return httpx.Response(200, json={"response": {"totalBytes": 99}})

    c = _client(handler)
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 8, tzinfo=timezone.utc)
    data = await c.get_usage_by_range("u1", start, end)
    assert seen == ["/api/bandwidth-stats/users/u1", "/api/bandwidth-stats/user/u1"]
    assert data == {"totalBytes": 99}
    await c.aclose()


async def test_get_usage_by_range_reraises_non_404():
    from datetime import datetime, timezone

    def handler(req):
        return httpx.Response(500, json={"message": "boom"})

    c = _client(handler)
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 8, tzinfo=timezone.utc)
    with pytest.raises(RemnawaveError):
        await c.get_usage_by_range("u1", start, end)
    await c.aclose()


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


async def test_network_error_raises_remnawave_error():
    """_request must wrap httpx.ConnectError as RemnawaveError (no-connection branch)."""

    def handler(req):
        raise httpx.ConnectError("boom")

    c = _client(handler)
    with pytest.raises(RemnawaveError, match="Нет связи с панелью"):
        await c.get_user("any-uuid")
    await c.aclose()


async def test_update_expire_normalizes_non_utc_to_utc():
    captured = {}

    def handler(req):
        import json as _json
        captured["body"] = _json.loads(req.content)
        return httpx.Response(200, json={"response": {"uuid": "u1", "username": "x"}})

    from datetime import datetime, timezone, timedelta

    c = _client(handler)
    await c.update_expire("u1", datetime(2026, 12, 31, 12, 0, 0, tzinfo=timezone(timedelta(hours=3))))
    assert captured["body"]["expireAt"] == "2026-12-31T09:00:00.000Z"
    await c.aclose()
