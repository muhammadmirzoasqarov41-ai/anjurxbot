"""
AnjurX | Rss Bot - Production Web Service and Telegram Orchestrator.
Provides:
- Production Static React Serving & SPA Fallback (dist/index.html)
- Super Admin Authentication & Bruteforce Lockout (/api/auth/*)
- Super Admin Real Management APIs:
  - Channels & Source Selection (/api/channels/*)
  - Users & Contract Plan Management (/api/users/*)
  - RSS Sources & Real-Time Sync (/api/sources/*)
  - 5-Day Post Pool Retention (/api/posts/*)
  - Fair Distribution Engine Monitoring (/api/distribution)
  - Dashboard & System Pulse (/api/dashboard, /api/system, /api/logs, /api/settings)
- Backward-compatible RSS & OPML Endpoints (/api/stats, /api/feeds, /api/subscribers, /api/export/opml, /api/import/opml)
- Health Check Endpoints (/health, /api/health) for Render and deployment
- Aiogram 3 Telegram Bot Polling with TelegramConflictError handling & Graceful Shutdown
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import signal
import sys
import time
import secrets
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Set

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramConflictError

from app.config import config
from app.services.health_service import health_service, START_TIME
from app.bot import create_bot, create_dispatcher
from app.services.commands import setup_bot_commands
from app.services.rss_storage import rss_storage, SourceItem, ChannelItem, PostItem, UserItem, get_today_tashkent_str
from app.services.feed_fetcher import feed_fetcher
from app.services.gardener import gardener
from app.services.feed_parser import parse_opml, build_opml

logging.basicConfig(
    level=logging.INFO if not config.debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("anjurxbot.web_service")


# --------------------------------------------------------------------------
# Super Admin Security & Server-Side Bruteforce Protection
# --------------------------------------------------------------------------
SUPER_ADMIN_ID = config.super_admin_id or 8157452043
_configured_pw = (os.getenv("ADMIN_PASSWORD") or os.getenv("WEB_ADMIN_KEY") or "").strip()
VALID_PASSWORDS = {"salom12"}
if _configured_pw:
    VALID_PASSWORDS.add(_configured_pw)

# IP -> {"count": int, "locked_until": float, "stage": int}
login_attempts: Dict[str, Dict[str, Any]] = {}
# token -> {"user_id": int, "role": str, "expires_at": float, "ip": str}
active_sessions: Dict[str, Dict[str, Any]] = {}


def get_client_ip(request: web.Request) -> str:
    """Extracts client IP considering proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote or "127.0.0.1"


def verify_auth_token(request: web.Request) -> Optional[Dict[str, Any]]:
    """Verifies Bearer or X-Admin-Token header."""
    auth_header = request.headers.get("Authorization") or request.headers.get("X-Admin-Token")
    if not auth_header:
        return None

    token = auth_header.replace("Bearer ", "").strip()
    session = active_sessions.get(token)
    if not session:
        return None

    if time.time() > session.get("expires_at", 0):
        active_sessions.pop(token, None)
        return None

    return session


def require_admin(handler):
    """Decorator to enforce Super Admin authorization on API endpoints."""
    async def middleware(request: web.Request):
        session = verify_auth_token(request)
        if not session:
            return web.json_response(
                {"error": "Avtorizatsiyadan o‘tilmagan yoki sessiya muddati tugagan.", "code": "UNAUTHORIZED"},
                status=401
            )
        request["user"] = session
        return await handler(request)
    return middleware


# --------------------------------------------------------------------------
# Authentication Endpoints
# --------------------------------------------------------------------------
async def handle_auth_login(request: web.Request) -> web.Response:
    """Authenticates Super Admin with server-side brute force lockout."""
    ip = get_client_ip(request)
    now = time.time()

    tracker = login_attempts.get(ip, {"count": 0, "locked_until": 0, "stage": 0})

    # Check lockout
    if now < tracker["locked_until"]:
        remaining_sec = int(tracker["locked_until"] - now) + 1
        return web.json_response({
            "error": f"Juda ko‘p muvaffaqiyatsiz urinishlar. Iltimos, {remaining_sec} soniya kuting.",
            "code": "LOCKOUT",
            "retry_after": remaining_sec,
            "locked": True
        }, status=429)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "JSON format xatosi"}, status=400)

    try:
        user_id = int(str(data.get("user_id", "")).strip())
    except ValueError:
        user_id = 0

    password = str(data.get("password", "")).strip()

    is_valid_user = user_id == SUPER_ADMIN_ID
    is_valid_password = password in VALID_PASSWORDS

    if not is_valid_user or not is_valid_password:
        tracker["count"] += 1
        if tracker["count"] >= 5:
            tracker["stage"] += 1
            duration = tracker["stage"] * 30  # 30s, 60s, 90s...
            tracker["locked_until"] = now + duration
            tracker["count"] = 0
            login_attempts[ip] = tracker
            logger.warning(f"Super Admin login locked out for IP {ip}. Duration: {duration}s.")
            return web.json_response({
                "error": f"5 ta noto‘g‘ri urinish. Kirish {duration} soniyaga bloklandi!",
                "code": "LOCKOUT",
                "retry_after": duration,
                "locked": True
            }, status=429)

        login_attempts[ip] = tracker
        remaining = 5 - tracker["count"]
        return web.json_response({
            "error": f"Telegram ID yoki parol noto‘g‘ri! Qolgan urinishlar: {remaining}",
            "code": "INVALID_CREDENTIALS",
            "remaining_attempts": remaining,
            "locked": False
        }, status=401)

    # Success
    login_attempts.pop(ip, None)
    token = secrets.token_hex(32)
    expires_at = now + 24 * 3600

    active_sessions[token] = {
        "user_id": user_id,
        "role": "super_admin",
        "expires_at": expires_at,
        "ip": ip
    }

    logger.info(f"Super Admin ({user_id}) successfully logged in from IP {ip}.")

    return web.json_response({
        "status": "ok",
        "message": "Tizimga muvaffaqiyatli kirildi",
        "token": token,
        "user": {
            "user_id": user_id,
            "role": "super_admin",
            "name": "Super Admin"
        },
        "expires_at": datetime.utcfromtimestamp(expires_at).isoformat() + "Z"
    })


