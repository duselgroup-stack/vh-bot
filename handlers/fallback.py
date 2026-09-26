"""Tushunilmagan xabarlar va eskirgan tugmalar."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from filters import is_admin
from handlers.admin_tools import question_kb
from services.helpers import user_link
from services.menus import send_main_menu
from services.notify import notify_admins
from texts import MENU_TEXTS, Btn, welcome
from utils import esc

router = Router(name="fallback")


@router.message(~StateFilter(None))
async def wrong_input(message: Message) -> None:
    await message.answer(f"🙂 Iltimos, so‘ralgan ma’lumotni yuboring yoki «{Btn.CANCEL}» ni bosing.")


@router.message(StateFilter(None), F.text, ~F.text.in_(MENU_TEXTS), ~F.text.startswith("/"))
async def free_text(message: Message, user: dict, bot: Bot) -> None:
    if not user.get("role"):
        await message.answer(welcome(message.from_user.first_name), reply_markup=kb.role_kb(is_admin(user["id"])))
        return
    if is_admin(user["id"]) or len(message.text.strip()) < 3:
        await send_main_menu(bot, message.chat.id, user, "🙂 Menyudan kerakli bo‘limni tanlang 👇")
        return
    phone = f"\n📱 {esc(user['phone'])}" if user.get("phone") else ""
    await notify_admins(
        bot,
        f"💬 <b>Foydalanuvchi savoli</b>\n{user_link(user['id'], user.get('full_name'), user.get('username'))}"
        f"{phone}\n\n{esc(message.text[:1500])}",
        question_kb(user["id"]))
    await send_main_menu(bot, message.chat.id, user,
                         "📨 Xabaringiz menejerga yuborildi — tez orada javob beramiz.\n"
                         "Uy qidirish yoki e’lon berish uchun menyudan foydalaning 👇")


@router.message(StateFilter(None))
async def unknown(message: Message, user: dict, bot: Bot) -> None:
    await send_main_menu(bot, message.chat.id, user, "🙂 Menyudan kerakli bo‘limni tanlang 👇")


@router.callback_query()
async def stale_callback(call: CallbackQuery) -> None:
    await call.answer("Bu tugma eskirgan yoki amal yakunlangan. /start ni bosing.", show_alert=False)
