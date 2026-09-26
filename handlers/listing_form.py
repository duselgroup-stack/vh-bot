"""Obyekt qo‘shish formasi: uy egasi, makler va admin (Voha obyekti) uchun umumiy."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from callbacks import Adm, Form
from constants import (
    DEAL_TYPES,
    DISTRICTS,
    MAX_PHOTOS,
    MODELS,
    PROPERTY_ICONS,
    PROPERTY_TYPES,
    TARIFFS_RENT,
    TARIFFS_SALE,
)
from database import db
from filters import TEXT_INPUT, IsAdmin
from keyboards import admin_listing_kb
from services.cards import admin_card, listing_title, price_text
from services.helpers import private_ctx, safe_edit
from services.menus import send_main_menu
from services.notify import notify_admins
from states import ListingForm
from texts import PRIVACY_NOTE, Btn
from utils import esc, fmt_money, fmt_short, normalize_phone, parse_price

router = Router(name="listing_form")

ORDER = ["deal", "tariff", "ptype", "district", "address", "rooms", "area", "floor", "price",
         "description", "media", "owner_name", "owner_phone", "shooting", "confirm"]


def _applicable(step: str, data: dict) -> bool:
    who = data.get("who")
    if step == "deal":
        return not data.get("deal")
    if step == "tariff":
        return who == "owner" and not data.get("tariff")
    if step == "rooms":
        return data.get("ptype") in ("h", "a")
    if step == "floor":
        return data.get("ptype") == "a"
    if step == "shooting":
        has_media = bool(data.get("photos") or data.get("video"))
        return who != "voha" and data.get("shooting") is None and has_media
    return True


def preview_text(data: dict) -> str:
    fake = {
        "property_type": data["ptype"], "deal_type": data["deal"], "price": data["price"],
    }
    lines = ["👀 <b>E’lonni tekshiring</b>\n", f"<b>{listing_title(fake)}</b>"]
    place = esc(data["district"])
    if data.get("address"):
        place += f", {esc(data['address'])}"
    lines.append(f"📍 {place}")
    if data.get("rooms"):
        lines.append(f"🚪 Xonalar: {data['rooms']}")
    if data.get("area"):
        lines.append(f"📐 Maydon: {esc(data['area'])}")
    if data.get("floor"):
        lines.append(f"🏢 Qavat: {esc(data['floor'])}")
    lines.append(f"💰 Narx: <b>{price_text(fake)}</b> ({fmt_short(data['price'])})")
    if data.get("description"):
        lines.append(f"📝 {esc(data['description'][:700])}")
    media = f"{len(data.get('photos') or [])} ta rasm" + (", 1 ta video" if data.get("video") else "")
    lines.append(f"🖼 Media: {media if (data.get('photos') or data.get('video')) else 'yo‘q'}")
    who = data.get("who")
    if who == "owner":
        tariffs = TARIFFS_SALE if data["deal"] == "s" else TARIFFS_RENT
        lines.append(f"💼 Tarif: {tariffs[data['tariff']]['title']}")
    elif who == "broker":
        lines.append(f"💼 Hamkorlik: {MODELS[2]['name']} ({MODELS[2]['short']})")
    else:
        lines.append(f"💼 {MODELS[1]['name']} ({MODELS[1]['short']})")
    owner = " ".join(x for x in [esc(data.get("owner_name") or ""), esc(data.get("owner_phone") or "")] if x)
    if owner:
        lines.append(f"👤 Aloqa: {owner}" + (" <i>(faqat admin ko‘radi)</i>" if who != "owner" else ""))
    shooting = data.get("shooting")
    if shooting is None:
        shooting = not (data.get("photos") or data.get("video"))
    lines.append(f"🎬 Professional syomka: {'kerak' if shooting else 'kerak emas'}")
    lines.append("")
    lines.append(PRIVACY_NOTE)
    return "\n".join(lines)


async def ask(step: str, bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(getattr(ListingForm, step))
    who = data.get("who")
    send = bot.send_message
    if step == "deal":
        await send(chat_id, "🎯 Obyektni nima maqsadda joylaysiz?", reply_markup=kb.deal_type_kb())
    elif step == "tariff":
        await send(chat_id, "💼 Xizmat turini (tarif) tanlang.\n"
                            "<i>Batafsil: «💰 Tariflar» bo‘limida.</i>",
                   reply_markup=kb.tariffs_kb(data["deal"]))
    elif step == "ptype":
        await send(chat_id, "🏠 Mulk turini tanlang:",
                   reply_markup=kb.ptypes_kb(lambda k: Form(f="ptype", v=k)))
    elif step == "district":
        await send(chat_id, "📍 Hududni tanlang:",
                   reply_markup=kb.districts_kb(lambda i: Form(f="district", v=str(i))))
    elif step == "address":
        await send(chat_id, "🗺 Manzil yoki mo‘ljalni yozing:\n"
                            "<i>Masalan: Mustaqillik ko‘chasi, 5-maktab yonida</i>",
                   reply_markup=kb.cancel_kb())
    elif step == "rooms":
        await send(chat_id, "🚪 Xonalar sonini tanlang:",
                   reply_markup=kb.rooms_kb(lambda n: Form(f="rooms", v=str(n))))
    elif step == "area":
        await send(chat_id, "📐 Maydonini yozing:\n<i>Masalan: 6 sotix yoki 85 m²</i>",
                   reply_markup=kb.cancel_kb(Btn.SKIP))
    elif step == "floor":
        await send(chat_id, "🏢 Qavatini yozing:\n<i>Masalan: 3/9 (3-qavat, 9 qavatli bino)</i>",
                   reply_markup=kb.cancel_kb(Btn.SKIP))
    elif step == "price":
        if data["deal"] == "r":
            text = "💰 Oylik ijara narxini so‘mda yozing:\n<i>Masalan: 4 mln yoki 4000000</i>"
        else:
            text = "💰 Sotuv narxini so‘mda yozing:\n<i>Masalan: 650 mln, 1,2 mlrd yoki 650000000</i>"
        await send(chat_id, text, reply_markup=kb.cancel_kb())
    elif step == "description":
        await send(chat_id, "📝 Qisqacha tavsif yozing: ta’mir holati, hujjatlar, kommunikatsiyalar "
                            "(gaz, suv, svet), afzalliklar…",
                   reply_markup=kb.cancel_kb(Btn.SKIP))
    elif step == "media":
        await send(chat_id, f"📸 Obyekt rasmlarini ({MAX_PHOTOS} tagacha) va/yoki 1 ta video yuboring.\n"
                            f"Tugatgach «{Btn.DONE}» ni bosing.\n\n"
                            f"Rasm yo‘qmi? «{Btn.SKIP}» ni bosing — jamoamiz professional syomka qiladi.",
                   reply_markup=kb.media_kb())
    elif step == "owner_name":
        if who == "owner":
            user = await db.get_user(chat_id)
            name = (user or {}).get("full_name") or ""
            await send(chat_id, "👤 Ismingizni yozing:",
                       reply_markup=kb.cancel_kb(name[:60]) if name else kb.cancel_kb())
        else:
            await send(chat_id, "👤 Mulk egasining ismi <i>(faqat admin ko‘radi)</i>:",
                       reply_markup=kb.cancel_kb(Btn.SKIP))
    elif step == "owner_phone":
        if who == "owner":
            user = await db.get_user(chat_id)
            await send(chat_id, "📱 Telefon raqamingizni yuboring (tugma orqali yoki yozib):\n"
                                f"<i>{PRIVACY_NOTE}</i>",
                       reply_markup=kb.phone_kb((user or {}).get("phone")))
        else:
            await send(chat_id, "📱 Mulk egasining telefon raqami <i>(faqat admin ko‘radi)</i>:",
                       reply_markup=kb.cancel_kb(Btn.SKIP))
    elif step == "shooting":
        await send(chat_id, "🎬 Obyekt uchun professional syomka (video, montaj) kerakmi?",
                   reply_markup=kb.yes_no_kb("shoot", "🎬 Ha, syomka kerak", "✅ Yo‘q, media yetarli"))
    elif step == "confirm":
        await send(chat_id, "Deyarli tayyor! 👇", reply_markup=kb.cancel_kb())
        await send(chat_id, preview_text(data), reply_markup=kb.confirm_listing_kb())


async def next_step(current: str, bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    idx = ORDER.index(current) + 1 if current in ORDER else 0
    for step in ORDER[idx:]:
        if _applicable(step, data):
            await ask(step, bot, chat_id, state)
            return


async def start_form(bot: Bot, chat_id: int, state: FSMContext, who: str,
                     deal: str | None = None, tariff: str | None = None) -> None:
    await state.clear()
    data: dict = {"who": who, "deal": deal, "photos": [], "video": None, "shooting": None}
    if tariff:
        t = TARIFFS_SALE[tariff]
        data.update(tariff=tariff, model=t["model"], shooting=True if t["shooting"] else None)
    await state.update_data(**data)
    titles = {"owner": "📝 <b>Yangi e’lon</b>", "broker": "➕ <b>Yangi obyekt (makler)</b>",
              "voha": "🏢 <b>Yangi Voha obyekti</b>"}
    await bot.send_message(chat_id, f"{titles[who]}\nBir necha savolga javob bering. "
                                    f"Istalgan payt «{Btn.CANCEL}» ni bosishingiz mumkin.",
                           reply_markup=kb.cancel_kb())
    await next_step("", bot, chat_id, state)


# ------------------------------------------------------------------ kirish
@router.message(F.text == Btn.SELL)
async def owner_sell(message: Message, state: FSMContext, bot: Bot) -> None:
    await start_form(bot, message.chat.id, state, "owner", deal="s")


@router.message(F.text == Btn.RENT_OUT)
async def owner_rent(message: Message, state: FSMContext, bot: Bot) -> None:
    await start_form(bot, message.chat.id, state, "owner", deal="r")


@router.message(F.text == Btn.ORDER_AD)
async def owner_order_ad(message: Message, state: FSMContext, bot: Bot) -> None:
    await message.answer(
        "🎬 <b>Professional reklama — 500 000 so‘m</b>\n"
        "Syomka, video montaj va Instagram/Telegramga joylashtirish. Sotuv foizi alohida "
        "kelishilmasa olinmaydi.\n\nObyekt ma’lumotlarini kiriting 👇")
    await start_form(bot, message.chat.id, state, "owner", tariff="ad")


@router.message(F.text == Btn.ADD_OBJECT)
async def broker_add(message: Message, state: FSMContext, bot: Bot, user: dict) -> None:
    broker = await db.get_broker(user["id"])
    if not broker or broker["status"] != "approved":
        await state.clear()
        await message.answer("🤝 Obyekt qo‘shish faqat tasdiqlangan hamkor maklerlar uchun. "
                             f"Avval «{Btn.BROKER_REGISTER}» orqali ariza yuboring.")
        return
    await start_form(bot, message.chat.id, state, "broker")


@router.callback_query(Adm.filter(F.a == "new"), IsAdmin())
async def admin_new(call: CallbackQuery, bot: Bot, fsm_storage: BaseStorage) -> None:
    await call.answer()
    ctx = private_ctx(bot, fsm_storage, call.from_user.id)
    await start_form(bot, call.from_user.id, ctx, "voha")


# ------------------------------------------------------------ tanlovlar
@router.callback_query(ListingForm.deal, Form.filter(F.f == "deal"))
async def pick_deal(call: CallbackQuery, callback_data: Form, state: FSMContext, bot: Bot) -> None:
    if callback_data.v not in DEAL_TYPES:
        await call.answer()
        return
    data = await state.get_data()
    await state.update_data(deal=callback_data.v)
    if data.get("tariff") and callback_data.v == "r":
        await state.update_data(tariff="ad")  # reklama tarifi ijara uchun ham bor
    await call.answer()
    await safe_edit(call, f"🎯 Maqsad: <b>{DEAL_TYPES[callback_data.v]}</b>")
    await next_step("deal", bot, call.from_user.id, state)


@router.callback_query(ListingForm.tariff, Form.filter(F.f == "tariff"))
async def pick_tariff(call: CallbackQuery, callback_data: Form, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    tariffs = TARIFFS_SALE if data.get("deal") == "s" else TARIFFS_RENT
    tariff = tariffs.get(callback_data.v)
    if not tariff:
        await call.answer()
        return
    await state.update_data(tariff=callback_data.v, model=tariff["model"],
                            shooting=True if tariff["shooting"] else None)
    await call.answer()
    await safe_edit(call, f"💼 Tarif: <b>{tariff['title']}</b>")
    await next_step("tariff", bot, call.from_user.id, state)


@router.callback_query(ListingForm.ptype, Form.filter(F.f == "ptype"))
async def pick_ptype(call: CallbackQuery, callback_data: Form, state: FSMContext, bot: Bot) -> None:
    if callback_data.v not in PROPERTY_TYPES:
        await call.answer()
        return
    await state.update_data(ptype=callback_data.v)
    await call.answer()
    await safe_edit(call, f"🏠 Mulk turi: <b>{PROPERTY_ICONS[callback_data.v]} {PROPERTY_TYPES[callback_data.v]}</b>")
    await next_step("ptype", bot, call.from_user.id, state)


@router.callback_query(ListingForm.district, Form.filter(F.f == "district"))
async def pick_district(call: CallbackQuery, callback_data: Form, state: FSMContext, bot: Bot) -> None:
    try:
        district = DISTRICTS[int(callback_data.v)]
    except (ValueError, IndexError):
        await call.answer()
        return
    await state.update_data(district=district)
    await call.answer()
    await safe_edit(call, f"📍 Hudud: <b>{district}</b>")
    await next_step("district", bot, call.from_user.id, state)


@router.callback_query(ListingForm.rooms, Form.filter(F.f == "rooms"))
async def pick_rooms(call: CallbackQuery, callback_data: Form, state: FSMContext, bot: Bot) -> None:
    rooms = int(callback_data.v) if callback_data.v.isdigit() else 0
    await state.update_data(rooms=rooms or None)
    await call.answer()
    await safe_edit(call, f"🚪 Xonalar: <b>{rooms}{'+' if rooms >= 5 else ''}</b>")
    await next_step("rooms", bot, call.from_user.id, state)


@router.callback_query(ListingForm.shooting, Form.filter(F.f == "shoot"))
async def pick_shooting(call: CallbackQuery, callback_data: Form, state: FSMContext, bot: Bot) -> None:
    shooting = callback_data.v == "1"
    await state.update_data(shooting=shooting)
    await call.answer()
    await safe_edit(call, f"🎬 Syomka: <b>{'kerak' if shooting else 'kerak emas'}</b>")
    await next_step("shooting", bot, call.from_user.id, state)


# ---------------------------------------------------------- matnli javoblar
@router.message(ListingForm.address, TEXT_INPUT)
async def got_address(message: Message, state: FSMContext, bot: Bot) -> None:
    text = message.text.strip()
    if not 3 <= len(text) <= 200:
        await message.answer("✍️ Manzilni 3–200 belgi oralig‘ida yozing.")
        return
    await state.update_data(address=text)
    await next_step("address", bot, message.chat.id, state)


@router.message(ListingForm.area, F.text == Btn.SKIP)
@router.message(ListingForm.area, TEXT_INPUT)
async def got_area(message: Message, state: FSMContext, bot: Bot) -> None:
    value = None if message.text == Btn.SKIP else message.text.strip()[:60]
    await state.update_data(area=value)
    await next_step("area", bot, message.chat.id, state)


@router.message(ListingForm.floor, F.text == Btn.SKIP)
@router.message(ListingForm.floor, TEXT_INPUT)
async def got_floor(message: Message, state: FSMContext, bot: Bot) -> None:
    value = None if message.text == Btn.SKIP else message.text.strip()[:20]
    await state.update_data(floor=value)
    await next_step("floor", bot, message.chat.id, state)


@router.message(ListingForm.price, TEXT_INPUT)
async def got_price(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    price = parse_price(message.text)
    minimum = 100_000 if data.get("deal") == "r" else 1_000_000
    if not price or price < minimum:
        await message.answer("❗️ Narxni tushunmadim. Masalan: <code>650 mln</code>, "
                             "<code>1,2 mlrd</code> yoki <code>650000000</code>.")
        return
    await state.update_data(price=price)
    await message.answer(f"💰 Narx: <b>{fmt_money(price)}</b> ({fmt_short(price)})")
    await next_step("price", bot, message.chat.id, state)


@router.message(ListingForm.description, F.text == Btn.SKIP)
@router.message(ListingForm.description, TEXT_INPUT)
async def got_description(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text == Btn.SKIP:
        value = None
    else:
        value = message.text.strip()
        if len(value) > 1500:
            await message.answer("✂️ Tavsif juda uzun — 1500 belgigacha qisqartiring.")
            return
    await state.update_data(description=value)
    await next_step("description", bot, message.chat.id, state)


@router.message(ListingForm.media, F.photo | F.video)
async def got_media(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    photos = list(data.get("photos") or [])
    video = data.get("video")
    if message.photo:
        if len(photos) < MAX_PHOTOS:
            photos.append(message.photo[-1].file_id)
    elif message.video:
        video = message.video.file_id
    await state.update_data(photos=photos, video=video)
    text = (f"📸 Rasmlar: <b>{len(photos)}/{MAX_PHOTOS}</b>   🎥 Video: <b>{'bor' if video else '—'}</b>\n"
            f"Yana yuboring yoki «{Btn.DONE}» ni bosing.")
    msg_id = data.get("media_msg")
    if msg_id:
        try:
            await bot.edit_message_text(text, chat_id=message.chat.id, message_id=msg_id)
            return
        except TelegramBadRequest as exc:
            if "not modified" in str(exc):
                return
    sent = await message.answer(text)
    await state.update_data(media_msg=sent.message_id)


@router.message(ListingForm.media, F.text.in_({Btn.DONE, Btn.SKIP}))
async def media_done(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    has_media = bool(data.get("photos") or data.get("video"))
    if message.text == Btn.DONE and not has_media:
        await message.answer(f"Hali rasm yubormadingiz. Rasm yuboring yoki «{Btn.SKIP}» ni bosing.")
        return
    if message.text == Btn.SKIP:
        await state.update_data(photos=[], video=None)
        if data.get("who") != "voha":
            await state.update_data(shooting=True)
    await state.update_data(media_msg=None)
    await next_step("media", bot, message.chat.id, state)


@router.message(ListingForm.owner_name, F.text == Btn.SKIP)
@router.message(ListingForm.owner_name, TEXT_INPUT)
async def got_owner_name(message: Message, state: FSMContext, bot: Bot) -> None:
    value = None if message.text == Btn.SKIP else message.text.strip()[:80]
    await state.update_data(owner_name=value)
    await next_step("owner_name", bot, message.chat.id, state)


@router.message(ListingForm.owner_phone, F.contact)
async def got_owner_contact(message: Message, state: FSMContext, bot: Bot) -> None:
    phone = normalize_phone(message.contact.phone_number) or message.contact.phone_number
    await state.update_data(owner_phone=phone)
    await message.answer(f"📱 Raqam: <b>{esc(phone)}</b>", reply_markup=kb.cancel_kb())
    await next_step("owner_phone", bot, message.chat.id, state)


@router.message(ListingForm.owner_phone, F.text == Btn.SKIP)
@router.message(ListingForm.owner_phone, TEXT_INPUT)
async def got_owner_phone(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    if message.text == Btn.SKIP:
        if data.get("who") == "owner":
            await message.answer("📱 Telefon raqam majburiy — menejer siz bilan bog‘lanishi kerak.")
            return
        phone = None
    else:
        phone = normalize_phone(message.text)
        if not phone:
            await message.answer("❗️ Raqam noto‘g‘ri. Masalan: <code>+998 90 123 45 67</code>")
            return
    await state.update_data(owner_phone=phone)
    await message.answer("✅ Qabul qilindi.", reply_markup=kb.cancel_kb())
    await next_step("owner_phone", bot, message.chat.id, state)


# ------------------------------------------------------------- tasdiqlash
@router.callback_query(ListingForm.confirm, Form.filter(F.f == "confirm"))
async def confirm(call: CallbackQuery, callback_data: Form, state: FSMContext, bot: Bot,
                  user: dict) -> None:
    data = await state.get_data()
    await call.answer()
    if callback_data.v == "no":
        await state.clear()
        await safe_edit(call, "❌ E’lon bekor qilindi.")
        await send_main_menu(bot, call.from_user.id, None)
        return
    if callback_data.v == "restart":
        await safe_edit(call, "🔁 Qaytadan to‘ldiramiz.")
        tariff = data.get("tariff") if data.get("tariff") == "ad" and data.get("who") == "owner" else None
        await start_form(bot, call.from_user.id, state, data["who"], deal=data.get("deal"), tariff=tariff)
        return

    who = data["who"]
    photos = data.get("photos") or []
    video = data.get("video")
    shooting = data.get("shooting")
    if shooting is None:
        shooting = not (photos or video)
    model = data.get("model", 1) if who == "owner" else (2 if who == "broker" else 1)
    m = MODELS[model]
    listing = await db.create_listing(
        deal_type=data["deal"], property_type=data["ptype"], district=data["district"],
        address=data.get("address"), rooms=data.get("rooms"), area=data.get("area"),
        floor=data.get("floor"), price=data["price"], description=data.get("description"),
        photos=photos, video=video, owner_name=data.get("owner_name"),
        owner_phone=data.get("owner_phone"), source_type=who, source_user_id=user["id"],
        broker_id=user["id"] if who == "broker" else None, model=model,
        commission_percent=str(m["total"]), ad_fee=m["ad_fee"], status="pending",
        shooting_requested=1 if shooting else 0,
    )
    if who == "owner" and data.get("owner_phone"):
        await db.set_user_phone(user["id"], data["owner_phone"])
    await state.clear()
    await safe_edit(call, f"✅ Yuborildi: <b>{listing['code']}</b>")

    card = await admin_card(listing)
    if who == "voha":
        await bot.send_message(call.from_user.id, "🏢 Voha obyekti yaratildi. E’lon qilish uchun "
                                                  "«✅ Tasdiqlash» ni bosing.\n\n" + card,
                               reply_markup=admin_listing_kb(listing))
        await send_main_menu(bot, call.from_user.id, None, "🏠 Bosh menyu")
        return

    await notify_admins(bot, "🆕 <b>Yangi obyekt moderatsiyaga</b>\n\n" + card,
                        reply_markup=admin_listing_kb(listing))
    lines = [f"✅ <b>E’loningiz qabul qilindi!</b>\n🆔 ID: <code>{listing['code']}</code>\n",
             "Moderator tekshirgach e’lon qilinadi va sizga xabar beramiz."]
    if shooting:
        lines.append("🎬 Syomka vaqtini kelishish uchun menejer siz bilan bog‘lanadi.")
    if m["ad_fee"] and who == "owner":
        lines.append(f"💳 Reklama to‘lovi: {fmt_money(m['ad_fee'])} — to‘lov tartibini menejer tushuntiradi.")
    menu_name = Btn.MY_LISTINGS if who == "owner" else Btn.MY_OBJECTS
    lines.append(f"\nHolatini «{menu_name}» bo‘limida kuzatishingiz mumkin.")
    await send_main_menu(bot, call.from_user.id, None, "\n".join(lines))