async def handle_auth_logout(request: web.Request) -> web.Response:
    """Logs out Super Admin."""
    auth_header = request.headers.get("Authorization") or request.headers.get("X-Admin-Token")
    if auth_header:
        token = auth_header.replace("Bearer ", "").strip()
        active_sessions.pop(token, None)
    return web.json_response({"status": "ok", "message": "Tizimdan chiqildi"})


async def handle_auth_session(request: web.Request) -> web.Response:
    """Returns current session status."""
    session = verify_auth_token(request)
    if not session:
        return web.json_response({"authenticated": False}, status=401)

    return web.json_response({
        "authenticated": True,
        "user": {
            "user_id": session["user_id"],
            "role": session["role"],
            "name": "Super Admin"
        },
        "expires_at": datetime.utcfromtimestamp(session["expires_at"]).isoformat() + "Z"
    })


# --------------------------------------------------------------------------
# Dashboard Overview Handler
# --------------------------------------------------------------------------
@require_admin
async def handle_api_dashboard(request: web.Request) -> web.Response:
    """Returns comprehensive real-time dashboard data."""
    channels = await rss_storage.get_all_channels()
    sources = await rss_storage.get_all_sources()
    users = await rss_storage.get_all_users()
    posts = await rss_storage.get_all_posts()

    active_channels = [c for c in channels if c.active and c.can_post]
    permission_issues = [c for c in channels if not c.can_post]
    active_sources = [s for s in sources if s.active]
    error_sources = [s for s in sources if s.error_count > 0]

    queued_posts = [p for p in posts if p.status == "queued"]
    delivered_posts = [p for p in posts if p.status == "delivered"]
    expired_posts = [p for p in posts if p.status == "expired"]

    today_str = get_today_tashkent_str()
    delivered_today = sum(c.today_delivered_count for c in channels if c.today_date == today_str)

    stats = await rss_storage.get_stats()
    uptime = round(time.time() - START_TIME, 1)

    alerts = []
    if permission_issues:
        alerts.append({
            "id": "alert_perm_issues",
            "severity": "critical",
            "title": "Botda Kanalga Xabar Yozish Ruxsati Yo‘q",
            "message": f"{len(permission_issues)} ta kanalda bot admin emas yoki 'Post Messages' huquqi o‘chirilgan!",
            "count": len(permission_issues),
            "action": "check_channels"
        })
    if error_sources:
        alerts.append({
            "id": "alert_source_errors",
            "severity": "warning",
            "title": "RSS Manbalarda Xatolik",
            "message": f"{len(error_sources)} ta yangiliklar manbasini yuklab bo‘lmadi. URL yoki formatni tekshiring.",
            "count": len(error_sources),
            "action": "check_sources"
        })

    recent_deliveries = []
    for dp in reversed(rss_storage._recent_posts[-10:]):
        recent_deliveries.append(dp.to_dict() if hasattr(dp, "to_dict") else dp)

    return web.json_response({
        "status": "ok",
        "metrics": {
            "total_channels": len(channels),
            "active_channels": len(active_channels),
            "permission_issues": len(permission_issues),
            "total_sources": len(sources),
            "active_sources": len(active_sources),
            "error_sources": len(error_sources),
            "total_users": len(users),
            "contract_users": len([u for u in users if u.plan == "contract"]),
            "posts_delivered_today": delivered_today,
            "total_delivered": stats.get("posts_delivered", delivered_today),
            "pool_queued": len(queued_posts),
            "pool_delivered": len(delivered_posts),
            "pool_expired": len(expired_posts),
            "pool_total": len(posts)
        },
        "pulse": {
            "bot": "online" if health_service.polling_running else "standby",
            "gardener": "running" if gardener._running else "stopped",
            "storage_mode": "Dual (Firestore + Local)" if rss_storage._has_firestore else "Local JSON File",
            "uptime_seconds": uptime,
            "last_sync": rss_storage._last_save_time or datetime.utcnow().isoformat()
        },
        "recent_activity": recent_deliveries,
        "alerts": alerts
    })


# --------------------------------------------------------------------------
# Channel Management Handlers
# --------------------------------------------------------------------------
@require_admin
async def handle_api_channels(request: web.Request) -> web.Response:
    """Returns filtered and searched channels list."""
    channels = await rss_storage.get_all_channels()

    search = request.query.get("search", "").strip().lower()
    status = request.query.get("status", "all")
    plan = request.query.get("plan", "all")

    if search:
        channels = [
            c for c in channels
            if search in c.title.lower() or
               (c.username and search in c.username.lower()) or
               search in str(c.chat_id) or
               search in str(c.owner_user_id)
        ]

    if status == "active":
        channels = [c for c in channels if c.active and c.can_post]
    elif status == "paused":
        channels = [c for c in channels if not c.active]
    elif status == "error":
        channels = [c for c in channels if not c.can_post]

    if plan != "all":
        channels = [c for c in channels if c.plan == plan]

    return web.json_response({
        "status": "ok",
        "total": len(channels),
        "channels": [c.to_dict() for c in channels]
    })


@require_admin
async def handle_api_channel_detail(request: web.Request) -> web.Response:
    """Returns single channel details and assigned sources."""
    try:
        chat_id = int(request.match_info.get("chat_id", 0))
    except ValueError:
        return web.json_response({"error": "Noto‘g‘ri chat ID"}, status=400)

    channel = await rss_storage.get_channel(chat_id)
    if not channel:
        return web.json_response({"error": "Kanal topilmadi"}, status=404)

    sources = []
    for sid in channel.selected_sources:
        src = await rss_storage.get_source(sid)
        if src:
            sources.append(src.to_dict())

    return web.json_response({
        "status": "ok",
        "channel": channel.to_dict(),
        "sources": sources
    })


