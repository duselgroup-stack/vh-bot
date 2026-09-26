"""Inline tugmalar uchun CallbackData fabrikalari (64 baytdan oshmaydi)."""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class Nav(CallbackData, prefix="nav"):
    to: str  # main | noop | close


class Form(CallbackData, prefix="frm"):
    f: str          # maydon: tariff, ptype, district, rooms, media, shoot, confirm ...
    v: str = ""


class Srch(CallbackData, prefix="sf"):
    s: str          # qadam: d (hudud), t (tur), r (xona), p (narx), res, sub, new
    dl: str = "s"   # s — sotuv, r — ijara
    d: int = -1     # hudud indeksi, -1 — barchasi
    t: str = "x"    # mulk turi, x — barchasi
    r: int = 0      # xonalar, 0 — farqi yo‘q
    p: int = -1     # narx oralig‘i indeksi, -1 — farqi yo‘q
    pg: int = 0     # sahifa


class Lst(CallbackData, prefix="ls"):
    a: str          # lead | media | owner-status ...
    id: int
    v: str = ""


class Ld(CallbackData, prefix="ld"):
    a: str          # st (status o‘zgartirish), view
    id: int
    v: str = ""


class Adm(CallbackData, prefix="adm"):
    a: str
    id: int = 0
    v: str = ""


class Brk(CallbackData, prefix="brk"):
    a: str
    id: int = 0
    v: str = ""


class Sub(CallbackData, prefix="sub"):
    a: str          # del
    id: int = 0
