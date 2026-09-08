"""
AnjurXBot - Production Web Service and Telegram Orchestrator.
Provides:
- Production Static React Serving & SPA Fallback (dist/index.html)
- Cybersecurity-grade Authentication with Brute Force Exponential Cooldown Protection
- Secure Admin API Endpoints (/api/admin/*, /api/auth/*)
- Platform Health Endpoint (/health) for Render
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
from typing import Dict, Any, Optional

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramConflictError

from app.config import config
from app.database.firestore import db
from app.services.health_service import health_service, START_TIME
from app.bot import create_bot, create_dispatcher

logging.basicConfig(
    level=logging.INFO if not config.debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("anjurxbot.web_service")

# Security and Session configuration
SECRET_KEY = (
    os.getenv("SECRET_KEY")
    or os.getenv("WEB_ADMIN_KEY")
    or "anjurx-cyber-control-center-2026-secret"
).encode("utf-8")

# Brute Force Protection Store
# ip -> {"failed_attempts": int, "blocked_until": float, "last_attempt": float}
_LOGIN_ATTEMPTS: Dict[str, Dict[str, Any]] = {}


def get_client_ip(request: web.Request) -> str:
    """Extract real client IP considering reverse proxies (Render, Cloudflare, Nginx)."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote or "unknown"


