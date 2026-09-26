"""Klaviaturalar (reply va inline)."""
from __future__ import annotations

from typing import Callable

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from callbacks import Adm, Brk, Form, Ld, Lst, Nav, Srch
from constants import (
    CLOSED_STATUSES,
    DEAL_TYPES,
    DISTRICTS,
    LEAD_STATUSES,
    PRICE_RANGES,
    PROPERTY_ICONS,
    PROPERTY_TYPES,
    ROOM_CHOICES,
    TARIFFS_RENT,
    TARIFFS_SALE,
    VIEWING_TIMES,
)
from texts import Btn


# ------------------------------------------------------------------ reply
def _reply(rows: list[list[str]], placeholder: str | None = None) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
        resize_keyboard=True,
        input_field_placeholder=placeholder,
    )


def role_kb(admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [[Btn.ROLE_BUYER], [Btn.ROLE_OWNER, Btn.ROLE_BROKER], [Btn.ABOUT, Btn.CONTACT]]
    if admin:
        rows.append([Btn.ADMIN])
    return _reply(rows, "Rolingizni tanlang")


def buyer_menu(admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [Btn.BUY, Btn.RENT],
        [Btn.BY_ID, Btn.SUBS],
        [Btn.MY_REQUESTS, Btn.ABOUT],
        [Btn.SWITCH_ROLE, Btn.CONTACT],
    ]
    if admin:
        rows.append([Btn.ADMIN])
    return _reply(rows, "Xaridor menyusi")


def owner_menu(admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [Btn.SELL, Btn.RENT_OUT],
        [Btn.ORDER_AD, Btn.MY_LISTINGS],
        [Btn.TARIFFS, Btn.ABOUT],
        [Btn.SWITCH_ROLE, Btn.CONTACT],
    ]
    if admin:
        rows.append([Btn.ADMIN])
    return _reply(rows, "Uy egasi menyusi")


def broker_menu(status: str | None, admin: bool = False) -> ReplyKeyboardMarkup:
    if status == "approved":
        rows = [
            [Btn.ADD_OBJECT, Btn.MY_OBJECTS],
            [Btn.BASE, Btn.MY_CLIENTS],
            [Btn.CALC, Btn.MY_STATS],
            [Btn.TERMS, Btn.WEB_CABINET],
            [Btn.SWITCH_ROLE],
        ]
    else:
        rows = [[Btn.BROKER_REGISTER], [Btn.TERMS, Btn.CALC], [Btn.SWITCH_ROLE, Btn.CONTACT]]
    if admin:
        rows.append([Btn.ADMIN])
    return _reply(rows, "Makler menyusi")


def cancel_kb(*extra: str) -> ReplyKeyboardMarkup:
    rows = [[t] for t in extra]
    rows.append([Btn.CANCEL])
    return _reply(rows)


def phone_kb(saved: str | None = None) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=Btn.SEND_PHONE, request_contact=True)]]
    if saved:
        rows.append([KeyboardButton(text=saved)])
    rows.append([KeyboardButton(text=Btn.CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True,
                               input_field_placeholder="+998 90 123 45 67")


def media_kb() -> ReplyKeyboardMarkup:
    return _reply([[Btn.DONE], [Btn.SKIP], [Btn.CANCEL]])


# ----------------------------------------------------------------- inline
def districts_kb(make: Callable[[int], CallbackData], all_cb: CallbackData | None = None,
                 back: CallbackData | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for idx, name in enumerate(DISTRICTS):
        b.button(text=name, callback_data=make(idx))
    b.adjust(2)
    if all_cb:
        b.row(InlineKeyboardButton(text="🌍 Barcha hududlar", callback_data=all_cb.pack()))
    if back:
        b.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back.pack()))
    return b.as_markup()


def ptypes_kb(make: Callable[[str], CallbackData], all_cb: CallbackData | None = None,
              back: CallbackData | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, name in PROPERTY_TYPES.items():
        b.button(text=f"{PROPERTY_ICONS[key]} {name}", callback_data=make(key))
    b.adjust(2)
    if all_cb:
        b.row(InlineKeyboardButton(text="🏘 Barcha turlar", callback_data=all_cb.pack()))
    if back:
        b.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back.pack()))
    return b.as_markup()


def rooms_kb(make: Callable[[int], CallbackData], any_cb: CallbackData | None = None,
             back: CallbackData | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for n in ROOM_CHOICES:
        b.button(text=f"{n}+" if n == 5 else str(n), callback_data=make(n))
    b.adjust(5)
    if any_cb:
        b.row(InlineKeyboardButton(text="🤷 Farqi yo‘q", callback_data=any_cb.pack()))
    if back:
        b.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back.pack()))
    return b.as_markup()