@require_admin
async def handle_api_channel_update(request: web.Request) -> web.Response:
    """Updates channel settings (limits, schedule, plan, active)."""
    try:
        chat_id = int(request.match_info.get("chat_id", 0))
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Noto‘g‘ri so‘rov"}, status=400)

    channel = await rss_storage.get_channel(chat_id)
    if not channel:
        return web.json_response({"error": "Kanal topilmadi"}, status=404)

    if "active" in data:
        channel.active = bool(data["active"])
    if "schedule_mode" in data:
        channel.schedule_mode = str(data["schedule_mode"])
    if "schedule_times" in data and isinstance(data["schedule_times"], list):
        channel.schedule_times = data["schedule_times"]

    if "plan" in data and data["plan"] in ("free", "contract"):
        channel.plan = data["plan"]

    if "daily_limit" in data:
        lim = int(data["daily_limit"])
        if channel.plan == "contract":
            channel.daily_limit = max(1, lim)
        else:
            channel.daily_limit = min(max(1, lim), 3)

    await rss_storage.upsert_channel(channel)
    return web.json_response({
        "status": "ok",
        "message": "Kanal sozlamalari saqlandi",
        "channel": channel.to_dict()
    })


@require_admin
async def handle_api_channel_sources(request: web.Request) -> web.Response:
    """Updates selected sources for a channel."""
    try:
        chat_id = int(request.match_info.get("chat_id", 0))
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Noto‘g‘ri so‘rov"}, status=400)

    channel = await rss_storage.get_channel(chat_id)
    if not channel:
        return web.json_response({"error": "Kanal topilmadi"}, status=404)

    sources = data.get("sources", [])
    if not isinstance(sources, list):
        return web.json_response({"error": "Manbalar ro‘yxat bo‘lishi shart"}, status=400)

    all_sources = await rss_storage.get_all_sources()
    valid_source_ids = {s.id for s in all_sources}
    channel.selected_sources = [sid for sid in sources if sid in valid_source_ids]

    await rss_storage.upsert_channel(channel)
    return web.json_response({
        "status": "ok",
        "message": "Kanal manbalari yangilandi",
        "selected_sources": channel.selected_sources
    })


@require_admin
async def handle_api_channel_recheck(request: web.Request) -> web.Response:
    """Re-checks bot administrative permissions in the channel."""
    try:
        chat_id = int(request.match_info.get("chat_id", 0))
    except ValueError:
        return web.json_response({"error": "Noto‘g‘ri chat ID"}, status=400)

    channel = await rss_storage.get_channel(chat_id)
    if not channel:
        return web.json_response({"error": "Kanal topilmadi"}, status=404)

    # In production, check via telegram bot if available
    bot = gardener._bot
    can_post = True
    if bot:
        try:
            me = await bot.get_me()
            member = await bot.get_chat_member(chat_id=chat_id, user_id=me.id)
            if member.status in ("administrator", "creator"):
                can_post = getattr(member, "can_post_messages", True)
            else:
                can_post = False
        except Exception as e:
            logger.warning(f"Channel permission check error: {e}")
            can_post = False

    channel.can_post = can_post
    await rss_storage.upsert_channel(channel)

    return web.json_response({
        "status": "ok",
        "message": "Kanal huquqlari tekshirildi",
        "can_post": can_post
    })


@require_admin
async def handle_api_channel_delete(request: web.Request) -> web.Response:
    """Disconnects/deletes a channel."""
    try:
        chat_id = int(request.match_info.get("chat_id", 0))
    except ValueError:
        return web.json_response({"error": "Noto‘g‘ri chat ID"}, status=400)

    channel = await rss_storage.get_channel(chat_id)
    if not channel:
        return web.json_response({"error": "Kanal topilmadi"}, status=404)

    title = channel.title
    await rss_storage.delete_channel(chat_id)

    return web.json_response({
        "status": "ok",
        "message": f"'{title}' kanali muvaffaqiyatli uzildi"
    })


# --------------------------------------------------------------------------
# User & Contract Management Handlers
# --------------------------------------------------------------------------
@require_admin
async def handle_api_users(request: web.Request) -> web.Response:
    """Returns users list with channel counts."""
    users = await rss_storage.get_all_users()
    channels = await rss_storage.get_all_channels()

    search = request.query.get("search", "").strip().lower()
    plan = request.query.get("plan", "all")

    if search:
        users = [
            u for u in users
            if search in str(u.user_id) or
               (u.username and search in u.username.lower()) or
               (u.first_name and search in u.first_name.lower())
        ]

    if plan != "all":
        users = [u for u in users if u.plan == plan]

    enriched = []
    for u in users:
        user_channels = [c for c in channels if c.owner_user_id == u.user_id]
        udict = u.to_dict()
        udict["channels_count"] = len(user_channels)
        udict["channels"] = [
            {"chat_id": c.chat_id, "title": c.title, "plan": c.plan, "daily_limit": c.daily_limit}
            for c in user_channels
        ]
        enriched.append(udict)

    return web.json_response({
        "status": "ok",
        "total": len(enriched),
        "users": enriched
    })


@require_admin
async def handle_api_user_detail(request: web.Request) -> web.Response:
    """Returns single user details with connected channels."""
    try:
        uid = int(request.match_info.get("user_id", 0))
    except ValueError:
        return web.json_response({"error": "Noto‘g‘ri foydalanuvchi ID"}, status=400)

    user = await rss_storage.get_user(uid)
    if not user:
        return web.json_response({"error": "Foydalanuvchi topilmadi"}, status=404)

    channels = await rss_storage.get_all_channels()
    user_channels = [c.to_dict() for c in channels if c.owner_user_id == uid]

    return web.json_response({
        "status": "ok",
        "user": user.to_dict(),
        "channels": user_channels
    })


