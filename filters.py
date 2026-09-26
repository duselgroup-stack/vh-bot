"""Maxsus filtrlar."""
from __future__ import annotations

from aiogram import F
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from config import config
from texts import MENU_TEXTS


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in config.admin_ids


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return bool(user and is_admin(user.id))


# Formadagi matnli javob: menyu tugmasi ham, buyruq ham emas.
TEXT_INPUT = F.text & ~F.text.in_(MENU_TEXTS) & ~F.text.startswith("/")
