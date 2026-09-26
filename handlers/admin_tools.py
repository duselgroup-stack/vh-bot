"""Admin: maklerlar, statistika (KPI), Excel eksport, xabar tarqatish, komissiyalar."""
from __future__ import annotations

import asyncio
import io
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import keyboards as kb
from callbacks import Adm
from constants import (
    BROKER_STATUSES,
    DEAL_TYPES,
    LEAD_STATUSES,
    LISTING_STATUSES,
    MODELS,
    OBJECT_SOURCES,
    PROPERTY_TYPES,
    ROLES,
    SOURCES,
    VIEWING_TIMES,
)
from database import db
from filters import IsAdmin
from services.backup import send_backup
from services.helpers import private_ctx, safe_edit, try_send, user_link
from services.menus import send_main_menu
from states import AdminInput
from texts import MENU_TEXTS
from utils import esc, fmt_money, now, short_dt

log = logging.getLogger(__name__)

router = Router(name="admin_tools")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# --------------------------------------------------------------- maklerlar
@router.callback_query(Adm.filter(F.a == "brokers"))
async def brokers_list(call: CallbackQuery, callback_data: Adm) -> None:
    status = callback_data.v or "pending"
    brokers = await db.list_brokers(status)
    await call.answer()
    b = InlineKeyboardBuilder()
    for br in brokers[:40]:
        b.row(InlineKeyboardButton(text=f"{br['full_name']} · {br['district']}",
                                   callback_data=Adm(a="broker", id=br["user_id"]).pack()))
    b.row(*[InlineKeyboardButton(text=("• " if key == status else "") + label.split(" ", 1)[1],
                                 callback_data=Adm(a="brokers", v=key).pack())
            for key, label in BROKER_STATUSES.items()])
    b.row(InlineKeyboardButton(text="🛠 Panel", callback_data=Adm(a="panel").pack()))
    await safe_edit(call, f"🤝 <b>Maklerlar — {BROKER_STATUSES[status]}</b>: {len(brokers)} ta", b.as_markup())


async def broker_card_text(user_id: int) -> str | None:
    br = await db.get_broker(user_id)
    if not br:
        return None
    user = await db.get_user(user_id)
    stats = await db.broker_stats(user_id)
    return (
        f"🤝 <b>{esc(br['full_name'])}</b>\n"
        f"Holat: {BROKER_STATUSES.get(br['status'], br['status'])}\n"
        f"👤 {user_link(user_id, (user or {}).get('full_name'), (user or {}).get('username'))}\n"
        f"📱 {esc(br['phone'])}\n📍 {esc(br['district'])}\n🧭 Tajriba: {esc(br['experience'])}\n"
        f"🗓 Ariza: {short_dt(br['created_at'])}\n\n"
        f"🏠 Obyektlar: {sum(stats['listings'].values())} · 🙋 Mijozlar: {stats['clients']} · "
        f"🤝 Bitimlar: {stats['deals']}\n"
        f"💰 Ulush: {fmt_money(stats['earned_paid'])} (+{fmt_money(stats['earned_unpaid'])} kutilmoqda)"
    )


def broker_card_kb(user_id: int, status: str):
    b = InlineKeyboardBuilder()
    if status != "approved":
        b.button(text="✅ Tasdiqlash", callback_data=Adm(a="bset", id=user_id, v="approved"))
    if status == "pending":
        b.button(text="❌ Rad etish", callback_data=Adm(a="bset", id=user_id, v="rejected"))
    if status != "blocked":
        b.button(text="⛔ Bloklash", callback_data=Adm(a="bset", id=user_id, v="blocked"))
    b.button(text="💬 Yozish", callback_data=Adm(a="reply", id=user_id))
    b.button(text="⬅️ Ro‘yxat", callback_data=Adm(a="brokers", v=status))
    b.adjust(2)
    return b.as_markup()


