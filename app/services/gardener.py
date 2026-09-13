"""
Gardener - Background feed polling, new item detection, and broadcast delivery engine.
Mirrors the gardener concept from iovxw/rssbot, adapted for aiogram 3.
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional
from aiogram import Bot
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramRetryAfter,
)

from app.services.rss_storage import rss_storage, RSSFeed
from app.services.feed_fetcher import feed_fetcher
from app.services.feed_parser import escape_tg_html, truncate_text

logger = logging.getLogger("anjurxbot.gardener")


class Gardener:
    """Background feed monitor and delivery scheduler."""

    def __init__(self):
        self._bot: Optional[Bot] = None
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._poll_interval: int = 60  # Check queue every 60 seconds

    def set_bot(self, bot: Bot):
        self._bot = bot

    def start(self, bot: Optional[Bot] = None):
        """Starts the gardener background polling loop."""
        if bot:
            self._bot = bot
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="gardener_feed_poll_loop")
        logger.info("Gardener background engine started successfully.")

    def stop(self):
        """Stops the gardener loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Gardener background engine stopped.")

    async def _loop(self):
        """Main loop that iterates through feeds and triggers checks."""
        await asyncio.sleep(5)  # initial warmup delay
        while self._running:
            try:
                await self.check_all_feeds()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in gardener loop: {e}", exc_info=True)

            try:
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break

    async def check_all_feeds(self):
        """Iterates over all feeds and checks those due for an update."""
        feeds = await rss_storage.get_all_feeds()
        if not feeds:
            return

        now = datetime.utcnow()
        for feed in feeds:
            if not self._running:
                break

            # If feed has no subscribers, skip polling
            if not feed.subscribers:
                continue

            # Check if due for poll
            should_check = True
            if feed.last_checked:
                try:
                    last_time = datetime.fromisoformat(feed.last_checked)
                    elapsed = (now - last_time).total_seconds()
                    # Backoff on error: interval * min(1 + feed.error_count, 6)
                    effective_interval = feed.interval * min(1 + feed.error_count, 6)
                    if elapsed < effective_interval:
                        should_check = False
                except Exception:
                    should_check = True

            if should_check:
                try:
                    await self.poll_feed(feed)
                except Exception as e:
                    logger.warning(f"Error checking feed {feed.url}: {e}")
                # Inter-feed delay to prevent network congestion
                await asyncio.sleep(1.0)

    async def poll_feed(self, feed: RSSFeed) -> int:
        """
        Polls a single feed, detects new items, delivers them to subscribers.
        Returns the number of new items sent.
        """
        try:
            parsed, status, new_etag, new_lm, not_modified = await feed_fetcher.fetch_and_parse(
                feed.url,
                etag=feed.etag,
                last_modified=feed.last_modified,
            )
        except Exception as e:
            await rss_storage.update_feed_state(feed.id, error=str(e))
            return 0

        if not_modified:
            await rss_storage.update_feed_state(feed.id, etag=feed.etag, last_modified=feed.last_modified)
            return 0

        if not parsed:
            await rss_storage.update_feed_state(feed.id, error=f"Status code {status}")
            return 0

        # Find items that haven't been seen yet
        new_items = []
        new_hashes = []
        for item in parsed.items:
            h = item.get_hash()
            new_hashes.append(h)
            if h not in feed.seen_hashes:
                new_items.append(item)

        # Update feed title/link if changed
        if parsed.title and parsed.title != feed.title and parsed.title != "Nomsiz RSS":
            feed.title = parsed.title
        if parsed.link and parsed.link != feed.link:
            feed.link = parsed.link

        # If this is the very first time we see this feed (no seen_hashes yet),
        # seed seen_hashes with existing items so we don't spam historical items.
        if not feed.seen_hashes and len(new_items) > 1:
            logger.info(f"Seeding {len(new_items)} historical items for new feed: {feed.title}")
            await rss_storage.update_feed_state(
                feed.id,
                seen_hashes=new_hashes,
                etag=new_etag,
                last_modified=new_lm,
            )
            return 0

        delivered_count = 0
        if new_items and self._bot:
            # Send newest items (limit to max 5 in one check to prevent flooding)
            items_to_send = list(reversed(new_items[:5]))
            for item in items_to_send:
                sent_to_any = await self._broadcast_item(feed, item)
                if sent_to_any:
                    delivered_count += 1
                await asyncio.sleep(0.5)

        # Mark all new hashes as seen
        await rss_storage.update_feed_state(
            feed.id,
            seen_hashes=new_hashes,
            etag=new_etag,
            last_modified=new_lm,
        )

        return delivered_count

    async def _broadcast_item(self, feed: RSSFeed, item) -> bool:
        """Sends a formatted feed item to all subscribed chat IDs."""
        if not self._bot or not feed.subscribers:
            return False

        msg_text = self._format_post_message(feed, item)
        recipients_reached = 0
        dead_chats = []

        for chat_id in list(feed.subscribers):
            try:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=msg_text,
                    parse_mode="HTML",
                    disable_web_page_preview=False,
                )
                recipients_reached += 1
                await asyncio.sleep(0.08)  # Anti-flood delay
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                try:
                    await self._bot.send_message(chat_id=chat_id, text=msg_text, parse_mode="HTML")
                    recipients_reached += 1
                except Exception:
                    pass
            except (TelegramForbiddenError, TelegramBadRequest) as e:
                err_text = str(e).lower()
                # Bot was blocked or kicked from group/channel
                if any(k in err_text for k in ["blocked", "kicked", "chat not found", "deactivated", "not a member"]):
                    logger.info(f"Removing inactive subscriber {chat_id} from feed {feed.id} ({feed.title})")
                    dead_chats.append(chat_id)
            except Exception as e:
                logger.warning(f"Failed to deliver item to chat {chat_id}: {e}")

        # Clean up dead subscribers
        for dead_id in dead_chats:
            await rss_storage.remove_subscription(dead_id, feed.id)

        if recipients_reached > 0:
            await rss_storage.record_delivery(
                feed_title=feed.title,
                item_title=item.title,
                item_link=item.link,
                recipient_count=recipients_reached,
            )
            return True

        return False

    @staticmethod
    def _format_post_message(feed: RSSFeed, item) -> str:
        """Formats item into a clean Telegram HTML message."""
        title_escaped = escape_tg_html(item.title)
        feed_title_escaped = escape_tg_html(feed.title)
        summary_clean = clean_summary = truncate_text(item.summary, 300)
        summary_escaped = escape_tg_html(clean_summary)

        header = f"📰 <b><a href=\"{item.link}\">{title_escaped}</a></b>"
        source = f"📡 <i>{feed_title_escaped}</i>"

        lines = [header, source]
        if summary_escaped and summary_escaped != title_escaped:
            lines.append("")
            lines.append(summary_escaped)

        meta = []
        if item.author:
            meta.append(f"✍️ {escape_tg_html(item.author)}")
        if item.published:
            meta.append(f"🕒 {escape_tg_html(item.published)}")

        if meta:
            lines.append("")
            lines.append(" • ".join(meta))

        return "\n".join(lines)


# Global gardener instance
gardener = Gardener()
