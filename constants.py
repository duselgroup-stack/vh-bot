"""Biznes konstantalari: hududlar, mulk turlari, hamkorlik modellari, statuslar."""
from __future__ import annotations

from decimal import Decimal

# Qashqadaryo viloyati hududlari (indeks callbackda ishlatiladi — tartibni o‘zgartirmang,
# yangi hududni faqat oxiriga qo‘shing).
DISTRICTS: list[str] = [
    "Qarshi shahri",
    "Shahrisabz shahri",
    "Qarshi tumani",
    "Shahrisabz tumani",
    "Kitob tumani",
    "Yakkabog‘ tumani",
    "Chiroqchi tumani",
    "G‘uzor tumani",
    "Dehqonobod tumani",
    "Kasbi tumani",
    "Koson tumani",
    "Ko‘kdala tumani",
    "Mirishkor tumani",
    "Muborak tumani",
    "Nishon tumani",
    "Qamashi tumani",
]

DEAL_TYPES = {"s": "Sotuv", "r": "Ijara"}
DEAL_ICONS = {"s": "🏷", "r": "🔑"}

PROPERTY_TYPES = {
    "h": "Hovli uy",
    "a": "Kvartira",
    "l": "Yer uchastkasi",
    "c": "Tijorat obyekti",
}
PROPERTY_ICONS = {"h": "🏡", "a": "🏢", "l": "🌳", "c": "🏪"}

# Xonalar: 0 — farqi yo‘q, 5 — 5 va undan ko‘p
ROOM_CHOICES = [1, 2, 3, 4, 5]

MLN = 1_000_000

# Narx oraliqlari (so‘m). None — chegara yo‘q.
PRICE_RANGES: dict[str, list[tuple[int | None, int | None, str]]] = {
    "s": [
        (None, 300 * MLN, "300 mln gacha"),
        (300 * MLN, 500 * MLN, "300–500 mln"),
        (500 * MLN, 800 * MLN, "500–800 mln"),
        (800 * MLN, 1500 * MLN, "800 mln – 1,5 mlrd"),
        (1500 * MLN, None, "1,5 mlrd dan yuqori"),
    ],
    "r": [
        (None, 3 * MLN, "3 mln gacha / oy"),
        (3 * MLN, 5 * MLN, "3–5 mln / oy"),
        (5 * MLN, 8 * MLN, "5–8 mln / oy"),
        (8 * MLN, None, "8 mln dan yuqori / oy"),
    ],
}

AD_FEE = 500_000  # Bir martalik reklama narxi (so‘m)

# Hamkorlik modellari (taqdimot, 20–23-slaydlar).
# total — jami komissiya foizi, voha/broker — ulushlar (foizda), ad_fee — oldindan to‘lov.
MODELS: dict[int, dict] = {
    0: {
        "name": "Faqat reklama",
        "short": "Reklama 500 ming",
        "total": Decimal("0"),
        "voha": Decimal("0"),
        "broker": Decimal("0"),
        "ad_fee": AD_FEE,
        "desc": "Syomka, video va Instagramga joylashtirish — 500 000 so‘m. "
                "Sotuv foizi alohida kelishilmasa olinmaydi.",
    },
    1: {
        "name": "1-model · Voha obyekti",
        "short": "2% (Voha 1,2% / makler 0,8%)",
        "total": Decimal("2"),
        "voha": Decimal("1.2"),
        "broker": Decimal("0.8"),
        "ad_fee": 0,
        "desc": "Obyekt Voha Uylariniki, xaridorni makler olib keladi. "
                "Jami 2%: Voha 1,2%, makler 0,8%.",
    },
    2: {
        "name": "2-model · Makler obyekti",
        "short": "2% (makler 1,2% / Voha 0,8%)",
        "total": Decimal("2"),
        "voha": Decimal("0.8"),
        "broker": Decimal("1.2"),
        "ad_fee": 0,
        "desc": "Obyektni makler olib keladi, Voha prodakshn, reklama va xaridor bilan yordam beradi. "
                "Jami 2%: makler 1,2%, Voha 0,8%.",
    },
    3: {
        "name": "3-model · Reklama + 1%",
        "short": "500 ming + 1% (0,5% / 0,5%)",
        "total": Decimal("1"),
        "voha": Decimal("0.5"),
        "broker": Decimal("0.5"),
        "ad_fee": AD_FEE,
        "desc": "Reklama uchun 500 000 so‘m oldindan, bitim bo‘lsa 1%: makler 0,5%, Voha 0,5%.",
    },
}

