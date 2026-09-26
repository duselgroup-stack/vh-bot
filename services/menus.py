"""Rolga mos bosh menyu."""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import ReplyKeyboardMarkup

import keyboards as kb
from database import db
from filters import is_admin


async def main_menu_markup(user: dict | None) -> ReplyKeyboardMarkup:
    if not user:
        return kb.role_kb()
    admin = is_admin(user["id"])
    role = user.get("role")
    if role == "buyer":
        return kb.buyer_menu(admin)
    if role == "owner":
        return kb.owner_menu(admin)
    if role == "broker":
        broker = await db.get_broker(user["id"])
        return kb.broker_menu(broker["status"] if broker else None, admin)
    return kb.role_kb(admin)


async def send_main_menu(bot: Bot, chat_id: int, user: dict | None, text: str | None = None) -> None:
    user = await db.get_user(chat_id) if user is None else user
    if text is None:
        text = "🏠 Bosh menyu. Kerakli bo‘limni tanlang 👇" if user and user.get("role") \
            else "Rolingizni tanlang 👇"
    await bot.send_message(chat_id, text, reply_markup=await main_menu_markup(user))
