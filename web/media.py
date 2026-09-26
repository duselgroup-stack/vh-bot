"""Telegram’dagi rasm/videolarni saytda ko‘rsatish: yuklab olib, diskda keshlaydi."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from pathlib import Path

from aiogram import Bot

from database import db

log = logging.getLogger(__name__)

CONTENT_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
    ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm",
}


class MediaStore:
    def __init__(self, bot: Bot | None, cache_dir: str) -> None:
        self.bot = bot
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.failed: dict[str, float] = {}

    @staticmethod
    def key(file_id: str) -> str:
        return hashlib.sha1(file_id.encode()).hexdigest()

    def cached(self, file_id: str) -> Path | None:
        for path in self.dir.glob(self.key(file_id) + ".*"):
            if path.suffix != ".part":
                return path
        return None

    @staticmethod
    async def is_listing_media(file_id: str) -> bool:
        """Faqat e’lonlarga tegishli fayllar beriladi (boshqa fayllarni ochib bo‘lmaydi)."""
        row = await db.fetchone(
            """SELECT id FROM listings WHERE (instr(photos, '"' || ? || '"') > 0 OR video = ?)
               AND status NOT IN ('rejected') LIMIT 1""", (file_id, file_id))
        return row is not None

    async def get(self, file_id: str) -> Path | None:
        path = self.cached(file_id)
        if path:
            return path
        if self.bot is None:
            return None
        if time.monotonic() - self.failed.get(file_id, -1e9) < 600:
            return None
        async with self.locks[file_id]:
            path = self.cached(file_id)
            if path:
                return path
            try:
                tg_file = await self.bot.get_file(file_id)
                suffix = Path(tg_file.file_path or "").suffix.lower() or ".jpg"
                dest = self.dir / f"{self.key(file_id)}{suffix}"
                tmp = self.dir / f"{self.key(file_id)}{suffix}.part"
                await self.bot.download_file(tg_file.file_path, destination=tmp)
                tmp.replace(dest)
                return dest
            except Exception as exc:  # noqa: BLE001 — masalan, 20 MB dan katta video
                log.warning("Media yuklanmadi (%s…): %s", file_id[:12], exc)
                self.failed[file_id] = time.monotonic()
                return None
            finally:
                self.locks.pop(file_id, None)
