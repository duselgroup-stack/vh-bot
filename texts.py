"""Bot matnlari va tugma yozuvlari (hammasi bir joyda — tahrirlash oson)."""
from __future__ import annotations

from config import config
from constants import AD_FEE, DISTRICTS
from utils import esc, fmt_money


class Btn:
    # Rol tanlash
    ROLE_BUYER = "🔎 Uy qidiryapman"
    ROLE_OWNER = "🏡 Uy egasiman"
    ROLE_BROKER = "🤝 Maklerman"

    # Umumiy
    CANCEL = "❌ Bekor qilish"
    MAIN = "🏠 Bosh menyu"
    SWITCH_ROLE = "🔄 Rolni almashtirish"
    ABOUT = "ℹ️ Biz haqimizda"
    CONTACT = "☎️ Aloqa"
    ADMIN = "🛠 Admin panel"
    SEND_PHONE = "📱 Raqamni yuborish"
    SKIP = "⏭ O‘tkazib yuborish"
    DONE = "✅ Tayyor"

    # Xaridor
    BUY = "🏠 Uy sotib olish"
    RENT = "🔑 Ijaraga olish"
    BY_ID = "🆔 ID bo‘yicha qidirish"
    SUBS = "🔔 Obunalarim"
    MY_REQUESTS = "📝 Murojaatlarim"

    # Uy egasi
    SELL = "🏷 Uy sotaman"
    RENT_OUT = "🔑 Ijaraga beraman"
    ORDER_AD = "🎬 Professional reklama"
    MY_LISTINGS = "📋 E’lonlarim"
    TARIFFS = "💰 Tariflar"

    # Makler
    BROKER_REGISTER = "📝 Hamkor bo‘lish"
    ADD_OBJECT = "➕ Obyekt qo‘shish"
    MY_OBJECTS = "📋 Obyektlarim"
    BASE = "🗂 Obyektlar bazasi"
    MY_CLIENTS = "👥 Mijozlar va murojaatlar"
    CALC = "🧮 Komissiya kalkulyatori"
    MY_STATS = "📊 Statistikam"
    TERMS = "📜 Hamkorlik shartlari"
    WEB_CABINET = "🌐 Sayt kabineti"


MENU_TEXTS = {
    value for key, value in vars(Btn).items() if not key.startswith("_") and isinstance(value, str)
}


def welcome(first_name: str) -> str:
    return (
        f"Assalomu alaykum, <b>{esc(first_name)}</b>! 👋\n\n"
        f"<b>{esc(config.company_name)}</b> — Qashqadaryodagi ko‘chmas mulk ekotizimi.\n"
        "Xaridor, uy egasi va makler bir tizimda: professional reklama, shaffof komissiya "
        "va har bir obyekt uchun yagona ID.\n\n"
        "Siz kimsiz? Pastdagi tugmalardan birini tanlang 👇"
    )


ROLE_HINTS = {
    "buyer": "🔎 <b>Xaridor menyusi</b>\nUy sotib olish yoki ijaraga olish uchun hudud, tur va narx "
             "bo‘yicha qidiring, yoqqan uyni ko‘rishga yoziling. Yangi e’lonlar haqida xabar olish "
             "uchun obuna bo‘ling.",
    "owner": "🏡 <b>Uy egasi menyusi</b>\nUyingizni sotish yoki ijaraga berish uchun e’lon bering, "
             "professional syomka va reklama buyurtma qiling. E’lon holatini «E’lonlarim» bo‘limida "
             "kuzatasiz.",
    "broker": "🤝 <b>Makler menyusi</b>\nObyekt qo‘shing, syomka so‘rang, obyektlar bazasidan "
              "mijozingizga uy toping va murojaatlarni kuzating. Mijozingiz tizimda qayd etiladi — "
              "hech kim olib qo‘ymaydi.",
}


def about_text() -> str:
    links = []
    if config.instagram_url:
        links.append(f"📸 Instagram: {esc(config.instagram_url)}")
    if config.telegram_channel_url:
        links.append(f"✈️ Telegram kanal: {esc(config.telegram_channel_url)}")
    if config.website_url:
        links.append(f"🌐 Sayt: {esc(config.website_url)}")
    links_text = ("\n" + "\n".join(links)) if links else ""
    return (
        f"🏡 <b>{esc(config.company_name)}</b>\n"
        "<i>Birga ishlaymiz. Birga o‘samiz.</i>\n\n"
        "Biz Qashqadaryoda uylarni professional syomka, video va Instagram/Telegram reklamasi "
        "orqali kuchliroq sotamiz.\n\n"
        "<b>Sizda uy bo‘lsa</b> — biz uni kuchliroq sotamiz.\n"
        "<b>Sizda xaridor bo‘lsa</b> — bizda sotiladigan obyektlar bor.\n\n"
        "✅ Har bir obyekt uchun yagona ID (masalan, VU-0248)\n"
        "✅ Obyekt va xaridor manbasi tizimda qayd etiladi\n"
        "✅ Komissiya faqat bitim bo‘lganda, oldindan kelishilgan foiz bo‘yicha\n"
        f"✅ Xizmat hududi: {len(DISTRICTS)} ta shahar va tuman\n\n"
        f"☎️ Aloqa: {esc(config.company_phone)}"
        f"{links_text}"
    )


