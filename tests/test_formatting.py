from datetime import datetime, timezone

from formatting import human_bytes, render_card, render_usage
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


def test_render_card_european_date_format():
    # 2026-12-31 00:00 UTC -> ДД.ММ.ГГ ЧЧ:ММ
    txt = render_card(_user())
    assert "31.12.26 00:00" in txt


def test_render_card_unlimited_expiry():
    assert "Истекает: ∞" in render_card(_user(expire_at=None))


# ---------------------------------------------------------------------------
# render_usage shapes
# ---------------------------------------------------------------------------

def test_render_usage_list_of_node_dicts():
    """(a) A list of node dicts renders the 'Трафик по узлам' header with human_bytes per node."""
    data = [
        {"nodeName": "Node A", "total": 1024},
        {"name": "Node B", "bytes": 2048},
    ]
    txt = render_usage(data)
    assert "Трафик по узлам" in txt
    assert "Node A" in txt
    assert "1.00 KB" in txt
    assert "Node B" in txt
    assert "2.00 KB" in txt


def test_render_usage_dict_with_nodes_key():
    """(b) A dict with a 'nodes' list is unwrapped and renders correctly."""
    data = {"nodes": [{"nodeName": "Node X", "total": 1024 ** 2}]}
    txt = render_usage(data)
    assert "Трафик по узлам" in txt
    assert "Node X" in txt
    assert "1.00 MB" in txt


def test_render_usage_with_period_label_and_total():
    """Период-режим: заголовок с периодом и строка 'Итого' с суммой по строкам."""
    data = [{"nodeName": "A", "total": 1024}, {"nodeName": "B", "total": 1024}]
    txt = render_usage(data, period_label="неделю")
    assert "Потребление за неделю" in txt
    assert "Итого: 2.00 KB" in txt


def test_render_usage_flat_total_dict():
    """Плоский ответ с одним числом суммируется в 'Итого'."""
    txt = render_usage({"totalBytes": 1024 ** 2}, period_label="30 дней")
    assert "Потребление за 30 дней" in txt
    assert "Итого: 1.00 MB" in txt


def test_render_usage_unknown_shape_returns_fallback():
    """(c) An unknown/empty shape (no recognisable list) returns the graceful fallback."""
    # A dict with no recognised key
    txt = render_usage({"something": "else"})
    assert "Детализация недоступна" in txt


def test_render_usage_none_or_empty_returns_no_data():
    """(d) None and empty falsy values return the 'Нет данных' string."""
    assert render_usage(None) == "Нет данных по трафику."
    assert render_usage([]) == "Нет данных по трафику."
    assert render_usage({}) == "Нет данных по трафику."
