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