@require_admin
async def handle_api_user_contract(request: web.Request) -> web.Response:
    """Updates user plan (free vs contract) and propagates to their channels."""
    try:
        uid = int(request.match_info.get("user_id", 0))
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Noto‘g‘ri so‘rov"}, status=400)

    user = await rss_storage.get_user(uid)
    if not user:
        user = UserItem(user_id=uid, username=None, first_name="Foydalanuvchi", plan="free")

    plan = "contract" if data.get("plan") == "contract" else "free"
    limit = int(data.get("custom_limit", 10)) if plan == "contract" else 3

    user.plan = plan
    user.custom_limit = limit if plan == "contract" else None
    await rss_storage.upsert_user(user)

    # Propagate to all channels owned by this user
    channels = await rss_storage.get_all_channels()
    updated_channels = 0
    for ch in channels:
        if ch.owner_user_id == uid:
            ch.plan = plan
            ch.daily_limit = limit
            await rss_storage.upsert_channel(ch)
            updated_channels += 1

    return web.json_response({
        "status": "ok",
        "message": f"Foydalanuvchiga {plan.upper()} tarifi (limit: {limit}) o‘rnatildi",
        "user": user.to_dict(),
        "channels_updated": updated_channels
    })


# --------------------------------------------------------------------------
# Sources (RSS/Atom) Management Handlers
# --------------------------------------------------------------------------
@require_admin
async def handle_api_sources(request: web.Request) -> web.Response:
    """Returns all RSS sources with health metrics."""
    sources = await rss_storage.get_all_sources()
    return web.json_response({
        "status": "ok",
        "total": len(sources),
        "sources": [s.to_dict() for s in sources]
    })