@router.callback_query(Adm.filter(F.a == "broker"))
async def broker_card(call: CallbackQuery, callback_data: Adm) -> None:
    text = await broker_card_text(callback_data.id)
    if not text:
        await call.answer("Topilmadi", show_alert=True)
        return
    br = await db.get_broker(callback_data.id)
    await call.answer()
    await safe_edit(call, text, broker_card_kb(callback_data.id, br["status"]))


@router.callback_query(Adm.filter(F.a == "bset"))
async def broker_set(call: CallbackQuery, callback_data: Adm, bot: Bot) -> None:
    br = await db.get_broker(callback_data.id)
    if not br or callback_data.v not in BROKER_STATUSES:
        await call.answer("Topilmadi", show_alert=True)
        return
    await db.set_broker_status(callback_data.id, callback_data.v)
    await call.answer(BROKER_STATUSES[callback_data.v])
    await safe_edit(call, await broker_card_text(callback_data.id), broker_card_kb(callback_data.id, callback_data.v))
    user = await db.get_user(callback_data.id)
    if callback_data.v == "approved":
        if user and user.get("role") != "broker":
            await db.set_user_role(callback_data.id, "broker")
        await send_main_menu(
            bot, callback_data.id, None,
            "🎉 <b>Tabriklaymiz! Siz Voha Uylari hamkor maklerisiz.</b>\n\n"
            "Endi obyekt qo‘shishingiz, obyektlar bazasidan mijozingizga uy tanlashingiz va "
            "murojaatlarni kuzatishingiz mumkin. Birga ishlaymiz — birga o‘samiz! 🤝")
    elif callback_data.v == "rejected":
        await try_send(bot, callback_data.id, "😕 Hamkorlik arizangiz hozircha qabul qilinmadi. "
                                              "Savollar bo‘lsa, «☎️ Aloqa» bo‘limi orqali bog‘laning.")
    elif callback_data.v == "blocked":
        await try_send(bot, callback_data.id, "⛔ Hamkorlik hisobingiz to‘xtatildi.")


# --------------------------------------------------------------- statistika
@router.callback_query(Adm.filter(F.a == "stats"))
async def stats(call: CallbackQuery, callback_data: Adm) -> None:
    days = int(callback_data.v) if callback_data.v.isdigit() else 30
    s = await db.stats(days)
    await call.answer()
    listings = s["listings"]
    roles = ", ".join(f"{ROLES.get(k, 'rol tanlamagan') if k else 'rol tanlamagan'}: {v}" for k, v in s["roles"].items())
    sources = ", ".join(f"{SOURCES.get(k, k)}: {v}" for k, v in s["lead_sources"].items()) or "—"
    lines = [
        f"📊 <b>Statistika</b> (davr: oxirgi {days} kun)\n",
        f"👥 Foydalanuvchilar: <b>{s['users']}</b> (+{s['users_new']})",
        f"   {roles}",
        "",
        "<b>1. Faol hamkor maklerlar</b>",
        f"   Davr ichida obyekt/mijoz olib kelgan: <b>{s['brokers_active']}</b> "
        f"(tasdiqlangan: {s['brokers_approved']}, arizalar: {s['brokers_pending']})",
        "<b>2. Faol va yangi obyektlar</b>",
        f"   Faol: <b>{listings.get('active', 0)}</b> · muzokarada: {listings.get('negotiation', 0)} · "
        f"yangi: {s['listings_new']}",
        f"   Moderatsiya: {listings.get('pending', 0)} · syomka: {listings.get('shooting', 0)}",
        "<b>3. Malakali murojaatlar</b>",
        f"   Jami: {s['leads_total']} · davrda: {s['leads_new']} · malakali: <b>{s['leads_qualified']}</b>",
        f"   Manbalar: {sources}",
        "<b>4. Yakunlangan savdolar</b>",
        f"   Bitimlar: <b>{s['deals']}</b> (davrda: {s['deals_period']}) · sotilgan: {listings.get('sold', 0)} · "
        f"ijaraga: {listings.get('rented', 0)}",
        "<b>5. Komissiyalar</b>",
        f"   Hisoblangan: {fmt_money(s['commission_total'])}",
        f"   Undirilgan: <b>{fmt_money(s['commission_paid'])}</b> (Voha: {fmt_money(s['voha_paid'])}, "
        f"maklerlar: {fmt_money(s['broker_paid'])})",
        f"   Undirilmagan: {fmt_money(s['commission_unpaid'])}",
        f"   Reklama to‘lovlari: {fmt_money(s['ad_fees'])}",
        "<b>6. Obyekt foydaliligi</b>",
        f"   Jami xarajat (syomka va b.): {fmt_money(s['expenses'])}",
    ]
    for row in s["profit_listings"]:
        profit = (row["income"] or 0) + (row["ad_fee"] or 0) - (row["expenses"] or 0)
        lines.append(f"   {row['code']}: tushum {fmt_money((row['income'] or 0) + (row['ad_fee'] or 0))} − "
                     f"xarajat {fmt_money(row['expenses'])} = <b>{fmt_money(profit)}</b>")
    if s["top_listings"]:
        lines.append("\n🔥 <b>Eng ko‘p qiziqish</b>")
        for row in s["top_listings"]:
            lines.append(f"   {row['code']}: 📩 {row['leads']} · 👁 {row['views']}")
    b = InlineKeyboardBuilder()
    for d in (7, 30, 90, 365):
        b.button(text=("• " if d == days else "") + f"{d} kun", callback_data=Adm(a="stats", v=str(d)))
    b.button(text="🛠 Panel", callback_data=Adm(a="panel"))
    b.adjust(4, 1)
    await safe_edit(call, "\n".join(lines), b.as_markup())


