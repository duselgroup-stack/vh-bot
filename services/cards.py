"""Obyekt, murojaat va bitim kartochkalari matni."""
from __future__ import annotations

from config import config
from constants import (
    BROKER_STATUSES,
    DEAL_ICONS,
    DEAL_STAGES,
    DEAL_TYPES,
    LEAD_STATUSES,
    LISTING_STATUSES,
    MODELS,
    OBJECT_SOURCES,
    PROPERTY_ICONS,
    PROPERTY_TYPES,
    SOURCES,
    VIEWING_TIMES,
)
from database import db
from services.commission import listing_percent
from utils import esc, fmt_money, fmt_percent, fmt_short, progress_bar, short_dt


def _cut(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def listing_title(listing: dict) -> str:
    pt = listing["property_type"]
    return f"{PROPERTY_ICONS.get(pt, '🏠')} {PROPERTY_TYPES.get(pt, pt)} · {DEAL_TYPES.get(listing['deal_type'], '')}"


def price_text(listing: dict) -> str:
    suffix = " / oy" if listing["deal_type"] == "r" else ""
    return f"{fmt_money(listing['price'])}{suffix}"


def listing_short(listing: dict) -> str:
    """Ro‘yxat uchun bir qatorli ko‘rinish."""
    pt = PROPERTY_ICONS.get(listing["property_type"], "🏠")
    rooms = f" · {listing['rooms']} xona" if listing.get("rooms") else ""
    return f"{listing['code']} {pt} {listing['district']}{rooms} · {fmt_short(listing['price'])}"


def _details(listing: dict) -> list[str]:
    lines = []
    place = esc(listing["district"])
    if listing.get("address"):
        place += f", {esc(_cut(listing['address'], 120))}"
    lines.append(f"📍 {place}")
    extra = []
    if listing.get("rooms"):
        extra.append(f"🚪 {listing['rooms']} xona")
    if listing.get("area"):
        extra.append(f"📐 {esc(_cut(listing['area'], 40))}")
    if listing.get("floor"):
        extra.append(f"🏢 {esc(_cut(listing['floor'], 20))}-qavat")
    if extra:
        lines.append("   ".join(extra))
    lines.append(f"💰 Narx: <b>{price_text(listing)}</b> ({fmt_short(listing['price'])})")
    return lines


async def public_card(listing: dict, desc_limit: int = 450, show_status: bool = True) -> str:
    lines = [f"<b>{listing_title(listing)}</b>", f"🆔 <code>{listing['code']}</code>", ""]
    lines += _details(listing)
    if listing.get("description"):
        lines += ["", f"📝 {esc(_cut(listing['description'], desc_limit))}"]
    if listing["status"] == "negotiation":
        lines += ["", "🤝 <i>Hozir muzokarada — lekin murojaat qoldirishingiz mumkin</i>"]
    elif listing["status"] != "active" and show_status:
        lines += ["", f"Holat: {LISTING_STATUSES.get(listing['status'], listing['status'])}"]
    broker = None
    if listing.get("broker_id"):
        broker = await db.get_broker(listing["broker_id"])
    lines.append("")
    if broker and broker["status"] == "approved":
        lines.append(f"👤 Mas’ul makler: {esc(broker['full_name'])}")
    lines.append(f"☎️ {esc(config.company_name)}: {esc(config.company_phone)}")
    return "\n".join(lines)


async def channel_caption(listing: dict) -> str:
    text = await public_card(listing, desc_limit=380, show_status=False)
    if listing["status"] in ("sold", "rented"):
        mark = "🔴 <b>SOTILDI</b>" if listing["status"] == "sold" else "🔴 <b>IJARAGA BERILDI</b>"
        text = f"{mark}\n\n{text}"
    elif listing["status"] == "archived":
        text = f"⚪️ <b>SOTUVDAN OLINDI</b>\n\n{text}"
    return text


async def stage_flags(listing: dict) -> list[bool]:
    counts = await db.lead_counts(listing["id"])
    deal = await db.listing_deal(listing["id"])
    has_media = bool(listing.get("photos") or listing.get("video"))
    viewed = any(counts.get(s) for s in ("viewed", "negotiation", "won"))
    return [
        bool(listing.get("accepted_at")) or listing["status"] in ("active", "negotiation", "sold", "rented"),
        has_media and listing["status"] != "shooting",
        bool(listing.get("published_at")),
        sum(counts.values()) > 0,
        viewed,
        listing["status"] in ("sold", "rented"),
        bool(deal and deal["status"] == "paid"),
    ]


async def stages_block(listing: dict) -> str:
    flags = await stage_flags(listing)
    done = sum(flags)
    lines = [f"📈 Bosqich: {progress_bar(done)}"]
    nxt = next((DEAL_STAGES[i] for i, ok in enumerate(flags) if not ok), None)
    if nxt:
        lines.append(f"➡️ Keyingi qadam: <i>{nxt}</i>")
    return "\n".join(lines)


async def owner_card(listing: dict) -> str:
    counts = await db.lead_counts(listing["id"])
    lines = [f"<b>{listing_title(listing)}</b>", f"🆔 <code>{listing['code']}</code>",
             f"Holat: <b>{LISTING_STATUSES.get(listing['status'], listing['status'])}</b>", ""]
    lines += _details(listing)
    if listing.get("description"):
        lines += ["", f"📝 {esc(_cut(listing['description'], 600))}"]
    lines += [
        "",
        await stages_block(listing),
        f"👁 Ko‘rishlar: {listing.get('views', 0)}   📩 Murojaatlar: {sum(counts.values())}",
        f"📐 Shart: {MODELS.get(listing.get('model') or 0, MODELS[1])['name']}",
        f"🗓 Qo‘shilgan: {short_dt(listing.get('created_at'))}",
    ]
    if listing["status"] == "rejected" and listing.get("reject_reason"):
        lines.append(f"❗️ Rad etish sababi: {esc(listing['reject_reason'])}")
    if listing["status"] == "shooting":
        lines.append("🎬 Syomka rejalashtirilmoqda — menejer siz bilan bog‘lanadi.")
    return "\n".join(lines)


async def admin_card(listing: dict) -> str:
    counts = await db.lead_counts(listing["id"])
    model = listing.get("model") or 0
    m = MODELS.get(model, MODELS[1])
    lines = [
        f"🛠 <b>{listing['code']}</b> · {listing_title(listing)}",
        f"Holat: <b>{LISTING_STATUSES.get(listing['status'], listing['status'])}</b>",
        await stages_block(listing),
        "",
    ]
    lines += _details(listing)
    if listing.get("description"):
        lines += [f"📝 {esc(_cut(listing['description'], 900))}"]
    lines.append("──────────────")
    src_user = await db.get_user(listing["source_user_id"]) if listing.get("source_user_id") else None
    src = OBJECT_SOURCES.get(listing["source_type"], listing["source_type"])
    if src_user:
        uname = f" @{esc(src_user['username'])}" if src_user.get("username") else ""
        src += f" — <a href=\"tg://user?id={src_user['id']}\">{esc(src_user['full_name'])}</a>{uname}"
    lines.append(f"🧭 Obyekt manbasi: {src}")
    if listing.get("broker_id"):
        broker = await db.get_broker(listing["broker_id"])
        if broker:
            lines.append(f"🤝 Mas’ul makler: {esc(broker['full_name'])} ({esc(broker['phone'])}) — "
                         f"{BROKER_STATUSES.get(broker['status'], broker['status'])}")
    else:
        lines.append("🤝 Mas’ul makler: —")
    lines.append(f"📐 Model: {m['name']} · jami {fmt_percent(listing_percent(listing))}")
    if listing.get("ad_fee"):
        paid = "✅ to‘langan" if listing.get("ad_fee_paid") else "❌ to‘lanmagan"
        lines.append(f"📣 Reklama to‘lovi: {fmt_money(listing['ad_fee'])} — {paid}")
    if listing.get("expenses"):
        lines.append(f"💸 Xarajatlar: {fmt_money(listing['expenses'])}")
    owner = " ".join(x for x in [esc(listing.get("owner_name") or ""), esc(listing.get("owner_phone") or "")] if x)
    lines.append(f"👤 Mulk egasi: {owner or '—'}")
    media = f"{len(listing.get('photos') or [])} rasm" + (", video bor" if listing.get("video") else "")
    lines.append(f"🖼 Media: {media}  ·  🎬 Syomka so‘ralgan: {'ha' if listing.get('shooting_requested') else 'yo‘q'}")
    lines.append(f"👁 Ko‘rishlar: {listing.get('views', 0)}  ·  📩 Murojaatlar: {sum(counts.values())} "
                 f"(yangi: {counts.get('new', 0)})")
    lines.append(f"🗓 Qo‘shilgan: {short_dt(listing.get('created_at'))}  ·  E’lon: {short_dt(listing.get('published_at'))}")
    if listing.get("reject_reason"):
        lines.append(f"❗️ Rad sababi: {esc(listing['reject_reason'])}")
    dups = await db.find_duplicates(listing)
    if dups:
        lines.append("⚠️ <b>Ehtimoliy dublikat:</b> " + ", ".join(
            f"{d['code']} ({LISTING_STATUSES.get(d['status'], d['status'])})" for d in dups))
    deal = await db.listing_deal(listing["id"])
    if deal:
        lines.append(f"🧾 Bitim #{deal['id']}: {fmt_money(deal['final_price'])}, komissiya "
                     f"{fmt_money(deal['commission'])} — {'✅ undirilgan' if deal['status'] == 'paid' else '⏳ undirilmagan'}")
    return "\n".join(lines)


async def lead_card(lead: dict, listing: dict | None, *, viewer_id: int | None = None,
                    admin: bool = False) -> str:
    """Murojaat kartochkasi. Makler boshqa maklerning mijoz raqamini ko‘rmaydi."""
    code = listing["code"] if listing else f"#{lead['listing_id']}"
    lines = [f"📩 <b>Murojaat #{lead['id']}</b> · {code}"]
    if listing:
        lines.append(f"🏠 {esc(listing_title(listing))} · {esc(listing['district'])} · {fmt_short(listing['price'])}")
    lines.append(f"Holat: <b>{LEAD_STATUSES.get(lead['status'], lead['status'])}</b>")
    bringer = await db.get_broker(lead["brought_by"]) if lead.get("brought_by") else None
    show_contact = admin or viewer_id is None or lead.get("brought_by") in (None, viewer_id)
    if show_contact:
        lines.append(f"👤 Mijoz: {esc(lead.get('buyer_name') or '—')}")
        lines.append(f"📱 Telefon: {esc(lead.get('buyer_phone') or '—')}")
    else:
        lines.append("👤 Mijoz: hamkor makler mijozi (raqam himoyalangan)")
        if bringer:
            lines.append(f"🤝 Aloqa makler orqali: {esc(bringer['full_name'])} ({esc(bringer['phone'])})")
    lines.append(f"🧭 Manba: {SOURCES.get(lead.get('source') or 'bot', lead.get('source'))}")
    if bringer and show_contact:
        lines.append(f"🤝 Olib kelgan makler: {esc(bringer['full_name'])} ({esc(bringer['phone'])})")
    if lead.get("preferred_time"):
        lines.append(f"🕒 Qulay vaqt: {esc(VIEWING_TIMES.get(lead['preferred_time'], lead['preferred_time']))}")
    if lead.get("comment"):
        lines.append(f"💬 Izoh: {esc(_cut(lead['comment'], 500))}")
    lines.append(f"🗓 Qayd etilgan: {short_dt(lead.get('created_at'))}")
    return "\n".join(lines)


def deal_icon(deal_type: str) -> str:
    return DEAL_ICONS.get(deal_type, "🏠")
