from datetime import timezone

import pytest

from handlers.actions import parse_date


def test_parse_date_two_digit_year():
    d = parse_date("31.12.26")
    assert (d.year, d.month, d.day) == (2026, 12, 31)
    assert d.tzinfo == timezone.utc


def test_parse_date_four_digit_year():
    d = parse_date("31.12.2026")
    assert (d.year, d.month, d.day) == (2026, 12, 31)
    assert d.tzinfo == timezone.utc


@pytest.mark.parametrize(
    "bad", ["2026-12-31", "31-12-2026", "31/12/2026", "32.13.26", "хрень", ""]
)
def test_parse_date_invalid_raises(bad):
    with pytest.raises(ValueError):
        parse_date(bad)
