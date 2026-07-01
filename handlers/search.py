from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import Message

from detect import detect_query
from formatting import render_card
from keyboards import card_keyboard, choice_keyboard
from remnawave.client import RemnawaveClient, RemnawaveError
from remnawave.models import RemnaUser

logger = logging.getLogger(__name__)
router = Router(name="search")

# Минимальная длина запроса для поиска по подстроке в описании (username).
# Иначе одна буква сканирует всех пользователей и матчит слишком много.
MIN_USERNAME_QUERY = 3

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


@router.message(StateFilter(None), F.text)
async def on_search(message: Message, client: RemnawaveClient) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer(_HELP)
        return
    kind, value = detect_query(text)
    if kind == "username" and len(value) < MIN_USERNAME_QUERY:
        await message.answer(
            f"🔎 Слишком короткий запрос — для поиска по @username/описанию "
            f"нужно минимум {MIN_USERNAME_QUERY} символа."
        )
        return
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
    shown = users[:20]
    if len(users) > len(shown):
        header = f"Найдено {len(users)}, показаны первые {len(shown)}:"
    else:
        header = f"Найдено {len(users)}. Выбери:"
    await message.answer(header, reply_markup=choice_keyboard(shown))
