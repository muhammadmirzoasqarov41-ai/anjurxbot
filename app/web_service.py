"""Free Render Web Service entry point for polling plus the admin panel."""

import asyncio

from app.bot import run_web_service


if __name__ == "__main__":
    asyncio.run(run_web_service())