from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

logger = logging.getLogger(__name__)


class AccessMiddleware(BaseMiddleware):
    def __init__(self, allowed: set[int]) -> None:
        self._allowed = allowed

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = getattr(event, "from_user", None)
        uid = getattr(user, "id", None)
        if uid not in self._allowed:
            logger.warning("Доступ запрещён: telegram_id=%s", uid)
            answer = getattr(event, "answer", None)
            if answer is not None:
                await answer("⛔️ Нет доступа.")
            return None
        return await handler(event, data)
