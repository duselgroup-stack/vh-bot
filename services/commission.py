"""Komissiya hisob-kitobi (Decimal bilan, yaxlitlash xatosiz)."""
from __future__ import annotations

from decimal import Decimal

from constants import MODELS
from utils import fmt_money, fmt_percent, fmt_short, pct_of


def listing_percent(listing: dict) -> Decimal:
    raw = listing.get("commission_percent")
    if raw not in (None, ""):
        return Decimal(str(raw))
    return MODELS.get(listing.get("model") or 0, MODELS[1])["total"]


def calc_split(price: int, model: int, percent: Decimal | None = None,
               with_broker: bool = True) -> dict:
    """Bitim narxidan komissiya va ulushlarni hisoblaydi.

    Agar jami foiz model standartidan farq qilsa, ulushlar proporsional taqsimlanadi
    (keyin admin qo‘lda o‘zgartirishi mumkin). Makler bo‘lmasa, uning ulushi Vohaga qoladi.
    """
    m = MODELS.get(model, MODELS[1])
    total_pct = Decimal(str(percent)) if percent is not None else m["total"]
    if m["total"] > 0 and with_broker:
        broker_pct = m["broker"] * total_pct / m["total"]
    else:
        broker_pct = Decimal("0")
    voha_pct = total_pct - broker_pct
    commission = pct_of(price, total_pct)
    broker_share = pct_of(price, broker_pct)
    return {
        "model": model,
        "total_pct": total_pct,
        "voha_pct": voha_pct,
        "broker_pct": broker_pct,
        "commission": commission,
        "broker_share": broker_share,
        "voha_share": commission - broker_share,
        "ad_fee": m["ad_fee"],
    }


def split_text(price: int, split: dict) -> str:
    lines = [
        f"💰 Bitim narxi: <b>{fmt_money(price)}</b>",
        f"📐 Model: {MODELS[split['model']]['name']}",
        f"％ Jami komissiya: {fmt_percent(split['total_pct'])} = <b>{fmt_money(split['commission'])}</b>",
        f"🏢 Voha ulushi: {fmt_percent(split['voha_pct'])} = {fmt_money(split['voha_share'])}",
        f"🤝 Makler ulushi: {fmt_percent(split['broker_pct'])} = {fmt_money(split['broker_share'])}",
    ]
    if split.get("ad_fee"):
        lines.append(f"📣 Reklama to‘lovi (alohida): {fmt_money(split['ad_fee'])}")
    return "\n".join(lines)


def calculator_text(price: int, deal: str = "s") -> str:
    lines = [f"🧮 <b>Komissiya hisobi</b>\nUy narxi: <b>{fmt_money(price)}</b> ({fmt_short(price)})\n"]
    for model_id in (1, 2, 3):
        m = MODELS[model_id]
        s = calc_split(price, model_id)
        extra = f" + reklama {fmt_short(m['ad_fee'])}" if m["ad_fee"] else ""
        lines.append(
            f"<b>{m['name']}</b>\n"
            f"  Jami {fmt_percent(s['total_pct'])}: {fmt_money(s['commission'])}{extra}\n"
            f"  🏢 Voha {fmt_percent(s['voha_pct'])}: {fmt_money(s['voha_share'])}\n"
            f"  🤝 Makler {fmt_percent(s['broker_pct'])}: {fmt_money(s['broker_share'])}\n"
        )
    lines.append("ℹ️ Umumiy foiz 2% dan farq qilsa, ulushlar alohida kelishiladi.")
    return "\n".join(lines)


def broker_share_hint(listing: dict) -> str:
    """Obyektlar bazasida maklerga «mijoz olib kelsangiz qancha olasiz» ko‘rsatkichi."""
    model = listing.get("model") or 0
    price = listing["price"]
    if listing["deal_type"] == "r":
        return "💼 Ijara bo‘yicha ulush admin bilan alohida kelishiladi."
    if model == 1:
        s = calc_split(price, 1, listing_percent(listing))
        return (f"💼 Mijoz olib kelsangiz ulushingiz: {fmt_percent(s['broker_pct'])} "
                f"≈ <b>{fmt_short(s['broker_share'])}</b>")
    if model == 3:
        s = calc_split(price, 3, listing_percent(listing))
        return (f"💼 Mijoz olib kelsangiz ulushingiz: {fmt_percent(s['broker_pct'])} "
                f"≈ <b>{fmt_short(s['broker_share'])}</b>")
    if model == 2:
        return "💼 Hamkor makler obyekti — ulushlar sotuvdan oldin admin orqali kelishiladi."
    return "💼 Faqat reklama obyekti — sotuv ulushi alohida kelishiladi."