# ------------------------------------------------------------------ Excel
def _label(mapping: dict, value) -> str:
    return mapping.get(value, value) if value is not None else ""


async def build_excel() -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    sheets = [
        ("Obyektlar", "listings", {
            "code": "ID", "deal_type": ("Bitim", DEAL_TYPES), "property_type": ("Tur", PROPERTY_TYPES),
            "district": "Hudud", "address": "Manzil", "rooms": "Xona", "area": "Maydon", "floor": "Qavat",
            "price": "Narx", "status": ("Holat", LISTING_STATUSES), "source_type": ("Manba", OBJECT_SOURCES),
            "source_user_id": "Manba user ID", "broker_id": "Makler ID", "model": "Model",
            "commission_percent": "Foiz", "ad_fee": "Reklama to‘lovi", "ad_fee_paid": "To‘langan",
            "expenses": "Xarajat", "owner_name": "Egasi", "owner_phone": "Egasi tel.", "views": "Ko‘rishlar",
            "created_at": "Qo‘shilgan", "published_at": "E’lon qilingan",
        }),
        ("Murojaatlar", "leads", {
            "id": "№", "listing_id": "Obyekt ID", "buyer_name": "Mijoz", "buyer_phone": "Telefon",
            "source": ("Manba", SOURCES), "brought_by": "Makler ID", "preferred_time": ("Qulay vaqt", VIEWING_TIMES),
            "comment": "Izoh", "status": ("Holat", LEAD_STATUSES), "created_at": "Sana",
        }),
        ("Bitimlar", "deals", {
            "id": "№", "listing_id": "Obyekt ID", "lead_id": "Murojaat", "final_price": "Narx",
            "model": "Model", "total_percent": "Foiz", "commission": "Komissiya", "voha_share": "Voha ulushi",
            "broker_share": "Makler ulushi", "broker_id": "Makler ID", "buyer_source": ("Manba", SOURCES),
            "status": "Holat", "created_at": "Sana", "paid_at": "Undirilgan",
        }),
        ("Maklerlar", "brokers", {
            "user_id": "Telegram ID", "full_name": "F.I.Sh", "phone": "Telefon", "district": "Hudud",
            "experience": "Tajriba", "status": ("Holat", BROKER_STATUSES), "created_at": "Ariza",
            "approved_at": "Tasdiqlangan",
        }),
        ("Foydalanuvchilar", "users", {
            "id": "Telegram ID", "full_name": "Ism", "username": "Username", "phone": "Telefon",
            "role": ("Rol", ROLES), "source": "Manba", "consent_at": "Rozilik", "created_at": "Qo‘shilgan",
            "last_seen": "Oxirgi faollik",
        }),
    ]
    listing_codes = {row["id"]: row["code"] for row in await db.table("listings")}
    header_fill = PatternFill("solid", fgColor="1F4E3D")
    first = True
    for title, table, columns in sheets:
        ws = wb.active if first else wb.create_sheet()
        first = False
        ws.title = title
        ws.append([c if isinstance(c, str) else c[0] for c in columns.values()])
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for row in await db.table(table):
            values = []
            for key, spec in columns.items():
                value = row.get(key)
                if isinstance(spec, tuple):
                    value = _label(spec[1], value)
                if key == "listing_id":
                    value = listing_codes.get(value, value)
                if key == "model" and value is not None:
                    value = MODELS.get(value, {}).get("name", value)
                values.append(value)
            ws.append(values)
        for idx, _ in enumerate(columns, 1):
            ws.column_dimensions[get_column_letter(idx)].width = 18
        ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@router.callback_query(Adm.filter(F.a == "export"))