def prices_kb(deal: str, make: Callable[[int], CallbackData], any_cb: CallbackData,
              back: CallbackData | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for idx, (_, _, label) in enumerate(PRICE_RANGES[deal]):
        b.button(text=label, callback_data=make(idx))
    b.adjust(2)
    b.row(InlineKeyboardButton(text="🤷 Farqi yo‘q", callback_data=any_cb.pack()))
    if back:
        b.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back.pack()))
    return b.as_markup()


def deal_type_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏷 Sotish", callback_data=Form(f="deal", v="s"))
    b.button(text="🔑 Ijaraga berish", callback_data=Form(f="deal", v="r"))
    b.adjust(2)
    return b.as_markup()


def tariffs_kb(deal: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    tariffs = TARIFFS_SALE if deal == "s" else TARIFFS_RENT
    for key, t in tariffs.items():
        b.button(text=t["title"], callback_data=Form(f="tariff", v=key))
    b.adjust(1)
    return b.as_markup()


def yes_no_kb(field: str, yes: str = "✅ Ha", no: str = "❌ Yo‘q") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=yes, callback_data=Form(f=field, v="1"))
    b.button(text=no, callback_data=Form(f=field, v="0"))
    b.adjust(2)
    return b.as_markup()


def confirm_listing_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Yuborish", callback_data=Form(f="confirm", v="yes"))
    b.button(text="🔁 Qaytadan to‘ldirish", callback_data=Form(f="confirm", v="restart"))
    b.button(text="❌ Bekor qilish", callback_data=Form(f="confirm", v="no"))
    b.adjust(1)
    return b.as_markup()


