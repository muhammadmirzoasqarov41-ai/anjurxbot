"""Small authenticated web panel for viewing Firestore user records."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from html import escape

from aiohttp import web

from app.config import settings
from app.services.firebase import firebase_service
from app.utils.logger import logger

_COOKIE = "anjurx_admin"
_PAGE_SIZE = 50


def _signature(value: str) -> str:
    return hmac.new(settings.web_admin_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def _authenticated(request: web.Request) -> bool:
    if not settings.web_admin_key:
        return False
    value = request.cookies.get(_COOKIE, "")
    if ":" not in value:
        return False
    identity, signature = value.split(":", 1)
    return hmac.compare_digest(signature, _signature(identity)) and identity == "admin"


def _login_page(error: str = "") -> web.Response:
    message = f'<p class="error">{escape(error)}</p>' if error else ""
    return web.Response(text=f"""<!doctype html><html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AnjurXBot Admin</title><style>body{{font-family:system-ui;margin:40px;background:#f4f6f8;color:#18212b}}main{{max-width:420px;margin:auto;background:white;padding:28px;border-radius:10px;box-shadow:0 4px 20px #0001}}input,button{{width:100%;padding:11px;margin-top:10px;box-sizing:border-box}}button{{background:#1769aa;color:white;border:0;border-radius:5px}}.error{{color:#b42318}}</style></head><body><main><h1>AnjurXBot</h1><p>Admin panelga kirish</p>{message}<form method="post" action="/login"><input type="password" name="key" placeholder="Admin key" required><button type="submit">Kirish</button></form></main></body></html>""", content_type="text/html")


async def login(request: web.Request) -> web.Response:
    if not settings.web_admin_key:
        return web.json_response({"error": "Web panel sozlanmagan"}, status=503)
    data = await request.post()
    if not hmac.compare_digest(str(data.get("key", "")), settings.web_admin_key):
        return _login_page("Admin key noto'g'ri.")
    response = web.HTTPFound("/")
    response.set_cookie(_COOKIE, f"admin:{_signature('admin')}", httponly=True, samesite="Strict", secure=os.getenv("WEB_ADMIN_SECURE", "1") != "0")
    return response


async def logout(request: web.Request) -> web.Response:
    response = web.HTTPFound("/login")
    response.del_cookie(_COOKIE)
    return response


async def users_page(request: web.Request) -> web.Response:
    if not settings.web_admin_key:
        return web.json_response({"error": "Web panel sozlanmagan"}, status=503)
    if not _authenticated(request):
        return _login_page()
    try:
        page = max(1, int(request.query.get("page", "1")))
    except ValueError:
        page = 1
    users = await firebase_service.list_users(limit=page * _PAGE_SIZE)
    page_users = users[(page - 1) * _PAGE_SIZE:page * _PAGE_SIZE]
    rows = []
    for user in page_users:
        user_id = escape(str(user.get("_id", "")))
        username = escape(str(user.get("username") or "-"))
        name = escape(str(user.get("first_name") or user.get("name") or "-"))
        rows.append(f"<tr><td>{user_id}</td><td>{username}</td><td>{name}</td><td>{escape(str(user.get('created_at') or '-'))}</td></tr>")
    previous = f'<a href="/?page={page - 1}">⬅️ Oldingi</a>' if page > 1 else ""
    next_link = f'<a href="/?page={page + 1}">Keyingi ➡️</a>' if len(users) == page * _PAGE_SIZE else ""
    text = f"""<!doctype html><html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Foydalanuvchilar</title><style>body{{font-family:system-ui;margin:24px;background:#f4f6f8;color:#18212b}}main{{max-width:1100px;margin:auto;background:#fff;padding:24px;border-radius:10px}}header{{display:flex;justify-content:space-between;align-items:center}}table{{border-collapse:collapse;width:100%;margin-top:20px}}th,td{{padding:10px;border-bottom:1px solid #e5e7eb;text-align:left}}th{{background:#eef4f8}}a{{color:#1769aa;text-decoration:none;margin-right:20px}}.muted{{color:#667085}}</style></head><body><main><header><h1>👥 Foydalanuvchilar</h1><a href="/logout">Chiqish</a></header><p class="muted">Ko'rsatilmoqda: {len(page_users)} ta</p><table><thead><tr><th>User ID</th><th>Username</th><th>Ism</th><th>Qo'shilgan vaqt</th></tr></thead><tbody>{''.join(rows) or '<tr><td colspan="4">Hozircha foydalanuvchilar yo‘q.</td></tr>'}</tbody></table><p>{previous}{next_link}</p></main></body></html>"""
    return web.Response(text=text, content_type="text/html")


async def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/", users_page)
    app.router.add_get("/login", lambda request: _login_page())
    app.router.add_post("/login", login)
    app.router.add_get("/logout", logout)
    return app


async def health(request: web.Request) -> web.Response:
    """Render health probe; intentionally exposes no configuration data."""
    return web.json_response({"status": "ok"})


async def run_web_admin() -> None:
    if not settings.web_admin_key:
        raise RuntimeError("WEB_ADMIN_KEY environment variable is required for the web panel")
    firebase_service.initialize()
    app = await create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000")))
    await site.start()
    logger.info("Web admin panel started")
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await firebase_service.close()


if __name__ == "__main__":
    asyncio.run(run_web_admin())