"""
AnjurX | Rss Bot - Production Web Service and Telegram Orchestrator.
Provides:
- Production Static React Serving & SPA Fallback (dist/index.html)
- RSS Feeds & Stats API Endpoints (/api/feeds, /api/stats, /api/subscribers, /api/export/opml, /api/import/opml)
- Health Check Endpoint (/health, /api/health) for Render and deployment
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
from datetime import datetime
from typing import Dict, Any, Optional

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramConflictError

from app.config import config
from app.services.health_service import health_service, START_TIME
from app.bot import create_bot, create_dispatcher
from app.services.commands import setup_bot_commands
from app.services.rss_storage import rss_storage
from app.services.feed_fetcher import feed_fetcher
from app.services.gardener import gardener
from app.services.feed_parser import parse_opml

logging.basicConfig(
    level=logging.INFO if not config.debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("anjurxbot.web_service")


# --------------------------------------------------------------------------
# Health & Diagnostic Handlers
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


# --------------------------------------------------------------------------
# RSS Bot REST API Endpoints (for Web Admin Panel)
# --------------------------------------------------------------------------
async def handle_api_stats(request: web.Request) -> web.Response:
    """Returns overview statistics of feeds and subscriber deliveries."""
    stats = await rss_storage.get_stats()
    stats["uptime_seconds"] = round(time.time() - START_TIME, 1)
    stats["bot_status"] = "running" if health_service.polling_running else "standby"
    stats["bot_username"] = config.bot_username or "AnjurXBot"
    return web.json_response(stats)


async def handle_api_feeds(request: web.Request) -> web.Response:
    """Returns all registered RSS feeds."""
    feeds = await rss_storage.get_all_feeds()
    return web.json_response({
        "feeds": [f.to_dict() for f in feeds],
        "total": len(feeds)
    })


async def handle_api_add_feed(request: web.Request) -> web.Response:
    """Adds a new feed via the web admin panel."""
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    url = body.get("url", "").strip()
    if not url or not url.startswith(("http://", "https://")):
        return web.json_response({"error": "Yaroqli HTTP/HTTPS havola kiriting"}, status=400)

    try:
        parsed, status, etag, lm, _ = await feed_fetcher.fetch_and_parse(url)
        if not parsed:
            return web.json_response({"error": f"Feed yuklanmadi. HTTP status: {status}"}, status=400)

        initial_seen = [item.get_hash() for item in parsed.items]
        admin_id = config.super_admin_id or 8157452043

        feed, is_new = await rss_storage.add_subscription(
            chat_id=admin_id,
            feed_url=parsed.feed_url,
            title=parsed.title,
            link=parsed.link,
            description=parsed.description,
            initial_seen_hashes=initial_seen,
            chat_title="Web Admin",
            chat_type="private"
        )
        return web.json_response({
            "status": "ok",
            "message": "Feed muvaffaqiyatli qo'shildi",
            "feed": feed.to_dict(),
            "is_new": is_new
        })
    except Exception as e:
        logger.error(f"Error adding feed via API: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def handle_api_delete_feed(request: web.Request) -> web.Response:
    """Removes a feed by ID."""
    feed_id = request.match_info.get("id")
    feed = await rss_storage.get_feed_by_id(feed_id)
    if not feed:
        return web.json_response({"error": "Feed topilmadi"}, status=404)

    # Remove all subscribers
    for cid in list(feed.subscribers):
        await rss_storage.remove_subscription(cid, feed.id)

    return web.json_response({"status": "ok", "message": "Feed o'chirildi"})


async def handle_api_sync_feed(request: web.Request) -> web.Response:
    """Forces an immediate check/sync for a specific feed."""
    feed_id = request.match_info.get("id")
    feed = await rss_storage.get_feed_by_id(feed_id)
    if not feed:
        return web.json_response({"error": "Feed topilmadi"}, status=404)

    delivered = await gardener.poll_feed(feed)
    return web.json_response({
        "status": "ok",
        "message": f"Feed tekshirildi. Yangi yuborilgan maqolalar: {delivered} ta",
        "delivered": delivered,
        "feed": feed.to_dict()
    })


async def handle_api_subscribers(request: web.Request) -> web.Response:
    """Lists all subscribers with their active feed count."""
    await rss_storage.init()
    subs = list(rss_storage._subscribers.values())
    return web.json_response({"subscribers": subs, "total": len(subs)})


async def handle_api_posts(request: web.Request) -> web.Response:
    """Returns recent delivered posts log."""
    await rss_storage.init()
    return web.json_response({
        "posts": list(reversed(rss_storage._recent_posts[-50:])),
        "total_delivered": rss_storage._posts_delivered
    })


async def handle_api_export_opml(request: web.Request) -> web.Response:
    """Exports all subscriptions as OPML XML download."""
    opml_xml = await rss_storage.export_opml()
    return web.Response(
        text=opml_xml,
        content_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="anjurx_feeds.opml"'}
    )


async def handle_api_import_opml(request: web.Request) -> web.Response:
    """Imports OPML content and subscribes."""
    try:
        data = await request.post()
        opml_text = ""
        if "file" in data:
            file_field = data["file"]
            opml_text = file_field.file.read().decode("utf-8", errors="replace")
        else:
            raw_body = await request.text()
            opml_text = raw_body

        feed_tuples = parse_opml(opml_text)
        if not feed_tuples:
            return web.json_response({"error": "Yaroqli OPML XML topilmadi"}, status=400)

        added = 0
        admin_id = config.super_admin_id or 8157452043
        for url, title in feed_tuples[:50]:
            try:
                await rss_storage.add_subscription(
                    chat_id=admin_id,
                    feed_url=url,
                    title=title,
                    link=url,
                    chat_title="Web Admin",
                    chat_type="private"
                )
                added += 1
            except Exception:
                pass

        return web.json_response({
            "status": "ok",
            "message": f"Muvaffaqiyatli import qilindi: {added} ta feed",
            "imported_count": added
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


# --------------------------------------------------------------------------
# Static file serving & SPA Fallback
# --------------------------------------------------------------------------
async def handle_spa_fallback(request: web.Request) -> web.Response:
    dist_index = os.path.join(os.getcwd(), "dist", "index.html")
    if os.path.exists(dist_index):
        with open(dist_index, "r", encoding="utf-8") as f:
            return web.Response(text=f.read(), content_type="text/html")
    return web.Response(
        text="<html><body><h2>AnjurX | Rss Bot</h2><p>Service active. Visit Telegram bot: @" + (config.bot_username or "AnjurXBot") + "</p></body></html>",
        content_type="text/html"
    )


def create_web_app() -> web.Application:
    """Configures the aiohttp Web application."""
    app = web.Application()

    # Health endpoints
    app.router.add_get("/health", handle_health)
    app.router.add_get("/api/health", handle_api_health)

    # RSS APIs
    app.router.add_get("/api/stats", handle_api_stats)
    app.router.add_get("/api/feeds", handle_api_feeds)
    app.router.add_post("/api/feeds", handle_api_add_feed)
    app.router.add_delete("/api/feeds/{id}", handle_api_delete_feed)
    app.router.add_post("/api/feeds/{id}/sync", handle_api_sync_feed)
    app.router.add_get("/api/subscribers", handle_api_subscribers)
    app.router.add_get("/api/posts", handle_api_posts)
    app.router.add_get("/api/export/opml", handle_api_export_opml)
    app.router.add_post("/api/import/opml", handle_api_import_opml)

    # Static files if dist exists
    dist_dir = os.path.join(os.getcwd(), "dist")
    if os.path.exists(dist_dir) and os.path.exists(os.path.join(dist_dir, "assets")):
        app.router.add_static("/assets", path=os.path.join(dist_dir, "assets"), show_index=False)
    app.router.add_get("/", handle_spa_fallback)
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
