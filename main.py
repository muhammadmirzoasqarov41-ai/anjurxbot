"""
Entry point for the Telegram Guard Bot.

Run with:
    python main.py

The script sets up the asyncio event loop and delegates everything to
``app.bot.run_polling()``.
"""

import asyncio
import sys

from app.bot import run_polling
from app.utils.logger import logger


def main() -> None:
    """Bootstrap the bot and handle top-level fatal errors gracefully."""
    try:
        asyncio.run(run_polling())
    except KeyboardInterrupt:
        logger.info("Bot stopped by KeyboardInterrupt (Ctrl+C).")
        sys.exit(0)
    except Exception as exc:
        logger.critical("Fatal error during bot startup: %s", exc, exc_info=exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
