"""Saytdagi kabinet/admin panelga bir martalik xavfsiz kirish havolasi."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from callbacks import Adm
from config import config
from database import db
from filters import IsAdmin, is_admin
from texts import Btn

router = Router(name="web_login")


async def login_message(user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    token = await db.create_web_token(user_id)
    url = f"{config.site_url}/login/{token}"
    place = "admin panel" if is_admin(user_id) else "shaxsiy kabinet"
    text = (f"🔐 <b>Saytdagi {place}ga kirish</b>\n\n"
            f"<a href=\"{url}\">👉 Kabinetni ochish</a>\n\n"
            "⏳ Havola 15 daqiqa amal qiladi va faqat bir marta ishlaydi. Uni hech kimga bermang.\n"
            f"🌐 Sayt: {config.site_url}")
    markup = None
    if url.startswith("https://"):
        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🌐 Kabinetni ochish", url=url)]])
    return text, markup


@router.message(Command("sayt"))
@router.message(F.text == Btn.WEB_CABINET)
async def web_link(message: Message, state: FSMContext, user: dict) -> None:
    await state.clear()
    broker = await db.get_broker(user["id"])
    if is_admin(user["id"]) or (broker and broker["status"] == "approved"):
        text, markup = await login_message(user["id"])
        await message.answer(text, reply_markup=markup)
        return
    await message.answer(f"🌐 Saytimiz: {config.site_url}\n\nBarcha e’lonlar, filtrlar va videolar saytda. "
                         "Shaxsiy kabinet hamkor maklerlar uchun.")


@router.callback_query(Adm.filter(F.a == "weblogin"), IsAdmin())
async def admin_web_link(call: CallbackQuery, bot: Bot) -> None:
    text, markup = await login_message(call.from_user.id)
    try:
        await bot.send_message(call.from_user.id, text, reply_markup=markup)
        await call.answer("Havola shaxsiy chatga yuborildi" if call.message and call.message.chat.id != call.from_user.id else None)
    except Exception:  # noqa: BLE001
        await call.answer("Avval bot bilan shaxsiy chatda /start bosing.", show_alert=True)