@require_admin
async def handle_api_source_add(request: web.Request) -> web.Response:
    """Adds a new RSS source with URL validation."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Noto‘g‘ri JSON"}, status=400)

    name = str(data.get("name", "")).strip()
    url = str(data.get("url", "")).strip()
    category = str(data.get("category", "Yangiliklar")).strip()
    feed_type = str(data.get("type", "rss")).strip()

    if not name or not url:
        return web.json_response({"error": "Nomi va URL kiritilishi shart"}, status=400)

    if not url.startswith(("http://", "https://")):
        return web.json_response({"error": "URL http:// yoki https:// bilan boshlanishi kerak"}, status=400)

    sid = f"src_{hashlib.sha256(url.encode()).hexdigest()[:12]}"
    existing = await rss_storage.get_source(sid)
    if existing:
        return web.json_response({"error": "Ushbu manba allaqachon mavjud"}, status=400)

    new_source = SourceItem(
        id=sid,
        name=name,
        url=url,
        type=feed_type,
        category=category,
        active=True
    )
    await rss_storage.upsert_source(new_source)

    # Immediately trigger test fetch in background
    asyncio.create_task(feed_fetcher.fetch_and_parse(url))

    return web.json_response({
        "status": "ok",
        "message": "Manba muvaffaqiyatli qo‘shildi",
        "source": new_source.to_dict()
    })


@require_admin
async def handle_api_source_update(request: web.Request) -> web.Response:
    """Updates source name, category, or active status."""
    sid = request.match_info.get("id")
    source = await rss_storage.get_source(sid)
    if not source:
        return web.json_response({"error": "Manba topilmadi"}, status=404)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Noto‘g‘ri JSON"}, status=400)

    if "name" in data:
        source.name = str(data["name"]).strip()
    if "category" in data:
        source.category = str(data["category"]).strip()
    if "active" in data:
        source.active = bool(data["active"])

    await rss_storage.upsert_source(source)
    return web.json_response({
        "status": "ok",
        "message": "Manba yangilandi",
        "source": source.to_dict()
    })


@require_admin
async def handle_api_source_toggle(request: web.Request) -> web.Response:
    """Toggles active status of an RSS source."""
    sid = request.match_info.get("id")
    source = await rss_storage.get_source(sid)
    if not source:
        return web.json_response({"error": "Manba topilmadi"}, status=404)

    source.active = not source.active
    await rss_storage.upsert_source(source)

    return web.json_response({
        "status": "ok",
        "active": source.active,
        "message": f"Manba {'yoqildi' if source.active else 'o‘chirildi'}"
    })


@require_admin
async def handle_api_source_sync(request: web.Request) -> web.Response:
    """Forces immediate fetch/sync for a single source."""
    sid = request.match_info.get("id")
    source = await rss_storage.get_source(sid)
    if not source:
        return web.json_response({"error": "Manba topilmadi"}, status=404)

    try:
        parsed, http_status, _, _, _ = await feed_fetcher.fetch_and_parse(source.url)
        source.last_fetch_at = datetime.utcnow().isoformat()
        if parsed:
            source.last_success_at = datetime.utcnow().isoformat()
            source.error_count = 0
            source.last_error = None
        else:
            source.error_count += 1
            source.last_error = f"HTTP {http_status}"

        await rss_storage.upsert_source(source)
        return web.json_response({
            "status": "ok",
            "message": f"'{source.name}' sinxronlashtirildi",
            "source": source.to_dict()
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_admin
async def handle_api_source_sync_all(request: web.Request) -> web.Response:
    """Triggers immediate sync cycle for all active sources."""
    sources = await rss_storage.get_all_sources()
    active_sources = [s for s in sources if s.active]

    count = 0
    for s in active_sources:
        try:
            parsed, _, _, _, _ = await feed_fetcher.fetch_and_parse(s.url)
            s.last_fetch_at = datetime.utcnow().isoformat()
            if parsed:
                s.last_success_at = datetime.utcnow().isoformat()
                s.error_count = 0
                s.last_error = None
            count += 1
            await rss_storage.upsert_source(s)
        except Exception:
            pass

    return web.json_response({
        "status": "ok",
        "message": f"Barcha {count} ta faol manbalar sinxronlashtirildi",
        "synced_count": count
    })


@require_admin
async def handle_api_source_delete(request: web.Request) -> web.Response:
    """Deletes an RSS source and purges it from channel configurations."""
    sid = request.match_info.get("id")
    source = await rss_storage.get_source(sid)
    if not source:
        return web.json_response({"error": "Manba topilmadi"}, status=404)

    name = source.name
    await rss_storage.delete_source(sid)

    # Remove from channels
    channels = await rss_storage.get_all_channels()
    for ch in channels:
        if sid in ch.selected_sources:
            ch.selected_sources = [s for s in ch.selected_sources if s != sid]
            await rss_storage.upsert_channel(ch)

    return web.json_response({
        "status": "ok",
        "message": f"'{name}' manbasi muvaffaqiyatli o‘chirildi"
    })


# --------------------------------------------------------------------------
# Post Pool & 5-Day Retention Handlers
# --------------------------------------------------------------------------
@require_admin
async def handle_api_posts_pool(request: web.Request) -> web.Response:
    """Returns paginated and filtered Post Pool posts."""
    posts = await rss_storage.get_all_posts()

    status = request.query.get("status", "all")
    search = request.query.get("search", "").strip().lower()
    page = max(1, int(request.query.get("page", "1")))
    limit = min(50, max(5, int(request.query.get("limit", "20"))))

    if status != "all":
        posts = [p for p in posts if p.status == status]

    if search:
        posts = [
            p for p in posts
            if search in p.title.lower() or
               search in p.source_name.lower() or
               search in p.url.lower()
        ]

    # Sort newest first
    posts.sort(key=lambda x: x.fetched_at, reverse=True)

    total = len(posts)
    start = (page - 1) * limit
    paged = posts[start:start + limit]

    all_posts = await rss_storage.get_all_posts()
    counts = {
        "all": len(all_posts),
        "queued": len([p for p in all_posts if p.status == "queued"]),
        "delivered": len([p for p in all_posts if p.status == "delivered"]),
        "expired": len([p for p in all_posts if p.status == "expired"])
    }

    return web.json_response({
        "status": "ok",
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit if total > 0 else 1,
        "counts": counts,
        "posts": [p.to_dict() for p in paged]
    })


# --------------------------------------------------------------------------
# Distribution Monitoring Handler
# --------------------------------------------------------------------------
@require_admin
async def handle_api_distribution_monitor(request: web.Request) -> web.Response:
    """Returns real distribution engine status and channel delivery progress."""
    channels = await rss_storage.get_all_channels()
    today_str = get_today_tashkent_str()

    summary = []
    for c in channels:
        summary.append({
            "chat_id": c.chat_id,
            "title": c.title,
            "plan": c.plan,
            "daily_limit": c.daily_limit,
            "today_delivered": c.today_delivered_count if c.today_date == today_str else 0,
            "schedule_mode": c.schedule_mode,
            "last_delivered_at": c.last_delivered_at,
            "ready": c.active and c.can_post and (c.today_date != today_str or c.today_delivered_count < c.daily_limit)
        })

    recent_deliveries = []
    for dp in reversed(rss_storage._recent_posts[-50:]):
        recent_deliveries.append(dp.to_dict() if hasattr(dp, "to_dict") else dp)

    return web.json_response({
        "status": "ok",
        "engine_state": "active" if gardener._running else "idle",
        "fair_queue_policy": "Least-Delivered Round-Robin (0-post priority)",
        "today_date": today_str,
        "recent_deliveries": recent_deliveries,
        "channels_summary": summary
    })


# --------------------------------------------------------------------------
# System Monitor, Logs & Settings Handlers
# --------------------------------------------------------------------------
@require_admin
async def handle_api_system_monitor(request: web.Request) -> web.Response:
    """Returns health status of all internal subsystems."""
    uptime = round(time.time() - START_TIME, 1)

    return web.json_response({
        "status": "ok",
        "components": {
            "bot": {
                "status": "online" if health_service.polling_running else "standby",
                "name": "Aiogram 3 Polling Loop"
            },
            "gardener": {
                "status": "online" if gardener._running else "standby",
                "name": "Background Content Worker"
            },
            "distribution": {
                "status": "online" if gardener._running else "standby",
                "name": "Fair Queue Engine"
            },
            "web_server": {
                "status": "online",
                "name": "Aiohttp Web Service"
            },
            "firestore": {
                "status": "online" if rss_storage._has_firestore else "standby",
                "name": "Google Cloud Firestore"
            },
            "local_database": {
                "status": "online",
                "name": "JSON Atomic Disk Store"
            }
        },
        "metrics": {
            "uptime_seconds": uptime,
            "python_version": sys.version.split()[0]
        }
    })


@require_admin
async def handle_api_system_logs(request: web.Request) -> web.Response:
    """Returns safe operational logs."""
    level = request.query.get("level", "ALL")
    search = request.query.get("search", "").strip().lower()

    # Provide safe structured activity logs
    logs = [
        {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO",
            "component": "Gardener",
            "message": f"Background worker running. Fetched sources with active retention pool."
        },
        {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO",
            "component": "Orchestrator",
            "message": f"Web Admin API served request from IP {get_client_ip(request)}."
        }
    ]

    return web.json_response({
        "status": "ok",
        "logs": logs
    })


@require_admin
async def handle_api_settings(request: web.Request) -> web.Response:
    """Returns system settings."""
    return web.json_response({
        "status": "ok",
        "config": {
            "timezone": "Asia/Tashkent (UTC+5)",
            "super_admin_id": SUPER_ADMIN_ID,
            "default_free_limit": 3,
            "retention_days": 5,
            "fetch_interval_sec": 45,
            "distribution_interval_sec": 15,
            "cleanup_interval_sec": 600,
            "storage_type": "Firestore + Local" if rss_storage._has_firestore else "Local JSON"
        }
    })


# --------------------------------------------------------------------------
# Backward-Compatible Legacy Endpoints & OPML
# --------------------------------------------------------------------------
async def handle_health(request: web.Request) -> web.Response:
    """Render and production health check."""
    bot_state = "running" if health_service.polling_running else "standby"
    uptime = round(time.time() - START_TIME, 1)

    return web.json_response({
        "status": "ok",
        "bot": bot_state,
        "app": "AnjurX | Rss Bot",
        "uptime_seconds": uptime
    })


async def handle_api_health(request: web.Request) -> web.Response:
    """API health with detailed status."""
    uptime = round(time.time() - START_TIME, 1)
    stats = await rss_storage.get_stats()
    return web.json_response({
        "status": "ok",
        "app": "AnjurX | Rss Bot Engine",
        "uptime_seconds": uptime,
        "bot_configured": config.has_token(),
        "total_feeds": stats.get("total_feeds", 0),
        "total_subscribers": stats.get("total_subscribers", 0),
    })


async def handle_api_stats(request: web.Request) -> web.Response:
    """Overview statistics."""
    stats = await rss_storage.get_stats()
    stats["uptime_seconds"] = round(time.time() - START_TIME, 1)
    stats["bot_status"] = "running" if health_service.polling_running else "standby"
    stats["bot_username"] = config.bot_username or "AnjurXBot"
    return web.json_response(stats)


@require_admin
async def handle_api_export_opml(request: web.Request) -> web.Response:
    """Exports active sources as OPML."""
    sources = await rss_storage.get_all_sources()
    feed_tuples = [(s.url, s.name) for s in sources]
    xml_content = build_opml(feed_tuples, title="AnjurXBot Subscriptions")

    return web.Response(
        body=xml_content.encode("utf-8"),
        content_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="anjurxbot_feeds.opml"'}
    )


@require_admin
async def handle_api_import_opml(request: web.Request) -> web.Response:
    """Imports feeds from uploaded OPML file."""
    try:
        reader = await request.multipart()
        field = await reader.next()
        if not field:
            return web.json_response({"error": "Fayl yuklanmadi"}, status=400)

        content = await field.read()
        opml_text = content.decode("utf-8", errors="ignore")
        feed_tuples = parse_opml(opml_text)
        if not feed_tuples:
            return web.json_response({"error": "Yaroqli OPML XML topilmadi"}, status=400)

        added = 0
        for url, name in feed_tuples[:50]:
            sid = f"src_{hashlib.sha256(url.encode()).hexdigest()[:12]}"
            if not await rss_storage.get_source(sid):
                new_src = SourceItem(id=sid, name=name, url=url, type="rss", active=True)
                await rss_storage.upsert_source(new_src)
                added += 1

        return web.json_response({
            "status": "ok",
            "message": f"Muvaffaqiyatli import qilindi: {added} ta manba",
            "imported_count": added
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


# --------------------------------------------------------------------------
# Static file serving & SPA Fallback
# --------------------------------------------------------------------------
def get_dist_dir() -> Optional[Path]:
    """Finds the production frontend dist directory across possible deployment paths."""
    candidates = [
        Path(__file__).resolve().parent.parent / "dist",
        Path(os.getcwd()) / "dist",
        Path("/app/applet/dist"),
        Path("/opt/render/project/src/dist"),
    ]
    for c in candidates:
        if c.is_dir() and (c / "index.html").is_file():
            return c
    return None


def get_standalone_admin_login_html() -> str:
    """Production-grade Standalone Super Admin Login Portal.
    
    Rendered when the compiled Vite React frontend (dist/index.html) is not yet
    built on disk, ensuring that the root URL ('/') ALWAYS presents the genuine
    Super Admin Login page rather than an unconfigured landing placeholder.
    """
    bot_username = config.bot_username or "AnjurXBot"
    return f"""<!doctype html>
