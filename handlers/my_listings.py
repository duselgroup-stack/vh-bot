"""Uy egasi va makler: o‘z e’lonlarini ko‘rish va holatini yangilash."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import keyboards as kb
from callbacks import Adm, Ld, Lst
from constants import LEAD_STATUSES, LISTING_STATUSES
from database import db
from handlers.leads import listing_brokers
from services.cards import admin_card, listing_short, owner_card
from services.helpers import safe_edit, user_link
from services.notify import notify_admins, update_channel_post
from texts import Btn

router = Router(name="my_listings")


def is_owner(listing: dict | None, user_id: int) -> bool:
    return bool(listing) and user_id in (listing.get("source_user_id"), listing.get("broker_id"))


async def can_see_leads(listing: dict, user_id: int) -> bool:
    if user_id not in listing_brokers(listing):
        return False
    broker = await db.get_broker(user_id)
    return bool(broker and broker["status"] == "approved")


@router.message(F.text.in_({Btn.MY_LISTINGS, Btn.MY_OBJECTS}))
async def my_listings(message: Message, state: FSMContext, user: dict) -> None:
    await state.clear()
    listings = await db.user_listings(user["id"])
    if not listings:
        hint = Btn.ADD_OBJECT if message.text == Btn.MY_OBJECTS else f"{Btn.SELL}» yoki «{Btn.RENT_OUT}"
        await message.answer(f"📋 Sizda hali e’lon yo‘q.\n«{hint}» orqali qo‘shing.")
        return
    b = InlineKeyboardBuilder()
    for listing in listings[:40]:
        status = LISTING_STATUSES.get(listing["status"], "").split(" ")[0]
        b.row(InlineKeyboardButton(text=f"{status} {listing_short(listing)}",
                                   callback_data=Lst(a="my", id=listing["id"]).pack()))
    await message.answer(f"📋 <b>E’lonlaringiz</b> — {len(listings)} ta\nBatafsil ko‘rish uchun tanlang:",
                         reply_markup=b.as_markup())


@router.callback_query(Lst.filter(F.a == "my"))
async def my_listing_card(call: CallbackQuery, callback_data: Lst, user: dict) -> None:
    listing = await db.get_listing(callback_data.id)
    if not is_owner(listing, user["id"]):
        await call.answer("Bu e’lon sizga tegishli emas", show_alert=True)
        return
    await call.answer()
    await call.bot.send_message(call.from_user.id, await owner_card(listing),
                                reply_markup=kb.owner_listing_kb(listing, await can_see_leads(listing, user["id"])))


ALLOWED = {
    "active": ("active", "negotiation"),
    "negotiation": ("active", "negotiation"),
    "sold": ("active", "negotiation"),
    "rented": ("active", "negotiation"),
    "archived": ("active", "negotiation", "pending", "shooting"),
    "pending": ("archived", "rejected"),
}


@router.callback_query(Lst.filter(F.a == "ost"))
async def my_listing_status(call: CallbackQuery, callback_data: Lst, user: dict, bot: Bot) -> None:
    listing = await db.get_listing(callback_data.id)
    new = callback_data.v
    if not is_owner(listing, user["id"]):
        await call.answer("Bu e’lon sizga tegishli emas", show_alert=True)
        return
    if new not in ALLOWED or listing["status"] not in ALLOWED[new]:
        await call.answer("Bu holatga o‘tkazib bo‘lmaydi", show_alert=True)
        return
    if listing["status"] == new:
        await call.answer("Holat o‘zgarmadi")
        return
    if new == "rented" and listing["deal_type"] != "r" or new == "sold" and listing["deal_type"] != "s":
        await call.answer("Bitim turiga mos emas", show_alert=True)
        return
    listing = await db.update_listing(listing["id"], status=new)
    await call.answer(f"Holat: {LISTING_STATUSES[new]}")
    await safe_edit(call, await owner_card(listing),
                    kb.owner_listing_kb(listing, await can_see_leads(listing, user["id"])))
    await update_channel_post(bot, listing)

    who = user_link(user["id"], user.get("full_name"), user.get("username"))
    if new in ("sold", "rented"):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧾 Bitimni rasmiylashtirish",
                                  callback_data=Adm(a="deal", id=listing["id"]).pack())],
            [InlineKeyboardButton(text="🛠 Obyekt kartasi", callback_data=Adm(a="card", id=listing["id"]).pack())],
        ])
        await notify_admins(bot, f"🏁 {who} <b>{listing['code']}</b> ni «{LISTING_STATUSES[new]}» deb belgiladi.\n"
                                 "Bitim narxi, xaridor manbasi va komissiyani rasmiylashtiring.", markup)
        await bot.send_message(call.from_user.id, "🎉 Tabriklaymiz! Admin bitimni rasmiylashtirish uchun "
                                                  "siz bilan bog‘lanadi.")
    elif new == "pending":
        await notify_admins(bot, f"♻️ {who} e’lonni qayta moderatsiyaga yubordi.\n\n" + await admin_card(listing),
                            kb.admin_listing_kb(listing))
    else:
        await notify_admins(bot, f"🔄 {who} <b>{listing['code']}</b> holatini «{LISTING_STATUSES[new]}» ga o‘zgartirdi.",
                            kb.back_kb(Adm(a="card", id=listing["id"]), "🛠 Obyekt kartasi"))


@router.callback_query(Lst.filter(F.a == "shootreq"))
async def request_shooting(call: CallbackQuery, callback_data: Lst, user: dict, bot: Bot) -> None:
    listing = await db.get_listing(callback_data.id)
    if not is_owner(listing, user["id"]):
        await call.answer("Bu e’lon sizga tegishli emas", show_alert=True)
        return
    if listing.get("shooting_requested"):
        await call.answer("Syomka allaqachon so‘ralgan")
        return
    listing = await db.update_listing(listing["id"], shooting_requested=1)
    await call.answer("🎬 So‘rov yuborildi — menejer vaqtni kelishish uchun bog‘lanadi.", show_alert=True)
    await safe_edit(call, await owner_card(listing),
                    kb.owner_listing_kb(listing, await can_see_leads(listing, user["id"])))
    who = user_link(user["id"], user.get("full_name"), user.get("username"))
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Syomka navbatiga", callback_data=Adm(a="shoot", id=listing["id"]).pack())],
        [InlineKeyboardButton(text="🛠 Obyekt kartasi", callback_data=Adm(a="card", id=listing["id"]).pack())],
    ])
    await notify_admins(bot, f"🎬 {who} <b>{listing['code']}</b> uchun professional syomka so‘radi.", markup)


@router.callback_query(Lst.filter(F.a == "leads"))
async def my_listing_leads(call: CallbackQuery, callback_data: Lst, user: dict) -> None:
    listing = await db.get_listing(callback_data.id)
    if not listing or not await can_see_leads(listing, user["id"]):
        await call.answer("Murojaatlarni faqat mas’ul makler ko‘radi", show_alert=True)
        return
    leads = await db.listing_leads(listing["id"])
    await call.answer()
    if not leads:
        await call.bot.send_message(call.from_user.id, f"📭 {listing['code']} bo‘yicha hali murojaat yo‘q.")
        return
    b = InlineKeyboardBuilder()
    lines = [f"👥 <b>{listing['code']}</b> murojaatlari\n"]
    for lead in leads[:20]:
        lines.append(f"#{lead['id']} · {LEAD_STATUSES.get(lead['status'], lead['status'])}")
        b.button(text=f"#{lead['id']}", callback_data=Ld(a="view", id=lead["id"]))
    b.adjust(4)
    await call.bot.send_message(call.from_user.id, "\n".join(lines), reply_markup=b.as_markup())
