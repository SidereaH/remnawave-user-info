from config import Settings


def _make(**over):
    base = dict(
        bot_token="x",
        remnawave_url="https://panel.example.com/",
        remnawave_token="t",
        allowed_admin_ids="111, 222 ,333",
    )
    base.update(over)
    return Settings(**base)


def test_admin_ids_parsed_to_set_of_ints():
    assert _make().admin_ids == {111, 222, 333}


def test_admin_ids_empty_string_is_empty_set():
    assert _make(allowed_admin_ids="").admin_ids == set()


def test_url_trailing_slash_stripped():
    assert _make().remnawave_url == "https://panel.example.com"


def test_defaults():
    s = _make()
    assert s.users_page_size == 250
    assert s.request_timeout == 20
