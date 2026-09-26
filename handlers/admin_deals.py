"""Admin: bitimni yopish (narx → xaridor → manba → makler → komissiya taqsimoti)."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import keyboards as kb
from callbacks import Adm
from constants import LEAD_STATUSES, MODELS, SOURCES
from database import db
from filters import TEXT_INPUT, IsAdmin
from services.commission import calc_split, listing_percent, split_text
from services.helpers import private_ctx, safe_edit, try_send
from services.menus import send_main_menu
from services.notify import update_channel_post
from states import DealForm
from utils import esc, fmt_money, fmt_short, parse_price

router = Router(name="admin_deals")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(Adm.filter(F.a == "deal"))
async def deal_start(call: CallbackQuery, callback_data: Adm, bot: Bot, fsm_storage: BaseStorage) -> None:
    listing = await db.get_listing(callback_data.id)
    if not listing:
        await call.answer("Topilmadi", show_alert=True)
        return
    ctx = private_ctx(bot, fsm_storage, call.from_user.id)
    b = InlineKeyboardBuilder()
    b.button(text=f"💰 E’londagi narx: {fmt_short(listing['price'])}",
             callback_data=Adm(a="dprice", id=listing["id"]))
    try:
        await bot.send_message(call.from_user.id, "🧾 Bitimni rasmiylashtirish", reply_markup=kb.cancel_kb())
        await bot.send_message(
            call.from_user.id,
            f"🤝 <b>{listing['code']}</b> — bitimni yopish\n\n"
            "1️⃣ Yakuniy bitim narxini yozing (so‘mda) yoki e’londagi narxni tanlang:",
            reply_markup=b.as_markup())
    except (TelegramForbiddenError, TelegramBadRequest):
        await call.answer("Avval bot bilan shaxsiy chatda /start bosing.", show_alert=True)
        return
    await ctx.clear()
    await ctx.set_state(DealForm.price)
    await ctx.update_data(listing_id=listing["id"])
    await call.answer("Shaxsiy chatda davom eting ✍️" if call.message and call.message.chat.id != call.from_user.id else None)


async def ask_lead(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    leads = [lead for lead in await db.listing_leads(data["listing_id"]) if lead["status"] != "lost"]
    b = InlineKeyboardBuilder()
    for lead in leads[:15]:
        who = "🤝 makler mijozi" if lead.get("brought_by") else (lead.get("buyer_name") or "")
        b.button(text=f"#{lead['id']} {who[:20]} · {LEAD_STATUSES.get(lead['status'], '')}",
                 callback_data=Adm(a="dlead", id=lead["id"]))
    b.button(text="➖ Murojaatsiz (tashqi xaridor)", callback_data=Adm(a="dlead", id=0))
    b.adjust(1)
    await state.set_state(DealForm.lead)
    await bot.send_message(chat_id, f"💰 Narx: <b>{fmt_money(data['price'])}</b>\n\n"
                                    "2️⃣ Xaridor qaysi murojaat orqali keldi?", reply_markup=b.as_markup())


@router.callback_query(DealForm.price, Adm.filter(F.a == "dprice"))
async def deal_price_btn(call: CallbackQuery, callback_data: Adm, state: FSMContext, bot: Bot) -> None:
    listing = await db.get_listing(callback_data.id)
    await state.update_data(price=listing["price"])
    await call.answer()
    await safe_edit(call, f"1️⃣ Narx: <b>{fmt_money(listing['price'])}</b>")
    await ask_lead(bot, call.from_user.id, state)


@router.message(DealForm.price, TEXT_INPUT)
async def deal_price_text(message: Message, state: FSMContext, bot: Bot) -> None:
    price = parse_price(message.text)
    if not price:
        await message.answer("❗️ Narxni tushunmadim. Masalan: 620 mln")
        return
    await state.update_data(price=price)
    await ask_lead(bot, message.chat.id, state)


@router.callback_query(DealForm.lead, Adm.filter(F.a == "dlead"))
async def deal_lead(call: CallbackQuery, callback_data: Adm, state: FSMContext) -> None:
    lead = await db.get_lead(callback_data.id) if callback_data.id else None
    default_source = lead["source"] if lead else "boshqa"
    await state.update_data(lead_id=lead["id"] if lead else None, source=default_source)
    await state.set_state(DealForm.source)
    await call.answer()
    b = InlineKeyboardBuilder()
    for key, label in SOURCES.items():
        b.button(text=("✅ " if key == default_source else "") + label, callback_data=Adm(a="dsrc", v=key))
    b.adjust(2)
    chosen = f"#{lead['id']}" if lead else "murojaatsiz"
    await safe_edit(call, f"2️⃣ Xaridor: <b>{chosen}</b>\n\n3️⃣ Xaridor manbasini tasdiqlang:", b.as_markup())


@router.callback_query(DealForm.source, Adm.filter(F.a == "dsrc"))
async def deal_source(call: CallbackQuery, callback_data: Adm, state: FSMContext) -> None:
    await state.update_data(source=callback_data.v if callback_data.v in SOURCES else "boshqa")
    data = await state.get_data()
    listing = await db.get_listing(data["listing_id"])
    lead = await db.get_lead(data["lead_id"]) if data.get("lead_id") else None
    candidates: list[int] = []
    model = listing.get("model") or 0
    # 2-model: obyekt maklerniki; 1/3-model: odatda xaridorni olib kelgan makler
    order = [listing.get("broker_id"), lead.get("brought_by") if lead else None]
    if model != 2:
        order.reverse()
    for uid in order:
        if uid and uid not in candidates:
            candidates.append(uid)
    b = InlineKeyboardBuilder()
    for uid in candidates:
        broker = await db.get_broker(uid)
        if broker:
            b.button(text=f"🤝 {broker['full_name']}", callback_data=Adm(a="dbrk", id=uid))
    for broker in (await db.list_brokers("approved"))[:15]:
        if broker["user_id"] not in candidates:
            b.button(text=f"👤 {broker['full_name']}", callback_data=Adm(a="dbrk", id=broker["user_id"]))
    b.button(text="🚫 Maklersiz (ulush Vohaga)", callback_data=Adm(a="dbrk", id=0))
    b.adjust(1)
    await state.set_state(DealForm.broker)
    await call.answer()
    await safe_edit(call, f"3️⃣ Manba: <b>{SOURCES[data['source']]}</b>\n\n"
                          "4️⃣ Komissiya ulushini oladigan maklerni tanlang (tavsiya etilgan — tepada):",
                    b.as_markup())


async def show_confirm(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    listing = await db.get_listing(data["listing_id"])
    if data.get("manual"):
        split = {**data["manual"]}
    else:
        split = calc_split(data["price"], listing.get("model") or 0, listing_percent(listing),
                           with_broker=bool(data.get("broker_id")))
        split = {k: (str(v) if k.endswith("_pct") else v) for k, v in split.items()}
        await state.update_data(split=split)
    broker = await db.get_broker(data["broker_id"]) if data.get("broker_id") else None
    from decimal import Decimal
    view = {**split, **{k: Decimal(str(v)) for k, v in split.items() if k.endswith("_pct")}}
    text = (
        f"🧾 <b>{listing['code']} — bitim xulosasi</b>\n\n"
        f"{split_text(data['price'], view)}\n"
        f"🧭 Xaridor manbasi: {SOURCES.get(data['source'], data['source'])}\n"
        f"👤 Makler: {esc(broker['full_name']) if broker else '—'}\n"
        f"📩 Murojaat: {('#' + str(data['lead_id'])) if data.get('lead_id') else '—'}\n\n"
        "Saqlansa, obyekt «sotilgan/ijaraga berilgan» bo‘ladi va komissiya «undirilmagan» ro‘yxatiga tushadi."
    )
    b = InlineKeyboardBuilder()
    b.button(text="✅ Saqlash", callback_data=Adm(a="dsave"))
    b.button(text="✏️ Summani qo‘lda kiritish", callback_data=Adm(a="dmanual"))
    b.button(text="❌ Bekor qilish", callback_data="nav:main")
    b.adjust(1)
    await state.set_state(DealForm.confirm)
    await bot.send_message(chat_id, text, reply_markup=b.as_markup())


@router.callback_query(DealForm.broker, Adm.filter(F.a == "dbrk"))
async def deal_broker(call: CallbackQuery, callback_data: Adm, state: FSMContext, bot: Bot) -> None:
    await state.update_data(broker_id=callback_data.id or None, manual=None)
    await call.answer()
    broker = await db.get_broker(callback_data.id) if callback_data.id else None
    await safe_edit(call, f"4️⃣ Makler: <b>{esc(broker['full_name']) if broker else 'maklersiz'}</b>")
    await show_confirm(bot, call.from_user.id, state)


@router.callback_query(DealForm.confirm, Adm.filter(F.a == "dmanual"))
async def deal_manual(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await call.answer()
    await state.set_state(DealForm.manual_total)
    await bot.send_message(call.from_user.id, "✏️ Jami komissiya summasini yozing (masalan: 12 mln):")


@router.message(DealForm.manual_total, TEXT_INPUT)
async def deal_manual_total(message: Message, state: FSMContext) -> None:
    total = 0 if message.text.strip() == "0" else parse_price(message.text)
    if total is None:
        await message.answer("❗️ Summani tushunmadim. Masalan: 12 mln")
        return
    await state.update_data(manual_total=total)
    data = await state.get_data()
    if not data.get("broker_id"):
        await _apply_manual(message, state, total, 0)
        return
    await state.set_state(DealForm.manual_broker)
    await message.answer("🤝 Shundan maklerga tegishli ulush summasi (masalan: 4 mln yoki 0):")


@router.message(DealForm.manual_broker, TEXT_INPUT)
async def deal_manual_broker(message: Message, state: FSMContext) -> None:
    value = 0 if message.text.strip() == "0" else parse_price(message.text)
    data = await state.get_data()
    if value is None or value > data["manual_total"]:
        await message.answer("❗️ Makler ulushi jami summadan oshmasligi kerak.")
        return
    await _apply_manual(message, state, data["manual_total"], value)


async def _apply_manual(message: Message, state: FSMContext, total: int, broker_share: int) -> None:
    from decimal import Decimal
    data = await state.get_data()
    listing = await db.get_listing(data["listing_id"])
    price = Decimal(data["price"])
    pct = lambda v: str((Decimal(v) * 100 / price).quantize(Decimal("0.001")))  # noqa: E731
    manual = {
        "model": listing.get("model") or 0,
        "total_pct": pct(total), "voha_pct": pct(total - broker_share), "broker_pct": pct(broker_share),
        "commission": total, "broker_share": broker_share, "voha_share": total - broker_share,
        "ad_fee": MODELS.get(listing.get("model") or 0, MODELS[1])["ad_fee"],
    }
    await state.update_data(manual=manual, split=manual)
    await show_confirm(message.bot, message.chat.id, state)


@router.callback_query(DealForm.confirm, Adm.filter(F.a == "dsave"))
async def deal_save(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    split = data["split"]
    listing = await db.get_listing(data["listing_id"])
    deal = await db.create_deal(
        listing_id=listing["id"], lead_id=data.get("lead_id"), final_price=data["price"],
        model=listing.get("model") or 0, total_percent=str(split["total_pct"]),
        commission=split["commission"], voha_share=split["voha_share"],
        broker_share=split["broker_share"], broker_id=data.get("broker_id"),
        buyer_source=data.get("source"), created_by=call.from_user.id)
    new_status = "sold" if listing["deal_type"] == "s" else "rented"
    listing = await db.update_listing(listing["id"], status=new_status)
    if data.get("lead_id"):
        await db.set_lead_status(data["lead_id"], "won")
    await state.clear()
    await call.answer("✅ Bitim saqlandi")
    await safe_edit(call, f"✅ <b>Bitim #{deal['id']} saqlandi</b> — {listing['code']}\n"
                          f"Komissiya: {fmt_money(deal['commission'])} "
                          f"({'undirilmagan' if deal['status'] == 'unpaid' else 'yopilgan'})")
    await update_channel_post(bot, listing)
    if deal.get("broker_id") and deal["broker_share"]:
        await try_send(bot, deal["broker_id"],
                       f"🎉 <b>{listing['code']}</b> bo‘yicha bitim yopildi!\n"
                       f"Bitim narxi: {fmt_money(deal['final_price'])}\n"
                       f"Sizning ulushingiz: <b>{fmt_money(deal['broker_share'])}</b>\n"
                       "Komissiya undirilgach xabar beramiz.")
    if listing.get("source_type") == "owner" and listing.get("source_user_id"):
        await try_send(bot, listing["source_user_id"],
                       f"🎉 Tabriklaymiz! <b>{listing['code']}</b> — "
                       f"{'sotildi' if new_status == 'sold' else 'ijaraga berildi'}. "
                       "Voha Uylarini tanlaganingiz uchun rahmat!")
    await send_main_menu(bot, call.from_user.id, None, "🏠 Bosh menyu")
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="💰 Undirilmagan komissiyalar", callback_data=Adm(a="unpaid").pack()))
    await bot.send_message(call.from_user.id, "Komissiya tushganda «✅ Undirildi» deb belgilang.",
                           reply_markup=b.as_markup())
