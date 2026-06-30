from datetime import datetime

from remnawave.models import RemnaUser


def test_from_dict_used_traffic_from_user_traffic_2_8():
    """Remnawave 2.8.0 nests used traffic under userTraffic."""
    u = RemnaUser.from_dict(
        {
            "uuid": "abc",
            "trafficLimitBytes": 1024 ** 3,
            "userTraffic": {"usedTrafficBytes": 2048, "lifetimeUsedTrafficBytes": 4096},
        }
    )
    assert u.used_traffic_bytes == 2048
    assert u.traffic_limit_bytes == 1024 ** 3


def test_from_dict_used_traffic_legacy_top_level():
    """Pre-2.8 panels keep usedTrafficBytes at the top level — still supported."""
    u = RemnaUser.from_dict({"uuid": "abc", "usedTrafficBytes": "777"})
    assert u.used_traffic_bytes == 777


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