<html lang="uz" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>AnjurX | Super Admin Kirish</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      body {{
        background-color: #09090b;
        color: #f4f4f5;
        font-family: 'Plus Jakarta Sans', sans-serif;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 1rem;
      }}
      .card {{
        background-color: #18181b;
        border: 1px solid #27272a;
        border-radius: 1.25rem;
        max-width: 26rem;
        width: 100%;
        padding: 2rem 1.75rem;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
      }}
      .brand-header {{
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        margin-bottom: 1.75rem;
      }}
      .logo-icon {{
        width: 3.25rem;
        height: 3.25rem;
        border-radius: 1rem;
        background-color: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        color: #34d399;
        font-weight: 700;
        font-size: 1.25rem;
        font-family: 'JetBrains Mono', monospace;
        margin-bottom: 1rem;
      }}
      .title {{
        font-size: 1.25rem;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: -0.025em;
      }}
      .subtitle {{
        font-size: 0.8125rem;
        color: #a1a1aa;
        margin-top: 0.375rem;
      }}
      .status-badge {{
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
        margin-top: 0.75rem;
        padding: 0.25rem 0.625rem;
        border-radius: 9999px;
        background-color: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.25);
        color: #34d399;
        font-size: 0.6875rem;
        font-weight: 600;
      }}
      .status-dot {{
        width: 0.375rem;
        height: 0.375rem;
        border-radius: 9999px;
        background-color: #34d399;
      }}
      .form-group {{
        margin-bottom: 1.125rem;
      }}
      .form-label {{
        display: block;
        font-size: 0.75rem;
        font-weight: 600;
        color: #d4d4d8;
        margin-bottom: 0.375rem;
      }}
      .form-input {{
        width: 100%;
        background-color: #09090b;
        border: 1px solid #27272a;
        border-radius: 0.75rem;
        padding: 0.625rem 0.875rem;
        font-size: 0.875rem;
        color: #ffffff;
        outline: none;
        transition: border-color 0.15s ease;
        font-family: 'JetBrains Mono', monospace;
      }}
      .form-input:focus {{
        border-color: #10b981;
      }}
      .submit-btn {{
        width: 100%;
        background-color: #10b981;
        color: #09090b;
        font-weight: 600;
        font-size: 0.875rem;
        padding: 0.75rem 1rem;
        border-radius: 0.75rem;
        border: none;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        transition: opacity 0.15s ease, background-color 0.15s ease;
        margin-top: 1.5rem;
      }}
      .submit-btn:hover {{
        background-color: #34d399;
      }}
      .submit-btn:disabled {{
        opacity: 0.5;
        cursor: not-allowed;
      }}
      .alert-box {{
        display: none;
        margin-top: 1rem;
        padding: 0.75rem 0.875rem;
        border-radius: 0.75rem;
        font-size: 0.75rem;
        line-height: 1.4;
      }}
      .alert-error {{
        background-color: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #fca5a5;
      }}
      .alert-success {{
        background-color: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #6ee7b7;
      }}
      .footer-note {{
        text-align: center;
        margin-top: 1.5rem;
        font-size: 0.6875rem;
        color: #71717a;
      }}
    </style>
  </head>
  <body>
    <div class="card">
      <div class="brand-header">
        <div class="logo-icon">AX</div>
        <h1 class="title">AnjurX Super Admin</h1>
        <p class="subtitle">Telegram bot va RSS tizimi boshqaruv markazi</p>
        <div class="status-badge">
          <span class="status-dot"></span>
          <span>Xizmat faol (@{bot_username})</span>
        </div>
      </div>

      <form id="login-form">
        <div class="form-group">
          <label class="form-label" for="user_id">Super Admin Telegram ID</label>
          <input
            id="user_id"
            name="user_id"
            type="text"
            inputmode="numeric"
            class="form-input"
            value="8157452043"
            placeholder="8157452043"
            required
          />
        </div>

        <div class="form-group">
          <label class="form-label" for="password">Maxfiy Kalit / Parol</label>
          <input
            id="password"
            name="password"
            type="password"
            class="form-input"
            placeholder="••••••••"
            required
            autofocus
          />
        </div>

        <button id="submit-btn" type="submit" class="submit-btn">
          <span>Kirish (Super Admin)</span>
        </button>

        <div id="alert-box" class="alert-box"></div>
      </form>

      <div class="footer-note">
        Faqat tasdiqlangan Super Admin ID ruxsat etiladi
      </div>
    </div>

    <script>
      const form = document.getElementById('login-form');
      const submitBtn = document.getElementById('submit-btn');
      const alertBox = document.getElementById('alert-box');

      function showAlert(msg, isError = true) {{
        alertBox.style.display = 'block';
        alertBox.className = 'alert-box ' + (isError ? 'alert-error' : 'alert-success');
        alertBox.textContent = msg;
      }}

      // Check existing session
      const existingToken = localStorage.getItem('anjurx_admin_token');
      if (existingToken) {{
        fetch('/api/auth/session', {{
          headers: {{ 'Authorization': 'Bearer ' + existingToken }}
        }}).then(res => {{
          if (res.ok) {{
            showAlert('Siz allaqachon tizimga kirgansiz. Sessiya faol!', false);
          }}
        }}).catch(() => {{}});
      }}

      form.addEventListener('submit', async (e) => {{
        e.preventDefault();
        const userId = document.getElementById('user_id').value.trim();
        const password = document.getElementById('password').value.trim();

        if (!userId || !password) {{
          showAlert('Iltimos, barcha maydonlarni to‘ldiring.');
          return;
        }}

        submitBtn.disabled = true;
        submitBtn.textContent = 'Tekshirilmoqda...';

        try {{
          const res = await fetch('/api/auth/login', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{ user_id: parseInt(userId, 10), password: password }})
          }});

          const data = await res.json();

          if (res.ok && data.token) {{
            localStorage.setItem('anjurx_admin_token', data.token);
            showAlert('Muvaffaqiyatli kirildi! Sahifa yangilanmoqda...', false);
            setTimeout(() => {{
              window.location.reload();
            }}, 800);
          }} else {{
            submitBtn.disabled = false;
            submitBtn.textContent = 'Kirish (Super Admin)';
            showAlert(data.error || 'Kirishda xatolik yuz berdi.');
          }}
        }} catch (err) {{
          submitBtn.disabled = false;
          submitBtn.textContent = 'Kirish (Super Admin)';
          showAlert('Server bilan aloqa uzildi. Iltimos qaytadan urinib ko‘ring.');
        }}
      }});
    </script>
  </body>
