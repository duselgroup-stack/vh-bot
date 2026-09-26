"""Bot sozlamalari (.env faylidan o‘qiladi)."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

PLACEHOLDER_TOKENS = {"", "BU_YERGA_TOKEN", "YOUR_BOT_TOKEN"}


def _parse_ids(raw: str | None) -> tuple[int, ...]:
    result: list[int] = []
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            result.append(int(part))
    return tuple(result)


def _parse_chat(raw: str | None) -> int | str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.lstrip("-").isdigit():
        return int(raw)
    if not raw.startswith("@"):
        raw = "@" + raw
    return raw


def _int(raw: str | None, default: int) -> int:
    try:
        return int(str(raw).replace(" ", ""))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_ids: tuple[int, ...]
    admin_group_id: int | str | None
    channel_id: int | str | None
    db_path: str
    redis_url: str | None
    company_name: str
    company_phone: str
    instagram_url: str
    telegram_channel_url: str
    website_url: str
    shooting_cost: int
    backup_hours: int
    web_enabled: bool
    web_host: str
    web_port: int
    secret_key: str
    media_cache_dir: str

    @property
    def token_ok(self) -> bool:
        return self.bot_token not in PLACEHOLDER_TOKENS and ":" in self.bot_token

    @property
    def site_url(self) -> str:
        """Saytning ochiq manzili (havolalar uchun). WEBSITE_URL bo‘lmasa — localhost."""
        return (self.website_url or f"http://localhost:{self.web_port}").rstrip("/")


def load_config() -> Config:
    return Config(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        admin_ids=_parse_ids(os.getenv("ADMIN_IDS")),
        admin_group_id=_parse_chat(os.getenv("ADMIN_GROUP_ID")),
        channel_id=_parse_chat(os.getenv("CHANNEL_ID")),
        db_path=os.getenv("DB_PATH", "voha_uylari.db").strip() or "voha_uylari.db",
        redis_url=(os.getenv("REDIS_URL") or "").strip() or None,
        company_name=os.getenv("COMPANY_NAME", "VOHA UYLARI").strip() or "VOHA UYLARI",
        company_phone=os.getenv("COMPANY_PHONE", "+998 90 000 00 00").strip(),
        instagram_url=os.getenv("INSTAGRAM_URL", "").strip(),
        telegram_channel_url=os.getenv("TELEGRAM_CHANNEL_URL", "").strip(),
        website_url=os.getenv("WEBSITE_URL", "").strip(),
        shooting_cost=_int(os.getenv("SHOOTING_COST"), 350_000),
        backup_hours=_int(os.getenv("BACKUP_HOURS"), 24),
        web_enabled=(os.getenv("WEB_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}),
        web_host=os.getenv("WEB_HOST", "0.0.0.0").strip() or "0.0.0.0",
        web_port=_int(os.getenv("WEB_PORT") or os.getenv("PORT"), 8080),
        secret_key=(os.getenv("SECRET_KEY", "").strip()
                    or hashlib.sha256(("voha-web:" + os.getenv("BOT_TOKEN", "")).encode()).hexdigest()),
        media_cache_dir=os.getenv("MEDIA_CACHE_DIR", "media_cache").strip() or "media_cache",
    )


config = load_config()
