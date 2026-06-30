from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import get_settings
from handlers import actions, search
from middlewares.access import AccessMiddleware
from remnawave.client import RemnawaveClient


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    client = RemnawaveClient(
        base_url=settings.remnawave_url,
        token=settings.remnawave_token,
        timeout=settings.request_timeout,
        page_size=settings.users_page_size,
    )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp["client"] = client

    access = AccessMiddleware(settings.admin_ids)
    dp.message.middleware(access)
    dp.callback_query.middleware(access)

    dp.include_router(actions.router)
    dp.include_router(search.router)

    logging.getLogger(__name__).info(
        "Бот запущен. Админов: %d", len(settings.admin_ids)
    )
    try:
        await dp.start_polling(bot)
    finally:
        await client.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