# Uy egasi tariflari (29-slayd) → model
TARIFFS_SALE: dict[str, dict] = {
    "ad": {"title": "📣 Faqat reklama — 500 000 so‘m", "model": 0, "shooting": True},
    "full": {"title": "🤝 To‘liq sotuv — 2%", "model": 1, "shooting": True},
    "adplus": {"title": "🚀 Reklama + savdo — 500 000 so‘m + 1%", "model": 3, "shooting": True},
}
TARIFFS_RENT: dict[str, dict] = {
    "ad": {"title": "📣 Faqat reklama — 500 000 so‘m", "model": 0, "shooting": True},
    "full": {"title": "🤝 Ijarachi topib berish — shartlar kelishiladi", "model": 1, "shooting": False},
}

SOURCES = {
    "bot": "🤖 Bot",
    "instagram": "📸 Instagram",
    "telegram": "✈️ Telegram",
    "sayt": "🌐 Sayt",
    "makler": "🤝 Makler",
    "boshqa": "📌 Boshqa",
}
# Deep-link qisqartmalari: t.me/BOT?start=ig  yoki  ?start=VU-0012_ig
SOURCE_ALIASES = {
    "ig": "instagram", "insta": "instagram", "instagram": "instagram",
    "tg": "telegram", "telegram": "telegram", "kanal": "telegram",
    "web": "sayt", "site": "sayt", "sayt": "sayt",
    "mk": "makler", "makler": "makler",
}

OBJECT_SOURCES = {"voha": "🏢 Voha Uylari", "broker": "🤝 Makler", "owner": "👤 Uy egasi"}

LISTING_STATUSES = {
    "pending": "⏳ Moderatsiyada",
    "shooting": "🎬 Syomka kutilmoqda",
    "active": "✅ Faol",
    "negotiation": "🤝 Muzokarada",
    "sold": "🏁 Sotilgan",
    "rented": "🔑 Ijaraga berilgan",
    "rejected": "❌ Rad etilgan",
    "archived": "📦 Arxivda",
}
PUBLIC_STATUSES = ("active", "negotiation")
CLOSED_STATUSES = ("sold", "rented")

LEAD_STATUSES = {
    "new": "🆕 Yangi",
    "contacted": "📞 Bog‘lanildi",
    "scheduled": "📅 Ko‘rish belgilandi",
    "viewed": "👀 Uy ko‘rildi",
    "negotiation": "🤝 Muzokara",
    "won": "🏆 Bitim bo‘ldi",
    "lost": "❌ Rad etdi",
}
QUALIFIED_LEAD_STATUSES = ("contacted", "scheduled", "viewed", "negotiation", "won")

BROKER_STATUSES = {
    "pending": "⏳ Ko‘rib chiqilmoqda",
    "approved": "✅ Tasdiqlangan hamkor",
    "rejected": "❌ Rad etilgan",
    "blocked": "⛔ Bloklangan",
}

ROLES = {"buyer": "🔎 Xaridor / ijarachi", "owner": "🏡 Uy egasi", "broker": "🤝 Makler"}

# Bitimning 7 bosqichi (27-slayd)
DEAL_STAGES = [
    "Obyektni qabul qilish (egasi, makler, model)",
    "Syomka va media tayyorlash",
    "E’lon joylashtirish",
    "Mijoz manbasini qayd etish",
    "Uy ko‘rishni tashkil qilish",
    "Bitim natijasini belgilash",
    "Komissiyani hisoblash va undirish",
]

VIEWING_TIMES = {
    "today": "Bugun",
    "tomorrow": "Ertaga",
    "weekend": "Dam olish kunlari",
    "call": "Qo‘ng‘iroq qilib kelishamiz",
}

MAX_PHOTOS = 10
MAX_SUBSCRIPTIONS = 10
PAGE_SIZE = 8
