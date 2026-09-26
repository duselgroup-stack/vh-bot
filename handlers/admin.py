"""Admin: panel, moderatsiya, obyekt kartasi va undagi amallar."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import keyboards as kb
from callbacks import Adm, Ld
from config import config
from constants import LEAD_STATUSES, LISTING_STATUSES, MAX_PHOTOS, MODELS, PAGE_SIZE
from database import db
from filters import TEXT_INPUT, IsAdmin
from services.cards import admin_card, listing_short
from services.helpers import private_ctx, safe_edit, try_send
from services.notify import (
    notify_subscribers,
    publish_to_channel,
    send_album,
    update_channel_post,
)
from states import AdminInput
from texts import Btn
from utils import esc, fmt_money, fmt_percent, now_str, parse_decimal, parse_price

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

LIST_GROUPS = {
    "pending": (("pending",), "🕓 Moderatsiya navbati"),
    "shooting": (("shooting",), "🎬 Syomka navbati"),
    "live": (("active", "negotiation"), "✅ Faol obyektlar"),
    "closed": (("sold", "rented"), "🏁 Sotilgan / ijaraga berilgan"),
    "archive": (("archived", "rejected"), "📦 Arxiv va rad etilganlar"),
}


# ------------------------------------------------------------------ panel
async def panel() -> tuple[str, InlineKeyboardMarkup]:
    pending = await db.count_listings("pending")
    shooting = await db.count_listings("shooting")
    live = await db.count_listings("active", "negotiation")
    closed = await db.count_listings("sold", "rented")
    new_leads = int(await db.scalar("SELECT COUNT(*) FROM leads WHERE status='new'") or 0)
    brokers_pending = int(await db.scalar("SELECT COUNT(*) FROM brokers WHERE status='pending'") or 0)
    unpaid = int(await db.scalar("SELECT COUNT(*) FROM deals WHERE status='unpaid'") or 0)
    text = (
        f"🛠 <b>{esc(config.company_name)} — Admin panel</b>\n\n"
        f"🕓 Moderatsiyada: <b>{pending}</b>\n"
        f"🎬 Syomka kutmoqda: <b>{shooting}</b>\n"
        f"✅ Faol obyektlar: <b>{live}</b>\n"
        f"🏁 Yopilgan bitimlar: <b>{closed}</b>\n"
        f"🔥 Yangi murojaatlar: <b>{new_leads}</b>\n"
        f"🤝 Makler arizalari: <b>{brokers_pending}</b>\n"
        f"💰 Undirilmagan komissiyalar: <b>{unpaid}</b>"
    )
    b = InlineKeyboardBuilder()
    b.button(text=f"🕓 Moderatsiya ({pending})", callback_data=Adm(a="list", v="pending"))
    b.button(text=f"🎬 Syomka ({shooting})", callback_data=Adm(a="list", v="shooting"))
    b.button(text=f"✅ Faol ({live})", callback_data=Adm(a="list", v="live"))
    b.button(text=f"🏁 Yopilgan ({closed})", callback_data=Adm(a="list", v="closed"))
    b.button(text=f"🔥 Murojaatlar ({new_leads})", callback_data=Adm(a="newleads"))
    b.button(text=f"🤝 Arizalar ({brokers_pending})", callback_data=Adm(a="brokers", v="pending"))
    b.button(text=f"💰 Komissiyalar ({unpaid})", callback_data=Adm(a="unpaid"))
    b.button(text="📊 Statistika", callback_data=Adm(a="stats"))
    b.button(text="➕ Voha obyekti", callback_data=Adm(a="new"))
    b.button(text="📤 Excel eksport", callback_data=Adm(a="export"))
    b.button(text="📢 Xabar yuborish", callback_data=Adm(a="bc"))
    b.button(text="👥 Maklerlar", callback_data=Adm(a="brokers", v="approved"))
    b.button(text="📦 Arxiv", callback_data=Adm(a="list", v="archive"))
    b.button(text="💾 Zaxira nusxa", callback_data=Adm(a="backup"))
    b.button(text="🌐 Sayt paneli", callback_data=Adm(a="weblogin"))
    b.adjust(2)
    return text, b.as_markup()


@router.message(Command("admin"))
@router.message(F.text == Btn.ADMIN)
async def admin_panel(message: Message, state: FSMContext) -> None:
    await state.clear()
    text, markup = await panel()
    await message.answer(text, reply_markup=markup)


@router.callback_query(Adm.filter(F.a == "panel"))
async def admin_panel_cb(call: CallbackQuery) -> None:
    await call.answer()
    text, markup = await panel()
    await safe_edit(call, text, markup)


@router.callback_query(Adm.filter(F.a == "list"))
async def admin_list(call: CallbackQuery, callback_data: Adm) -> None:
    statuses, title = LIST_GROUPS.get(callback_data.v, LIST_GROUPS["pending"])
    listings = await db.listings_by_status(*statuses, limit=500)
    await call.answer()
    total = len(listings)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(callback_data.id, pages - 1))
    b = InlineKeyboardBuilder()
    for listing in listings[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        b.row(InlineKeyboardButton(text=listing_short(listing),
                                   callback_data=Adm(a="card", id=listing["id"]).pack()))
    if pages > 1:
        b.row(
            InlineKeyboardButton(text="◀️", callback_data=Adm(a="list", id=(page - 1) % pages, v=callback_data.v).pack()),
            InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="nav:noop"),
            InlineKeyboardButton(text="▶️", callback_data=Adm(a="list", id=(page + 1) % pages, v=callback_data.v).pack()),
        )
    b.row(InlineKeyboardButton(text="🛠 Panel", callback_data=Adm(a="panel").pack()))
    text = f"<b>{title}</b> — {total} ta" + ("" if total else "\n\nBo‘sh ✨")
    await safe_edit(call, text, b.as_markup())


# ------------------------------------------------------------ obyekt kartasi
async def send_card(bot: Bot, chat_id: int | str, listing_id: int, prefix: str = "") -> None:
    listing = await db.get_listing(listing_id)
    if listing:
        await bot.send_message(chat_id, prefix + await admin_card(listing),
                               reply_markup=kb.admin_listing_kb(listing))


async def refresh_card(call: CallbackQuery, listing_id: int) -> None:
    listing = await db.get_listing(listing_id)
    if listing:
        await safe_edit(call, await admin_card(listing), kb.admin_listing_kb(listing))


@router.callback_query(Adm.filter(F.a == "card"))
async def admin_card_cb(call: CallbackQuery, callback_data: Adm, bot: Bot) -> None:
    listing = await db.get_listing(callback_data.id)
    if not listing:
        await call.answer("Obyekt topilmadi", show_alert=True)
        return
    await call.answer()
    if callback_data.v == "e":
        await refresh_card(call, listing["id"])
    else:
        chat_id = call.message.chat.id if call.message else call.from_user.id
        await send_card(bot, chat_id, listing["id"])


@router.callback_query(Adm.filter(F.a == "approve"))
async def approve(call: CallbackQuery, callback_data: Adm, bot: Bot) -> None:
    listing = await db.get_listing(callback_data.id)
    if not listing:
        await call.answer("Topilmadi", show_alert=True)
        return
    if listing["status"] in ("active", "negotiation"):
        await call.answer("Allaqachon e’lon qilingan")
        return
    first = not listing.get("published_at")
    listing = await db.update_listing(listing["id"], status="active", reject_reason=None,
                                      published_at=listing.get("published_at") or now_str(),
                                      accepted_at=listing.get("accepted_at") or now_str())
    posted = ""
    if config.channel_id:
        if listing.get("channel_message_id"):
            await update_channel_post(bot, listing)
            posted = " · kanal yangilandi"
        elif await publish_to_channel(bot, listing):
            posted = " · kanalga joylandi"
        else:
            posted = " · ⚠️ kanalga joylanmadi (bot kanalda adminmi?)"
    await call.answer(f"✅ E’lon qilindi{posted}", show_alert=True)
    await refresh_card(call, listing["id"])
    if listing.get("source_user_id") and listing["source_type"] != "voha":
        await try_send(bot, listing["source_user_id"],
                       f"🎉 <b>{listing['code']}</b> e’loningiz tasdiqlandi va e’lon qilindi!\n"
                       "Murojaatlar kelishi bilan xabar beramiz.")
    if first:
        subs = await notify_subscribers(bot, listing)
        if subs:
            await try_send(bot, call.from_user.id,
                           f"🔔 {listing['code']}: talabiga mos {subs} ta obunachiga xabar yuborildi.")


@router.callback_query(Adm.filter(F.a == "shoot"))
async def to_shooting(call: CallbackQuery, callback_data: Adm, bot: Bot) -> None:
    listing = await db.get_listing(callback_data.id)
    if listing:
        # Faol e’lon ro‘yxatdan tushmasin — faqat moderatsiyadagisi «syomka» holatiga o‘tadi
        status = "shooting" if listing["status"] == "pending" else listing["status"]
        listing = await db.update_listing(listing["id"], status=status, shooting_requested=1,
                                          accepted_at=listing.get("accepted_at") or now_str())
    if not listing:
        await call.answer("Topilmadi", show_alert=True)
        return
    await call.answer("🎬 Syomka navbatiga qo‘shildi")
    await refresh_card(call, listing["id"])
    if listing.get("source_user_id") and listing["source_type"] != "voha":
        await try_send(bot, listing["source_user_id"],
                       f"🎬 <b>{listing['code']}</b>: e’loningiz qabul qilindi! Professional syomka "
                       "rejalashtirilmoqda — menejer vaqtni kelishish uchun bog‘lanadi.")


@router.callback_query(Adm.filter(F.a == "st"))
async def admin_status(call: CallbackQuery, callback_data: Adm, bot: Bot) -> None:
    if callback_data.v not in ("active", "negotiation", "archived"):
        await call.answer()
        return
    listing = await db.update_listing(callback_data.id, status=callback_data.v)
    if not listing:
        await call.answer("Topilmadi", show_alert=True)
        return
    await call.answer(f"Holat: {LISTING_STATUSES[callback_data.v]}")
    await update_channel_post(bot, listing)
    await refresh_card(call, listing["id"])


@router.callback_query(Adm.filter(F.a == "adpaid"))
async def toggle_ad_fee(call: CallbackQuery, callback_data: Adm) -> None:
    listing = await db.get_listing(callback_data.id)
    if not listing:
        await call.answer("Topilmadi", show_alert=True)
        return
    if not listing.get("ad_fee"):
        await call.answer("Bu obyekt uchun reklama to‘lovi yo‘q (model 1/2).", show_alert=True)
        return
    paid = 0 if listing.get("ad_fee_paid") else 1
    await db.update_listing(listing["id"], ad_fee_paid=paid)
    await call.answer("✅ To‘landi deb belgilandi" if paid else "❌ To‘lanmagan deb belgilandi")
    await refresh_card(call, listing["id"])


@router.callback_query(Adm.filter(F.a == "model"))
async def choose_model(call: CallbackQuery, callback_data: Adm) -> None:
    await call.answer()
    b = InlineKeyboardBuilder()
    for key, m in MODELS.items():
        b.button(text=f"{m['name']} — {m['short']}", callback_data=Adm(a="setmodel", id=callback_data.id, v=str(key)))
    b.button(text="⬅️ Orqaga", callback_data=Adm(a="card", id=callback_data.id, v="e"))
    b.adjust(1)
    await safe_edit(call, "📐 Hamkorlik modelini tanlang:", b.as_markup())


@router.callback_query(Adm.filter(F.a == "setmodel"))
async def set_model(call: CallbackQuery, callback_data: Adm) -> None:
    model = int(callback_data.v) if callback_data.v.isdigit() else 1
    m = MODELS.get(model, MODELS[1])
    await db.update_listing(callback_data.id, model=model, commission_percent=str(m["total"]), ad_fee=m["ad_fee"])
    await call.answer(f"Model: {m['name']}")
    await refresh_card(call, callback_data.id)


@router.callback_query(Adm.filter(F.a == "assign"))
async def choose_broker(call: CallbackQuery, callback_data: Adm) -> None:
    brokers = await db.list_brokers("approved")
    await call.answer()
    b = InlineKeyboardBuilder()
    for br in brokers[:40]:
        b.button(text=f"🤝 {br['full_name']} · {br['district']}",
                 callback_data=Adm(a="setbroker", id=callback_data.id, v=str(br["user_id"])))
    b.button(text="🚫 Maklersiz", callback_data=Adm(a="setbroker", id=callback_data.id, v="0"))
    b.button(text="⬅️ Orqaga", callback_data=Adm(a="card", id=callback_data.id, v="e"))
    b.adjust(1)
    text = "👤 Mas’ul maklerni tanlang:" if brokers else "Tasdiqlangan makler hali yo‘q."
    await safe_edit(call, text, b.as_markup())


@router.callback_query(Adm.filter(F.a == "setbroker"))
async def set_broker(call: CallbackQuery, callback_data: Adm, bot: Bot) -> None:
    broker_id = int(callback_data.v) if callback_data.v.isdigit() and callback_data.v != "0" else None
    listing = await db.update_listing(callback_data.id, broker_id=broker_id)
    await call.answer("Saqlandi")
    await refresh_card(call, callback_data.id)
    if broker_id and listing:
        await try_send(bot, broker_id, f"📌 Sizga <b>{listing['code']}</b> obyekti biriktirildi. "
                                       f"«{Btn.MY_OBJECTS}» bo‘limida ko‘rasiz.")


@router.callback_query(Adm.filter(F.a == "media"))
async def show_media(call: CallbackQuery, callback_data: Adm, bot: Bot) -> None:
    listing = await db.get_listing(callback_data.id)
    if not listing or not await send_album(bot, call.from_user.id, listing):
        await call.answer("Media yo‘q", show_alert=True)
        return
    await call.answer("Shaxsiy chatga yuborildi" if call.message and call.message.chat.id != call.from_user.id else None)


@router.callback_query(Adm.filter(F.a == "repost"))
async def repost(call: CallbackQuery, callback_data: Adm, bot: Bot) -> None:
    if not config.channel_id:
        await call.answer("CHANNEL_ID sozlanmagan (.env)", show_alert=True)
        return
    listing = await db.get_listing(callback_data.id)
    ok = listing and await publish_to_channel(bot, listing)
    await call.answer("📢 Kanalga joylandi" if ok else "⚠️ Joylanmadi — bot kanalda adminmi?", show_alert=True)


@router.callback_query(Adm.filter(F.a == "leads"))
async def listing_leads(call: CallbackQuery, callback_data: Adm) -> None:
    listing = await db.get_listing(callback_data.id)
    leads = await db.listing_leads(callback_data.id)
    await call.answer()
    if not leads:
        await call.bot.send_message(call.from_user.id, f"📭 {listing['code'] if listing else ''} bo‘yicha murojaat yo‘q.")
        return
    b = InlineKeyboardBuilder()
    lines = [f"👥 <b>{listing['code']}</b> murojaatlari — {len(leads)} ta\n"]
    for lead in leads[:30]:
        who = "🤝 makler mijozi" if lead.get("brought_by") else esc(lead.get("buyer_name") or "")
        lines.append(f"#{lead['id']} · {LEAD_STATUSES.get(lead['status'], lead['status'])} · {who} · {lead['source']}")
        b.button(text=f"#{lead['id']}", callback_data=Ld(a="view", id=lead["id"]))
    b.adjust(5)
    await call.bot.send_message(call.from_user.id, "\n".join(lines), reply_markup=b.as_markup())


@router.callback_query(Adm.filter(F.a == "newleads"))
async def new_leads(call: CallbackQuery) -> None:
    leads = await db.leads_by_status("new", "contacted", "scheduled", limit=40)
    await call.answer()
    b = InlineKeyboardBuilder()
    lines = ["🔥 <b>Ishlanayotgan murojaatlar</b>\n"]
    for lead in leads:
        lines.append(f"#{lead['id']} · {lead['code']} · {LEAD_STATUSES.get(lead['status'])} · "
                     f"{esc(lead.get('buyer_name') or '')}")
        b.button(text=f"#{lead['id']}", callback_data=Ld(a="view", id=lead["id"]))
    b.adjust(5)
    b.row(InlineKeyboardButton(text="🛠 Panel", callback_data=Adm(a="panel").pack()))
    if not leads:
        lines.append("Hammasi ishlangan ✨")
    await safe_edit(call, "\n".join(lines), b.as_markup())


# --------------------------------------------- matn kiritiladigan amallar
PROMPTS = {
    "reject": (AdminInput.reject_reason, "❌ Rad etish sababini yozing (egasiga yuboriladi):"),
    "price": (AdminInput.price, "💰 Yangi narxni yozing (masalan: 650 mln):"),
    "pct": (AdminInput.percent, "％ Jami komissiya foizini yozing (masalan: 2 yoki 1,5):"),
    "exp": (AdminInput.expenses, "💸 Obyekt bo‘yicha jami xarajatni yozing (syomka va h.k., masalan: 350 ming yoki 0):"),
}


@router.callback_query(Adm.filter(F.a.in_(PROMPTS.keys())))
async def ask_input(call: CallbackQuery, callback_data: Adm, bot: Bot, fsm_storage: BaseStorage) -> None:
    listing = await db.get_listing(callback_data.id)
    if not listing:
        await call.answer("Topilmadi", show_alert=True)
        return
    st, prompt = PROMPTS[callback_data.a]
    ctx = private_ctx(bot, fsm_storage, call.from_user.id)
    try:
        await bot.send_message(call.from_user.id, f"<b>{listing['code']}</b>\n{prompt}",
                               reply_markup=kb.cancel_kb())
    except (TelegramForbiddenError, TelegramBadRequest):
        await call.answer("Avval bot bilan shaxsiy chatda /start bosing.", show_alert=True)
        return
    await ctx.clear()
    await ctx.set_state(st)
    await ctx.update_data(listing_id=listing["id"])
    await call.answer("Shaxsiy chatda davom eting ✍️" if call.message and call.message.chat.id != call.from_user.id else None)


async def _finish_input(message: Message, state: FSMContext, bot: Bot, listing_id: int, note: str) -> None:
    await state.clear()
    from services.menus import send_main_menu
    await send_main_menu(bot, message.chat.id, None, note)
    await send_card(bot, message.chat.id, listing_id)


@router.message(AdminInput.reject_reason, TEXT_INPUT)
async def got_reject(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    listing = await db.update_listing(data["listing_id"], status="rejected", reject_reason=message.text.strip()[:500])
    if listing and listing.get("source_user_id") and listing["source_type"] != "voha":
        await try_send(bot, listing["source_user_id"],
                       f"😕 <b>{listing['code']}</b> e’loningiz rad etildi.\nSabab: {esc(listing['reject_reason'])}\n\n"
                       "Tuzatib, «E’lonlarim» bo‘limidan qayta yuborishingiz mumkin.")
    await _finish_input(message, state, bot, data["listing_id"], "❌ Rad etildi, egasiga xabar yuborildi.")


@router.message(AdminInput.price, TEXT_INPUT)
async def got_price(message: Message, state: FSMContext, bot: Bot) -> None:
    price = parse_price(message.text)
    if not price:
        await message.answer("❗️ Narxni tushunmadim. Masalan: 650 mln")
        return
    data = await state.get_data()
    listing = await db.update_listing(data["listing_id"], price=price)
    if listing:
        await update_channel_post(bot, listing)
    await _finish_input(message, state, bot, data["listing_id"], f"💰 Narx yangilandi: {fmt_money(price)}")


@router.message(AdminInput.percent, TEXT_INPUT)
async def got_percent(message: Message, state: FSMContext, bot: Bot) -> None:
    value = parse_decimal(message.text)
    if value is None or value > 10:
        await message.answer("❗️ 0 dan 10 gacha foiz yozing. Masalan: 2 yoki 1,5")
        return
    data = await state.get_data()
    await db.update_listing(data["listing_id"], commission_percent=str(value))
    await _finish_input(message, state, bot, data["listing_id"], f"％ Komissiya: {fmt_percent(value)}")


@router.message(AdminInput.expenses, TEXT_INPUT)
async def got_expenses(message: Message, state: FSMContext, bot: Bot) -> None:
    value = 0 if message.text.strip() == "0" else parse_price(message.text)
    if value is None:
        await message.answer("❗️ Summani tushunmadim. Masalan: 350 ming yoki 0")
        return
    data = await state.get_data()
    await db.update_listing(data["listing_id"], expenses=value)
    await _finish_input(message, state, bot, data["listing_id"], f"💸 Xarajat: {fmt_money(value)}")


# ------------------------------------------------------ media yuklash
@router.callback_query(Adm.filter(F.a == "upload"))
async def upload_start(call: CallbackQuery, callback_data: Adm, bot: Bot, fsm_storage: BaseStorage) -> None:
    listing = await db.get_listing(callback_data.id)
    if not listing:
        await call.answer("Topilmadi", show_alert=True)
        return
    ctx = private_ctx(bot, fsm_storage, call.from_user.id)
    try:
        await bot.send_message(
            call.from_user.id,
            f"📤 <b>{listing['code']}</b> uchun tayyor rasmlar ({MAX_PHOTOS} tagacha) va video yuboring.\n"
            f"Yuklangan media eskisini almashtiradi. Tugatgach «{Btn.DONE}» ni bosing.",
            reply_markup=kb.cancel_kb(Btn.DONE))
    except (TelegramForbiddenError, TelegramBadRequest):
        await call.answer("Avval bot bilan shaxsiy chatda /start bosing.", show_alert=True)
        return
    await ctx.clear()
    await ctx.set_state(AdminInput.media)
    await ctx.update_data(listing_id=listing["id"], photos=[], video=None)
    await call.answer()


@router.message(AdminInput.media, F.photo | F.video)
async def upload_media(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    photos = list(data.get("photos") or [])
    video = data.get("video")
    if message.photo and len(photos) < MAX_PHOTOS:
        photos.append(message.photo[-1].file_id)
    elif message.video:
        video = message.video.file_id
    await state.update_data(photos=photos, video=video)
    text = f"📸 {len(photos)}/{MAX_PHOTOS} rasm · 🎥 video: {'bor' if video else '—'}"
    if data.get("media_msg"):
        try:
            await bot.edit_message_text(text, chat_id=message.chat.id, message_id=data["media_msg"])
            return
        except TelegramBadRequest as exc:
            if "not modified" in str(exc):
                return
    sent = await message.answer(text)
    await state.update_data(media_msg=sent.message_id)


@router.message(AdminInput.media, F.text == Btn.DONE)
async def upload_done(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if not data.get("photos") and not data.get("video"):
        await message.answer("Hali media yuborilmadi.")
        return
    listing = await db.get_listing(data["listing_id"])
    fields: dict = {"photos": data["photos"], "video": data.get("video")}
    note = "✅ Media saqlandi."
    if listing and listing["status"] == "shooting":
        fields["status"] = "pending"
        fields["expenses"] = (listing.get("expenses") or 0) + config.shooting_cost
        note += f" Syomka bajarildi (xarajat +{fmt_money(config.shooting_cost)}). Endi e’lon qilishingiz mumkin."
    listing = await db.update_listing(data["listing_id"], **fields)
    if listing and listing["status"] in ("active", "negotiation") and listing.get("channel_message_id"):
        note += "\nℹ️ Kanaldagi post rasmi o‘zgarmaydi — kerak bo‘lsa «📢 Kanalga qayta joylash»."
    await _finish_input(message, state, bot, data["listing_id"], note)


# ------------------------------------------------ foydalanuvchiga javob
@router.callback_query(Adm.filter(F.a == "reply"))
async def reply_start(call: CallbackQuery, callback_data: Adm, bot: Bot, fsm_storage: BaseStorage) -> None:
    ctx = private_ctx(bot, fsm_storage, call.from_user.id)
    try:
        await bot.send_message(call.from_user.id, "✍️ Foydalanuvchiga javobingizni yozing:",
                               reply_markup=kb.cancel_kb())
    except (TelegramForbiddenError, TelegramBadRequest):
        await call.answer("Avval bot bilan shaxsiy chatda /start bosing.", show_alert=True)
        return
    await ctx.clear()
    await ctx.set_state(AdminInput.reply)
    await ctx.update_data(target=callback_data.id)
    await call.answer()


@router.message(AdminInput.reply, TEXT_INPUT)
async def reply_send(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    ok = await try_send(bot, data["target"], f"💬 <b>{esc(config.company_name)} menejeri:</b>\n\n{esc(message.text)}")
    from services.menus import send_main_menu
    await send_main_menu(bot, message.chat.id, None, "✅ Javob yuborildi." if ok else "⚠️ Yuborilmadi (bot bloklangan).")
