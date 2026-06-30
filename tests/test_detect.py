import pytest

from detect import detect_query


@pytest.mark.parametrize(
    "text,expected",
    [
        ("user@example.com", ("email", "user@example.com")),
        ("  user@example.com  ", ("email", "user@example.com")),
        ("@john_doe", ("username", "john_doe")),
        ("123456789", ("telegram_id", "123456789")),
        ("john_doe", ("username", "john_doe")),
        ("John Doe", ("username", "John Doe")),
    ],
)
def test_detect_query(text, expected):
    assert detect_query(text) == expected