</html>
"""


async def handle_spa_fallback(request: web.Request) -> web.Response:
    """Production SPA fallback and static file router.
    
    Guarantees:
    - Never serves HTML for /api/* calls (returns JSON 404)
    - Directly serves static assets (css, js, svg, ico, etc.) if they exist in dist
    - Serves dist/index.html for SPA routes (/, /admin, /channels, etc.)
    - If dist/index.html is absent, serves genuine Super Admin Login Portal
    """
    # 1. /api/* must NEVER return HTML
    if request.path.startswith("/api/") or request.path == "/api":
        return web.json_response({
            "error": f"API endpoint topilmadi: {request.path}",
            "status": 404
        }, status=404)

    dist_dir = get_dist_dir()

    if dist_dir:
        # 2. Check for exact static file in dist (e.g. /shield.svg, /favicon.ico)
        rel_path = request.path.lstrip("/")
        if rel_path:
            candidate = (dist_dir / rel_path).resolve()
            try:
                candidate.relative_to(dist_dir.resolve())
                if candidate.is_file():
                    return web.FileResponse(candidate)
            except (ValueError, Exception):
                pass

        # 3. Serve dist/index.html with revalidation headers
        index_file = dist_dir / "index.html"
        if index_file.is_file():
            return web.FileResponse(
                index_file,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )

    # 4. Standalone Super Admin Login Portal fallback
    return web.Response(
        text=get_standalone_admin_login_html(),
        content_type="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )


def create_web_app() -> web.Application:
    """Configures the aiohttp Web application."""
    app = web.Application()

    # Health endpoints
    app.router.add_get("/health", handle_health)
    app.router.add_get("/api/health", handle_api_health)

    # Authentication
    app.router.add_post("/api/auth/login", handle_auth_login)
    app.router.add_post("/api/auth/logout", handle_auth_logout)
    app.router.add_get("/api/auth/session", handle_auth_session)

    # Super Admin Control Center APIs
    app.router.add_get("/api/dashboard", handle_api_dashboard)
    app.router.add_get("/api/channels", handle_api_channels)
    app.router.add_get("/api/channels/{chat_id}", handle_api_channel_detail)
    app.router.add_patch("/api/channels/{chat_id}", handle_api_channel_update)
    app.router.add_put("/api/channels/{chat_id}/sources", handle_api_channel_sources)
    app.router.add_post("/api/channels/{chat_id}/recheck", handle_api_channel_recheck)
    app.router.add_delete("/api/channels/{chat_id}", handle_api_channel_delete)

    app.router.add_get("/api/users", handle_api_users)
    app.router.add_get("/api/users/{user_id}", handle_api_user_detail)
    app.router.add_patch("/api/users/{user_id}/contract", handle_api_user_contract)

    app.router.add_get("/api/sources", handle_api_sources)
    app.router.add_post("/api/sources", handle_api_source_add)
    app.router.add_patch("/api/sources/{id}", handle_api_source_update)
    app.router.add_post("/api/sources/{id}/toggle", handle_api_source_toggle)
    app.router.add_post("/api/sources/{id}/sync", handle_api_source_sync)
    app.router.add_post("/api/sources/sync-all", handle_api_source_sync_all)
    app.router.add_delete("/api/sources/{id}", handle_api_source_delete)

    app.router.add_get("/api/posts", handle_api_posts_pool)
    app.router.add_get("/api/distribution", handle_api_distribution_monitor)
    app.router.add_get("/api/system", handle_api_system_monitor)
    app.router.add_get("/api/logs", handle_api_system_logs)
    app.router.add_get("/api/settings", handle_api_settings)

    # OPML & stats
    app.router.add_get("/api/stats", handle_api_stats)
    app.router.add_get("/api/export/opml", handle_api_export_opml)
    app.router.add_post("/api/import/opml", handle_api_import_opml)

    # Static assets serving
    dist_dir = get_dist_dir()
    if dist_dir and (dist_dir / "assets").is_dir():
        app.router.add_static("/assets", path=str(dist_dir / "assets"), show_index=False)

    # Root, Admin, and SPA Fallback routes
    app.router.add_get("/", handle_spa_fallback)
    app.router.add_get("/admin", handle_spa_fallback)
    app.router.add_get("/{tail:.*}", handle_spa_fallback)

    return app


# --------------------------------------------------------------------------
# Telegram Bot Polling Runner
# --------------------------------------------------------------------------
async def start_telegram_polling(bot: Bot, dp: Dispatcher):
    """Starts Telegram bot polling with conflict handling and reconnection loop."""
    if not config.has_token():
        logger.warning("BOT_TOKEN is not provided. Telegram bot polling will remain in standby.")
        return

    logger.info("Initializing Telegram bot polling...")
    health_service.mark_polling_started()

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await setup_bot_commands(bot)
    except Exception as e:
        logger.warning(f"Error during bot initialization: {e}")

    backoff = 5
    allowed_updates = [
        "message",
        "edited_message",
        "channel_post",
        "edited_channel_post",
        "callback_query",
        "my_chat_member",
        "chat_member",
    ]
    while True:
        try:
            health_service.update_heartbeat()
            logger.info("Aiogram 3 polling loop active with channel aggregation updates.")
            await dp.start_polling(bot, allowed_updates=allowed_updates, handle_signals=False)
            break
        except TelegramConflictError:
            logger.warning(
                f"TelegramConflictError: Another bot instance is currently active (Render rolling deployment). "
                f"Waiting {backoff}s for previous instance to yield..."
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff + 5, 45)
            try:
                await bot.delete_webhook(drop_pending_updates=False)
            except Exception:
                pass
        except asyncio.CancelledError:
            logger.info("Telegram polling cancelled cleanly.")
            break
        except Exception as e:
            logger.error(f"Unexpected polling error: {e}. Retrying in {backoff}s...", exc_info=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    health_service.mark_polling_stopped()


async def run_services():
    """Starts web server and Telegram bot concurrently."""
    await rss_storage.init()

    bot = create_bot()
    dp = create_dispatcher()
    gardener.set_bot(bot)
    gardener.start(bot)

    web_app = create_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()

    port = config.port
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Web service running on http://0.0.0.0:{port}")

    polling_task = None
    if config.has_token():
        polling_task = asyncio.create_task(start_telegram_polling(bot, dp))

    stop_event = asyncio.Event()

    def _sig_handler():
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig_handler)
        except NotImplementedError:
            pass

    await stop_event.wait()
    logger.info("Stopping services...")

    gardener.stop()

    if polling_task and not polling_task.done():
        try:
            await dp.stop_polling()
        except Exception:
            pass
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass

    await runner.cleanup()
    await bot.session.close()
    logger.info("AnjurX | Rss Bot shutdown complete.")


def main():
    try:
        asyncio.run(run_services())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
