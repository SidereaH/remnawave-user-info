from keyboards import (
    ConfirmCB,
    UserCB,
    card_keyboard,
    choice_keyboard,
    confirm_keyboard,
    extend_keyboard,
    usage_period_keyboard,
)
from remnawave.models import RemnaUser


def _user(status="ACTIVE"):
    return RemnaUser(
        uuid="u-1", username="john", status=status,
        used_traffic_bytes=0, traffic_limit_bytes=0, expire_at=None,
        telegram_id=None, email=None, description="", subscription_url=None,
        short_uuid=None, raw={},
    )


def _all_cb(markup):
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


def test_card_keyboard_shows_enable_when_disabled():
    cbs = _all_cb(card_keyboard(_user(status="DISABLED")))
    assert any("enable" in c for c in cbs)
    assert not any(c.startswith("u:disable") for c in cbs)


def test_card_keyboard_shows_disable_when_active():
    cbs = _all_cb(card_keyboard(_user(status="ACTIVE")))
    assert any("disable" in c for c in cbs)


def test_extend_keyboard_has_preset_and_custom():
    cbs = _all_cb(extend_keyboard("u-1"))
    assert any(c == "ext:1:u-1" for c in cbs)
    assert any(c == "ext:30:u-1" for c in cbs)
    assert any(c == "ext:custom:u-1" for c in cbs)


def test_confirm_keyboard_yes_no():
    cbs = _all_cb(confirm_keyboard("revoke", "u-1"))
    assert "cf:revoke:u-1:1" in cbs
    assert "cf:revoke:u-1:0" in cbs


def test_card_keyboard_has_usage_action():
    cbs = _all_cb(card_keyboard(_user()))
    assert any(c == "u:usage:u-1" for c in cbs)


def test_card_keyboard_has_devices_action():
    cbs = _all_cb(card_keyboard(_user()))
    assert any(c == "u:devices_ask:u-1" for c in cbs)


def test_confirm_keyboard_devices():
    cbs = _all_cb(confirm_keyboard("devices", "u-1"))
    assert "cf:devices:u-1:1" in cbs
    assert "cf:devices:u-1:0" in cbs


def test_usage_period_keyboard_has_three_periods_and_back():
    cbs = _all_cb(usage_period_keyboard("u-1"))
    assert "usg:7:u-1" in cbs
    assert "usg:30:u-1" in cbs
    assert "usg:60:u-1" in cbs
    assert any(c == "u:refresh:u-1" for c in cbs)


def test_choice_keyboard_one_button_per_user():
    markup = choice_keyboard([_user(), _user()])
    assert len(_all_cb(markup)) == 2