def viewing_time_kb(listing_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in VIEWING_TIMES.items():
        b.button(text=label, callback_data=Lst(a="time", id=listing_id, v=key))
    b.adjust(2)
    return b.as_markup()


def public_listing_kb(listing: dict, bot_username: str | None, *, source: str = "",
                      broker_view: bool = False, nav: tuple[Srch, Srch, str] | None = None,
                      search_cb: Srch | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if broker_view:
        b.row(InlineKeyboardButton(text="🤝 Mijozim bor — qayd etish",
                                   callback_data=Brk(a="client", id=listing["id"]).pack()))
    else:
        b.row(InlineKeyboardButton(text="📩 Ko‘rishga yozilish",
                                   callback_data=Lst(a="lead", id=listing["id"], v=source).pack()))
    media_count = len(listing.get("photos") or []) + (1 if listing.get("video") else 0)
    if media_count > 1:
        b.row(InlineKeyboardButton(text=f"🖼 Barcha rasm/video ({media_count})",
                                   callback_data=Lst(a="media", id=listing["id"]).pack()))
    if nav:
        prev_cb, next_cb, label = nav
        b.row(
            InlineKeyboardButton(text="◀️", callback_data=prev_cb.pack()),
            InlineKeyboardButton(text=label, callback_data=Nav(to="noop").pack()),
            InlineKeyboardButton(text="▶️", callback_data=next_cb.pack()),
        )
    if search_cb:
        b.row(
            InlineKeyboardButton(text="🔔 Obuna bo‘lish", callback_data=search_cb.model_copy(update={"s": "sub"}).pack()),
            InlineKeyboardButton(text="🔄 Yangi qidiruv", callback_data=Srch(s="new", dl=search_cb.dl).pack()),
        )
    if bot_username:
        link = f"https://t.me/{bot_username}?start={listing['code']}"
        b.row(InlineKeyboardButton(text="📤 Ulashish",
                                   url=f"https://t.me/share/url?url={link}"))
    return b.as_markup()


def lead_status_kb(lead_id: int, current: str, listing_id: int | None = None,
                   admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in LEAD_STATUSES.items():
        text = f"• {label} •" if key == current else label
        b.button(text=text, callback_data=Ld(a="st", id=lead_id, v=key))
    b.adjust(2)
    if listing_id:
        b.row(InlineKeyboardButton(text="🏠 Obyektni ochish",
                                   callback_data=(Adm(a="card", id=listing_id) if admin
                                                  else Lst(a="open", id=listing_id)).pack()))
    if admin and current == "won" and listing_id:
        b.row(InlineKeyboardButton(text="🤝 Bitimni rasmiylashtirish",
                                   callback_data=Adm(a="deal", id=listing_id).pack()))
    return b.as_markup()


def owner_listing_kb(listing: dict, can_see_leads: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    lid = listing["id"]
    status = listing["status"]
    if status in ("active", "negotiation"):
        b.button(text=("• " if status == "active" else "") + "✅ Faol",
                 callback_data=Lst(a="ost", id=lid, v="active"))
        b.button(text=("• " if status == "negotiation" else "") + "🤝 Muzokarada",
                 callback_data=Lst(a="ost", id=lid, v="negotiation"))
        if listing["deal_type"] == "s":
            b.button(text="🏁 Sotildi", callback_data=Lst(a="ost", id=lid, v="sold"))
        else:
            b.button(text="🔑 Ijaraga berildi", callback_data=Lst(a="ost", id=lid, v="rented"))
        b.button(text="📦 Sotuvdan olish", callback_data=Lst(a="ost", id=lid, v="archived"))
    elif status in ("pending", "shooting"):
        b.button(text="📦 E’lonni bekor qilish", callback_data=Lst(a="ost", id=lid, v="archived"))
    elif status in ("archived", "rejected"):
        b.button(text="♻️ Qayta moderatsiyaga yuborish", callback_data=Lst(a="ost", id=lid, v="pending"))
    b.adjust(2)
    if status in ("pending", "active", "negotiation") and not listing.get("shooting_requested"):
        b.row(InlineKeyboardButton(text="🎬 Professional syomka so‘rash",
                                   callback_data=Lst(a="shootreq", id=lid).pack()))
    extra = []
    if listing.get("photos") or listing.get("video"):
        extra.append(InlineKeyboardButton(text="🖼 Media", callback_data=Lst(a="media", id=lid).pack()))
    if can_see_leads:
        extra.append(InlineKeyboardButton(text="👥 Murojaatlar", callback_data=Lst(a="leads", id=lid).pack()))
    if extra:
        b.row(*extra)
    return b.as_markup()


def admin_listing_kb(listing: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    lid = listing["id"]
    status = listing["status"]
    if status in ("pending", "shooting", "rejected", "archived"):
        b.row(InlineKeyboardButton(text="✅ Tasdiqlash va e’lon qilish",
                                   callback_data=Adm(a="approve", id=lid).pack()))
    if status == "pending":
        b.row(
            InlineKeyboardButton(text="🎬 Syomkaga", callback_data=Adm(a="shoot", id=lid).pack()),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=Adm(a="reject", id=lid).pack()),
        )
    if status in ("active", "negotiation"):
        b.row(
            InlineKeyboardButton(text=("• " if status == "active" else "") + "✅ Faol",
                                 callback_data=Adm(a="st", id=lid, v="active").pack()),
            InlineKeyboardButton(text=("• " if status == "negotiation" else "") + "🤝 Muzokarada",
                                 callback_data=Adm(a="st", id=lid, v="negotiation").pack()),
        )
        b.row(
            InlineKeyboardButton(text="🏁 Bitimni yopish", callback_data=Adm(a="deal", id=lid).pack()),
            InlineKeyboardButton(text="📦 Arxiv", callback_data=Adm(a="st", id=lid, v="archived").pack()),
        )
    if status in CLOSED_STATUSES:
        b.row(InlineKeyboardButton(text="🧾 Bitimni qayta rasmiylashtirish",
                                   callback_data=Adm(a="deal", id=lid).pack()))
    b.row(
        InlineKeyboardButton(text="💰 Narx", callback_data=Adm(a="price", id=lid).pack()),
        InlineKeyboardButton(text="📐 Model", callback_data=Adm(a="model", id=lid).pack()),
        InlineKeyboardButton(text="％ Foiz", callback_data=Adm(a="pct", id=lid).pack()),
    )
    b.row(
        InlineKeyboardButton(text="👤 Makler", callback_data=Adm(a="assign", id=lid).pack()),
        InlineKeyboardButton(text="💸 Xarajat", callback_data=Adm(a="exp", id=lid).pack()),
        InlineKeyboardButton(
            text=("✅" if listing.get("ad_fee_paid") else "💳") + " Reklama to‘lovi",
            callback_data=Adm(a="adpaid", id=lid).pack()),
    )
    b.row(
        InlineKeyboardButton(text="🖼 Media", callback_data=Adm(a="media", id=lid).pack()),
        InlineKeyboardButton(text="📤 Media yuklash", callback_data=Adm(a="upload", id=lid).pack()),
        InlineKeyboardButton(text="👥 Murojaatlar", callback_data=Adm(a="leads", id=lid).pack()),
    )
    if status in ("active", "negotiation"):
        b.row(InlineKeyboardButton(text="📢 Kanalga qayta joylash",
                                   callback_data=Adm(a="repost", id=lid).pack()))
    b.row(
        InlineKeyboardButton(text="🔄 Yangilash", callback_data=Adm(a="card", id=lid, v="e").pack()),
        InlineKeyboardButton(text="🛠 Panel", callback_data=Adm(a="panel").pack()),
    )
    return b.as_markup()


def back_kb(cb: CallbackData, text: str = "⬅️ Orqaga") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=cb.pack())]])


def deal_label(deal: str) -> str:
    return DEAL_TYPES.get(deal, deal)
