"""Middleware’lar: foydalanuvchini bazaga yozish va spamdan himoya."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from database import db
from filters import is_admin


class UserMiddleware(BaseMiddleware):
    """Har bir hodisada foydalanuvchini bazada yangilaydi va data['user'] ga qo‘yadi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: User | None = data.get("event_from_user")
        if tg_user and not tg_user.is_bot:
            data["user"] = await db.upsert_user(tg_user.id, tg_user.full_name, tg_user.username)
            data["is_admin"] = is_admin(tg_user.id)
        else:
            data["user"] = None
            data["is_admin"] = False
        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """Bir foydalanuvchidan juda tez kelayotgan xabarlarni cheklaydi."""

    def __init__(self, limit: int = 10, period: float = 3.0) -> None:
        self.limit = limit
        self.period = period
        self.events: dict[int, deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None or is_admin(user.id):
            return await handler(event, data)
        if isinstance(event, Message) and event.media_group_id:
            return await handler(event, data)  # albomdagi rasmlar cheklanmaydi
        now = time.monotonic()
        queue = self.events[user.id]
        while queue and now - queue[0] > self.period:
            queue.popleft()
        if len(queue) >= self.limit:
            if isinstance(event, CallbackQuery):
                await event.answer("⏳ Biroz sekinroq…", show_alert=False)
            return None
        queue.append(now)
        if len(self.events) > 10_000:  # xotira tozalash
            self.events = defaultdict(deque, {k: v for k, v in self.events.items() if v})
        return await handler(event, data)
