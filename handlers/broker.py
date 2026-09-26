"""Makler: ro‘yxatdan o‘tish, obyektlar bazasi, «Mijozim bor», mijozlar, statistika."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import keyboards as kb
from callbacks import Adm, Brk, Ld
from constants import (
    BROKER_STATUSES,
    DISTRICTS,
    LEAD_STATUSES,
    LISTING_STATUSES,
    PAGE_SIZE,
    PUBLIC_STATUSES,
)
from database import db
from filters import TEXT_INPUT
from handlers.leads import dispatch_new_lead
from services.cards import listing_short
from services.helpers import safe_edit, user_link
from services.menus import send_main_menu
from services.notify import notify_admins
from services.views import show_listing
from states import BrokerClient, BrokerReg
from texts import Btn, terms_text
from utils import esc, fmt_money, normalize_phone, short_dt

router = Router(name="broker")

EXPERIENCE = ["1 yilgacha", "1–3 yil", "3–5 yil", "5 yildan ko‘p"]


async def approved_broker(message: Message, user: dict) -> dict | None:
    broker = await db.get_broker(user["id"])
    if broker and broker["status"] == "approved":
        return broker
    if broker and broker["status"] == "pending":
        await message.answer("⏳ Arizangiz ko‘rib chiqilmoqda. Tasdiqlangach bu bo‘lim ochiladi.")
    elif broker and broker["status"] == "blocked":
        await message.answer("⛔ Hamkorlik hisobingiz bloklangan. Savollar bo‘lsa, «☎️ Aloqa».")
    else:
        await message.answer(f"🤝 Bu bo‘lim hamkor maklerlar uchun. «{Btn.BROKER_REGISTER}» orqali "
                             "ariza yuboring — qo‘shilish bepul.")
    return None


# ------------------------------------------------------ ro‘yxatdan o‘tish
@router.message(F.text == Btn.BROKER_REGISTER)
async def reg_start(message: Message, state: FSMContext, user: dict) -> None:
    await state.clear()
    broker = await db.get_broker(user["id"])
    if broker and broker["status"] == "approved":
        await message.answer("✅ Siz allaqachon tasdiqlangan hamkorsiz.")
        return
    if broker and broker["status"] == "pending":
        await message.answer("⏳ Arizangiz ko‘rib chiqilmoqda. Tez orada javob beramiz.")
        return
    if broker and broker["status"] == "blocked":
        await message.answer("⛔ Hamkorlik hisobingiz bloklangan.")
        return
    if user.get("role") != "broker":
        await db.set_user_role(user["id"], "broker")
    await state.set_state(BrokerReg.full_name)
    await message.answer("📝 <b>Hamkor makler arizasi</b>\n\n👤 To‘liq ism-familiyangizni yozing:",
                         reply_markup=kb.cancel_kb((user.get("full_name") or "")[:60]))


@router.message(BrokerReg.full_name, TEXT_INPUT)
async def reg_name(message: Message, state: FSMContext, user: dict) -> None:
    name = message.text.strip()
    if not 3 <= len(name) <= 80:
        await message.answer("✍️ Ismni 3–80 belgi oralig‘ida yozing.")
        return
    await state.update_data(full_name=name)
    await state.set_state(BrokerReg.phone)
    await message.answer("📱 Telefon raqamingizni yuboring:", reply_markup=kb.phone_kb(user.get("phone")))


async def _reg_phone(message: Message, state: FSMContext, phone: str, user: dict) -> None:
    await db.set_user_phone(user["id"], phone)
    await state.update_data(phone=phone)
    await state.set_state(BrokerReg.district)
    await message.answer("✅ Raqam qabul qilindi.", reply_markup=kb.cancel_kb())
    await message.answer("📍 Asosan qaysi hududda ishlaysiz?",
                         reply_markup=kb.districts_kb(lambda i: Brk(a="regd", v=str(i))))


@router.message(BrokerReg.phone, F.contact)
async def reg_contact(message: Message, state: FSMContext, user: dict) -> None:
    phone = normalize_phone(message.contact.phone_number) or message.contact.phone_number
    await _reg_phone(message, state, phone, user)


@router.message(BrokerReg.phone, TEXT_INPUT)
async def reg_phone_text(message: Message, state: FSMContext, user: dict) -> None:
    phone = normalize_phone(message.text)
    if not phone:
        await message.answer("❗️ Raqam noto‘g‘ri. Masalan: <code>+998 90 123 45 67</code>")
        return
    await _reg_phone(message, state, phone, user)


@router.callback_query(BrokerReg.district, Brk.filter(F.a == "regd"))
async def reg_district(call: CallbackQuery, callback_data: Brk, state: FSMContext) -> None:
    try:
        district = DISTRICTS[int(callback_data.v)]
    except (ValueError, IndexError):
        await call.answer()
        return
    await state.update_data(district=district)
    await state.set_state(BrokerReg.experience)
    await call.answer()
    b = InlineKeyboardBuilder()
    for i, label in enumerate(EXPERIENCE):
        b.button(text=label, callback_data=Brk(a="rege", v=str(i)))
    b.adjust(2)
    await safe_edit(call, f"📍 Hudud: <b>{district}</b>\n\n🧭 Makler sifatidagi tajribangiz:", b.as_markup())


@router.callback_query(BrokerReg.experience, Brk.filter(F.a == "rege"))
async def reg_experience(call: CallbackQuery, callback_data: Brk, state: FSMContext) -> None:
    exp = EXPERIENCE[int(callback_data.v)] if callback_data.v.isdigit() and int(callback_data.v) < len(EXPERIENCE) else "—"
    await state.update_data(experience=exp)
    await state.set_state(BrokerReg.terms)
    await call.answer()
    b = InlineKeyboardBuilder()
    b.button(text="✅ Shartlarga roziman", callback_data=Brk(a="regt", v="1"))
    b.button(text="❌ Rozi emasman", callback_data=Brk(a="regt", v="0"))
    b.adjust(1)
    await safe_edit(call, terms_text() + "\n\n<b>Shartlarga rozimisiz?</b>", b.as_markup())


@router.callback_query(BrokerReg.terms, Brk.filter(F.a == "regt"))
async def reg_terms(call: CallbackQuery, callback_data: Brk, state: FSMContext, user: dict,
                    bot: Bot) -> None:
    await call.answer()
    if callback_data.v != "1":
        await state.clear()
        await safe_edit(call, "Ariza bekor qilindi. Istalgan vaqtda qayta topshirishingiz mumkin.")
        await send_main_menu(bot, call.from_user.id, None)
        return
    data = await state.get_data()
    await state.clear()
    await db.save_broker(user["id"], data["full_name"], data["phone"], data["district"], data["experience"])
    await safe_edit(call, "✅ Shartlar qabul qilindi.")
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data=Adm(a="bset", id=user["id"], v="approved"))
    b.button(text="❌ Rad etish", callback_data=Adm(a="bset", id=user["id"], v="rejected"))
    b.adjust(2)
    await notify_admins(
        bot,
        "🤝 <b>Yangi makler arizasi</b>\n\n"
        f"👤 {esc(data['full_name'])} ({user_link(user['id'], user.get('full_name'), user.get('username'))})\n"
        f"📱 {esc(data['phone'])}\n📍 {esc(data['district'])}\n🧭 Tajriba: {esc(data['experience'])}",
        b.as_markup())
    await send_main_menu(bot, call.from_user.id, None,
                         "📨 Arizangiz yuborildi! Admin ko‘rib chiqqach, sizga xabar beramiz.")


@router.message(F.text == Btn.TERMS)
async def terms(message: Message) -> None:
    await message.answer(terms_text())


# ------------------------------------------------------- obyektlar bazasi
async def render_base(user_id: int, deal: str, page: int) -> tuple[str, object]:
    listings = await db.base_listings(user_id, deal)
    total = len(listings)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    chunk = listings[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text=("• " if deal == "s" else "") + "🏷 Sotuv",
                             callback_data=Brk(a="base", id=0, v="s").pack()),
        InlineKeyboardButton(text=("• " if deal == "r" else "") + "🔑 Ijara",
                             callback_data=Brk(a="base", id=0, v="r").pack()),
    )
    for listing in chunk:
        b.row(InlineKeyboardButton(text=listing_short(listing),
                                   callback_data=Brk(a="bopen", id=listing["id"]).pack()))
    if pages > 1:
        b.row(
            InlineKeyboardButton(text="◀️", callback_data=Brk(a="base", id=(page - 1) % pages, v=deal).pack()),
            InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data="nav:noop"),
            InlineKeyboardButton(text="▶️", callback_data=Brk(a="base", id=(page + 1) % pages, v=deal).pack()),
        )
    text = (f"🗂 <b>Obyektlar bazasi</b> · {'Sotuv' if deal == 's' else 'Ijara'} — {total} ta\n\n"
            "Mijozingizga mos uyni tanlang va «🤝 Mijozim bor» orqali qayd eting. "
            "Mijoz sizga biriktiriladi — hech kim olib qo‘ymaydi.")
    if not total:
        text += "\n\n😕 Hozircha faol obyekt yo‘q."
    return text, b.as_markup()


@router.message(F.text == Btn.BASE)
async def base(message: Message, state: FSMContext, user: dict) -> None:
    await state.clear()
    if not await approved_broker(message, user):
        return
    text, markup = await render_base(user["id"], "s", 0)
    await message.answer(text, reply_markup=markup)


@router.callback_query(Brk.filter(F.a == "base"))
async def base_page(call: CallbackQuery, callback_data: Brk, user: dict) -> None:
    await call.answer()
    text, markup = await render_base(user["id"], callback_data.v or "s", callback_data.id)
    await safe_edit(call, text, markup)


@router.callback_query(Brk.filter(F.a == "bopen"))
async def base_open(call: CallbackQuery, callback_data: Brk, user: dict, bot: Bot) -> None:
    listing = await db.get_listing(callback_data.id)
    await call.answer()
    if listing:
        await show_listing(bot, call.from_user.id, listing, user)


# ------------------------------------------------------ «Mijozim bor»
@router.callback_query(Brk.filter(F.a == "client"))
async def client_start(call: CallbackQuery, callback_data: Brk, state: FSMContext, user: dict,
                       bot: Bot) -> None:
    broker = await db.get_broker(user["id"])
    if not broker or broker["status"] != "approved":
        await call.answer("Faqat tasdiqlangan hamkor maklerlar uchun.", show_alert=True)
        return
    listing = await db.get_listing(callback_data.id)
    if not listing or listing["status"] not in PUBLIC_STATUSES:
        await call.answer("Obyekt hozir faol emas.", show_alert=True)
        return
    await call.answer()
    await state.clear()
    await state.update_data(listing_id=listing["id"])
    await state.set_state(BrokerClient.name)
    await bot.send_message(call.from_user.id,
                           f"🤝 <b>{listing['code']}</b> — mijozingizni qayd etish\n\n"
                           "👤 Mijozning ismi:", reply_markup=kb.cancel_kb())


@router.message(BrokerClient.name, TEXT_INPUT)
async def client_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip()[:80])
    await state.set_state(BrokerClient.phone)
    await message.answer("📱 Mijozning telefon raqami (faqat admin ko‘radi, boshqa maklerlarga ko‘rinmaydi):")


@router.message(BrokerClient.phone, TEXT_INPUT)
async def client_phone(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text)
    if not phone:
        await message.answer("❗️ Raqam noto‘g‘ri. Masalan: <code>+998 90 123 45 67</code>")
        return
    data = await state.get_data()
    existing = await db.find_lead(data["listing_id"], phone=phone)
    if existing:
        await state.clear()
        mine = existing.get("brought_by") == message.from_user.id
        await message.answer(
            ("ℹ️ Bu mijozni siz allaqachon qayd etgansiz" if mine else
             "⚠️ Bu mijoz ushbu obyekt bo‘yicha allaqachon qayd etilgan") +
            f" (#{existing['id']}, {short_dt(existing['created_at'])}).\n"
            "Mijoz birinchi qayd etilgan manbaga biriktiriladi.")
        await send_main_menu(message.bot, message.chat.id, None)
        return
    await state.update_data(phone=phone)
    await state.set_state(BrokerClient.comment)
    await message.answer("💬 Izoh (mijoz talabi, ko‘rish vaqti va h.k.):", reply_markup=kb.cancel_kb(Btn.SKIP))


@router.message(BrokerClient.comment, F.text == Btn.SKIP)
@router.message(BrokerClient.comment, TEXT_INPUT)
async def client_finish(message: Message, state: FSMContext, user: dict, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    listing = await db.get_listing(data["listing_id"])
    if not listing or listing["status"] not in PUBLIC_STATUSES:
        await send_main_menu(bot, message.chat.id, user, "😕 Obyekt endi faol emas.")
        return
    comment = None if message.text == Btn.SKIP else message.text.strip()[:500]
    lead = await db.create_lead(listing_id=listing["id"], buyer_user_id=None, buyer_name=data["name"],
                                buyer_phone=data["phone"], source="makler", brought_by=user["id"],
                                preferred_time=None, comment=comment)
    await dispatch_new_lead(bot, lead, listing)
    await send_main_menu(
        bot, message.chat.id, user,
        f"✅ <b>Mijozingiz qayd etildi!</b>\nMurojaat #{lead['id']} · {listing['code']}\n"
        f"🕒 Qayd vaqti: {short_dt(lead['created_at'])}\n\n"
        "Mijoz tizimda sizga biriktirildi. Uy ko‘rishni admin bilan kelishing — holatini "
        f"«{Btn.MY_CLIENTS}» bo‘limida yangilab borasiz.")


# ------------------------------------------------ mijozlar va statistika
@router.message(F.text == Btn.MY_CLIENTS)
async def my_clients(message: Message, state: FSMContext, user: dict) -> None:
    await state.clear()
    if not await approved_broker(message, user):
        return
    leads = await db.broker_leads(user["id"])
    if not leads:
        await message.answer("👥 Hozircha murojaat yo‘q.\n«🗂 Obyektlar bazasi» dan mijozingizga uy "
                             "tanlang yoki o‘z obyektingizni qo‘shing.")
        return
    b = InlineKeyboardBuilder()
    lines = ["👥 <b>Mijozlar va murojaatlar</b>\n"]
    for lead in leads[:20]:
        mine = lead.get("brought_by") == user["id"]
        tag = "🙋 mening mijozim" if mine else "📩 obyektimga"
        lines.append(f"#{lead['id']} · {lead['code']} · {LEAD_STATUSES.get(lead['status'], lead['status'])} · {tag}")
        b.button(text=f"#{lead['id']} {lead['code']}", callback_data=Ld(a="view", id=lead["id"]))
    b.adjust(3)
    await message.answer("\n".join(lines), reply_markup=b.as_markup())


@router.message(F.text == Btn.MY_STATS)
async def my_stats(message: Message, state: FSMContext, user: dict) -> None:
    await state.clear()
    broker = await approved_broker(message, user)
    if not broker:
        return
    s = await db.broker_stats(user["id"])
    by_status = s["listings"]
    lines = [
        f"📊 <b>Statistikangiz</b> — {esc(broker['full_name'])}",
        f"{BROKER_STATUSES[broker['status']]} · {short_dt(broker.get('approved_at'))} dan beri\n",
        f"🏠 Obyektlar: {sum(by_status.values())} ta",
    ]
    for key in ("active", "negotiation", "pending", "shooting", "sold", "rented"):
        if by_status.get(key):
            lines.append(f"   {LISTING_STATUSES[key]}: {by_status[key]}")
    lines += [
        f"👁 Obyektlaringiz ko‘rishlari: {s['views']}",
        f"🙋 Siz olib kelgan mijozlar: {s['clients']}",
        f"📩 Obyektlaringizga murojaatlar: {s['incoming']}",
        f"🤝 Bitimlar: {s['deals']}",
        f"💰 Olingan ulush: <b>{fmt_money(s['earned_paid'])}</b>",
        f"⏳ Kutilayotgan ulush: {fmt_money(s['earned_unpaid'])}",
    ]
    await message.answer("\n".join(lines))