def generate_session_token(username: str) -> str:
    """Generates an HMAC-SHA256 authenticated session token."""
    ts = int(time.time())
    payload = f"{username}:{ts}"
    signature = hmac.new(SECRET_KEY, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def verify_session_token(token: str) -> Optional[str]:
    """Verifies HMAC-SHA256 session token and enforces 7-day expiration."""
    if not token or ":" not in token:
        return None
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return None
        username, ts_str, signature = parts
        ts = int(ts_str)
        # Token expiration: 7 days
        if time.time() - ts > 7 * 86400:
            return None
        expected_payload = f"{username}:{ts}"
        expected_sig = hmac.new(SECRET_KEY, expected_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected_sig):
            return username
        return None
    except Exception:
        return None


def is_request_authenticated(request: web.Request) -> bool:
    """Checks cookie or Authorization header for a valid admin session."""
    cookie_token = request.cookies.get("anjurx_admin")
    if cookie_token and verify_session_token(cookie_token):
        return True

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        bearer_token = auth_header[7:].strip()
        if verify_session_token(bearer_token):
            return True

    return False


def require_admin(handler):
    """Decorator to protect sensitive admin endpoints."""
    async def middleware(request: web.Request):
        if not is_request_authenticated(request):
            return web.json_response(
                {"error": "Unauthorized. Super Admin authentication required."},
                status=401
            )
        return await handler(request)
    return middleware


# --- Health & Diagnostic Handlers ---

async def handle_health(request: web.Request) -> web.Response:
    """
    Render Health Check endpoint.
    Returns:
    {
      "status": "ok",
      "bot": "running" | "standby",
      "firebase": "connected"
    }
    """
    bot_state = "running" if health_service.polling_running else "standby"
    fb_state = "connected" if db.is_connected else "fallback_mode"
    uptime = round(time.time() - START_TIME, 1)

    return web.json_response({
        "status": "ok",
        "bot": bot_state,
        "firebase": fb_state,
        "uptime_seconds": uptime
    })


# --- Authentication Handlers (with Brute Force Protection) ---

async def handle_login(request: web.Request) -> web.Response:
    """
    Super Admin Authentication endpoint with progressive brute-force cooldown:
    5 failed attempts  -> 30s cooldown
    10 failed attempts -> 60s cooldown
    15 failed attempts -> 90s cooldown
    Formula: cooldown = (failed_attempts // 5) * 30 seconds.
    """
    ip = get_client_ip(request)
    now = time.time()

    # Check brute-force status
    client_state = _LOGIN_ATTEMPTS.setdefault(ip, {"failed_attempts": 0, "blocked_until": 0.0, "last_attempt": now})
    if now < client_state["blocked_until"]:
        remaining = int(client_state["blocked_until"] - now) + 1
        return web.json_response({
            "error": "Brute-force protection active. Too many failed attempts.",
            "cooldown_remaining": remaining,
            "blocked": True
        }, status=429)

    try:
        body = await request.json()
    except Exception:
        body = {}

    input_username = str(body.get("username", "")).strip()
    input_password = str(body.get("password", "") or body.get("key", "")).strip()

    # Expected credentials from Environment
    expected_username = os.getenv("ADMIN_USERNAME", "usafes").lstrip("@").lower()
    expected_password = (
        os.getenv("ADMIN_PASSWORD")
        or os.getenv("WEB_ADMIN_KEY")
        or "hyperactive67"
    ).strip()

    # Normalize input username
    norm_user = input_username.lstrip("@").lower()

    # Check valid username
    allowed_usernames = [expected_username, "usafes"]
    for u in config.admin_usernames:
        allowed_usernames.append(u.lstrip("@").lower())

    username_match = norm_user in allowed_usernames or not input_username
    password_match = hmac.compare_digest(input_password, expected_password)

    if username_match and password_match:
        # Reset brute-force counter upon successful authentication
        _LOGIN_ATTEMPTS.pop(ip, None)
        token = generate_session_token(input_username or "usafes")

        response = web.json_response({
            "status": "ok",
            "message": "ACCESS GRANTED",
            "token": token,
            "redirect": "/admin",
            "user": {
                "username": input_username or "usafes",
                "role": "Super Admin",
                "telegram_id": config.super_admin_id or 8157452043
            }
        })
        # Set HttpOnly session cookie
        response.set_cookie(
            "anjurx_admin",
            token,
            max_age=7 * 86400,
            httponly=True,
            samesite="Lax",
            path="/"
        )
        logger.info(f"Successful Super Admin login from IP: {ip}")
        return response

    # Failed login attempt
    client_state["failed_attempts"] += 1
    client_state["last_attempt"] = now
    failed = client_state["failed_attempts"]

    if failed % 5 == 0:
        multiplier = failed // 5
        cooldown = multiplier * 30
        client_state["blocked_until"] = now + cooldown
        logger.warning(f"Brute-force lockout triggered for IP: {ip}. Cooldown: {cooldown}s")
        return web.json_response({
            "error": "Invalid credentials. Temporary cooldown activated.",
            "cooldown_remaining": cooldown,
            "blocked": True
        }, status=429)

    attempts_left = 5 - (failed % 5)
    return web.json_response({
        "error": "Invalid credentials. Access Denied.",
        "attempts_remaining": attempts_left,
        "blocked": False
    }, status=401)


async def handle_logout(request: web.Request) -> web.Response:
    """Logs out and clears admin session cookie."""
    response = web.json_response({"status": "ok", "message": "Session terminated"})
    response.del_cookie("anjurx_admin", path="/")
    return response


async def handle_auth_session(request: web.Request) -> web.Response:
    """Verifies if current visitor holds a valid authenticated session."""
    authed = is_request_authenticated(request)
    return web.json_response({
        "authenticated": authed,
        "user": {
            "username": "usafes",
            "role": "Super Admin",
            "telegram_id": config.super_admin_id or 8157452043
        } if authed else None
    })


# --- Protected Admin API Endpoints ---

@require_admin
async def handle_admin_dashboard(request: web.Request) -> web.Response:
    """
    Returns real dashboard telemetry from Firestore.
    NO MOCK DATA.
    """
    groups = await db.list_documents("groups", limit=500)
    users = await db.list_documents("users", limit=500)
    logs = await db.list_documents("moderation_logs", limit=100)

    total_groups = len(groups)
    active_guard_groups = sum(
        1 for g in groups if g.get("guard", {}).get("enabled", True) and g.get("is_active", True)
    )
    total_users = len(users)

    # Real incident metrics calculated from actual moderation logs
    spam_blocked = sum(1 for log in logs if "spam" in str(log.get("reason", "")).lower())
    links_deleted = sum(1 for log in logs if "link" in str(log.get("reason", "")).lower() or "havola" in str(log.get("reason", "")).lower())
    warnings_issued = sum(1 for log in logs if log.get("action") == "warn")

    return web.json_response({
        "total_groups": total_groups,
        "active_guard_groups": active_guard_groups,
        "total_users": total_users,
        "moderation_events": len(logs),
        "spam_blocked": spam_blocked,
        "links_deleted": links_deleted,
        "warnings_issued": warnings_issued,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "bot_status": "running" if health_service.polling_running else "standby",
        "firebase_status": "connected" if db.is_connected else "fallback_mode",
        "super_admin": {
            "username": "@usafes",
            "telegram_id": config.super_admin_id or 8157452043
        }
    })


@require_admin
async def handle_admin_groups(request: web.Request) -> web.Response:
    """Returns list of real groups from Firestore."""
    groups = await db.list_documents("groups", limit=200)
    return web.json_response({"groups": groups, "total": len(groups)})


@require_admin
async def handle_admin_group_detail(request: web.Request) -> web.Response:
    """Returns single group detail by group_id."""
    group_id = request.match_info.get("id")
    group = await db.get_document("groups", group_id)
    if not group:
        return web.json_response({"error": "Group not found"}, status=404)
    return web.json_response(group)


@require_admin
async def handle_admin_group_guard_update(request: web.Request) -> web.Response:
    """Updates guard settings for a specific group in Firestore."""
    group_id = request.match_info.get("id")
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    guard_settings = data.get("guard", data)
    success = await db.update_document("groups", group_id, {"guard": guard_settings})
    if success:
        return web.json_response({"status": "ok", "message": "Guard settings updated"})
    return web.json_response({"error": "Failed to update guard settings"}, status=500)


@require_admin
async def handle_admin_group_fsub(request: web.Request) -> web.Response:
    """Handles Force Subscribe channels for a group."""
    group_id = request.match_info.get("id")
    group = await db.get_document("groups", group_id)
    if not group:
        return web.json_response({"error": "Group not found"}, status=404)

    if request.method == "GET":
        return web.json_response({"channels": group.get("fsub_channels", [])})

    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        channels = group.get("fsub_channels", [])
        channel_id = str(body.get("channel_id", "")).strip()
        username = str(body.get("username", "")).strip()

        # Deduplicate
        existing = next((c for c in channels if str(c.get("channel_id")) == channel_id or c.get("username") == username), None)
        if not existing:
            channels.append({
                "channel_id": channel_id,
                "username": username,
                "title": body.get("title", username),
                "is_active": True,
                "invite_link": body.get("invite_link", "")
            })
            await db.update_document("groups", group_id, {"fsub_channels": channels})

        return web.json_response({"status": "ok", "channels": channels})

    return web.json_response({"error": "Method not allowed"}, status=405)


@require_admin
async def handle_admin_group_fsub_delete(request: web.Request) -> web.Response:
    """Removes a force subscribe channel from a group."""
    group_id = request.match_info.get("id")
    channel_id = request.match_info.get("channel_id")
    group = await db.get_document("groups", group_id)
    if not group:
        return web.json_response({"error": "Group not found"}, status=404)

    channels = group.get("fsub_channels", [])
    updated_channels = [c for c in channels if str(c.get("channel_id")) != str(channel_id) and c.get("username") != str(channel_id)]
    await db.update_document("groups", group_id, {"fsub_channels": updated_channels})
    return web.json_response({"status": "ok", "channels": updated_channels})


@require_admin
async def handle_admin_users(request: web.Request) -> web.Response:
    """Returns registered Telegram users from Firestore."""
    search = request.query.get("search", "").strip().lower()
    page = int(request.query.get("page", 1))
    limit = int(request.query.get("limit", 50))

    users = await db.list_documents("users", limit=500)
    if search:
        users = [
            u for u in users
            if search in str(u.get("username", "")).lower()
            or search in str(u.get("first_name", "")).lower()
            or search in str(u.get("user_id", ""))
        ]

    total = len(users)
    start = (page - 1) * limit
    paged = users[start:start + limit]
    total_pages = max(1, (total + limit - 1) // limit)

    return web.json_response({
        "users": paged,
        "total": total,
        "page": page,
        "total_pages": total_pages
    })


@require_admin
async def handle_admin_logs(request: web.Request) -> web.Response:
    """Returns real moderation logs from Firestore."""
    logs = await db.list_documents("moderation_logs", limit=150)
    # Sort descending by timestamp if present
    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return web.json_response({"logs": logs, "total": len(logs)})


@require_admin
async def handle_admin_clear_warns(request: web.Request) -> web.Response:
    """Clears warnings for a user in Firestore."""
    try:
        body = await request.json()
        user_id = str(body.get("user_id"))
        if not user_id:
            return web.json_response({"error": "user_id required"}, status=400)
        await db.update_document("users", user_id, {"warnings_count": 0})
        return web.json_response({"status": "ok", "message": f"Warnings reset for user {user_id}"})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@require_admin
async def handle_admin_system(request: web.Request) -> web.Response:
    """Returns system telemetry information."""
    return web.json_response({
        "system": "AnjurXBot Cyber Control Center",
        "version": "2.4.0-production",
        "python_version": sys.version.split()[0],
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "super_admin_id": config.super_admin_id or 8157452043,
        "super_admin_username": "@usafes",
        "bot_username": config.bot_username or "@anjurxbot",
        "bot_status": "running" if health_service.polling_running else "standby",
        "firebase_connected": db.is_connected,
        "environment": "Render Production" if os.getenv("RENDER") else "Production Cloud"
    })


# --- Static Files & SPA Fallback Handler ---

def get_fallback_login_html() -> str:
    """
    High-performance built-in Cyber Admin Login UI rendered if dist/index.html is missing.
    Follows Black + Neon Green cybersecurity aesthetic.
    """
    return """<!doctype html>
<html lang="uz" class="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AnjurXBot // Cyber Control Center</title>
  <style>
    :root {
      --bg: #05070a;
      --panel: #0b0f17;
      --border: #1a2333;
      --neon: #00ff66;
      --neon-glow: rgba(0, 255, 102, 0.2);
      --text: #e2e8f0;
      --text-muted: #64748b;
      --danger: #ef4444;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      background-image: 
        radial-gradient(ellipse at 50% 10%, rgba(0, 255, 102, 0.08) 0%, transparent 60%),
        linear-gradient(to right, rgba(255,255,255,0.02) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(255,255,255,0.02) 1px, transparent 1px);
      background-size: 100% 100%, 32px 32px, 32px 32px;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      max-width: 440px;
      width: 100%;
      padding: 32px;
      box-shadow: 0 20px 50px rgba(0,0,0,0.8), 0 0 20px rgba(0,255,102,0.05);
      position: relative;
      overflow: hidden;
    }
    .card::before {
      content: '';
      position: absolute;
      top: 0; left: 0; right: 0;
      height: 2px;
      background: linear-gradient(90deg, transparent, var(--neon), transparent);
    }
    .header {
      text-align: center;
      margin-bottom: 28px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-weight: 600;
      background: rgba(0,255,102,0.1);
      color: var(--neon);
      border: 1px solid rgba(0,255,102,0.25);
      margin-bottom: 12px;
    }
    .pulse-dot {
      width: 6px; height: 6px;
      border-radius: 50%;
      background: var(--neon);
      box-shadow: 0 0 8px var(--neon);
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.4; transform: scale(0.85); }
    }
    h1 {
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #fff;
    }
    p.sub {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 6px;
    }
    .form-group {
      margin-bottom: 18px;
    }
    label {
      display: block;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 6px;
    }
    input {
      width: 100%;
      background: #06090e;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 10px 14px;
      color: #fff;
      font-size: 14px;
      font-family: inherit;
      outline: none;
      transition: all 0.2s;
    }
    input:focus {
      border-color: var(--neon);
      box-shadow: 0 0 12px var(--neon-glow);
    }
    .btn {
      width: 100%;
      background: var(--neon);
      color: #05070a;
      border: none;
      border-radius: 8px;
      padding: 12px;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      cursor: pointer;
      transition: all 0.2s;
      margin-top: 8px;
    }
    .btn:hover {
      background: #33ff85;
      box-shadow: 0 0 16px var(--neon-glow);
    }
    .btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    .status-msg {
      margin-top: 14px;
      padding: 10px 12px;
      border-radius: 6px;
      font-size: 12px;
      display: none;
    }
    .status-msg.error {
      display: block;
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #fca5a5;
    }
    .status-msg.success {
      display: block;
      background: rgba(0, 255, 102, 0.1);
      border: 1px solid rgba(0, 255, 102, 0.3);
      color: var(--neon);
    }
    .footer-meta {
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      font-size: 11px;
      color: var(--text-muted);
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="badge">
        <span class="pulse-dot"></span>
        <span>Secure Cyber Gateway</span>
      </div>
      <h1>ANJURX_BOT // COMMAND CENTER</h1>
      <p class="sub">Enter Super Admin credentials to unlock control protocols</p>
    </div>

    <div id="statusBox" class="status-msg"></div>

    <form id="loginForm">
      <div class="form-group">
        <label>Admin Username</label>
        <input type="text" id="username" placeholder="usafes" required autocomplete="username">
      </div>
      <div class="form-group">
        <label>Password / Security Key</label>
        <input type="password" id="password" placeholder="••••••••••••" required autocomplete="current-password">
      </div>
      <button type="submit" id="submitBtn" class="btn">AUTHENTICATE PROTOCOL</button>
    </form>

    <div class="footer-meta">
      <span>PROTOCOL: AES-256</span>
      <span>SUPER ADMIN: @usafes</span>
    </div>
  </div>

  <script>
    const form = document.getElementById('loginForm');
    const statusBox = document.getElementById('statusBox');
    const btn = document.getElementById('submitBtn');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      statusBox.style.display = 'none';
      btn.disabled = true;
      btn.innerText = 'VERIFYING CREDENTIALS...';

      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            username: document.getElementById('username').value.trim(),
            password: document.getElementById('password').value
          })
        });
        const data = await res.json();
        if (!res.ok) {
          statusBox.className = 'status-msg error';
          if (data.cooldown_remaining) {
            statusBox.innerText = 'BRUTE-FORCE LOCKOUT: ' + data.cooldown_remaining + 's cooldown active.';
          } else {
            statusBox.innerText = data.error || 'Access Denied: Invalid credentials.';
          }
          statusBox.style.display = 'block';
          btn.disabled = false;
          btn.innerText = 'AUTHENTICATE PROTOCOL';
        } else {
          statusBox.className = 'status-msg success';
          statusBox.innerText = 'ACCESS GRANTED. INITIALIZING DASHBOARD...';
          statusBox.style.display = 'block';
          btn.innerText = 'ACCESS GRANTED';
          setTimeout(() => {
            window.location.href = '/admin';
          }, 800);
        }
      } catch (err) {
        statusBox.className = 'status-msg error';
        statusBox.innerText = 'Connection error with gateway: ' + err.message;
        statusBox.style.display = 'block';
        btn.disabled = false;
        btn.innerText = 'AUTHENTICATE PROTOCOL';
      }
    });
  </script>
</body>
</html>"""


async def handle_spa_fallback(request: web.Request) -> web.Response:
    """
    Renders React SPA entry point or built-in Cyber Login page.
    Directly serves dist/index.html if built, otherwise serves the embedded Cyber Login page.
    """
    dist_index = os.path.join(os.getcwd(), "dist", "index.html")
    if os.path.exists(dist_index):
        try:
            with open(dist_index, "r", encoding="utf-8") as f:
                content = f.read()
            return web.Response(text=content, content_type="text/html")
        except Exception as e:
            logger.error(f"Error serving dist/index.html: {e}")

    return web.Response(text=get_fallback_login_html(), content_type="text/html")


def create_web_app() -> web.Application:
    """Creates and configures the aiohttp Web Application."""
    app = web.Application()

    # 1. Platform Health Check for Render
    app.router.add_get("/health", handle_health)

    # 2. Authentication APIs
    app.router.add_post("/api/auth/login", handle_login)
    app.router.add_post("/api/login", handle_login)
    app.router.add_post("/api/auth/logout", handle_logout)
    app.router.add_post("/api/logout", handle_logout)
    app.router.add_get("/api/auth/session", handle_auth_session)
    app.router.add_get("/api/auth/me", handle_auth_session)

    # 3. Protected Admin Telemetry & Control APIs
    app.router.add_get("/api/admin/dashboard", handle_admin_dashboard)
    app.router.add_get("/api/stats", handle_admin_dashboard)
    app.router.add_get("/api/admin/groups", handle_admin_groups)
    app.router.add_get("/api/groups", handle_admin_groups)
    app.router.add_get("/api/admin/groups/{id}", handle_admin_group_detail)
    app.router.add_put("/api/admin/groups/{id}/guard", handle_admin_group_guard_update)
    app.router.add_get("/api/admin/groups/{id}/fsub", handle_admin_group_fsub)
    app.router.add_post("/api/admin/groups/{id}/fsub", handle_admin_group_fsub)
    app.router.add_delete("/api/admin/groups/{id}/fsub/{channel_id}", handle_admin_group_fsub_delete)
    app.router.add_get("/api/admin/users", handle_admin_users)
    app.router.add_get("/api/users", handle_admin_users)
    app.router.add_get("/api/admin/logs", handle_admin_logs)
    app.router.add_get("/api/moderation", handle_admin_logs)
    app.router.add_post("/api/admin/logs/clearwarns", handle_admin_clear_warns)
    app.router.add_post("/api/moderation/clearwarns", handle_admin_clear_warns)
    app.router.add_get("/api/admin/system", handle_admin_system)

    # 4. Static assets serving (dist/assets, icons, etc.)
    dist_path = os.path.join(os.getcwd(), "dist")
    assets_path = os.path.join(dist_path, "assets")
    if os.path.exists(assets_path):
        app.router.add_static("/assets", assets_path, show_index=False)

    # Serve direct static files from dist if requested (e.g. /shield.svg, /favicon.ico)
    async def handle_static_file(request: web.Request) -> web.Response:
        filename = request.match_info.get("filename")
        filepath = os.path.join(dist_path, filename)
        if os.path.exists(filepath) and os.path.isfile(filepath):
            return web.FileResponse(filepath)
        return await handle_spa_fallback(request)

    app.router.add_get("/{filename:[^/]+\\.(?:svg|png|jpg|jpeg|ico|json|txt)}", handle_static_file)

    # 5. SPA Fallback for all other frontend routes (/, /admin, /admin/groups, etc.)
    app.router.add_get("/", handle_spa_fallback)
    app.router.add_get("/admin", handle_spa_fallback)
    app.router.add_get("/admin/{tail:.*}", handle_spa_fallback)

    return app


# --- Telegram Bot Polling (with Conflict Error Recovery & Clean Shutdown) ---

async def run_bot_polling(bot: Bot, dp: Dispatcher, shutdown_event: asyncio.Event):
    """
    Runs Aiogram Telegram Bot Polling safely.
    Handles TelegramConflictError caused by Render zero-downtime container replacement.
    """
    if not config.has_token():
        logger.warning(
            "BOT_TOKEN is not configured or is placeholder. "
            "Web service is LIVE and serving Admin Panel and Health checks. "
            "Configure BOT_TOKEN in Render environment to activate live Telegram polling."
        )
        try:
            await shutdown_event.wait()
        except asyncio.CancelledError:
            pass
        return

    # Never log bot token prefix or secrets in production
    logger.info("Connecting to Telegram bot...")
    health_service.mark_polling_started()

    conflict_retry_count = 0
    while not shutdown_event.is_set():
        try:
            # Delete any existing webhook before beginning polling
            try:
                await bot.delete_webhook(drop_pending_updates=False)
            except Exception as whe:
                logger.warning(f"Webhook reset check: {whe}")

            logger.info("Aiogram polling loop running...")
            # Start polling until cancelled
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                handle_as_tasks=False
            )
            break
        except TelegramConflictError as conflict_err:
            conflict_retry_count += 1
            wait_time = min(30, 5 + conflict_retry_count * 3)
            logger.warning(
                f"Telegram Conflict detected: An active getUpdates connection exists (e.g. Previous Render container terminating). "
                f"Waiting {wait_time}s for clean handoff (Attempt {conflict_retry_count})..."
            )
            try:
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                break
        except asyncio.CancelledError:
            logger.info("Polling received cancellation signal.")
            break
        except Exception as e:
            logger.error(f"Polling loop exception: {e}. Retrying in 5 seconds...", exc_info=True)
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break

    health_service.mark_polling_stopped()
    try:
        await bot.session.close()
    except Exception:
        pass
    logger.info("Telegram Bot session closed cleanly.")


async def start_services():
    """Main orchestrator: boots Firestore, web server, and bot polling in unified event loop."""
    logger.info("Starting AnjurXBot Unified Production Web Service...")

    # 1. Connect Firestore
    await db.connect()

    # 2. Setup Bot & Dispatcher
    bot = create_bot()
    dp = create_dispatcher()

    # 3. Setup aiohttp web app
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()

    # Determine port: priority os.getenv("PORT") (Render default 10000 or assigned)
    port = int(os.getenv("PORT", str(config.port or 10000)))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info(f"AnjurXBot Cyber Web Service ACTIVE on http://0.0.0.0:{port}")

    # 4. Graceful Shutdown Coordinator
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def handle_signal():
        logger.info("Received termination signal (SIGTERM/SIGINT). Initiating graceful shutdown...")
        shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except (NotImplementedError, RuntimeError):
            pass

    # 5. Start Polling Task
    polling_task = asyncio.create_task(run_bot_polling(bot, dp, shutdown_event))

    # Wait until shutdown event fires
    await shutdown_event.wait()

    # Cancel polling task and cleanup
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass

    logger.info("Cleaning up web server runner and database connections...")
    await runner.cleanup()
    await db.close()
    logger.info("AnjurXBot shutdown completed.")


def main():
    """Sync entry point for main.py."""
    try:
        asyncio.run(start_services())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown completed.")
    except Exception as e:
        logger.critical(f"Fatal error in web service: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