async def export(call: CallbackQuery, bot: Bot) -> None:
    await call.answer("⏳ Tayyorlanmoqda…")
    data = await build_excel()
    name = f"voha_uylari_{now().strftime('%Y%m%d_%H%M')}.xlsx"
    try:
        await bot.send_document(call.from_user.id, BufferedInputFile(data, filename=name),
                                caption="📤 Barcha ma’lumotlar: obyektlar, murojaatlar, bitimlar, maklerlar, foydalanuvchilar")
    except (TelegramForbiddenError, TelegramBadRequest):
        await call.answer("Avval bot bilan shaxsiy chatda /start bosing.", show_alert=True)


@router.callback_query(Adm.filter(F.a == "backup"))
async def backup(call: CallbackQuery, bot: Bot) -> None:
    await call.answer("⏳ Tayyorlanmoqda…")
    if not await send_backup(bot, call.from_user.id):
        await bot.send_message(call.from_user.id, "⚠️ Zaxira nusxa yuborilmadi. Avval botga shaxsiy chatda /start bosing.")


# ---------------------------------------------------------- komissiyalar
@router.callback_query(Adm.filter(F.a == "unpaid"))
async def unpaid(call: CallbackQuery) -> None:
    deals = await db.unpaid_deals()
    await call.answer()
    b = InlineKeyboardBuilder()
    lines = ["💰 <b>Undirilmagan komissiyalar</b>\n"]
    total = 0
    for deal in deals:
        total += deal["commission"]
        broker = await db.get_broker(deal["broker_id"]) if deal.get("broker_id") else None
        lines.append(f"#{deal['id']} · {deal['code']} · {fmt_money(deal['commission'])} "
                     f"(Voha {fmt_money(deal['voha_share'])}"
                     + (f", {esc(broker['full_name'])} {fmt_money(deal['broker_share'])}" if broker else "")
                     + f") · {short_dt(deal['created_at'])}")
        b.button(text=f"✅ #{deal['id']} undirildi", callback_data=Adm(a="paid", id=deal["id"]))
    b.adjust(2)
    b.row(InlineKeyboardButton(text="🛠 Panel", callback_data=Adm(a="panel").pack()))
    if deals:
        lines.append(f"\nJami: <b>{fmt_money(total)}</b>")
    else:
        lines.append("Hammasi undirilgan ✨")
    await safe_edit(call, "\n".join(lines), b.as_markup())


@router.callback_query(Adm.filter(F.a == "paid"))
async def mark_paid(call: CallbackQuery, callback_data: Adm, bot: Bot) -> None:
    deal = await db.get_deal(callback_data.id)
    if not deal or deal["status"] == "paid":
        await call.answer("Allaqachon belgilangan")
        return
    await db.mark_deal_paid(deal["id"])
    await call.answer("✅ Undirildi")
    if deal.get("broker_id") and deal["broker_share"]:
        await try_send(bot, deal["broker_id"],
                       f"💰 <b>{deal['code']}</b> bo‘yicha komissiya undirildi.\n"
                       f"Sizning ulushingiz: <b>{fmt_money(deal['broker_share'])}</b> — hisob-kitob uchun "
                       "admin bog‘lanadi.")
    await unpaid(call)


