"""FSM holatlari."""
from aiogram.fsm.state import State, StatesGroup


class ListingForm(StatesGroup):
    deal = State()
    tariff = State()
    ptype = State()
    district = State()
    address = State()
    rooms = State()
    area = State()
    floor = State()
    price = State()
    description = State()
    media = State()
    owner_name = State()
    owner_phone = State()
    shooting = State()
    confirm = State()


class LeadForm(StatesGroup):
    phone = State()
    time = State()
    comment = State()


class BrokerClient(StatesGroup):
    """Makler «Mijozim bor» — o‘z mijozini obyektga qayd etadi."""
    name = State()
    phone = State()
    comment = State()


class BrokerReg(StatesGroup):
    full_name = State()
    phone = State()
    district = State()
    experience = State()
    terms = State()


class SearchId(StatesGroup):
    code = State()


class CalcForm(StatesGroup):
    price = State()


class AdminInput(StatesGroup):
    reject_reason = State()
    price = State()
    percent = State()
    expenses = State()
    media = State()
    broadcast = State()
    broadcast_confirm = State()
    reply = State()


class DealForm(StatesGroup):
    price = State()
    lead = State()
    source = State()
    broker = State()
    confirm = State()
    manual_total = State()
    manual_broker = State()
