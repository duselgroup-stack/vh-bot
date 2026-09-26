"""VOHA UYLARI Telegram-bot — ishga tushirish fayli.

Ishga tushirish:  python bot.py
"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.fsm.storage.base import BaseEventIsolation, BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import BotCommand, ErrorEvent

from config import config
from database import db
from handlers import (
    admin,
    admin_deals,
    admin_tools,
    broker,
    buyer,
    calc,
    common,
    fallback,
    leads,
    listing_form,
    my_listings,
    web_login,
)
from middlewares import ThrottlingMiddleware, UserMiddleware
from services.backup import backup_loop

log = logging.getLogger("voha_bot")
background_tasks: set[asyncio.Task] = set()


def build_storage() -> tuple[BaseStorage, BaseEventIsolation]:
    if config.redis_url:
        try:
            from aiogram.fsm.storage.redis import RedisStorage

            storage = RedisStorage.from_url(config.redis_url)
            log.info("FSM: Redis (%s)", config.redis_url)
            return storage, storage.create_isolation()
        except Exception as exc:  # noqa: BLE001
            log.warning("Redis ishlamadi (%s) — xotiradagi storage ishlatiladi", exc)
    return MemoryStorage(), SimpleEventIsolation()


def build_dispatcher() -> Dispatcher:
    storage, isolation = build_storage()
    dp = Dispatcher(storage=storage, events_isolation=isolation)

    # Bot faqat shaxsiy chatda xabarlarga javob beradi (admin guruhida faqat tugmalar ishlaydi)
    dp.message.filter(F.chat.type == ChatType.PRIVATE)

    user_mw = UserMiddleware()
    throttle = ThrottlingMiddleware()
    dp.message.outer_middleware(throttle)
    dp.callback_query.outer_middleware(throttle)
    dp.message.outer_middleware(user_mw)
    dp.callback_query.outer_middleware(user_mw)

    dp.include_routers(
        common.router,
        admin.router,
        admin_deals.router,
        admin_tools.router,
        listing_form.router,
        leads.router,
        broker.router,
        my_listings.router,
        buyer.router,
        calc.router,
        web_login.router,
        fallback.router,
    )

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        log.exception("Xatolik: %s", event.exception, exc_info=event.exception)
        update = event.update
        try:
            if update.callback_query:
                await update.callback_query.answer("⚠️ Xatolik yuz berdi. Qayta urinib ko‘ring.", show_alert=True)
            elif update.message:
                await update.message.answer("⚠️ Xatolik yuz berdi. /start ni bosib qayta urinib ko‘ring.")
        except Exception:  # noqa: BLE001
            pass
        return True

    return dp


async def on_startup(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="Bosh menyu"),
        BotCommand(command="id", description="ID bo‘yicha obyekt qidirish"),
        BotCommand(command="role", description="Rolni almashtirish"),
        BotCommand(command="sayt", description="Sayt va shaxsiy kabinet"),
        BotCommand(command="cancel", description="Amalni bekor qilish"),
        BotCommand(command="help", description="Yordam"),
    ])
    me = await bot.me()
    log.info("Bot ishga tushdi: @%s", me.username)
    if not config.admin_ids:
        log.warning("ADMIN_IDS bo‘sh — admin panel hech kimga ochilmaydi!")
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, "✅ Bot ishga tushdi. Admin panel: /admin")
        except Exception:  # noqa: BLE001
            log.warning("Admin %s ga xabar yuborilmadi (botga /start bosmagan bo‘lishi mumkin)", admin_id)
    task = asyncio.create_task(backup_loop(bot))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


async def on_shutdown(bot: Bot) -> None:
    for task in list(background_tasks):
        task.cancel()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    if not config.token_ok:
        log.error("BOT_TOKEN topilmadi! .env fayliga @BotFather bergan tokenni yozing.")
        sys.exit(1)

    await db.connect(config.db_path)
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    dp = build_dispatcher()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    web_runner = None
    if config.web_enabled:
        from web.server import start_web
        web_runner = await start_web(bot)
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if web_runner is not None:
            await web_runner.cleanup()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot to‘xtatildi")
