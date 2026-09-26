"""Obyektni foydalanuvchiga ko‘rsatish (rolga qarab tugmalar bilan)."""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import Message

from callbacks import Srch
from constants import LISTING_STATUSES, PUBLIC_STATUSES
from database import db
from filters import is_admin
from keyboards import public_listing_kb
from services.cards import public_card
from services.commission import broker_share_hint
from services.notify import bot_username, send_listing


async def viewer_is_broker(user: dict | None) -> bool:
    if not user or user.get("role") != "broker":
        return False
    broker = await db.get_broker(user["id"])
    return bool(broker and broker["status"] == "approved")


async def show_listing(bot: Bot, chat_id: int, listing: dict, viewer: dict | None, *,
                       source: str = "", nav: tuple[Srch, Srch, str] | None = None,
                       search_cb: Srch | None = None) -> Message | None:
    viewer_id = viewer["id"] if viewer else chat_id
    own = viewer_id in (listing.get("source_user_id"), listing.get("broker_id"))
    admin = is_admin(viewer_id)
    if listing["status"] not in PUBLIC_STATUSES and not (own or admin):
        status = LISTING_STATUSES.get(listing["status"], listing["status"])
        return await bot.send_message(
            chat_id, f"ℹ️ <b>{listing['code']}</b> hozir faol emas ({status}).\n"
                     "Boshqa obyektlarni qidiruv orqali ko‘rishingiz mumkin.")
    broker_view = not own and await viewer_is_broker(viewer)
    card = await public_card(listing)
    if broker_view:
        card += "\n\n" + broker_share_hint(listing)
    kb = public_listing_kb(listing, await bot_username(bot), source=source,
                           broker_view=broker_view, nav=nav, search_cb=search_cb)
    if not own and not admin:
        await db.add_view(listing["id"])
    return await send_listing(bot, chat_id, listing, card, kb)