# -------------------------------------------------------- xabar tarqatish
AUDIENCES = {"all": "👥 Hammaga", "buyer": "🔎 Xaridorlar", "owner": "🏡 Uy egalari", "broker": "🤝 Maklerlar"}


@router.callback_query(Adm.filter(F.a == "bc"))
async def bc_start(call: CallbackQuery) -> None:
    await call.answer()
    b = InlineKeyboardBuilder()
    for key, label in AUDIENCES.items():
        b.button(text=label, callback_data=Adm(a="bca", v=key))
    b.button(text="🛠 Panel", callback_data=Adm(a="panel"))
    b.adjust(2)
    await safe_edit(call, "📢 <b>Xabar tarqatish</b>\nKimga yuboramiz?", b.as_markup())


@router.callback_query(Adm.filter(F.a == "bca"))
async def bc_audience(call: CallbackQuery, callback_data: Adm, bot: Bot, fsm_storage: BaseStorage) -> None:
    ctx = private_ctx(bot, fsm_storage, call.from_user.id)
    try:
        await bot.send_message(call.from_user.id,
                               f"📢 Auditoriya: <b>{AUDIENCES.get(callback_data.v)}</b>\n"
                               "Yuboriladigan xabarni jo‘nating (matn, rasm, video — istalgan format):",
                               reply_markup=kb.cancel_kb())
    except (TelegramForbiddenError, TelegramBadRequest):
        await call.answer("Avval bot bilan shaxsiy chatda /start bosing.", show_alert=True)
        return
    await ctx.clear()
    await ctx.set_state(AdminInput.broadcast)
    await ctx.update_data(audience=callback_data.v)
    await call.answer()


@router.message(AdminInput.broadcast, ~F.text.in_(MENU_TEXTS))
async def bc_message(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    role = None if data["audience"] == "all" else data["audience"]
    count = len(await db.user_ids(role))
    await state.update_data(src_chat=message.chat.id, src_msg=message.message_id)
    await state.set_state(AdminInput.broadcast_confirm)
    b = InlineKeyboardBuilder()
    b.button(text=f"✅ Yuborish ({count} kishi)", callback_data=Adm(a="bcgo"))
    b.button(text="❌ Bekor qilish", callback_data="nav:main")
    b.adjust(1)
    await message.answer("👆 Xabar shunday ko‘rinadi. Yuboramizmi?", reply_markup=b.as_markup())


@router.callback_query(AdminInput.broadcast_confirm, Adm.filter(F.a == "bcgo"))
async def bc_go(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()
    role = None if data["audience"] == "all" else data["audience"]
    user_ids = await db.user_ids(role)
    await call.answer("📤 Yuborilmoqda…")
    await safe_edit(call, f"📤 Yuborilmoqda: {len(user_ids)} kishi…")
    ok = fail = 0
    for uid in user_ids:
        try:
            await bot.copy_message(uid, data["src_chat"], data["src_msg"])
            ok += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 1)
            try:
                await bot.copy_message(uid, data["src_chat"], data["src_msg"])
                ok += 1
            except Exception:  # noqa: BLE001
                fail += 1
        except TelegramForbiddenError:
            await db.set_user_blocked(uid, True)
            fail += 1
        except TelegramBadRequest:
            fail += 1
        await asyncio.sleep(0.05)
    await send_main_menu(bot, call.from_user.id, None,
                         f"✅ Tarqatish tugadi.\nYetkazildi: <b>{ok}</b> · yetkazilmadi: {fail}")


# ------------------------------------------------ foydalanuvchi savollari
def question_kb(user_id: int):
    b = InlineKeyboardBuilder()
    b.button(text="↩️ Javob berish", callback_data=Adm(a="reply", id=user_id))
    return b.as_markup()


