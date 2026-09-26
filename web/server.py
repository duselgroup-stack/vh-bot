"""VOHA UYLARI sayti: katalog, obyekt sahifasi, ko‘rishga yozilish, makler kabineti, admin panel."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import jinja2
from aiogram import Bot
from aiohttp import web

from config import config
from constants import (
    BROKER_STATUSES,
    DEAL_STAGES,
    DEAL_TYPES,
    DISTRICTS,
    LEAD_STATUSES,
    LISTING_STATUSES,
    MODELS,
    PROPERTY_ICONS,
    PROPERTY_TYPES,
    PUBLIC_STATUSES,
    SOURCES,
    VIEWING_TIMES,
)
from database import db
from filters import is_admin
from services.commission import calc_split
from utils import esc, fmt_money, fmt_percent, fmt_short, normalize_phone, short_dt
from web.auth import (
    SESSION_COOKIE,
    RateLimiter,
    check_form_token,
    client_ip,
    current_user_id,
    form_token,
    set_session,
)
from web.media import CONTENT_TYPES, MediaStore

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
PAGE_SIZE = 12
lead_limiter = RateLimiter(limit=5, period=600)
request_limiter = RateLimiter(limit=3, period=600)


# ------------------------------------------------------------------ shablon
def _media_url(file_id: str | None) -> str | None:
    return f"/media/{file_id}" if file_id else None


def _cover(listing: dict) -> str | None:
    photos = listing.get("photos") or []
    return _media_url(photos[0]) if photos else None


def _title(listing: dict) -> str:
    parts = [PROPERTY_TYPES.get(listing["property_type"], "")]
    if listing.get("rooms"):
        parts.append(f"{listing['rooms']} xonali")
    if listing.get("area"):
        parts.append(str(listing["area"]))
    return " · ".join(p for p in parts if p)


def _price(listing: dict) -> str:
    return fmt_money(listing["price"]) + (" / oy" if listing["deal_type"] == "r" else "")


def build_env() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(BASE_DIR / "templates")),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters.update(money=fmt_money, short=fmt_short, percent=fmt_percent, dt=short_dt)
    env.globals.update(
        DISTRICTS=DISTRICTS, PROPERTY_TYPES=PROPERTY_TYPES, PROPERTY_ICONS=PROPERTY_ICONS,
        DEAL_TYPES=DEAL_TYPES, LISTING_STATUSES=LISTING_STATUSES, LEAD_STATUSES=LEAD_STATUSES,
        BROKER_STATUSES=BROKER_STATUSES, SOURCES=SOURCES, VIEWING_TIMES=VIEWING_TIMES,
        MODELS=MODELS, DEAL_STAGES=DEAL_STAGES, config=config,
        media_url=_media_url, cover=_cover, title=_title, price=_price,
    )
    return env


async def render(request: web.Request, template: str, status: int = 200, **ctx) -> web.Response:
    app = request.app
    user_id = current_user_id(request)
    username = app.get("bot_username")
    base = {
        "request": request,
        "path": request.path,
        "year": datetime.now().year,
        "bot_username": username,
        "bot_link": f"https://t.me/{username}" if username else "#",
        "session_user": user_id,
        "session_admin": bool(user_id and is_admin(user_id)),
        "site_url": config.site_url,
    }
    base.update(ctx)
    html = app["jinja"].get_template(template).render(**base)
    return web.Response(text=html, status=status, content_type="text/html")


def bot_deeplink(app: web.Application, payload: str) -> str:
    username = app.get("bot_username")
    return f"https://t.me/{username}?start={payload}" if username else "#"


# ---------------------------------------------------------------- yordamchi
def _int_arg(value: str | None, default: int = 0) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def _mln_arg(value: str | None) -> int | None:
    if not value:
        return None
    try:
        amount = float(value.replace(",", ".").replace(" ", ""))
    except ValueError:
        return None
    return int(amount * 1_000_000) if amount > 0 else None


def parse_filters(query) -> dict:
    deal = query.get("turi", "s")
    deal = deal if deal in ("s", "r", "all") else "s"
    district_idx = _int_arg(query.get("hudud"), -1)
    ptype = query.get("mulk", "")
    return {
        "turi": deal,
        "hudud": district_idx if 0 <= district_idx < len(DISTRICTS) else -1,
        "mulk": ptype if ptype in PROPERTY_TYPES else "",
        "xona": max(0, min(_int_arg(query.get("xona")), 5)),
        "narx_min": query.get("narx_min", "").strip()[:12],
        "narx_max": query.get("narx_max", "").strip()[:12],
        "saralash": query.get("saralash", "new") if query.get("saralash") in ("new", "cheap", "expensive", "popular") else "new",
        "sahifa": max(1, _int_arg(query.get("sahifa"), 1)),
    }


def filters_to_query(f: dict, **override) -> str:
    data = {**f, **override}
    clean = {k: v for k, v in data.items()
             if v not in ("", None, -1, 0) and not (k == "sahifa" and v == 1) and not (k == "saralash" and v == "new")}
    return urlencode(clean)


async def listings_by_ids_counts(listings: list[dict]) -> dict[int, int]:
    if not listings:
        return {}
    ids = [l["id"] for l in listings]
    marks = ",".join("?" for _ in ids)
    rows = await db.fetchall(f"SELECT listing_id, COUNT(*) AS n FROM leads WHERE listing_id IN ({marks}) GROUP BY listing_id", ids)
    return {r["listing_id"]: r["n"] for r in rows}


# ------------------------------------------------------------ ommaviy sahifalar
async def index(request: web.Request) -> web.Response:
    latest, _ = await db.catalog(deal_type="s", limit=6)
    rent, _ = await db.catalog(deal_type="r", limit=3)
    return await render(
        request, "index.html", latest=latest, rent=rent, counts=await db.public_counts(),
        district_counts=await db.district_counts(),
        page_title=f"{config.company_name} — Qashqadaryo ko‘chmas mulk")


async def catalog(request: web.Request) -> web.Response:
    f = parse_filters(request.query)
    offset = (f["sahifa"] - 1) * PAGE_SIZE
    rows, total = await db.catalog(
        deal_type=None if f["turi"] == "all" else f["turi"],
        district=DISTRICTS[f["hudud"]] if f["hudud"] >= 0 else None,
        property_type=f["mulk"] or None, rooms=f["xona"],
        price_min=_mln_arg(f["narx_min"]), price_max=_mln_arg(f["narx_max"]),
        sort=f["saralash"], limit=PAGE_SIZE, offset=offset)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    heading = {"s": "Sotuvdagi uylar", "r": "Ijaraga beriladigan uylar", "all": "Barcha e’lonlar"}[f["turi"]]
    if f["hudud"] >= 0:
        heading += f" — {DISTRICTS[f['hudud']]}"
    return await render(
        request, "catalog.html", listings=rows, total=total, f=f, pages=pages,
        page_url=lambda n: "/uylar?" + filters_to_query(f, sahifa=n),
        sort_url=lambda s: "/uylar?" + filters_to_query(f, saralash=s, sahifa=1),
        heading=heading, page_title=f"{heading} | {config.company_name}")


async def _listing_or_404(request: web.Request) -> dict:
    code = request.match_info["code"].upper()
    listing = await db.get_listing_by_code(code)
    if not listing:
        raise web.HTTPNotFound()
    if listing["status"] not in PUBLIC_STATUSES + ("sold", "rented"):
        uid = current_user_id(request)
        if not uid or not (is_admin(uid) or uid in (listing.get("source_user_id"), listing.get("broker_id"))):
            raise web.HTTPNotFound()
    return listing


async def listing_page(request: web.Request, *, errors: dict | None = None, form: dict | None = None,
                       status: int = 200) -> web.Response:
    listing = await _listing_or_404(request)
    ua = request.headers.get("User-Agent", "").lower()
    if request.method == "GET" and not any(b in ua for b in ("bot", "spider", "crawl", "preview")):
        uid = current_user_id(request)
        if uid not in (listing.get("source_user_id"), listing.get("broker_id")):
            await db.add_view(listing["id"])
    broker = await db.get_broker(listing["broker_id"]) if listing.get("broker_id") else None
    if broker and broker["status"] != "approved":
        broker = None
    similar, _ = await db.catalog(deal_type=listing["deal_type"], district=listing["district"], limit=4)
    similar = [s for s in similar if s["id"] != listing["id"]][:3]
    if len(similar) < 3:
        more, _ = await db.catalog(deal_type=listing["deal_type"], property_type=listing["property_type"], limit=6)
        similar += [m for m in more if m["id"] != listing["id"] and m["id"] not in {s["id"] for s in similar}]
        similar = similar[:3]
    channel_link = None
    if isinstance(config.channel_id, str) and listing.get("channel_message_id"):
        channel_link = f"https://t.me/{config.channel_id.lstrip('@')}/{listing['channel_message_id']}"
    split = None
    if listing["deal_type"] == "s" and listing.get("model") in (1, 2, 3):
        split = calc_split(listing["price"], listing["model"])
    return await render(
        request, "listing.html", status=status, listing=listing, broker=broker, similar=similar,
        sent=request.query.get("yuborildi"), errors=errors or {}, form=form or {},
        token=form_token(), tg_link=bot_deeplink(request.app, f"{listing['code']}_web"),
        channel_link=channel_link, split=split,
        page_title=f"{_title(listing)}, {listing['district']} — {fmt_short(listing['price'])} | {listing['code']}",
        og_image=(config.site_url + _cover(listing)) if _cover(listing) else None,
        og_description=(listing.get("description") or "")[:200])


async def listing_get(request: web.Request) -> web.Response:
    return await listing_page(request)


async def listing_lead(request: web.Request) -> web.Response:
    listing = await _listing_or_404(request)
    data = await request.post()
    form = {k: str(data.get(k, "")).strip() for k in ("ism", "telefon", "vaqt", "izoh", "rozilik")}
    if data.get("website"):  # bot-spam tuzog‘i
        raise web.HTTPFound(f"/uy/{listing['code']}?yuborildi=1#forma")
    errors: dict[str, str] = {}
    if not check_form_token(str(data.get("token", ""))):
        errors["umumiy"] = "Sahifa eskirgan — iltimos, qayta yuboring."
    if listing["status"] not in PUBLIC_STATUSES:
        errors["umumiy"] = "Bu obyekt hozir sotuvda emas."
    if not 2 <= len(form["ism"]) <= 80:
        errors["ism"] = "Ismingizni yozing."
    phone = normalize_phone(form["telefon"])
    if not phone:
        errors["telefon"] = "Telefon raqamini to‘g‘ri yozing: +998 90 123 45 67"
    if not form["rozilik"]:
        errors["rozilik"] = "Ma’lumotlardan foydalanishga rozilik bering."
    if not errors and not lead_limiter.allow(client_ip(request)):
        errors["umumiy"] = "Juda ko‘p so‘rov yuborildi. Birozdan keyin urinib ko‘ring."
    if errors:
        return await listing_page(request, errors=errors, form=form, status=400)

    existing = await db.find_lead(listing["id"], phone=phone)
    if not existing:
        lead = await db.create_lead(
            listing_id=listing["id"], buyer_user_id=None, buyer_name=form["ism"][:80],
            buyer_phone=phone, source="sayt",
            preferred_time=form["vaqt"] if form["vaqt"] in VIEWING_TIMES else None,
            comment=form["izoh"][:500] or None)
        bot: Bot | None = request.app.get("bot")
        if bot:
            from handlers.leads import dispatch_new_lead
            try:
                await dispatch_new_lead(bot, lead, listing)
            except Exception as exc:  # noqa: BLE001
                log.warning("Murojaat xabari yuborilmadi: %s", exc)
    raise web.HTTPFound(f"/uy/{listing['code']}?yuborildi={'2' if existing else '1'}#forma")


async def partner(request: web.Request) -> web.Response:
    examples = {m: calc_split(500_000_000, m) for m in (1, 2, 3)}
    return await render(request, "partner.html", examples=examples,
                        join_link=bot_deeplink(request.app, "mk"),
                        page_title=f"Maklerlar uchun hamkorlik | {config.company_name}")


async def sell_page(request: web.Request, *, errors: dict | None = None, form: dict | None = None,
                    status: int = 200) -> web.Response:
    return await render(request, "sell.html", status=status, errors=errors or {}, form=form or {},
                        sent=request.query.get("yuborildi"), token=form_token(),
                        bot_sell=bot_deeplink(request.app, "web"),
                        page_title=f"Uyingizni soting yoki ijaraga bering | {config.company_name}")


async def sell_get(request: web.Request) -> web.Response:
    return await sell_page(request)


async def sell_post(request: web.Request) -> web.Response:
    data = await request.post()
    form = {k: str(data.get(k, "")).strip() for k in ("ism", "telefon", "hudud", "maqsad", "izoh", "rozilik")}
    if data.get("website"):
        raise web.HTTPFound("/uy-sotish?yuborildi=1#ariza")
    errors: dict[str, str] = {}
    if not check_form_token(str(data.get("token", ""))):
        errors["umumiy"] = "Sahifa eskirgan — iltimos, qayta yuboring."
    if not 2 <= len(form["ism"]) <= 80:
        errors["ism"] = "Ismingizni yozing."
    phone = normalize_phone(form["telefon"])
    if not phone:
        errors["telefon"] = "Telefon raqamini to‘g‘ri yozing: +998 90 123 45 67"
    if not form["rozilik"]:
        errors["rozilik"] = "Ma’lumotlardan foydalanishga rozilik bering."
    if not errors and not request_limiter.allow(client_ip(request)):
        errors["umumiy"] = "Juda ko‘p so‘rov yuborildi. Birozdan keyin urinib ko‘ring."
    if errors:
        return await sell_page(request, errors=errors, form=form, status=400)
    district_idx = _int_arg(form["hudud"], -1)
    district = DISTRICTS[district_idx] if 0 <= district_idx < len(DISTRICTS) else None
    kind = {"s": "sotish", "r": "ijara", "ad": "reklama"}.get(form["maqsad"], "sotish")
    req = await db.add_site_request(kind, form["ism"][:80], phone, district, form["izoh"][:500] or None)
    bot: Bot | None = request.app.get("bot")
    if bot:
        from services.notify import notify_admins
        await notify_admins(
            bot,
            f"🌐 <b>Saytdan yangi ariza #{req['id']}</b> — {esc(kind)}\n"
            f"👤 {esc(req['name'])}\n📱 {esc(phone)}\n📍 {esc(district or '—')}\n"
            + (f"💬 {esc(req['comment'])}" if req.get("comment") else ""))
    raise web.HTTPFound("/uy-sotish?yuborildi=1#ariza")


# ------------------------------------------------------------------- kirish
async def login(request: web.Request) -> web.Response:
    user_id = await db.consume_web_token(request.match_info["token"])
    if not user_id:
        return await render(request, "message.html", status=403, icon="⏳",
                            heading="Havola eskirgan",
                            text="Kirish havolasi 15 daqiqa amal qiladi va bir marta ishlaydi. "
                                 "Botda /sayt buyrug‘ini yuborib, yangi havola oling.")
    response = web.Response(status=302, headers={"Location": "/admin" if is_admin(user_id) else "/kabinet"})
    set_session(response, user_id)
    return response


async def logout(request: web.Request) -> web.Response:
    response = web.Response(status=302, headers={"Location": "/"})
    response.del_cookie(SESSION_COOKIE, path="/")
    return response


def _need_login(request: web.Request) -> web.Response:
    return render(request, "message.html", status=401, icon="🔐", heading="Kabinetga kirish",
                  text="Kabinetga Telegram-bot orqali kirasiz: botda /sayt buyrug‘ini yuboring "
                       "yoki «🌐 Sayt kabineti» tugmasini bosing — bot sizga shaxsiy kirish havolasini beradi.",
                  cta=("Botni ochish", bot_deeplink(request.app, "")))


async def cabinet(request: web.Request) -> web.Response:
    uid = current_user_id(request)
    if not uid:
        return await _need_login(request)
    broker = await db.get_broker(uid)
    if not broker or broker["status"] != "approved":
        if is_admin(uid):
            raise web.HTTPFound("/admin")
        return await render(request, "message.html", status=403, icon="🤝", heading="Kabinet hamkor maklerlar uchun",
                            text="Hamkor bo‘lish uchun botda «📝 Hamkor bo‘lish» orqali ariza yuboring.",
                            cta=("Hamkor bo‘lish", bot_deeplink(request.app, "mk")))
    listings = await db.user_listings(uid)
    lead_counts = await listings_by_ids_counts(listings)
    leads = await db.broker_leads(uid)
    deals = await db.broker_deals(uid)
    stats = await db.broker_stats(uid)
    from services.cards import stage_flags
    stages = {l["id"]: sum(await stage_flags(l)) for l in listings}
    bringers = {}
    for lead in leads:
        if lead.get("brought_by") and lead["brought_by"] not in bringers:
            bringers[lead["brought_by"]] = await db.get_broker(lead["brought_by"])
    return await render(request, "cabinet.html", broker=broker, listings=listings, lead_counts=lead_counts,
                        leads=leads, deals=deals, stats=stats, stages=stages, uid=uid, bringers=bringers,
                        page_title=f"Kabinet — {broker['full_name']}")


async def admin_page(request: web.Request) -> web.Response:
    uid = current_user_id(request)
    if not uid:
        return await _need_login(request)
    if not is_admin(uid):
        raise web.HTTPForbidden()
    days = _int_arg(request.query.get("davr"), 30)
    days = days if days in (7, 30, 90, 365) else 30
    stats = await db.stats(days)
    queue = await db.listings_by_status("pending", "shooting", limit=30)
    dups = {l["id"]: await db.find_duplicates(l) for l in queue}
    return await render(
        request, "admin.html", stats=stats, days=days, queue=queue, dups=dups,
        leads=await db.recent_leads(25), unpaid=await db.unpaid_deals(),
        requests=await db.site_requests(20), brokers_pending=await db.list_brokers("pending"),
        admin_link=lambda lid: bot_deeplink(request.app, f"adm{lid}"), page_title="Admin panel")


# -------------------------------------------------------------------- media
async def media(request: web.Request) -> web.StreamResponse:
    file_id = request.match_info["file_id"]
    store: MediaStore = request.app["media"]
    if not store.cached(file_id) and not await store.is_listing_media(file_id):
        raise web.HTTPNotFound()
    path = await store.get(file_id)
    if not path:
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={
        "Cache-Control": "public, max-age=2592000, immutable",
        "Content-Type": CONTENT_TYPES.get(path.suffix, "application/octet-stream"),
    })


# ---------------------------------------------------------------------- SEO
async def robots(request: web.Request) -> web.Response:
    return web.Response(text=f"User-agent: *\nDisallow: /kabinet\nDisallow: /admin\nDisallow: /login/\n"
                             f"Sitemap: {config.site_url}/sitemap.xml\n")


async def sitemap(request: web.Request) -> web.Response:
    rows, _ = await db.catalog(deal_type=None, limit=5000)
    urls = [f"{config.site_url}/", f"{config.site_url}/uylar", f"{config.site_url}/uylar?turi=r",
            f"{config.site_url}/uy-sotish", f"{config.site_url}/hamkorlik"]
    urls += [f"{config.site_url}/uy/{r['code']}" for r in rows]
    body = "".join(f"<url><loc>{esc(u)}</loc></url>" for u in urls)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
    return web.Response(text=xml, content_type="application/xml")


# --------------------------------------------------------------- xatoliklar
@web.middleware
async def errors_middleware(request: web.Request, handler):
    try:
        response = await handler(request)
    except web.HTTPNotFound:
        return await render(request, "message.html", status=404, icon="🏚",
                            heading="Sahifa topilmadi",
                            text="Bu e’lon o‘chirilgan yoki havola noto‘g‘ri bo‘lishi mumkin.",
                            cta=("Barcha uylar", "/uylar"))
    except web.HTTPForbidden:
        return await render(request, "message.html", status=403, icon="⛔", heading="Ruxsat yo‘q",
                            text="Bu sahifa faqat adminlar uchun.")
    except web.HTTPException:
        raise
    except Exception:  # noqa: BLE001
        log.exception("Sayt xatosi: %s", request.path)
        return await render(request, "message.html", status=500, icon="⚠️", heading="Xatolik yuz berdi",
                            text="Birozdan keyin qayta urinib ko‘ring.")
    if isinstance(response, web.Response) and response.content_type == "text/html":
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return response


# --------------------------------------------------------------------- ilova
def create_app(bot: Bot | None) -> web.Application:
    app = web.Application(middlewares=[errors_middleware], client_max_size=64 * 1024)
    app["bot"] = bot
    app["jinja"] = build_env()
    app["media"] = MediaStore(bot, config.media_cache_dir)
    app.router.add_get("/", index)
    app.router.add_get("/uylar", catalog)
    app.router.add_get("/uy/{code}", listing_get)
    app.router.add_post("/uy/{code}/yozilish", listing_lead)
    app.router.add_get("/hamkorlik", partner)
    app.router.add_get("/uy-sotish", sell_get)
    app.router.add_post("/uy-sotish", sell_post)
    app.router.add_get("/login/{token}", login)
    app.router.add_get("/chiqish", logout)
    app.router.add_get("/kabinet", cabinet)
    app.router.add_get("/admin", admin_page)
    app.router.add_get("/media/{file_id}", media)
    app.router.add_get("/robots.txt", robots)
    app.router.add_get("/sitemap.xml", sitemap)
    app.router.add_static("/static", str(BASE_DIR / "static"), name="static", append_version=True)

    async def on_startup(app: web.Application) -> None:
        if bot is not None:
            try:
                app["bot_username"] = (await bot.me()).username
            except Exception:  # noqa: BLE001
                app["bot_username"] = None

    app.on_startup.append(on_startup)
    return app


async def start_web(bot: Bot | None) -> web.AppRunner:
    app = create_app(bot)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, config.web_host, config.web_port)
    await site.start()
    log.info("Sayt ishga tushdi: http://%s:%s (ochiq manzil: %s)", config.web_host, config.web_port, config.site_url)
    return runner