def contact_text() -> str:
    parts = [f"☎️ <b>Aloqa</b>\n\nTelefon: {esc(config.company_phone)}"]
    if config.instagram_url:
        parts.append(f"Instagram: {esc(config.instagram_url)}")
    if config.telegram_channel_url:
        parts.append(f"Telegram kanal: {esc(config.telegram_channel_url)}")
    if config.website_url:
        parts.append(f"Sayt: {esc(config.website_url)}")
    parts.append("\nSavolingizni shu yerga yozib qoldirishingiz ham mumkin — menejer javob beradi.")
    return "\n".join(parts)


def tariffs_text() -> str:
    return (
        "💰 <b>Uy egasi uchun tariflar</b>\n"
        "Har bir tarifda reklama, sotuv ishtiroki va to‘lov shartlari oldindan tushuntiriladi.\n\n"
        f"<b>1. Faqat reklama — {fmt_money(AD_FEE)}</b>\n"
        "Syomka, video montaj va Instagramga joylashtirish. Sotuv foizi alohida kelishilmasa "
        "olinmaydi.\n\n"
        "<b>2. To‘liq sotuv — 2%</b>\n"
        "Obyekt Voha Uylari tomonidan yuritiladi; hamkor makler sotuvga jalb qilinishi mumkin. "
        "To‘lov faqat uy sotilganda.\n\n"
        f"<b>3. Reklama + savdo — {fmt_money(AD_FEE)} + 1%</b>\n"
        "Reklama oldindan to‘lanadi, sotuv komissiyasi faqat bitim bo‘lsa yuzaga keladi.\n\n"
        "<b>4. Makler orqali hamkorlik</b>\n"
        "Obyekt hamkor makler tomonidan olib kelinadi va xizmat ulushi avvaldan belgilanadi.\n\n"
        "📌 <i>Misol: 500 mln so‘mlik uy uchun 2% = 10 mln so‘m, 1% = 5 mln so‘m.</i>"
    )


def terms_text() -> str:
    return (
        "📜 <b>Hamkorlik shartlari (makler uchun)</b>\n\n"
        "<b>1-model · Voha obyekti</b> — jami 2%\n"
        "Voha 1,2% · makler 0,8%. 500 mln uyda makler ulushi ≈ 4 mln so‘m.\n\n"
        "<b>2-model · Makler obyekti</b> — jami 2%\n"
        "Makler 1,2% · Voha 0,8%. 500 mln uyda makler ulushi ≈ 6 mln so‘m.\n\n"
        "<b>3-model · Reklama 500 ming + 1%</b>\n"
        "Makler 0,5% · Voha 0,5% (+500 ming reklama). 500 mln uyda makler ≈ 2,5 mln so‘m.\n\n"
        "ℹ️ Agar umumiy foiz 2% dan farq qilsa, ulushlar alohida kelishiladi.\n\n"
        "<b>Ishonch kafolatlari</b>\n"
        "• Har bir obyekt uchun yagona ID (VU-0248)\n"
        "• Obyektni kim olib kelgani tizimda qayd etiladi\n"
        "• Xaridor manbasi (makler, Instagram, Telegram, bot, sayt) belgilanadi\n"
        "• Kim qancha olishi sotuvdan oldin kelishiladi\n\n"
        "<b>Ko‘p so‘raladigan savollar</b>\n"
        "❓ <i>Mijozimni olib qo‘ymaysizlarmi?</i> — Obyekt, xaridor manbasi va mas’ul makler "
        "tizimda qayd etiladi.\n"
        "❓ <i>Nega 0,8% beraman?</i> — Prodakshn, reklama, tizim va qo‘shimcha obyektlar bazasidan "
        "foydalanasiz.\n"
        "❓ <i>Uy sotilmasa-chi?</i> — Foizli hamkorlikda komissiya faqat bitim yakunlanganda "
        "olinadi.\n"
        "❓ <i>Barcha uyimni berishim shartmi?</i> — Yo‘q, qaysi obyektlarni kiritishni o‘zingiz "
        "tanlaysiz.\n"
        "❓ <i>Xaridorni siz topsangiz-chi?</i> — Oldindan tanlangan model bo‘yicha ulushlar "
        "shartnomada belgilanadi.\n\n"
        "⚖️ Hamkorlik 2026-yil 8-noyabrdan kuchga kiradigan rieltorlik qoidalarini hisobga olgan "
        "holda shartnoma asosida yuritiladi. Qo‘shilish bepul — komissiya faqat bitimdan."
    )


PRIVACY_NOTE = (
    "🔒 Telefon raqamingiz va shaxsiy ma’lumotlaringiz faqat xizmat ko‘rsatish (e’lon, uy ko‘rish, "
    "bitim) maqsadida, sizning roziligingiz asosida ishlatiladi."
)

HELP_TEXT = (
    "ℹ️ <b>Yordam</b>\n\n"
    "/start — bosh menyu\n"
    "/menu — bosh menyu\n"
    "/role — rolni almashtirish\n"
    "/cancel — joriy amalni bekor qilish\n"
    "/id — ID bo‘yicha obyekt qidirish\n"
    "/sayt — sayt va shaxsiy kabinet havolasi\n"
    "/help — yordam\n\n"
    "Obyekt kodini (masalan, <code>VU-0012</code>) yozsangiz, bot uni darhol ko‘rsatadi."
)
