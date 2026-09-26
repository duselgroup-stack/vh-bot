"""SQLite ma’lumotlar bazasi (aiosqlite)."""
from __future__ import annotations

import json
import logging
from typing import Any, Iterable

import aiosqlite

from constants import PUBLIC_STATUSES, QUALIFIED_LEAD_STATUSES
from utils import days_ago_str, listing_code, now_str

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    full_name TEXT,
    username TEXT,
    phone TEXT,
    role TEXT,
    source TEXT,
    consent_at TEXT,
    is_blocked INTEGER DEFAULT 0,
    created_at TEXT,
    last_seen TEXT
);

CREATE TABLE IF NOT EXISTS brokers (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT,
    phone TEXT,
    district TEXT,
    experience TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    approved_at TEXT
);

CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE,
    deal_type TEXT NOT NULL,
    property_type TEXT NOT NULL,
    district TEXT NOT NULL,
    address TEXT,
    rooms INTEGER,
    area TEXT,
    floor TEXT,
    price INTEGER NOT NULL,
    description TEXT,
    photos TEXT DEFAULT '[]',
    video TEXT,
    owner_name TEXT,
    owner_phone TEXT,
    source_type TEXT NOT NULL,
    source_user_id INTEGER,
    broker_id INTEGER,
    model INTEGER DEFAULT 1,
    commission_percent TEXT,
    ad_fee INTEGER DEFAULT 0,
    ad_fee_paid INTEGER DEFAULT 0,
    expenses INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    shooting_requested INTEGER DEFAULT 0,
    reject_reason TEXT,
    channel_message_id INTEGER,
    views INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    published_at TEXT,
    accepted_at TEXT
);

CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    buyer_user_id INTEGER,
    buyer_name TEXT,
    buyer_phone TEXT,
    source TEXT DEFAULT 'bot',
    brought_by INTEGER,
    preferred_time TEXT,
    comment TEXT,
    status TEXT DEFAULT 'new',
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL,
    lead_id INTEGER,
    final_price INTEGER NOT NULL,
    model INTEGER,
    total_percent TEXT,
    commission INTEGER DEFAULT 0,
    voha_share INTEGER DEFAULT 0,
    broker_share INTEGER DEFAULT 0,
    broker_id INTEGER,
    buyer_source TEXT,
    status TEXT DEFAULT 'unpaid',
    created_by INTEGER,
    created_at TEXT,
    paid_at TEXT
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    deal_type TEXT NOT NULL,
    district TEXT,
    property_type TEXT,
    rooms INTEGER DEFAULT 0,
    price_min INTEGER,
    price_max INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS web_tokens (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    used INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS site_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    name TEXT,
    phone TEXT,
    district TEXT,
    comment TEXT,
    status TEXT DEFAULT 'new',
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_listings_status ON listings(status);
CREATE INDEX IF NOT EXISTS idx_listings_search ON listings(deal_type, status, district, property_type);
CREATE INDEX IF NOT EXISTS idx_listings_source_user ON listings(source_user_id);
CREATE INDEX IF NOT EXISTS idx_leads_listing ON leads(listing_id);
CREATE INDEX IF NOT EXISTS idx_leads_brought ON leads(brought_by);
CREATE INDEX IF NOT EXISTS idx_leads_buyer ON leads(buyer_user_id);
CREATE INDEX IF NOT EXISTS idx_subs_user ON subscriptions(user_id);
"""

LISTING_FIELDS = {
    "deal_type", "property_type", "district", "address", "rooms", "area", "floor", "price",
    "description", "photos", "video", "owner_name", "owner_phone", "source_type",
    "source_user_id", "broker_id", "model", "commission_percent", "ad_fee", "ad_fee_paid",
    "expenses", "status", "shooting_requested", "reject_reason", "channel_message_id",
    "views", "published_at", "accepted_at",
}


def _row(row: aiosqlite.Row | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    if "photos" in data:
        try:
            data["photos"] = json.loads(data["photos"] or "[]")
        except (TypeError, ValueError):
            data["photos"] = []
    return data


def _rows(rows: Iterable[aiosqlite.Row]) -> list[dict]:
    return [_row(r) for r in rows]  # type: ignore[misc]


class Database:
    def __init__(self) -> None:
        self.conn: aiosqlite.Connection | None = None
        self.path: str | None = None

    # ------------------------------------------------------------------ core
    async def connect(self, path: str) -> None:
        self.path = path
        self.conn = await aiosqlite.connect(path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self.conn.executescript(SCHEMA)
        await self._migrate()
        await self.conn.commit()
        log.info("Baza ulandi: %s", path)

    async def _migrate(self) -> None:
        """Eski bazaga yangi ustunlarni qo‘shadi (versiya yangilanganda ma’lumot yo‘qolmaydi)."""
        assert self.conn is not None
        async with self.conn.execute("PRAGMA table_info(listings)") as cur:
            columns = {row[1] for row in await cur.fetchall()}
        for column, ddl in (("accepted_at", "TEXT"), ("expenses", "INTEGER DEFAULT 0")):
            if column not in columns:
                await self.conn.execute(f"ALTER TABLE listings ADD COLUMN {column} {ddl}")

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()
            self.conn = None

    async def execute(self, sql: str, params: Iterable[Any] = ()) -> aiosqlite.Cursor:
        assert self.conn is not None, "Baza ulanmagan"
        cur = await self.conn.execute(sql, tuple(params))
        await self.conn.commit()
        return cur

    async def fetchone(self, sql: str, params: Iterable[Any] = ()) -> dict | None:
        assert self.conn is not None, "Baza ulanmagan"
        async with self.conn.execute(sql, tuple(params)) as cur:
            return _row(await cur.fetchone())

    async def fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        assert self.conn is not None, "Baza ulanmagan"
        async with self.conn.execute(sql, tuple(params)) as cur:
            return _rows(await cur.fetchall())

    async def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        assert self.conn is not None, "Baza ulanmagan"
        async with self.conn.execute(sql, tuple(params)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

    # ----------------------------------------------------------------- users
    async def upsert_user(self, user_id: int, full_name: str, username: str | None) -> dict:
        ts = now_str()
        await self.execute(
            """INSERT INTO users (id, full_name, username, created_at, last_seen)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET full_name=excluded.full_name,
                   username=excluded.username, last_seen=excluded.last_seen, is_blocked=0""",
            (user_id, full_name, username, ts, ts),
        )
        return await self.get_user(user_id)  # type: ignore[return-value]

    async def get_user(self, user_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM users WHERE id=?", (user_id,))

    async def set_user_role(self, user_id: int, role: str | None) -> None:
        await self.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))

    async def set_user_phone(self, user_id: int, phone: str) -> None:
        await self.execute(
            "UPDATE users SET phone=?, consent_at=COALESCE(consent_at, ?) WHERE id=?",
            (phone, now_str(), user_id),
        )

    async def set_user_source(self, user_id: int, source: str) -> None:
        await self.execute("UPDATE users SET source=? WHERE id=? AND source IS NULL", (source, user_id))

    async def set_user_blocked(self, user_id: int, blocked: bool = True) -> None:
        await self.execute("UPDATE users SET is_blocked=? WHERE id=?", (1 if blocked else 0, user_id))

    async def user_ids(self, role: str | None = None) -> list[int]:
        if role:
            rows = await self.fetchall(
                "SELECT id FROM users WHERE is_blocked=0 AND role=?", (role,)
            )
        else:
            rows = await self.fetchall("SELECT id FROM users WHERE is_blocked=0")
        return [r["id"] for r in rows]

    # --------------------------------------------------------------- brokers
    async def get_broker(self, user_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM brokers WHERE user_id=?", (user_id,))

    async def save_broker(self, user_id: int, full_name: str, phone: str, district: str,
                          experience: str) -> None:
        await self.execute(
            """INSERT INTO brokers (user_id, full_name, phone, district, experience, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)
               ON CONFLICT(user_id) DO UPDATE SET full_name=excluded.full_name, phone=excluded.phone,
                   district=excluded.district, experience=excluded.experience,
                   status=CASE WHEN brokers.status='approved' THEN 'approved' ELSE 'pending' END""",
            (user_id, full_name, phone, district, experience, now_str()),
        )

    async def set_broker_status(self, user_id: int, status: str) -> None:
        approved_at = now_str() if status == "approved" else None
        await self.execute(
            "UPDATE brokers SET status=?, approved_at=COALESCE(?, approved_at) WHERE user_id=?",
            (status, approved_at, user_id),
        )

    async def list_brokers(self, status: str | None = None) -> list[dict]:
        if status:
            return await self.fetchall(
                "SELECT * FROM brokers WHERE status=? ORDER BY created_at DESC", (status,)
            )
        return await self.fetchall("SELECT * FROM brokers ORDER BY created_at DESC")

    # -------------------------------------------------------------- listings
    async def create_listing(self, **fields: Any) -> dict:
        data = {k: v for k, v in fields.items() if k in LISTING_FIELDS}
        if "photos" in data and not isinstance(data["photos"], str):
            data["photos"] = json.dumps(data["photos"])
        ts = now_str()
        data["created_at"] = ts
        data["updated_at"] = ts
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        cur = await self.execute(f"INSERT INTO listings ({cols}) VALUES ({marks})", data.values())
        listing_id = cur.lastrowid
        await self.execute("UPDATE listings SET code=? WHERE id=?", (listing_code(listing_id), listing_id))
        return await self.get_listing(listing_id)  # type: ignore[return-value]

    async def get_listing(self, listing_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM listings WHERE id=?", (listing_id,))

    async def update_listing(self, listing_id: int, **fields: Any) -> dict | None:
        data = {k: v for k, v in fields.items() if k in LISTING_FIELDS}
        if not data:
            return await self.get_listing(listing_id)
        if "photos" in data and not isinstance(data["photos"], str):
            data["photos"] = json.dumps(data["photos"])
        data["updated_at"] = now_str()
        sets = ", ".join(f"{k}=?" for k in data)
        await self.execute(f"UPDATE listings SET {sets} WHERE id=?", [*data.values(), listing_id])
        return await self.get_listing(listing_id)

    async def add_view(self, listing_id: int) -> None:
        await self.execute("UPDATE listings SET views=views+1 WHERE id=?", (listing_id,))

    async def search_listings(self, deal_type: str, district: str | None = None,
                              property_type: str | None = None, rooms: int = 0,
                              price_min: int | None = None, price_max: int | None = None) -> list[int]:
        sql = ["SELECT id FROM listings WHERE deal_type=? AND status IN ('active','negotiation')"]
        params: list[Any] = [deal_type]
        if district:
            sql.append("AND district=?")
            params.append(district)
        if property_type:
            sql.append("AND property_type=?")
            params.append(property_type)
        if rooms:
            if rooms >= 5:
                sql.append("AND rooms>=5")
            else:
                sql.append("AND rooms=?")
                params.append(rooms)
        if price_min is not None:
            sql.append("AND price>=?")
            params.append(price_min)
        if price_max is not None:
            sql.append("AND price<?")
            params.append(price_max)
        sql.append("ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, published_at DESC, id DESC")
        rows = await self.fetchall(" ".join(sql), params)
        return [r["id"] for r in rows]

    async def listings_by_status(self, *statuses: str, limit: int = 100) -> list[dict]:
        marks = ",".join("?" for _ in statuses)
        return await self.fetchall(
            f"SELECT * FROM listings WHERE status IN ({marks}) ORDER BY id DESC LIMIT ?",
            [*statuses, limit],
        )

    async def user_listings(self, user_id: int) -> list[dict]:
        return await self.fetchall(
            "SELECT * FROM listings WHERE source_user_id=? OR broker_id=? ORDER BY id DESC",
            (user_id, user_id),
        )

    async def base_listings(self, exclude_user: int, deal_type: str | None = None) -> list[dict]:
        sql = ("SELECT * FROM listings WHERE status IN ('active','negotiation') "
               "AND COALESCE(broker_id, 0)<>? AND COALESCE(source_user_id, 0)<>?")
        params: list[Any] = [exclude_user, exclude_user]
        if deal_type:
            sql += " AND deal_type=?"
            params.append(deal_type)
        sql += " ORDER BY published_at DESC, id DESC"
        return await self.fetchall(sql, params)

    async def find_duplicates(self, listing: dict) -> list[dict]:
        """Bir xil hudud/tur/narx yoki bir xil egasi telefoni bo‘lgan boshqa e’lonlar."""
        rows = await self.fetchall(
            """SELECT * FROM listings WHERE id<>? AND status NOT IN ('rejected','archived') AND (
                   (owner_phone IS NOT NULL AND owner_phone<>'' AND owner_phone=?)
                   OR (district=? AND property_type=? AND deal_type=? AND COALESCE(rooms,0)=COALESCE(?,0)
                       AND ABS(price-?) <= ?*0.05)
               ) ORDER BY id DESC LIMIT 5""",
            (listing["id"], listing.get("owner_phone") or "", listing["district"],
             listing["property_type"], listing["deal_type"], listing.get("rooms"),
             listing["price"], listing["price"]),
        )
        return rows

    async def count_listings(self, *statuses: str) -> int:
        if not statuses:
            return int(await self.scalar("SELECT COUNT(*) FROM listings") or 0)
        marks = ",".join("?" for _ in statuses)
        return int(await self.scalar(
            f"SELECT COUNT(*) FROM listings WHERE status IN ({marks})", statuses) or 0)

    # ----------------------------------------------------------------- leads
    async def create_lead(self, listing_id: int, buyer_user_id: int | None, buyer_name: str,
                          buyer_phone: str, source: str, brought_by: int | None = None,
                          preferred_time: str | None = None, comment: str | None = None) -> dict:
        ts = now_str()
        cur = await self.execute(
            """INSERT INTO leads (listing_id, buyer_user_id, buyer_name, buyer_phone, source,
                   brought_by, preferred_time, comment, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)""",
            (listing_id, buyer_user_id, buyer_name, buyer_phone, source, brought_by,
             preferred_time, comment, ts, ts),
        )
        return await self.get_lead(cur.lastrowid)  # type: ignore[return-value]

    async def get_lead(self, lead_id: int) -> dict | None:
        return await self.fetchone("SELECT * FROM leads WHERE id=?", (lead_id,))

    async def find_lead(self, listing_id: int, phone: str | None = None,
                        user_id: int | None = None) -> dict | None:
        return await self.fetchone(
            """SELECT * FROM leads WHERE listing_id=? AND status<>'lost'
               AND ((? IS NOT NULL AND buyer_phone=?) OR (? IS NOT NULL AND buyer_user_id=?))
               ORDER BY id LIMIT 1""",
            (listing_id, phone, phone, user_id, user_id),
        )

    async def set_lead_status(self, lead_id: int, status: str) -> None:
        await self.execute("UPDATE leads SET status=?, updated_at=? WHERE id=?",
                           (status, now_str(), lead_id))

    async def listing_leads(self, listing_id: int) -> list[dict]:
        return await self.fetchall("SELECT * FROM leads WHERE listing_id=? ORDER BY id DESC",
                                   (listing_id,))

    async def buyer_leads(self, user_id: int) -> list[dict]:
        return await self.fetchall(
            """SELECT leads.*, listings.code AS code FROM leads
               JOIN listings ON listings.id=leads.listing_id
               WHERE buyer_user_id=? AND brought_by IS NULL ORDER BY leads.id DESC LIMIT 30""",
            (user_id,),
        )

    async def broker_leads(self, broker_id: int) -> list[dict]:
        """Makler olib kelgan mijozlar + uning obyektlariga kelgan murojaatlar."""
        return await self.fetchall(
            """SELECT leads.*, listings.code AS code, listings.broker_id AS listing_broker,
                      listings.source_user_id AS listing_owner
               FROM leads JOIN listings ON listings.id=leads.listing_id
               WHERE leads.brought_by=? OR listings.broker_id=? OR listings.source_user_id=?
               ORDER BY leads.id DESC LIMIT 50""",
            (broker_id, broker_id, broker_id),
        )

    async def leads_by_status(self, *statuses: str, limit: int = 50) -> list[dict]:
        marks = ",".join("?" for _ in statuses)
        return await self.fetchall(
            f"""SELECT leads.*, listings.code AS code FROM leads
                JOIN listings ON listings.id=leads.listing_id
                WHERE leads.status IN ({marks}) ORDER BY leads.id DESC LIMIT ?""",
            [*statuses, limit],
        )

    async def lead_counts(self, listing_id: int) -> dict[str, int]:
        rows = await self.fetchall(
            "SELECT status, COUNT(*) AS n FROM leads WHERE listing_id=? GROUP BY status",
            (listing_id,),
        )
        return {r["status"]: r["n"] for r in rows}

    # ----------------------------------------------------------------- deals
    async def create_deal(self, **fields: Any) -> dict:
        allowed = {"listing_id", "lead_id", "final_price", "model", "total_percent", "commission",
                   "voha_share", "broker_share", "broker_id", "buyer_source", "created_by"}
        data = {k: v for k, v in fields.items() if k in allowed}
        data["created_at"] = now_str()
        data["status"] = "unpaid" if data.get("commission") else "paid"
        if data["status"] == "paid":
            data["paid_at"] = data["created_at"]
        cols = ", ".join(data)
        marks = ", ".join("?" for _ in data)
        cur = await self.execute(f"INSERT INTO deals ({cols}) VALUES ({marks})", data.values())
        return await self.get_deal(cur.lastrowid)  # type: ignore[return-value]

    async def get_deal(self, deal_id: int) -> dict | None:
        return await self.fetchone(
            """SELECT deals.*, listings.code AS code FROM deals
               JOIN listings ON listings.id=deals.listing_id WHERE deals.id=?""",
            (deal_id,),
        )

    async def listing_deal(self, listing_id: int) -> dict | None:
        return await self.fetchone(
            "SELECT * FROM deals WHERE listing_id=? ORDER BY id DESC LIMIT 1", (listing_id,))

    async def unpaid_deals(self) -> list[dict]:
        return await self.fetchall(
            """SELECT deals.*, listings.code AS code FROM deals
               JOIN listings ON listings.id=deals.listing_id
               WHERE deals.status='unpaid' ORDER BY deals.id DESC LIMIT 50"""
        )

    async def mark_deal_paid(self, deal_id: int) -> None:
        await self.execute("UPDATE deals SET status='paid', paid_at=? WHERE id=?",
                           (now_str(), deal_id))

    async def broker_deals(self, broker_id: int) -> list[dict]:
        return await self.fetchall(
            """SELECT deals.*, listings.code AS code FROM deals
               JOIN listings ON listings.id=deals.listing_id
               WHERE deals.broker_id=? ORDER BY deals.id DESC""",
            (broker_id,),
        )

    # --------------------------------------------------------- subscriptions
    async def add_subscription(self, user_id: int, deal_type: str, district: str | None,
                               property_type: str | None, rooms: int, price_min: int | None,
                               price_max: int | None) -> dict:
        existing = await self.fetchone(
            """SELECT * FROM subscriptions WHERE user_id=? AND deal_type=? AND district IS ?
               AND property_type IS ? AND rooms=? AND price_min IS ? AND price_max IS ?""",
            (user_id, deal_type, district, property_type, rooms, price_min, price_max),
        )
        if existing:
            return existing
        cur = await self.execute(
            """INSERT INTO subscriptions (user_id, deal_type, district, property_type, rooms,
                   price_min, price_max, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, deal_type, district, property_type, rooms, price_min, price_max, now_str()),
        )
        return await self.fetchone("SELECT * FROM subscriptions WHERE id=?", (cur.lastrowid,))  # type: ignore[return-value]

    async def user_subscriptions(self, user_id: int) -> list[dict]:
        return await self.fetchall("SELECT * FROM subscriptions WHERE user_id=? ORDER BY id", (user_id,))

    async def delete_subscription(self, sub_id: int, user_id: int) -> None:
        await self.execute("DELETE FROM subscriptions WHERE id=? AND user_id=?", (sub_id, user_id))

    async def matching_subscribers(self, listing: dict) -> list[int]:
        rows = await self.fetchall(
            """SELECT DISTINCT s.user_id FROM subscriptions s JOIN users u ON u.id=s.user_id
               WHERE u.is_blocked=0 AND s.deal_type=?
                 AND (s.district IS NULL OR s.district=?)
                 AND (s.property_type IS NULL OR s.property_type=?)
                 AND (s.rooms=0 OR (s.rooms>=5 AND ?>=5) OR s.rooms=?)
                 AND (s.price_min IS NULL OR ?>=s.price_min)
                 AND (s.price_max IS NULL OR ?<s.price_max)""",
            (listing["deal_type"], listing["district"], listing["property_type"],
             listing.get("rooms") or 0, listing.get("rooms") or 0, listing["price"], listing["price"]),
        )
        return [r["user_id"] for r in rows]

    # ----------------------------------------------------------------- stats
    async def stats(self, days: int = 30) -> dict[str, Any]:
        since = days_ago_str(days)
        s: dict[str, Any] = {}
        s["users"] = await self.scalar("SELECT COUNT(*) FROM users") or 0
        s["users_new"] = await self.scalar("SELECT COUNT(*) FROM users WHERE created_at>=?", (since,)) or 0
        roles = await self.fetchall("SELECT role, COUNT(*) AS n FROM users GROUP BY role")
        s["roles"] = {r["role"]: r["n"] for r in roles}
        s["brokers_approved"] = await self.scalar(
            "SELECT COUNT(*) FROM brokers WHERE status='approved'") or 0
        s["brokers_pending"] = await self.scalar(
            "SELECT COUNT(*) FROM brokers WHERE status='pending'") or 0
        # Faol hamkor — davr ichida real obyekt yoki mijoz olib kelgan makler (34-slayd)
        s["brokers_active"] = await self.scalar(
            """SELECT COUNT(DISTINCT uid) FROM (
                   SELECT source_user_id AS uid FROM listings WHERE source_type='broker' AND created_at>=?
                   UNION SELECT brought_by AS uid FROM leads WHERE brought_by IS NOT NULL AND created_at>=?
               ) JOIN brokers ON brokers.user_id=uid WHERE brokers.status='approved'""", (since, since)) or 0
        statuses = await self.fetchall("SELECT status, COUNT(*) AS n FROM listings GROUP BY status")
        s["listings"] = {r["status"]: r["n"] for r in statuses}
        s["listings_new"] = await self.scalar(
            "SELECT COUNT(*) FROM listings WHERE created_at>=?", (since,)) or 0
        s["leads_total"] = await self.scalar("SELECT COUNT(*) FROM leads") or 0
        s["leads_new"] = await self.scalar("SELECT COUNT(*) FROM leads WHERE created_at>=?", (since,)) or 0
        q_marks = ",".join("?" for _ in QUALIFIED_LEAD_STATUSES)
        s["leads_qualified"] = await self.scalar(
            f"SELECT COUNT(*) FROM leads WHERE status IN ({q_marks})", QUALIFIED_LEAD_STATUSES) or 0
        sources = await self.fetchall("SELECT source, COUNT(*) AS n FROM leads GROUP BY source ORDER BY n DESC")
        s["lead_sources"] = {r["source"]: r["n"] for r in sources}
        s["deals"] = await self.scalar("SELECT COUNT(*) FROM deals") or 0
        s["deals_period"] = await self.scalar("SELECT COUNT(*) FROM deals WHERE created_at>=?", (since,)) or 0
        s["commission_total"] = await self.scalar("SELECT COALESCE(SUM(commission),0) FROM deals") or 0
        s["commission_paid"] = await self.scalar(
            "SELECT COALESCE(SUM(commission),0) FROM deals WHERE status='paid'") or 0
        s["commission_unpaid"] = await self.scalar(
            "SELECT COALESCE(SUM(commission),0) FROM deals WHERE status='unpaid'") or 0
        s["voha_paid"] = await self.scalar(
            "SELECT COALESCE(SUM(voha_share),0) FROM deals WHERE status='paid'") or 0
        s["broker_paid"] = await self.scalar(
            "SELECT COALESCE(SUM(broker_share),0) FROM deals WHERE status='paid'") or 0
        s["ad_fees"] = await self.scalar(
            "SELECT COALESCE(SUM(ad_fee),0) FROM listings WHERE ad_fee_paid=1") or 0
        s["expenses"] = await self.scalar("SELECT COALESCE(SUM(expenses),0) FROM listings") or 0
        s["top_listings"] = await self.fetchall(
            """SELECT l.code, l.views, (SELECT COUNT(*) FROM leads WHERE listing_id=l.id) AS leads
               FROM listings l WHERE l.status IN ('active','negotiation')
               ORDER BY leads DESC, l.views DESC LIMIT 5""")
        s["profit_listings"] = await self.fetchall(
            """SELECT l.code, COALESCE(SUM(d.voha_share),0) AS income, l.expenses,
                      CASE WHEN l.ad_fee_paid=1 THEN l.ad_fee ELSE 0 END AS ad_fee
               FROM listings l JOIN deals d ON d.listing_id=l.id
               GROUP BY l.id ORDER BY l.id DESC LIMIT 5""")
        return s

    async def broker_stats(self, broker_id: int) -> dict[str, Any]:
        s: dict[str, Any] = {}
        rows = await self.fetchall(
            "SELECT status, COUNT(*) AS n FROM listings WHERE source_user_id=? OR broker_id=? GROUP BY status",
            (broker_id, broker_id))
        s["listings"] = {r["status"]: r["n"] for r in rows}
        s["clients"] = await self.scalar("SELECT COUNT(*) FROM leads WHERE brought_by=?", (broker_id,)) or 0
        s["incoming"] = await self.scalar(
            """SELECT COUNT(*) FROM leads JOIN listings ON listings.id=leads.listing_id
               WHERE (listings.broker_id=? OR listings.source_user_id=?)
               AND COALESCE(leads.brought_by,0)<>?""", (broker_id, broker_id, broker_id)) or 0
        s["deals"] = await self.scalar("SELECT COUNT(*) FROM deals WHERE broker_id=?", (broker_id,)) or 0
        s["earned_paid"] = await self.scalar(
            "SELECT COALESCE(SUM(broker_share),0) FROM deals WHERE broker_id=? AND status='paid'",
            (broker_id,)) or 0
        s["earned_unpaid"] = await self.scalar(
            "SELECT COALESCE(SUM(broker_share),0) FROM deals WHERE broker_id=? AND status='unpaid'",
            (broker_id,)) or 0
        s["views"] = await self.scalar(
            "SELECT COALESCE(SUM(views),0) FROM listings WHERE source_user_id=? OR broker_id=?",
            (broker_id, broker_id)) or 0
        return s

    async def backup(self, dest_path: str) -> None:
        """Bazaning to‘liq, izchil nusxasini yaratadi (ishlab turgan paytda ham xavfsiz)."""
        import os
        if os.path.exists(dest_path):
            os.remove(dest_path)
        await self.execute("VACUUM INTO ?", (dest_path,))

    # ------------------------------------------------------------- sayt
    async def catalog(self, deal_type: str | None = None, district: str | None = None,
                      property_type: str | None = None, rooms: int = 0,
                      price_min: int | None = None, price_max: int | None = None,
                      sort: str = "new", limit: int = 12, offset: int = 0) -> tuple[list[dict], int]:
        where = ["status IN ('active','negotiation')"]
        params: list[Any] = []
        if deal_type in ("s", "r"):
            where.append("deal_type=?")
            params.append(deal_type)
        if district:
            where.append("district=?")
            params.append(district)
        if property_type:
            where.append("property_type=?")
            params.append(property_type)
        if rooms:
            if rooms >= 5:
                where.append("rooms>=5")
            else:
                where.append("rooms=?")
                params.append(rooms)
        if price_min:
            where.append("price>=?")
            params.append(price_min)
        if price_max:
            where.append("price<=?")
            params.append(price_max)
        order = {
            "cheap": "price ASC, id DESC",
            "expensive": "price DESC, id DESC",
            "popular": "views DESC, id DESC",
        }.get(sort, "CASE status WHEN 'active' THEN 0 ELSE 1 END, COALESCE(published_at, created_at) DESC, id DESC")
        cond = " AND ".join(where)
        total = int(await self.scalar(f"SELECT COUNT(*) FROM listings WHERE {cond}", params) or 0)
        rows = await self.fetchall(
            f"SELECT * FROM listings WHERE {cond} ORDER BY {order} LIMIT ? OFFSET ?",
            [*params, limit, offset])
        return rows, total

    async def public_counts(self) -> dict[str, int]:
        return {
            "active": await self.count_listings("active", "negotiation"),
            "closed": await self.count_listings("sold", "rented"),
            "brokers": int(await self.scalar("SELECT COUNT(*) FROM brokers WHERE status='approved'") or 0),
            "districts": int(await self.scalar(
                "SELECT COUNT(DISTINCT district) FROM listings WHERE status IN ('active','negotiation')") or 0),
        }

    async def district_counts(self) -> dict[str, int]:
        rows = await self.fetchall(
            """SELECT district, COUNT(*) AS n FROM listings WHERE status IN ('active','negotiation')
               GROUP BY district ORDER BY n DESC""")
        return {r["district"]: r["n"] for r in rows}

    async def get_listing_by_code(self, code: str) -> dict | None:
        return await self.fetchone("SELECT * FROM listings WHERE code=?", (code.upper(),))

    async def create_web_token(self, user_id: int, minutes: int = 15) -> str:
        import secrets
        from datetime import timedelta
        from utils import now
        token = secrets.token_urlsafe(24)
        expires = (now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        await self.execute("DELETE FROM web_tokens WHERE expires_at<? OR used=1", (now_str(),))
        await self.execute("INSERT INTO web_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
                           (token, user_id, expires))
        return token

    async def consume_web_token(self, token: str) -> int | None:
        row = await self.fetchone(
            "SELECT * FROM web_tokens WHERE token=? AND used=0 AND expires_at>=?", (token, now_str()))
        if not row:
            return None
        await self.execute("UPDATE web_tokens SET used=1 WHERE token=?", (token,))
        return row["user_id"]

    async def add_site_request(self, kind: str, name: str, phone: str, district: str | None,
                               comment: str | None) -> dict:
        cur = await self.execute(
            """INSERT INTO site_requests (kind, name, phone, district, comment, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""", (kind, name, phone, district, comment, now_str()))
        return await self.fetchone("SELECT * FROM site_requests WHERE id=?", (cur.lastrowid,))  # type: ignore[return-value]

    async def site_requests(self, limit: int = 30) -> list[dict]:
        return await self.fetchall("SELECT * FROM site_requests ORDER BY id DESC LIMIT ?", (limit,))

    async def recent_leads(self, limit: int = 30) -> list[dict]:
        return await self.fetchall(
            """SELECT leads.*, listings.code AS code FROM leads
               JOIN listings ON listings.id=leads.listing_id ORDER BY leads.id DESC LIMIT ?""", (limit,))

    async def table(self, name: str) -> list[dict]:
        assert name in {"users", "brokers", "listings", "leads", "deals", "subscriptions", "site_requests"}
        return await self.fetchall(f"SELECT * FROM {name} ORDER BY rowid")


db = Database()

__all__ = ["db", "Database", "PUBLIC_STATUSES"]
