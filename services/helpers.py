"""Umumiy yordamchi funksiyalar (xabar tahrirlash, FSM kontekst va h.k.)."""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from utils import esc

log = logging.getLogger(__name__)


def private_ctx(bot: Bot, storage: BaseStorage, user_id: int) -> FSMContext:
    """Foydalanuvchining shaxsiy chatidagi FSM konteksti.

    Admin guruhdagi tugmani bossa ham, kiritish jarayoni admin bilan shaxsiy chatda davom etadi.
    """
    key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


async def safe_edit(call: CallbackQuery, text: str,
                    reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Xabarni tahrirlaydi; bo‘lmasa (masalan, rasmli xabar) yangisini yuboradi."""
    msg = call.message
    if not isinstance(msg, Message):
        await call.bot.send_message(call.from_user.id, text, reply_markup=reply_markup)
        return
    try:
        if msg.photo or msg.video or msg.document:
            if len(text) <= 1024:
                await msg.edit_caption(caption=text, reply_markup=reply_markup)
            else:
                await msg.answer(text, reply_markup=reply_markup)
        else:
            await msg.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return
        await msg.answer(text, reply_markup=reply_markup)


async def safe_delete(message: Message | None) -> None:
    if not isinstance(message, Message):
        return
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


async def try_send(bot: Bot, chat_id: int | str, text: str, **kwargs) -> Message | None:
    try:
        return await bot.send_message(chat_id, text, **kwargs)
    except TelegramForbiddenError:
        from database import db  # aylanma importdan qochish uchun
        if isinstance(chat_id, int) and chat_id > 0:
            await db.set_user_blocked(chat_id, True)
        return None
    except TelegramBadRequest as exc:
        log.warning("Xabar yuborilmadi (%s): %s", chat_id, exc)
        return None


def user_link(user_id: int, name: str | None, username: str | None = None) -> str:
    link = f"<a href=\"tg://user?id={user_id}\">{esc(name or user_id)}</a>"
    if username:
        link += f" @{esc(username)}"
    return link
