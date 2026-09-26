"""Uy ko‘rishga yozilish (xaridor murojaati) va murojaat holatlarini boshqarish."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from callbacks import Ld, Lst
from constants import LEAD_STATUSES, PUBLIC_STATUSES, SOURCES, VIEWING_TIMES
from database import db
from filters import TEXT_INPUT, is_admin
from services.cards import lead_card
from services.helpers import safe_edit, try_send
from services.menus import send_main_menu
from services.notify import notify_admins
from states import LeadForm
from texts import PRIVACY_NOTE, Btn
from utils import esc, normalize_phone

router = Router(name="leads")


async def lead_permissions(lead: dict, listing: dict | None, user_id: int) -> str | None:
    """Kim murojaat holatini o‘zgartira oladi: admin, obyekt maklari yoki mijozni olib kelgan makler."""
    if is_admin(user_id):
        return "admin"
    if lead.get("brought_by") == user_id:
        return "bringer"
    if listing and user_id in listing_brokers(listing):
        broker = await db.get_broker(user_id)
        if broker and broker["status"] == "approved":
            return "listing_broker"
    return None


def listing_brokers(listing: dict) -> set[int]:
    """Obyekt uchun mas’ul maklerlar: biriktirilgan makler va obyektni olib kelgan makler."""
    ids = {listing.get("broker_id")}
    if listing.get("source_type") == "broker":
        ids.add(listing.get("source_user_id"))
    ids.discard(None)
    return ids  # type: ignore[return-value]


async def dispatch_new_lead(bot: Bot, lead: dict, listing: dict) -> None:
    """Yangi murojaatni admin, mas’ul makler va uy egasiga yetkazadi."""
    admin_text = "🔥 <b>Yangi murojaat!</b>\n\n" + await lead_card(lead, listing, admin=True)
    await notify_admins(bot, admin_text, kb.lead_status_kb(lead["id"], lead["status"], listing["id"], admin=True))

    for broker_id in listing_brokers(listing):
        if broker_id in (lead.get("brought_by"), lead.get("buyer_user_id")):
            continue
        broker = await db.get_broker(broker_id)
        if broker and broker["status"] == "approved":
            text = "📩 <b>Obyektingizga yangi murojaat</b>\n\n" + await lead_card(lead, listing, viewer_id=broker_id)
            await try_send(bot, broker_id, text, reply_markup=kb.lead_status_kb(lead["id"], lead["status"], listing["id"]))

    owner_id = listing.get("source_user_id")
    if listing.get("source_type") == "owner" and owner_id and owner_id != lead.get("buyer_user_id"):
        await try_send(bot, owner_id,
                       f"📩 <b>{listing['code']}</b> e’loningizga yangi murojaat keldi!\n"
                       "Voha Uylari menejeri xaridor bilan ishlaydi va uy ko‘rish vaqtini siz bilan kelishadi.")


# ------------------------------------------------------------ xaridor
@router.callback_query(Lst.filter(F.a == "lead"))
async def lead_start(call: CallbackQuery, callback_data: Lst, state: FSMContext, user: dict,
                     bot: Bot) -> None:
    listing = await db.get_listing(callback_data.id)
    if not listing or listing["status"] not in PUBLIC_STATUSES:
        await call.answer("Bu obyekt hozir faol emas.", show_alert=True)
        return
    if user["id"] in (listing.get("source_user_id"), listing.get("broker_id")):
        await call.answer("Bu sizning obyektingiz 🙂", show_alert=True)
        return
    existing = await db.find_lead(listing["id"], user_id=user["id"])
    if existing:
        await call.answer(f"Siz bu obyektga allaqachon yozilgansiz (#{existing['id']}). "
                          "Menejer tez orada bog‘lanadi.", show_alert=True)
        return
    await call.answer()
    source = callback_data.v if callback_data.v in SOURCES else (user.get("source") or "bot")
    await state.clear()
    await state.update_data(listing_id=listing["id"], source=source)
    await state.set_state(LeadForm.phone)
    await bot.send_message(
        call.from_user.id,
        f"📩 <b>{listing['code']}</b> — uy ko‘rishga yozilish\n\n"
        "📱 Telefon raqamingizni yuboring — menejer siz bilan bog‘lanadi:\n"
        f"<i>{PRIVACY_NOTE}</i>",
        reply_markup=kb.phone_kb(user.get("phone")))


async def _after_phone(message: Message, state: FSMContext, phone: str, user: dict) -> None:
    await db.set_user_phone(user["id"], phone)
    await state.update_data(phone=phone)
    data = await state.get_data()
    await state.set_state(LeadForm.time)
    await message.answer("✅ Raqam qabul qilindi.", reply_markup=kb.cancel_kb())
    await message.answer("🕒 Uyni qachon ko‘rish sizga qulay? (yoki o‘zingiz yozing)",
                         reply_markup=kb.viewing_time_kb(data["listing_id"]))


@router.message(LeadForm.phone, F.contact)
async def lead_contact(message: Message, state: FSMContext, user: dict) -> None:
    phone = normalize_phone(message.contact.phone_number) or message.contact.phone_number
    await _after_phone(message, state, phone, user)


@router.message(LeadForm.phone, TEXT_INPUT)
async def lead_phone_text(message: Message, state: FSMContext, user: dict) -> None:
    phone = normalize_phone(message.text)
    if not phone:
        await message.answer("❗️ Raqam noto‘g‘ri. Masalan: <code>+998 90 123 45 67</code>")
        return
    await _after_phone(message, state, phone, user)


async def _ask_comment(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(LeadForm.comment)
    await bot.send_message(chat_id, "💬 Qo‘shimcha izoh yoki savolingiz bormi? "
                                    "(masalan: ipoteka, bo‘lib to‘lash, qo‘shimcha rasm)",
                           reply_markup=kb.cancel_kb(Btn.SKIP))


@router.callback_query(LeadForm.time, Lst.filter(F.a == "time"))
async def lead_time_btn(call: CallbackQuery, callback_data: Lst, state: FSMContext, bot: Bot) -> None:
    await state.update_data(time=callback_data.v)
    await call.answer()
    await safe_edit(call, f"🕒 Qulay vaqt: <b>{VIEWING_TIMES.get(callback_data.v, callback_data.v)}</b>")
    await _ask_comment(bot, call.from_user.id, state)


@router.message(LeadForm.time, TEXT_INPUT)
async def lead_time_text(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.update_data(time=message.text.strip()[:100])
    await _ask_comment(bot, message.chat.id, state)


@router.message(LeadForm.comment, F.text == Btn.SKIP)
@router.message(LeadForm.comment, TEXT_INPUT)
async def lead_finish(message: Message, state: FSMContext, user: dict, bot: Bot) -> None:
    data = await state.get_data()
    comment = None if message.text == Btn.SKIP else message.text.strip()[:500]
    listing = await db.get_listing(data["listing_id"])
    await state.clear()
    if not listing or listing["status"] not in PUBLIC_STATUSES:
        await send_main_menu(bot, message.chat.id, user, "😕 Afsuski, bu obyekt endi faol emas.")
        return
    lead = await db.create_lead(
        listing_id=listing["id"], buyer_user_id=user["id"], buyer_name=user.get("full_name") or "",
        buyer_phone=data["phone"], source=data.get("source") or "bot",
        preferred_time=data.get("time"), comment=comment)
    await dispatch_new_lead(bot, lead, listing)
    await send_main_menu(
        bot, message.chat.id, user,
        f"✅ <b>So‘rovingiz qabul qilindi!</b>\nMurojaat raqami: <b>#{lead['id']}</b> · {listing['code']}\n\n"
        "Menejer tez orada siz bilan bog‘lanib, uy ko‘rish vaqtini kelishadi.\n"
        f"Holatini «{Btn.MY_REQUESTS}» bo‘limida ko‘rasiz.")


# ------------------------------------------------- holatni boshqarish
@router.callback_query(Ld.filter(F.a == "view"))
async def lead_view(call: CallbackQuery, callback_data: Ld) -> None:
    lead = await db.get_lead(callback_data.id)
    if not lead:
        await call.answer("Murojaat topilmadi", show_alert=True)
        return
    listing = await db.get_listing(lead["listing_id"])
    role = await lead_permissions(lead, listing, call.from_user.id)
    if not role:
        await call.answer("Bu murojaatni ko‘rish huquqi yo‘q", show_alert=True)
        return
    await call.answer()
    admin = role == "admin"
    text = await lead_card(lead, listing, viewer_id=call.from_user.id, admin=admin)
    await call.bot.send_message(call.from_user.id, text,
                                reply_markup=kb.lead_status_kb(lead["id"], lead["status"],
                                                               lead["listing_id"], admin=admin))


@router.callback_query(Ld.filter(F.a == "st"))
async def lead_set_status(call: CallbackQuery, callback_data: Ld, bot: Bot) -> None:
    lead = await db.get_lead(callback_data.id)
    if not lead or callback_data.v not in LEAD_STATUSES:
        await call.answer("Murojaat topilmadi", show_alert=True)
        return
    listing = await db.get_listing(lead["listing_id"])
    role = await lead_permissions(lead, listing, call.from_user.id)
    if not role:
        await call.answer("Bu murojaat holatini o‘zgartirish huquqi yo‘q", show_alert=True)
        return
    if lead["status"] == callback_data.v:
        await call.answer("Holat o‘zgarmadi")
        return
    await db.set_lead_status(lead["id"], callback_data.v)
    lead = await db.get_lead(lead["id"])
    admin = role == "admin"
    await call.answer(f"Holat: {LEAD_STATUSES[callback_data.v]}")
    text = await lead_card(lead, listing, viewer_id=call.from_user.id, admin=admin)
    await safe_edit(call, text, kb.lead_status_kb(lead["id"], lead["status"], lead["listing_id"], admin=admin))
    if not admin:
        who = esc(call.from_user.full_name)
        await notify_admins(
            bot, f"🔄 Makler {who} murojaat #{lead['id']} ({listing['code'] if listing else ''}) holatini "
                 f"«{LEAD_STATUSES[callback_data.v]}» ga o‘zgartirdi.",
            kb.lead_status_kb(lead["id"], lead["status"], lead["listing_id"], admin=True))
    if lead.get("buyer_user_id") and callback_data.v in ("scheduled", "won") and not lead.get("brought_by"):
        msg = {"scheduled": "📅 Uy ko‘rish vaqti belgilandi — menejer siz bilan kelishgan vaqtda kutadi.",
               "won": "🎉 Tabriklaymiz! Bitim muvaffaqiyatli yakunlandi."}[callback_data.v]
        await try_send(bot, lead["buyer_user_id"], f"<b>{listing['code'] if listing else ''}</b>: {msg}")
