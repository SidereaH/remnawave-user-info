from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from detect import detect_query
from formatting import render_card
from keyboards import card_keyboard, choice_keyboard
from remnawave.client import RemnawaveClient, RemnawaveError
from remnawave.models import RemnaUser

logger = logging.getLogger(__name__)
router = Router(name="search")

_HELP = (
    "🔎 Пришли для поиска:\n"
    "• <b>Telegram ID</b> — например <code>123456789</code>\n"
    "• <b>Email</b> — например <code>user@example.com</code>\n"
    "• <b>@username</b> — ищется в описании пользователя"
)


async def lookup(
    client: RemnawaveClient, kind: str, value: str
) -> list[RemnaUser]:
    if kind == "email":
        return await client.get_by_email(value)
    if kind == "telegram_id":
        return await client.get_by_telegram_id(int(value))
    return await client.search_by_description(value)


@router.message(CommandStart())
async def on_start(message: Message) -> None:
    await message.answer(_HELP)


@router.message(F.text)
async def on_search(message: Message, client: RemnawaveClient) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer(_HELP)
        return
    kind, value = detect_query(text)
    try:
        users = await lookup(client, kind, value)
    except RemnawaveError as e:
        await message.answer(f"⚠️ {e}")
        return
    if not users:
        await message.answer("🤷 Ничего не найдено.")
        return
    if len(users) == 1:
        u = users[0]
        await message.answer(render_card(u), reply_markup=card_keyboard(u))
        return
    await message.answer(
        f"Найдено {len(users)}. Выбери:",
        reply_markup=choice_keyboard(users[:20]),
    )
