"""Yordamchi funksiyalar: pul formatlash, narx va telefonni tahlil qilish, vaqt."""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

TZ = timezone(timedelta(hours=5))  # Toshkent vaqti (UTC+5)


def now() -> datetime:
    return datetime.now(TZ)


def now_str() -> str:
    return now().strftime("%Y-%m-%d %H:%M:%S")


def days_ago_str(days: int) -> str:
    return (now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def short_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return datetime.strptime(value[:16], "%Y-%m-%d %H:%M").strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return value


def esc(value) -> str:
    """HTML uchun xavfsiz matn."""
    if value is None:
        return ""
    return html.escape(str(value), quote=False)


def fmt_money(amount: int | float | Decimal | None) -> str:
    """650000000 → '650 000 000 so‘m'"""
    if amount is None:
        return "—"
    value = int(Decimal(str(amount)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return f"{value:,}".replace(",", " ") + " so‘m"


def fmt_short(amount: int | float | Decimal | None) -> str:
    """650000000 → '650 mln', 1500000000 → '1,5 mlrd', 350000 → '350 ming'"""
    if amount is None:
        return "—"
    value = Decimal(str(amount))
    if value >= 1_000_000_000:
        num, unit = value / Decimal(1_000_000_000), "mlrd"
    elif value >= 1_000_000:
        num, unit = value / Decimal(1_000_000), "mln"
    elif value >= 1_000:
        num, unit = value / Decimal(1_000), "ming"
    else:
        return f"{int(value)} so‘m"
    num = num.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP).normalize()
    text = f"{num:f}".replace(".", ",")
    return f"{text} {unit}"


def fmt_percent(value: Decimal | float | str | None) -> str:
    if value is None:
        return "—"
    dec = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP).normalize()
    return f"{dec:f}".replace(".", ",") + "%"


_MULTIPLIERS = [
    (("mlrd", "milliard", "млрд"), 1_000_000_000),
    (("mln", "million", "mil", "млн", "m"), 1_000_000),
    (("ming", "k", "тыс", "min"), 1_000),
]


def parse_price(text: str | None) -> int | None:
    """Foydalanuvchi yozgan narxni so‘mga aylantiradi.

    Misollar: '650000000', '650 000 000', '650 mln', '1,2 mlrd', '4.5mln', '350 ming'.
    """
    if not text:
        return None
    raw = text.lower().strip()
    raw = raw.replace("so‘m", "").replace("so'm", "").replace("som", "").replace("сум", "")
    raw = raw.replace("’", "").replace("'", "").strip()
    multiplier = 1
    for words, mult in _MULTIPLIERS:
        for word in words:
            if re.search(rf"\d\s*{re.escape(word)}\b", raw) or raw.endswith(word):
                multiplier = mult
                raw = re.sub(rf"\s*{re.escape(word)}\b", "", raw)
                break
        if multiplier != 1:
            break
    raw = raw.replace(" ", "").replace(" ", "")
    if multiplier != 1:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "").replace(".", "")
    if not re.fullmatch(r"\d+(\.\d+)?", raw):
        return None
    try:
        value = int(Decimal(raw) * multiplier)
    except Exception:  # noqa: BLE001
        return None
    if value <= 0 or value > 10**14:
        return None
    return value


def parse_decimal(text: str | None) -> Decimal | None:
    if not text:
        return None
    raw = text.replace("%", "").replace(",", ".").strip()
    try:
        value = Decimal(raw)
    except Exception:  # noqa: BLE001
        return None
    if value < 0 or value > 100:
        return None
    return value


def normalize_phone(text: str | None) -> str | None:
    """'+998 90 123-45-67', '901234567', '998901234567' → '+998901234567'."""
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    if 10 <= len(digits) <= 15 and text.strip().startswith("+"):
        return "+" + digits
    return None


def listing_code(listing_id: int) -> str:
    return f"VU-{listing_id:04d}"


def parse_code(text: str | None) -> int | None:
    """'VU-0012', 'vu12', '12' → 12"""
    if not text:
        return None
    match = re.fullmatch(r"\s*(?:vu)?[\s\-_]*0*(\d{1,7})\s*", text.strip(), flags=re.IGNORECASE)
    if not match:
        return None
    value = int(match.group(1))
    return value or None


def progress_bar(done: int, total: int = 7) -> str:
    return "🟩" * done + "⬜" * (total - done) + f"  {done}/{total}"


def pct_of(amount: int | Decimal, percent: Decimal) -> int:
    value = Decimal(amount) * Decimal(percent) / Decimal(100)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
