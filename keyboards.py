from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from remnawave.models import RemnaUser


class UserCB(CallbackData, prefix="u"):
    action: str  # enable|disable|extend_menu|reset_ask|devices_ask|revoke_ask|usage|refresh|open
    uuid: str


class ExtendCB(CallbackData, prefix="ext"):
    days: str  # "1" | "30" | "90" | "180" | "custom"
    uuid: str


class ConfirmCB(CallbackData, prefix="cf"):
    action: str  # reset | revoke
    uuid: str
    yes: int


class UsageCB(CallbackData, prefix="usg"):
    period: str  # "7" | "30" | "60" (дней)
    uuid: str


def card_keyboard(u: RemnaUser) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if u.status == "DISABLED":
        b.button(text="🟢 Включить", callback_data=UserCB(action="enable", uuid=u.uuid))
    else:
        b.button(text="🔴 Выключить", callback_data=UserCB(action="disable", uuid=u.uuid))
    b.button(text="➕ Продлить", callback_data=UserCB(action="extend_menu", uuid=u.uuid))
    b.button(text="🧹 Сброс трафика", callback_data=UserCB(action="reset_ask", uuid=u.uuid))
    b.button(text="📵 Сброс устройств", callback_data=UserCB(action="devices_ask", uuid=u.uuid))
    b.button(text="🔁 Ревок подписки", callback_data=UserCB(action="revoke_ask", uuid=u.uuid))
    b.button(text="📊 Статистика трафика", callback_data=UserCB(action="usage", uuid=u.uuid))
    b.button(text="🔄 Обновить", callback_data=UserCB(action="refresh", uuid=u.uuid))
    # По одной кнопке в ряд для длинных подписей, чтобы текст не обрезался.
    b.adjust(1, 1, 1, 1, 1, 1, 1)
    return b.as_markup()


def extend_keyboard(uuid: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="+1 день", callback_data=ExtendCB(days="1", uuid=uuid))
    for d in ("30", "90", "180"):
        b.button(text=f"+{d} дней", callback_data=ExtendCB(days=d, uuid=uuid))
    b.button(text="📅 Ввести дату", callback_data=ExtendCB(days="custom", uuid=uuid))
    b.button(text="⬅️ Назад", callback_data=UserCB(action="refresh", uuid=uuid))
    b.adjust(1, 3, 1, 1)
    return b.as_markup()


def usage_period_keyboard(uuid: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Неделя", callback_data=UsageCB(period="7", uuid=uuid))
    b.button(text="30 дней", callback_data=UsageCB(period="30", uuid=uuid))
    b.button(text="60 дней", callback_data=UsageCB(period="60", uuid=uuid))
    b.button(text="⬅️ Назад", callback_data=UserCB(action="refresh", uuid=uuid))
    b.adjust(3, 1)
    return b.as_markup()


def confirm_keyboard(action: str, uuid: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да", callback_data=ConfirmCB(action=action, uuid=uuid, yes=1))
    b.button(text="❌ Нет", callback_data=ConfirmCB(action=action, uuid=uuid, yes=0))
    b.adjust(2)
    return b.as_markup()


def choice_keyboard(users: list[RemnaUser]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, u in enumerate(users, 1):
        label = f"{i}. {u.username or u.uuid}"
        b.button(text=label[:60], callback_data=UserCB(action="open", uuid=u.uuid))
    b.adjust(1)
    return b.as_markup()
