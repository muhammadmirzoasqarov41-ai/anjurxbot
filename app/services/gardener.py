"""
Gardener - Background feed polling, 5-day post retention, and fair channel distribution engine.
Integrates PostDistributionService for AnjurX | Obuna Bot.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from aiogram import Bot

from app.services.rss_storage import rss_storage
from app.services.distribution_service import distribution_service
from app.services.firebase import firebase_service

logger = logging.getLogger("anjurxbot.gardener")


class Gardener:
    """Background engine managing news fetching into pool and fair queue distribution to channels."""

    def __init__(self):
        self._bot: Optional[Bot] = None
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._poll_interval: int = 45  # Check pool and feeds every 45 seconds

    def set_bot(self, bot: Bot):
        self._bot = bot

    def start(self, bot: Optional[Bot] = None):
        """Starts the gardener background polling loop."""
        if bot:
            self._bot = bot
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="gardener_news_engine_loop")
        logger.info("Gardener background distribution engine started successfully.")

    def stop(self):
        """Stops the gardener loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Gardener background engine stopped.")

    async def _loop(self):
        """Main periodic loop for news pooling and channel distribution."""
        await asyncio.sleep(4)  # Initial warmup delay
        while self._running:
            try:
                # 1. Fetch new articles into 5-day post pool
                await distribution_service.fetch_and_pool_all_sources(self._bot)

                # 2. Distribute queued posts to eligible channels fairly
                if self._bot:
                    await distribution_service.distribute_queued_posts(self._bot)
                    await distribution_service.distribute_premium_posts(self._bot)

                # 3. Resilient recovery queue flush (processes small batch if recovering/healthy)
                if firebase_service.is_initialized():
                    await firebase_service.flush_recovery_queue(batch_size=20)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in gardener cycle: {e}", exc_info=True)

            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break

    async def check_all_feeds(self):
        """Manual trigger for feed check and queue distribution."""
        await distribution_service.fetch_and_pool_all_sources(self._bot)
        if self._bot:
            await distribution_service.distribute_queued_posts(self._bot)

    async def poll_feed(self, feed) -> int:
        """Polls specific feed and triggers distribution."""
        await distribution_service.fetch_and_pool_all_sources(self._bot)
        if self._bot:
            return await distribution_service.distribute_queued_posts(self._bot)
        return 0


# Global gardener instance
gardener = Gardener()
