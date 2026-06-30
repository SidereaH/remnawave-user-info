from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from formatting import render_card, render_usage
from keyboards import (
    ConfirmCB,
    ExtendCB,
    UserCB,
    card_keyboard,
    confirm_keyboard,
    extend_keyboard,
)
from remnawave.client import RemnawaveClient, RemnawaveError
from states import ExtendStates

logger = logging.getLogger(__name__)
router = Router(name="actions")


def parse_date(text: str) -> datetime:
    dt = datetime.strptime(text.strip(), "%Y-%m-%d")
    return dt.replace(tzinfo=timezone.utc)


async def _show_card(cq: CallbackQuery, client: RemnawaveClient, uuid: str) -> None:
    user = await client.get_user(uuid)
    try:
        await cq.message.edit_text(render_card(user), reply_markup=card_keyboard(user))
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


@router.callback_query(UserCB.filter(F.action == "open"))
@router.callback_query(UserCB.filter(F.action == "refresh"))
async def cb_open(cq: CallbackQuery, callback_data: UserCB, client: RemnawaveClient):
    try:
        await _show_card(cq, client, callback_data.uuid)
    except RemnawaveError as e:
        await cq.answer(str(e), show_alert=True)
        return
    await cq.answer()


@router.callback_query(UserCB.filter(F.action == "enable"))
async def cb_enable(cq: CallbackQuery, callback_data: UserCB, client: RemnawaveClient):
    await _do_simple(cq, client, callback_data.uuid, client.enable_user, "Включён")


@router.callback_query(UserCB.filter(F.action == "disable"))
async def cb_disable(cq: CallbackQuery, callback_data: UserCB, client: RemnawaveClient):
    await _do_simple(cq, client, callback_data.uuid, client.disable_user, "Выключен")


async def _do_simple(cq, client, uuid, method, ok_text):
    try:
        await method(uuid)
        await _show_card(cq, client, uuid)
    except RemnawaveError as e:
        await cq.answer(str(e), show_alert=True)
        return
    await cq.answer(ok_text)


@router.callback_query(UserCB.filter(F.action == "usage"))
async def cb_usage(cq: CallbackQuery, callback_data: UserCB, client: RemnawaveClient):
    try:
        data = await client.get_usage(callback_data.uuid)
    except RemnawaveError as e:
        await cq.answer(str(e), show_alert=True)
        return
    await cq.message.answer(render_usage(data))
    await cq.answer()


@router.callback_query(UserCB.filter(F.action == "extend_menu"))
async def cb_extend_menu(cq: CallbackQuery, callback_data: UserCB):
    await cq.message.edit_reply_markup(
        reply_markup=extend_keyboard(callback_data.uuid)
    )
    await cq.answer()


@router.callback_query(ExtendCB.filter(F.days != "custom"))
async def cb_extend_preset(cq: CallbackQuery, callback_data: ExtendCB, client: RemnawaveClient):
    days = int(callback_data.days)
    new_expire = datetime.now(timezone.utc) + timedelta(days=days)
    try:
        await client.update_expire(callback_data.uuid, new_expire)
        await _show_card(cq, client, callback_data.uuid)
    except RemnawaveError as e:
        await cq.answer(str(e), show_alert=True)
        return
    await cq.answer(f"Продлено на {days} дней")


@router.callback_query(ExtendCB.filter(F.days == "custom"))
async def cb_extend_custom(cq: CallbackQuery, callback_data: ExtendCB, state: FSMContext):
    await state.update_data(uuid=callback_data.uuid)
    await state.set_state(ExtendStates.waiting_for_date)
    await cq.message.answer("📅 Пришли дату окончания в формате <b>YYYY-MM-DD</b>:")
    await cq.answer()


@router.message(ExtendStates.waiting_for_date, F.text)
async def on_custom_date(message: Message, state: FSMContext, client: RemnawaveClient):
    try:
        new_expire = parse_date(message.text or "")
    except ValueError:
        await message.answer("❌ Неверный формат. Нужно <b>YYYY-MM-DD</b>, например 2026-12-31.")
        return
    data = await state.get_data()
    uuid = data.get("uuid")
    await state.clear()
    if not uuid:
        await message.answer("⚠️ Сессия истекла, начните продление заново.")
        return
    try:
        user = await client.update_expire(uuid, new_expire)
    except RemnawaveError as e:
        await message.answer(f"⚠️ {e}")
        return
    await message.answer(render_card(user), reply_markup=card_keyboard(user))


@router.callback_query(UserCB.filter(F.action == "reset_ask"))
async def cb_reset_ask(cq: CallbackQuery, callback_data: UserCB):
    await cq.message.edit_reply_markup(
        reply_markup=confirm_keyboard("reset", callback_data.uuid)
    )
    await cq.answer("Подтвердите сброс трафика")


@router.callback_query(UserCB.filter(F.action == "revoke_ask"))
async def cb_revoke_ask(cq: CallbackQuery, callback_data: UserCB):
    await cq.message.edit_reply_markup(
        reply_markup=confirm_keyboard("revoke", callback_data.uuid)
    )
    await cq.answer("Подтвердите ревок подписки")


@router.callback_query(ConfirmCB.filter())
async def cb_confirm(cq: CallbackQuery, callback_data: ConfirmCB, client: RemnawaveClient):
    if not callback_data.yes:
        await _safe_show(cq, client, callback_data.uuid)
        await cq.answer("Отменено")
        return
    try:
        if callback_data.action == "reset":
            await client.reset_traffic(callback_data.uuid)
            done = "Трафик сброшен"
        elif callback_data.action == "revoke":
            await client.revoke_subscription(callback_data.uuid)
            done = "Подписка перевыпущена"
        else:
            await cq.answer("Неизвестное действие", show_alert=True)
            return
        await _show_card(cq, client, callback_data.uuid)
    except RemnawaveError as e:
        await cq.answer(str(e), show_alert=True)
        return
    await cq.answer(done)


async def _safe_show(cq, client, uuid):
    try:
        await _show_card(cq, client, uuid)
    except RemnawaveError:
        pass
