"""Bazaning zaxira nusxasini adminga Telegram orqali yuborish."""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from aiogram import Bot
from aiogram.types import BufferedInputFile

from config import config
from database import db
from utils import now

log = logging.getLogger(__name__)


async def send_backup(bot: Bot, chat_id: int | str) -> bool:
    stamp = now().strftime("%Y%m%d_%H%M")
    path = os.path.join(tempfile.gettempdir(), f"voha_backup_{stamp}.db")
    try:
        await db.backup(path)
        with open(path, "rb") as fh:
            data = fh.read()
        await bot.send_document(
            chat_id, BufferedInputFile(data, filename=f"voha_uylari_{stamp}.db"),
            caption=f"💾 Baza zaxira nusxasi — {now().strftime('%d.%m.%Y %H:%M')}\n"
                    "Tiklash uchun: botni to‘xtatib, faylni DB_PATH nomi bilan almashtiring.")
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Zaxira nusxa yuborilmadi: %s", exc)
        return False
    finally:
        if os.path.exists(path):
            os.remove(path)


async def backup_loop(bot: Bot) -> None:
    """Har BACKUP_HOURS soatda birinchi adminga baza nusxasini yuboradi."""
    if config.backup_hours <= 0 or not config.admin_ids:
        return
    while True:
        await asyncio.sleep(config.backup_hours * 3600)
        await send_backup(bot, config.admin_ids[0])
