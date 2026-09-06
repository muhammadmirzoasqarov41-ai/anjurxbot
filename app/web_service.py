"""
Web Service and Telegram Polling Orchestrator.
Runs aiohttp web service for health checks (/health) alongside aiogram 3 polling loop.
Compatible with Render, Cloud Run, and local execution.
"""
import asyncio
import logging
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher

from app.config import config
from app.database.firestore import db
from app.services.health_service import health_service
from app.bot import create_bot, create_dispatcher

logging.basicConfig(
    level=logging.INFO if not config.debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("anjurxbot.web_service")


async def handle_health(request: web.Request) -> web.Response:
    """Returns JSON health status for Render and platform health checks."""
    status = health_service.get_health_status()
    return web.json_response(status)


async def handle_root(request: web.Request) -> web.Response:
    """Root info page displaying bot runtime status and instructions."""
    bot_name = config.bot_username or "AnjurXBot"
    uptime = health_service.get_health_status().get("uptime_seconds", 0)
    has_token = config.has_token()
    token_status = "Ulangan (Active)" if has_token else "Token kiritilmagan (Standby)"

    html_content = f"""<!doctype html>
<html lang="uz">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AnjurXBot - Telegram Guard & Force Sub Service</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #090d16;
            color: #f1f5f9;
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
        }}
        .card {{
            background: #131b2e;
            border: 1px solid #1e293b;
            border-radius: 12px;
            max-width: 600px;
            width: 100%;
            padding: 32px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
        }}
        h1 {{ font-size: 24px; margin-top: 0; color: #38bdf8; display: flex; align-items: center; gap: 8px; }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            background: #0284c7;
            color: white;
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
            margin: 24px 0;
        }}
        .stat-box {{
            background: #1e293b;
            padding: 16px;
            border-radius: 8px;
            border: 1px solid #334155;
        }}
        .stat-label {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }}
        .stat-val {{ font-size: 18px; font-weight: 700; margin-top: 6px; color: #f8fafc; }}
        a.btn {{
            display: inline-block;
            background: #0284c7;
            color: white;
            text-decoration: none;
            padding: 10px 20px;
            border-radius: 6px;
            font-weight: 600;
            margin-top: 12px;
        }}
        a.btn:hover {{ background: #0369a1; }}
        code {{ background: #0f172a; padding: 2px 6px; border-radius: 4px; font-size: 13px; color: #38bdf8; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>🛡 {bot_name} Service</h1>
        <p>Telegram guruhlarini spam, flood, havolalar va reklamalardan himoyalovchi hamda majburiy kanal a'zoligini (Force Subscribe) nazorat qiluvchi avtomatlashtirilgan xizmat.</p>
        
        <div class="stat-grid">
            <div class="stat-box">
                <div class="stat-label">Bot Holati</div>
                <div class="stat-val">{token_status}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Uptime</div>
                <div class="stat-val">{uptime}s</div>
            </div>
        </div>

        <p>Diagnostic va tekshiruv: <a href="/health" style="color: #38bdf8;">/health</a></p>
        <p>Veb boshqaruv paneli uchun port <code>3000</code> orqali React boshqaruv interfeysiga kiring.</p>
    </div>
</body>
</html>"""
    return web.Response(text=html_content, content_type="text/html")


def create_web_app() -> web.Application:
    """Creates the aiohttp Web Application."""
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    return app


async def run_bot_polling(bot: Bot, dp: Dispatcher):
    """Starts Telegram Bot polling with graceful cancellation and error recovery."""
    if not config.has_token():
        logger.warning(
            "BOT_TOKEN is not configured or is placeholder. "
            "Web health server is ACTIVE in standby mode. "
            "Provide BOT_TOKEN in Render environment variables to activate live Telegram bot polling."
        )
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Standby loop received cancellation.")
        return

    logger.info(f"Connecting to Telegram with bot token: {bot.token[:8]}***")
    health_service.mark_polling_started()

    try:
        while True:
            try:
                # Delete webhook if any was active before polling
                await bot.delete_webhook(drop_pending_updates=False)
                logger.info("Starting aiogram polling loop...")
                await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
                break
            except asyncio.CancelledError:
                logger.info("Bot polling loop received cancellation.")
                break
            except Exception as e:
                logger.error(f"Error during bot polling: {e}. Retrying polling in 5 seconds...", exc_info=True)
                await asyncio.sleep(5)
    finally:
        health_service.mark_polling_stopped()
        try:
            await bot.session.close()
        except Exception:
            pass
        logger.info("Bot session closed.")


async def start_services():
    """Initializes Firestore, launches web server, and starts Telegram polling loop."""
    # 1. Initialize Firestore DB connection
    await db.connect()

    # 2. Setup Bot & Dispatcher
    bot = create_bot()
    dp = create_dispatcher()

    # 3. Setup aiohttp web app
    app = create_web_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = config.port or 10000
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info(f"Health web service started at http://0.0.0.0:{port}")

    # 4. Start polling loop concurrently
    try:
        await run_bot_polling(bot, dp)
    finally:
        logger.info("Cleaning up web server and database resources...")
        await runner.cleanup()
        await db.close()


def main():
    """Sync entry point called by main.py or python -m app.web_service"""
    try:
        asyncio.run(start_services())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Service shutdown completed.")
    except Exception as e:
        logger.critical(f"Fatal error starting services: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
