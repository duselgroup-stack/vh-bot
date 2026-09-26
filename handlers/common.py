"""Umumiy buyruqlar: /start (deep-link), rol tanlash, bosh menyu, bekor qilish."""
from __future__ import annotations

import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from callbacks import Nav
from constants import SOURCE_ALIASES
from database import db
from filters import is_admin
from services.helpers import safe_delete
from services.menus import send_main_menu
from services.views import show_listing
from texts import HELP_TEXT, ROLE_HINTS, Btn, about_text, contact_text, welcome
from utils import esc, parse_code

router = Router(name="common")

ROLE_BY_BUTTON = {Btn.ROLE_BUYER: "buyer", Btn.ROLE_OWNER: "owner", Btn.ROLE_BROKER: "broker"}


def parse_start_payload(payload: str | None) -> tuple[int | None, str | None]:
    """'VU-0012_tg' → (12, 'telegram'); 'ig' → (None, 'instagram')."""
    listing_id, source = None, None
    for part in re.split(r"[_ ]+", (payload or "").strip()):
        if not part:
            continue
        low = part.lower()
        if low in SOURCE_ALIASES:
            source = SOURCE_ALIASES[low]
        elif low.startswith("vu"):
            listing_id = parse_code(part) or listing_id
    return listing_id, source


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext, user: dict,
                    bot: Bot) -> None:
    await state.clear()
    admin_card_match = re.fullmatch(r"adm(\d+)", (command.args or "").strip())
    if admin_card_match and is_admin(user["id"]):
        from handlers.admin import send_card
        await send_card(bot, message.chat.id, int(admin_card_match.group(1)))
        return
    listing_id, source = parse_start_payload(command.args)
    if source:
        await db.set_user_source(user["id"], source)
    if listing_id:
        listing = await db.get_listing(listing_id)
        if not user.get("role"):
            await db.set_user_role(user["id"], "buyer")
            user = await db.get_user(user["id"])
        await send_main_menu(bot, message.chat.id, user,
                             f"👋 Xush kelibsiz, <b>{esc(message.from_user.first_name)}</b>! Siz so‘ragan obyekt 👇")
        if listing:
            await show_listing(bot, message.chat.id, listing, user, source=source or "bot")
        else:
            await message.answer("😕 Bu ID bo‘yicha obyekt topilmadi.")
        return
    if not user.get("role"):
        await message.answer(welcome(message.from_user.first_name),
                             reply_markup=kb.role_kb(is_admin(user["id"])))
        return
    await send_main_menu(bot, message.chat.id, user,
                         f"👋 Qaytganingizdan xursandmiz, <b>{esc(message.from_user.first_name)}</b>!\n"
                         "Kerakli bo‘limni tanlang 👇")


@router.message(F.text.in_(ROLE_BY_BUTTON.keys()))
async def choose_role(message: Message, state: FSMContext, user: dict, bot: Bot) -> None:
    await state.clear()
    role = ROLE_BY_BUTTON[message.text]
    await db.set_user_role(user["id"], role)
    user = await db.get_user(user["id"])
    text = ROLE_HINTS[role]
    if role == "broker":
        broker = await db.get_broker(user["id"])
        if not broker or broker["status"] == "rejected":
            text += ("\n\n📝 Hamkor bo‘lish uchun «" + Btn.BROKER_REGISTER + "» tugmasini bosing — "
                     "qo‘shilish bepul, komissiya faqat bitimdan.")
        elif broker["status"] == "pending":
            text += "\n\n⏳ Arizangiz ko‘rib chiqilmoqda. Tasdiqlangach to‘liq menyu ochiladi."
    await send_main_menu(bot, message.chat.id, user, text)


@router.message(Command("role"))
@router.message(F.text == Btn.SWITCH_ROLE)
async def switch_role(message: Message, state: FSMContext, user: dict) -> None:
    await state.clear()
    await message.answer("Qaysi rolda davom etasiz? 👇", reply_markup=kb.role_kb(is_admin(user["id"])))


@router.message(Command("cancel"))
@router.message(F.text == Btn.CANCEL)
async def cancel(message: Message, state: FSMContext, user: dict, bot: Bot) -> None:
    had_state = await state.get_state()
    await state.clear()
    await send_main_menu(bot, message.chat.id, user,
                         "❌ Bekor qilindi." if had_state else "🏠 Bosh menyu.")


@router.message(Command("menu"))
@router.message(F.text == Btn.MAIN)
async def main_menu(message: Message, state: FSMContext, user: dict, bot: Bot) -> None:
    await state.clear()
    await send_main_menu(bot, message.chat.id, user)


@router.message(F.text == Btn.ABOUT)
async def about(message: Message) -> None:
    await message.answer(about_text())


@router.message(F.text == Btn.CONTACT)
async def contact(message: Message) -> None:
    await message.answer(contact_text())


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.callback_query(Nav.filter(F.to == "main"))
async def nav_main(call: CallbackQuery, state: FSMContext, user: dict, bot: Bot) -> None:
    await state.clear()
    await call.answer()
    await send_main_menu(bot, call.from_user.id, user)


@router.callback_query(Nav.filter(F.to == "close"))
async def nav_close(call: CallbackQuery) -> None:
    await call.answer()
    await safe_delete(call.message)


@router.callback_query(Nav.filter(F.to == "noop"))
async def nav_noop(call: CallbackQuery) -> None:
    await call.answer()
