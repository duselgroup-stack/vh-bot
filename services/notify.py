"""Xabarnomalar: adminlarga, obunachilarga, kanalga e’lon."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo,
    Message,
)

from config import config
from database import db
from keyboards import public_listing_kb
from services.cards import channel_caption, public_card
from services.helpers import try_send

log = logging.getLogger(__name__)


async def bot_username(bot: Bot) -> str | None:
    try:
        me = await bot.me()
        return me.username
    except Exception:  # noqa: BLE001
        return None


async def notify_admins(bot: Bot, text: str,
                        reply_markup: InlineKeyboardMarkup | None = None) -> int:
    """Admin guruhiga (bo‘lsa) yoki har bir adminga shaxsan yuboradi."""
    sent = 0
    if config.admin_group_id:
        if await try_send(bot, config.admin_group_id, text, reply_markup=reply_markup):
            return 1
    for admin_id in config.admin_ids:
        if await try_send(bot, admin_id, text, reply_markup=reply_markup):
            sent += 1
    if not sent and not config.admin_group_id and not config.admin_ids:
        log.warning("ADMIN_IDS sozlanmagan — admin xabari yuborilmadi")
    return sent


async def send_listing(bot: Bot, chat_id: int | str, listing: dict, caption: str,
                       reply_markup: InlineKeyboardMarkup | None = None) -> Message | None:
    """Obyektni birinchi rasm/video bilan yuboradi (media bo‘lmasa — matn)."""
    photos = listing.get("photos") or []
    try:
        if (photos or listing.get("video")) and len(caption) <= 1024:
            if photos:
                return await bot.send_photo(chat_id, photos[0], caption=caption, reply_markup=reply_markup)
            return await bot.send_video(chat_id, listing["video"], caption=caption, reply_markup=reply_markup)
        if photos:
            await bot.send_photo(chat_id, photos[0])
        elif listing.get("video"):
            await bot.send_video(chat_id, listing["video"])
        return await bot.send_message(chat_id, caption, reply_markup=reply_markup)
    except TelegramForbiddenError:
        if isinstance(chat_id, int) and chat_id > 0:
            await db.set_user_blocked(chat_id, True)
    except TelegramBadRequest as exc:
        log.warning("Obyekt yuborilmadi (%s → %s): %s", listing.get("code"), chat_id, exc)
        try:  # media fayl yaroqsiz bo‘lsa, matnni yuboramiz
            return await bot.send_message(chat_id, caption, reply_markup=reply_markup)
        except Exception:  # noqa: BLE001
            return None
    return None


async def send_album(bot: Bot, chat_id: int | str, listing: dict) -> bool:
    photos = list(listing.get("photos") or [])
    video = listing.get("video")
    items: list[tuple[str, str]] = [("photo", p) for p in photos[: 9 if video else 10]]
    if video:
        items.append(("video", video))
    if not items:
        return False
    caption = f"🖼 {listing['code']} — barcha media"
    try:
        if len(items) == 1:
            kind, file_id = items[0]
            if kind == "video":
                await bot.send_video(chat_id, file_id, caption=caption)
            else:
                await bot.send_photo(chat_id, file_id, caption=caption)
        else:
            media: list[InputMediaPhoto | InputMediaVideo] = []
            for idx, (kind, file_id) in enumerate(items):
                cls = InputMediaVideo if kind == "video" else InputMediaPhoto
                media.append(cls(media=file_id, caption=caption if idx == 0 else None))
            await bot.send_media_group(chat_id, media=media)
        return True
    except TelegramBadRequest as exc:
        log.warning("Albom yuborilmadi: %s", exc)
        return False


def _channel_kb(listing: dict, username: str | None) -> InlineKeyboardMarkup | None:
    if not username or listing["status"] not in ("active", "negotiation"):
        return None
    url = f"https://t.me/{username}?start={listing['code']}_tg"
    rows = [[InlineKeyboardButton(text="📩 Ko‘rishga yozilish", url=url)]]
    if config.website_url.startswith("https://"):
        rows.append([InlineKeyboardButton(text="🌐 Saytda ko‘rish (video, barcha rasmlar)",
                                          url=f"{config.site_url}/uy/{listing['code']}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def publish_to_channel(bot: Bot, listing: dict) -> int | None:
    """Obyektni Telegram kanalga joylaydi va xabar ID sini saqlaydi."""
    if not config.channel_id:
        return None
    username = await bot_username(bot)
    caption = await channel_caption(listing)
    msg = await send_listing(bot, config.channel_id, listing, caption, _channel_kb(listing, username))
    if msg:
        await db.update_listing(listing["id"], channel_message_id=msg.message_id)
        return msg.message_id
    return None


async def update_channel_post(bot: Bot, listing: dict) -> None:
    """Holat o‘zgarganda kanal postini yangilaydi (masalan, «SOTILDI» belgisi)."""
    if not config.channel_id or not listing.get("channel_message_id"):
        return
    username = await bot_username(bot)
    caption = await channel_caption(listing)
    kb = _channel_kb(listing, username)
    has_media = bool(listing.get("photos") or listing.get("video")) and len(caption) <= 1024
    try:
        if has_media:
            await bot.edit_message_caption(chat_id=config.channel_id,
                                           message_id=listing["channel_message_id"],
                                           caption=caption, reply_markup=kb)
        else:
            await bot.edit_message_text(caption, chat_id=config.channel_id,
                                        message_id=listing["channel_message_id"], reply_markup=kb)
    except TelegramBadRequest as exc:
        if "not modified" not in str(exc):
            log.warning("Kanal posti yangilanmadi (%s): %s", listing["code"], exc)


async def notify_subscribers(bot: Bot, listing: dict) -> int:
    """Yangi e’longa mos obunachilarga xabar beradi."""
    user_ids = await db.matching_subscribers(listing)
    if not user_ids:
        return 0
    username = await bot_username(bot)
    card = await public_card(listing)
    text = "🔔 <b>Talabingizga mos yangi e’lon!</b>\n\n" + card
    kb = public_listing_kb(listing, username, source="")
    sent = 0
    for uid in user_ids:
        if uid == listing.get("source_user_id"):
            continue
        try:
            if await send_listing(bot, uid, listing, text, kb):
                sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
        await asyncio.sleep(0.05)
    return sent
