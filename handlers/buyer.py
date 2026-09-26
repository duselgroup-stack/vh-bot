"""Xaridor: qidiruv, ID bo‘yicha qidirish, obunalar, murojaatlarim."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import keyboards as kb
from callbacks import Lst, Srch, Sub
from constants import (
    DEAL_TYPES,
    DISTRICTS,
    LEAD_STATUSES,
    MAX_SUBSCRIPTIONS,
    PRICE_RANGES,
    PROPERTY_TYPES,
)
from database import db
from filters import TEXT_INPUT
from services.helpers import safe_delete, safe_edit
from services.notify import send_album
from services.views import show_listing
from states import SearchId
from texts import Btn
from utils import fmt_short, parse_code, short_dt

router = Router(name="buyer")


# ----------------------------------------------------------- filtr matni
def filter_summary(cb: Srch) -> str:
    parts = [f"🎯 {DEAL_TYPES[cb.dl]}"]
    parts.append(f"📍 {DISTRICTS[cb.d] if 0 <= cb.d < len(DISTRICTS) else 'Barcha hududlar'}")
    parts.append(f"🏠 {PROPERTY_TYPES.get(cb.t, 'Barcha turlar')}")
    if cb.r:
        parts.append(f"🚪 {cb.r}{'+' if cb.r >= 5 else ''} xona")
    ranges = PRICE_RANGES[cb.dl]
    parts.append(f"💰 {ranges[cb.p][2] if 0 <= cb.p < len(ranges) else 'Istalgan narx'}")
    return " · ".join(parts)


def filter_params(cb: Srch) -> dict:
    ranges = PRICE_RANGES[cb.dl]
    pmin, pmax = (ranges[cb.p][0], ranges[cb.p][1]) if 0 <= cb.p < len(ranges) else (None, None)
    return {
        "deal_type": cb.dl,
        "district": DISTRICTS[cb.d] if 0 <= cb.d < len(DISTRICTS) else None,
        "property_type": cb.t if cb.t in PROPERTY_TYPES else None,
        "rooms": cb.r,
        "price_min": pmin,
        "price_max": pmax,
    }


def sub_summary(sub: dict) -> str:
    cb = Srch(s="x", dl=sub["deal_type"],
              d=DISTRICTS.index(sub["district"]) if sub.get("district") in DISTRICTS else -1,
              t=sub.get("property_type") or "x", r=sub.get("rooms") or 0, p=-1)
    text = filter_summary(cb)
    if sub.get("price_min") or sub.get("price_max"):
        low = fmt_short(sub["price_min"]) if sub.get("price_min") else "0"
        high = fmt_short(sub["price_max"]) if sub.get("price_max") else "∞"
        text = text.replace("💰 Istalgan narx", f"💰 {low} – {high}")
    return text


# ------------------------------------------------------------- qidiruv
async def start_search(message: Message, state: FSMContext, deal: str) -> None:
    await state.clear()
    cb = Srch(s="d", dl=deal)
    await message.answer(
        f"🔎 <b>{'Uy sotib olish' if deal == 's' else 'Ijaraga olish'}</b>\n📍 Hududni tanlang:",
        reply_markup=kb.districts_kb(lambda i: cb.model_copy(update={"d": i}),
                                     all_cb=cb.model_copy(update={"d": -1})))


@router.message(F.text == Btn.BUY)
async def search_buy(message: Message, state: FSMContext) -> None:
    await start_search(message, state, "s")


@router.message(F.text == Btn.RENT)
async def search_rent(message: Message, state: FSMContext) -> None:
    await start_search(message, state, "r")


@router.callback_query(Srch.filter(F.s == "new"))
async def search_new(call: CallbackQuery, callback_data: Srch) -> None:
    await call.answer()
    cb = Srch(s="d", dl=callback_data.dl)
    markup = kb.districts_kb(lambda i: cb.model_copy(update={"d": i}),
                             all_cb=cb.model_copy(update={"d": -1}))
    text = f"🔎 <b>{'Uy sotib olish' if cb.dl == 's' else 'Ijaraga olish'}</b>\n📍 Hududni tanlang:"
    if isinstance(call.message, Message) and (call.message.photo or call.message.video):
        await safe_delete(call.message)
        await call.bot.send_message(call.from_user.id, text, reply_markup=markup)
    else:
        await safe_edit(call, text, markup)


@router.callback_query(Srch.filter(F.s == "d"))
async def search_district(call: CallbackQuery, callback_data: Srch) -> None:
    await call.answer()
    cb = callback_data.model_copy(update={"s": "t"})
    await safe_edit(
        call, f"{filter_summary(cb)}\n\n🏠 Mulk turini tanlang:",
        kb.ptypes_kb(lambda k: cb.model_copy(update={"t": k}), all_cb=cb.model_copy(update={"t": "x"}),
                     back=Srch(s="new", dl=cb.dl)))


@router.callback_query(Srch.filter(F.s == "t"))
async def search_type(call: CallbackQuery, callback_data: Srch) -> None:
    await call.answer()
    back = callback_data.model_copy(update={"s": "d"})
    if callback_data.t in ("h", "a", "x"):
        cb = callback_data.model_copy(update={"s": "r"})
        await safe_edit(call, f"{filter_summary(cb)}\n\n🚪 Xonalar soni:",
                        kb.rooms_kb(lambda n: cb.model_copy(update={"r": n}),
                                    any_cb=cb.model_copy(update={"r": 0}), back=back))
        return
    cb = callback_data.model_copy(update={"s": "p", "r": 0})
    await safe_edit(call, f"{filter_summary(cb)}\n\n💰 Narx oralig‘ini tanlang:",
                    kb.prices_kb(cb.dl, lambda i: cb.model_copy(update={"p": i}),
                                 any_cb=cb.model_copy(update={"p": -1}), back=back))


@router.callback_query(Srch.filter(F.s == "r"))
async def search_rooms(call: CallbackQuery, callback_data: Srch) -> None:
    await call.answer()
    cb = callback_data.model_copy(update={"s": "p"})
    back = callback_data.model_copy(update={"s": "t"})
    await safe_edit(call, f"{filter_summary(cb)}\n\n💰 Narx oralig‘ini tanlang:",
                    kb.prices_kb(cb.dl, lambda i: cb.model_copy(update={"p": i}),
                                 any_cb=cb.model_copy(update={"p": -1}), back=back))


@router.callback_query(Srch.filter(F.s.in_({"p", "pg"})))
async def search_results(call: CallbackQuery, callback_data: Srch, user: dict, bot: Bot) -> None:
    ids = await db.search_listings(**filter_params(callback_data))
    await call.answer()
    if not ids:
        sub_cb = callback_data.model_copy(update={"s": "sub"})
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Yangi e’lon chiqsa xabar berish", callback_data=sub_cb.pack())],
            [InlineKeyboardButton(text="🔄 Yangi qidiruv", callback_data=Srch(s="new", dl=callback_data.dl).pack())],
        ])
        await safe_edit(call, f"{filter_summary(callback_data)}\n\n😕 Hozircha mos obyekt topilmadi.\n"
                              "Obuna bo‘ling — mos uy chiqishi bilan xabar beramiz.", markup)
        return
    total = len(ids)
    page = callback_data.pg % total
    listing = await db.get_listing(ids[page])
    prev_cb = callback_data.model_copy(update={"s": "pg", "pg": (page - 1) % total})
    next_cb = callback_data.model_copy(update={"s": "pg", "pg": (page + 1) % total})
    search_cb = callback_data.model_copy(update={"pg": 0})
    await safe_delete(call.message)
    if callback_data.s == "p":
        await bot.send_message(call.from_user.id,
                               f"{filter_summary(callback_data)}\n✅ Topildi: <b>{total}</b> ta obyekt")
    await show_listing(bot, call.from_user.id, listing, user, source="",
                       nav=(prev_cb, next_cb, f"{page + 1}/{total}"), search_cb=search_cb)


@router.callback_query(Srch.filter(F.s == "sub"))
async def search_subscribe(call: CallbackQuery, callback_data: Srch, user: dict) -> None:
    subs = await db.user_subscriptions(user["id"])
    if len(subs) >= MAX_SUBSCRIPTIONS:
        await call.answer(f"Obunalar soni {MAX_SUBSCRIPTIONS} tadan oshmasin. «{Btn.SUBS}» bo‘limida "
                          "keraksizlarini o‘chiring.", show_alert=True)
        return
    p = filter_params(callback_data)
    await db.add_subscription(user["id"], p["deal_type"], p["district"], p["property_type"],
                              p["rooms"], p["price_min"], p["price_max"])
    await call.answer("🔔 Obuna qo‘shildi! Mos yangi e’lon chiqishi bilan xabar beramiz.", show_alert=True)


# ------------------------------------------------------------ obunalar
async def render_subs(user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    subs = await db.user_subscriptions(user_id)
    if not subs:
        return ("🔔 Sizda obuna yo‘q.\n\nQidiruv natijasida «🔔 Obuna bo‘lish» tugmasini bosing — "
                "talabingizga mos yangi e’lon chiqishi bilan xabar beramiz."), None
    b = InlineKeyboardBuilder()
    lines = ["🔔 <b>Obunalaringiz</b>\n"]
    for i, sub in enumerate(subs, 1):
        lines.append(f"{i}. {sub_summary(sub)}")
        b.button(text=f"🗑 {i}-obunani o‘chirish", callback_data=Sub(a="del", id=sub["id"]))
    b.adjust(2)
    return "\n".join(lines), b.as_markup()


@router.message(F.text == Btn.SUBS)
async def my_subs(message: Message, state: FSMContext, user: dict) -> None:
    await state.clear()
    text, markup = await render_subs(user["id"])
    await message.answer(text, reply_markup=markup)


@router.callback_query(Sub.filter(F.a == "del"))
async def del_sub(call: CallbackQuery, callback_data: Sub, user: dict) -> None:
    await db.delete_subscription(callback_data.id, user["id"])
    await call.answer("O‘chirildi")
    text, markup = await render_subs(user["id"])
    await safe_edit(call, text, markup)


# ------------------------------------------------------ ID bo‘yicha qidirish
@router.message(Command("id"))
@router.message(F.text == Btn.BY_ID)
async def ask_id(message: Message, state: FSMContext) -> None:
    await state.set_state(SearchId.code)
    await message.answer("🆔 Obyekt ID sini yozing:\n<i>Masalan: VU-0012 yoki 12</i>",
                         reply_markup=kb.cancel_kb())


async def open_by_code(message: Message, user: dict, bot: Bot, text: str) -> bool:
    listing_id = parse_code(text)
    listing = await db.get_listing(listing_id) if listing_id else None
    if not listing:
        await message.answer("😕 Bunday ID li obyekt topilmadi. Qayta tekshirib yozing.")
        return False
    await show_listing(bot, message.chat.id, listing, user, source="")
    return True


@router.message(SearchId.code, TEXT_INPUT)
async def got_id(message: Message, state: FSMContext, user: dict, bot: Bot) -> None:
    if await open_by_code(message, user, bot, message.text):
        await state.clear()
        from services.menus import send_main_menu
        await send_main_menu(bot, message.chat.id, user, "Yana biror ID yozish uchun «🆔 ID bo‘yicha qidirish».")


@router.message(StateFilter(None), F.text.regexp(r"(?i)^\s*vu[\s\-_]*\d{1,7}\s*$"))
async def code_anywhere(message: Message, user: dict, bot: Bot) -> None:
    await open_by_code(message, user, bot, message.text)


# ------------------------------------------------------- ochish va media
@router.callback_query(Lst.filter(F.a == "open"))
async def open_listing(call: CallbackQuery, callback_data: Lst, user: dict, bot: Bot) -> None:
    listing = await db.get_listing(callback_data.id)
    await call.answer()
    if listing:
        await show_listing(bot, call.from_user.id, listing, user, source="")


@router.callback_query(Lst.filter(F.a == "media"))
async def listing_media(call: CallbackQuery, callback_data: Lst, bot: Bot) -> None:
    listing = await db.get_listing(callback_data.id)
    if not listing or not await send_album(bot, call.from_user.id, listing):
        await call.answer("Media topilmadi", show_alert=True)
        return
    await call.answer()


# --------------------------------------------------------- murojaatlarim
@router.message(F.text == Btn.MY_REQUESTS)
async def my_requests(message: Message, state: FSMContext, user: dict) -> None:
    await state.clear()
    leads = await db.buyer_leads(user["id"])
    if not leads:
        await message.answer("📝 Sizda hali murojaat yo‘q.\nYoqqan uyni topib «📩 Ko‘rishga yozilish» ni bosing.")
        return
    b = InlineKeyboardBuilder()
    lines = ["📝 <b>Murojaatlaringiz</b>\n"]
    for lead in leads[:15]:
        lines.append(f"• <b>{lead['code']}</b> — {LEAD_STATUSES.get(lead['status'], lead['status'])} "
                     f"({short_dt(lead['created_at'])})")
        b.button(text=f"🏠 {lead['code']}", callback_data=Lst(a="open", id=lead["listing_id"]))
    b.adjust(3)
    await message.answer("\n".join(lines), reply_markup=b.as_markup())
