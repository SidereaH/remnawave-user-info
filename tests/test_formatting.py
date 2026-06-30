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
