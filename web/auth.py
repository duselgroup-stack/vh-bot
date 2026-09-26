"""Sayt xavfsizligi: imzolangan sessiya cookie, forma tokeni (CSRF), so‘rovlar chastotasi."""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
from collections import defaultdict, deque

from aiohttp import web

from config import config

SESSION_COOKIE = "vu_session"
SESSION_DAYS = 30


def _sign(payload: str) -> str:
    return hmac.new(config.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def make_session(user_id: int) -> str:
    expires = int(time.time()) + SESSION_DAYS * 86400
    payload = f"{user_id}:{expires}"
    raw = f"{payload}:{_sign(payload)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def read_session(value: str | None) -> int | None:
    if not value:
        return None
    try:
        raw = base64.urlsafe_b64decode(value.encode()).decode()
        user_id, expires, sig = raw.split(":")
    except (ValueError, UnicodeDecodeError):
        return None
    if not hmac.compare_digest(sig, _sign(f"{user_id}:{expires}")):
        return None
    if int(expires) < time.time():
        return None
    return int(user_id)


def set_session(response: web.StreamResponse, user_id: int) -> None:
    response.set_cookie(
        SESSION_COOKIE, make_session(user_id), max_age=SESSION_DAYS * 86400, httponly=True,
        samesite="Lax", secure=config.site_url.startswith("https://"), path="/")


def current_user_id(request: web.Request) -> int | None:
    return read_session(request.cookies.get(SESSION_COOKIE))


# ------------------------------------------------------------- forma tokeni
def form_token() -> str:
    ts = str(int(time.time()))
    return f"{ts}.{_sign('form:' + ts)[:32]}"


def check_form_token(token: str | None, max_age: int = 6 * 3600) -> bool:
    if not token or "." not in token:
        return False
    ts, sig = token.split(".", 1)
    if not ts.isdigit() or not hmac.compare_digest(sig, _sign("form:" + ts)[:32]):
        return False
    return 0 <= time.time() - int(ts) <= max_age


# --------------------------------------------------------- chastota cheklovi
class RateLimiter:
    def __init__(self, limit: int, period: float) -> None:
        self.limit = limit
        self.period = period
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        queue = self.hits[key]
        while queue and now - queue[0] > self.period:
            queue.popleft()
        if len(queue) >= self.limit:
            return False
        queue.append(now)
        if len(self.hits) > 20_000:
            self.hits = defaultdict(deque, {k: v for k, v in self.hits.items() if v})
        return True


def client_ip(request: web.Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.headers.get("X-Real-IP") or request.remote or "?"
