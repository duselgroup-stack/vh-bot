"""Komissiya kalkulyatori va tariflar."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import keyboards as kb
from filters import TEXT_INPUT
from services.commission import calculator_text
from states import CalcForm
from texts import Btn, tariffs_text
from utils import parse_price

router = Router(name="calc")


@router.message(F.text == Btn.CALC)
async def calc_start(message: Message, state: FSMContext) -> None:
    await state.set_state(CalcForm.price)
    await message.answer("🧮 Uy narxini yozing — uchala hamkorlik modeli bo‘yicha ulushlarni hisoblab beraman.\n"
                         "<i>Masalan: 500 mln</i>", reply_markup=kb.cancel_kb())


@router.message(CalcForm.price, TEXT_INPUT)
async def calc_result(message: Message, state: FSMContext) -> None:
    price = parse_price(message.text)
    if not price:
        await message.answer("❗️ Narxni tushunmadim. Masalan: <code>500 mln</code>")
        return
    await message.answer(calculator_text(price) + "\n\n🔁 Yana narx yozing yoki «❌ Bekor qilish».")


@router.message(F.text == Btn.TARIFFS)
async def tariffs(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(tariffs_text())
