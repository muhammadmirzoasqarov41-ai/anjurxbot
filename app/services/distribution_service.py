"""
Post Distribution & Fair Queue Engine for AnjurX | Obuna Bot.
Implements:
- 5-Day Retention Post Pool fetching & normalization
- Fair Distribution Algorithm (Least Delivered / Fair Round Robin)
- Schedule & Daily 3-Post Limit Strict Enforcement
- Source Interleaving for Balance
- Atomic Claiming & Race Condition Prevention
- Strict Channel Delivery (Never sends RSS content to User DM)
- Automated 5-Day Expiration & Cleanup
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from aiogram import Bot
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramBadRequest,
    TelegramRetryAfter,
)

from app.config import config
from app.services.rss_storage import (
    rss_storage,
    SourceItem,
    ChannelItem,
    PostItem,
    get_tashkent_now,
    get_today_tashkent_str,
)
from app.services.feed_fetcher import feed_fetcher
from app.services.feed_parser import escape_tg_html, truncate_text

logger = logging.getLogger("anjurxbot.distribution")


class PostDistributionService:
    """Manages news pooling, fair queue distribution, and scheduled channel delivery."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._is_distributing = False

    # ==========================================================================
    # 1. FETCH & NORMALIZATION INTO 5-DAY POST POOL
    # ==========================================================================

    async def fetch_and_pool_all_sources(self, bot: Optional[Bot] = None) -> int:
        """
        Fetches all active sources, normalizes items, and inserts them into
        the 5-Day Retention Post Pool. Returns count of newly pooled items.
        """
        sources = await rss_storage.get_active_sources()
        if not sources:
            return 0

        new_items_count = 0
        now = datetime.utcnow()

        for source in sources:
            try:
                parsed, status, new_etag, new_lm, not_modified = await feed_fetcher.fetch_and_parse(
                    source.url,
                    etag=source.etag,
                    last_modified=source.last_modified,
                )
            except Exception as e:
                logger.warning(f"[RSS Fetch Error] Source {source.name} ({source.url}): {e}")
                await rss_storage.update_source(
                    source.id,
                    last_fetch_at=now.isoformat(),
                    last_error=str(e),
                    error_count=source.error_count + 1,
                )
                continue

            if not_modified:
                await rss_storage.update_source(
                    source.id,
                    last_fetch_at=now.isoformat(),
                    error_count=0,
                    last_error=None,
                )
                continue

            if not parsed or not parsed.items:
                await rss_storage.update_source(
                    source.id,
                    last_fetch_at=now.isoformat(),
                    error_count=0,
                )
                continue

            # Process items into Post Pool
            source_new = 0
            for item in parsed.items:
                ext_id = item.get_hash()
                post_id = f"post_{source.id}_{ext_id}"

                # Check if already in pool
                existing = await rss_storage.get_post_from_pool(post_id)
                if existing:
                    continue

                # 5-day retention calculation
                fetched_at_dt = datetime.utcnow()
                expires_at_dt = fetched_at_dt + timedelta(days=5)

                post = PostItem(
                    post_id=post_id,
                    source_id=source.id,
                    source_name=source.name,
                    external_post_id=ext_id,
                    title=item.title or "",
                    description=item.summary or "",
                    content=getattr(item, "content", None) or item.summary or item.title or "",
                    url=item.link,
                    image_url=getattr(item, "image_url", None),
                    media_type=getattr(item, "media_type", None),
                    published_at=item.published,
                    fetched_at=fetched_at_dt.isoformat(),
                    expires_at=expires_at_dt.isoformat(),
                    status="queued",
                )
                saved = await rss_storage.save_post_to_pool(post)
                if saved:
                    source_new += 1
                    new_items_count += 1

            # Update source metadata
            await rss_storage.update_source(
                source.id,
                etag=new_etag,
                last_modified=new_lm,
                last_fetch_at=now.isoformat(),
                last_success_at=now.isoformat(),
                last_error=None,
                error_count=0,
                posts_count=source.posts_count + source_new,
            )

            # Polite inter-feed pacing
            await asyncio.sleep(0.5)

        if new_items_count > 0:
            logger.info(f"[Post Pool] Added {new_items_count} new articles to 5-day pool.")
        return new_items_count

    # ==========================================================================
    # 2. FAIR CHANNEL SELECTION & ELIGIBILITY
    # ==========================================================================

    def is_channel_schedule_ready(self, channel: ChannelItem) -> bool:
        """
        Determines whether a channel is eligible based on its schedule settings.
        - 'instant': Always ready if daily limit is not reached.
        - 'custom' / 'scheduled': Checks if current Tashkent time matches/has passed a scheduled slot today.
        """
        if channel.schedule_mode == "instant":
            return channel.today_delivered_count < channel.daily_limit

        # Custom / Scheduled mode
        tashkent_now = get_tashkent_now()
        current_hm = tashkent_now.strftime("%H:%M")

        # Sort schedule times (e.g. ["09:00", "14:00", "19:00"])
        raw_times = channel.schedule_times or ["09:00", "14:00", "19:00"]
        max_slots = channel.daily_limit if channel.plan == "contract" else min(channel.daily_limit, 3)
        times = sorted(set(raw_times))[:max_slots]

        # Calculate how many slots have passed today in Tashkent timezone
        slots_passed = sum(1 for t in times if current_hm >= t)

        # If more slots have passed than posts delivered today, channel is ready!
        return (slots_passed > channel.today_delivered_count) and (channel.today_delivered_count < channel.daily_limit)

    async def get_eligible_channels_for_post(
        self,
        post: PostItem,
        channels: List[ChannelItem],
    ) -> List[ChannelItem]:
        """
        Evaluates eligibility for a post against all channels:
        1. Channel active & bot has posting rights (can_post)
        2. Channel subscribed to post.source_id
        3. Today's limit not exceeded (strict max 3 for free users)
        4. Schedule condition met
        5. Post not already delivered to this channel (duplicate prevention)
        """
        today_str = get_today_tashkent_str()
        eligible: List[ChannelItem] = []

        for ch in channels:
            ch.reset_daily_if_needed(today_str)

            if not ch.active or not ch.can_post:
                continue

            # Must have chosen this source
            if post.source_id not in ch.selected_sources:
                continue

            # Daily limit check (strict max 3 for normal users)
            if ch.today_delivered_count >= ch.daily_limit:
                continue

            # Schedule check
            if not self.is_channel_schedule_ready(ch):
                continue

            # Duplicate protection check
            is_del = await rss_storage.is_post_delivered(
                source_id=post.source_id,
                external_post_id=post.external_post_id,
                channel_id=ch.chat_id,
            )
            if is_del:
                continue

            eligible.append(ch)

        return eligible

    def select_fair_channel(self, eligible_channels: List[ChannelItem]) -> Optional[ChannelItem]:
        """
        Selects the fairest channel using LEAST DELIVERED / FAIR ROUND ROBIN:
        Priority:
        1. Channel with lowest today_delivered_count (0-post channel wins over 1 or 2 post channels!)
        2. Channel that received a post longest ago (oldest last_delivered_at)
        3. Tie-breaker by chat_id
        """
        if not eligible_channels:
            return None

        def sort_key(ch: ChannelItem):
            # 1. Least delivered today
            count = ch.today_delivered_count
            # 2. Time since last delivered (None = never delivered today = highest priority)
            last_ts = ch.last_delivered_at or "1970-01-01T00:00:00"
            return (count, last_ts, ch.chat_id)

        sorted_channels = sorted(eligible_channels, key=sort_key)
        return sorted_channels[0]

    # ==========================================================================
    # 3. FAIR DISTRIBUTION WORKER
    # ==========================================================================

    async def distribute_queued_posts(self, bot: Bot) -> int:
        """
        Runs a distribution cycle across all queued posts:
        - Interleaves posts from different sources to maintain source balance.
        - For each post, picks the fairest eligible channel.
        - Delivers to Telegram channel directly (never user DM).
        - Unmatched posts remain safely in Post Pool for up to 5 days.
        """
        if self._is_distributing:
            return 0

        async with self._lock:
            self._is_distributing = True
            try:
                # 1. Clean up expired posts older than 5 days
                await rss_storage.cleanup_expired_posts()

                # 2. Load active channels
                all_channels = await rss_storage.get_all_channels()
                active_channels = [c for c in all_channels if c.active and c.can_post]
                if not active_channels:
                    return 0

                # 3. Load queued posts from Post Pool
                queued_posts = await rss_storage.get_queued_posts()
                if not queued_posts:
                    return 0

                # 4. Group by source and interleave for source balance
                by_source: Dict[str, List[PostItem]] = {}
                for p in queued_posts:
                    by_source.setdefault(p.source_id, []).append(p)

                # Round-robin interleaved post sequence
                interleaved_posts: List[PostItem] = []
                source_keys = list(by_source.keys())
                max_len = max(len(v) for v in by_source.values()) if by_source else 0

                for i in range(max_len):
                    for k in source_keys:
                        if i < len(by_source[k]):
                            interleaved_posts.append(by_source[k][i])

                delivered_count = 0

                # 5. Distribute interleaved posts
                for post in interleaved_posts:
                    # Find eligible channels for this post
                    eligible = await self.get_eligible_channels_for_post(post, active_channels)
                    if not eligible:
                        # Post stays in Post Pool! It will wait for tomorrow or schedule
                        continue

                    # Select fairest channel
                    target_channel = self.select_fair_channel(eligible)
                    if not target_channel:
                        continue

                    # Atomic Claim
                    await rss_storage.update_post_status(
                        post.post_id,
                        status="assigned",
                        assigned_channel_id=target_channel.chat_id,
                    )

                    # Deliver to channel
                    success = await self._deliver_post_to_channel(bot, post, target_channel)
                    if success:
                        delivered_count += 1
                        # Small anti-flood pacing
                        await asyncio.sleep(0.3)
                    else:
                        # Release post back to queued status so other eligible channels can take it
                        await rss_storage.update_post_status(post.post_id, status="queued")

                return delivered_count
            finally:
                self._is_distributing = False

    # ==========================================================================
    # 4. TELEGRAM CHANNEL DELIVERY (DIRECT TO CHANNEL, NEVER USER DM)
    # ==========================================================================

    async def _deliver_post_to_channel(
        self,
        bot: Bot,
        post: PostItem,
        channel: ChannelItem,
    ) -> bool:
        """
        Sends formatted news post to Telegram channel.
        Strict requirement: Destination is channel.chat_id. User DM is NEVER used.
        """
        formatted_text = self._format_channel_post(post)

        try:
            # If post has a valid photo/image URL, send as photo
            sent_msg = None
            if post.image_url and post.image_url.startswith("http"):
                try:
                    # Telegram caption limit is 1024 chars
                    caption_text = truncate_text(formatted_text, 1000)
                    sent_msg = await bot.send_photo(
                        chat_id=channel.chat_id,
                        photo=post.image_url,
                        caption=caption_text,
                        parse_mode="HTML",
                    )
                except Exception as img_err:
                    logger.debug(f"Photo send failed for {post.url}, falling back to text: {img_err}")
                    sent_msg = None

            if sent_msg is None:
                sent_msg = await bot.send_message(
                    chat_id=channel.chat_id,
                    text=formatted_text,
                    parse_mode="HTML",
                    disable_web_page_preview=False,
                )

            msg_id = sent_msg.message_id if sent_msg else None

            # Record delivery for duplicate protection and channel stats
            await rss_storage.record_delivery(
                source_id=post.source_id,
                external_post_id=post.external_post_id,
                channel_id=channel.chat_id,
                title=post.title,
                url=post.url,
                telegram_message_id=msg_id,
            )
            # Mark post as delivered
            await rss_storage.update_post_status(
                post.post_id,
                status="delivered",
                assigned_channel_id=channel.chat_id,
            )

            logger.info(
                f"[Delivery Success] '{post.title[:35]}' → Kanal: '{channel.title}' "
                f"({channel.today_delivered_count}/{channel.daily_limit} today)"
            )
            return True

        except TelegramRetryAfter as e:
            logger.warning(f"Rate limited by Telegram. Retry after {e.retry_after}s.")
            await asyncio.sleep(e.retry_after)
            return False

        except (TelegramForbiddenError, TelegramBadRequest) as e:
            err_text = str(e).lower()
            logger.warning(f"Delivery failed for channel {channel.title} ({channel.chat_id}): {e}")

            # Check if bot was kicked or lacks posting permissions
            if any(k in err_text for k in [
                "chat not found",
                "bot was kicked",
                "not a member",
                "have no rights to send a message",
                "can't write",
                "forbidden",
            ]):
                channel.can_post = False
                await rss_storage.update_channel_settings(
                    chat_id=channel.chat_id,
                    user_id=channel.owner_user_id,
                    can_post=False,
                    is_super_admin=True,
                )

                # Inform channel owner in their private DM about the permission issue
                if channel.owner_user_id > 0:
                    try:
                        await bot.send_message(
                            chat_id=channel.owner_user_id,
                            text=(
                                f"⚠️ <b>Kanalingizga post yuborib bo‘lmadi!</b>\n\n"
                                f"📢 <b>{channel.title}</b>\n\n"
                                f"Bot kanal administratorlaridan chiqarilgan yoki <b>Post Messages</b> "
                                f"(Xabarlar yozish) huquqi o‘chirilgan.\n"
                                f"Iltimos, botni administrator qilib, kerakli huquqni bering."
                            ),
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass

            await rss_storage.update_post_status(
                post.post_id,
                status="queued",
                error=str(e),
            )
            return False

        except Exception as e:
            logger.error(f"Unexpected delivery error for post {post.post_id}: {e}")
            await rss_storage.update_post_status(
                post.post_id,
                status="queued",
                error=str(e),
            )
            return False

    @staticmethod
    def _format_channel_post(post: PostItem) -> str:
        """Formats news item into an elegant, clean Telegram HTML message."""
        title_escaped = escape_tg_html(post.title)
        source_escaped = escape_tg_html(post.source_name)
        clean_desc = truncate_text(post.description or "", 350)
        desc_escaped = escape_tg_html(clean_desc)

        header = f"📰 <b><a href=\"{post.url}\">{title_escaped}</a></b>"
        source_line = f"📡 <i>Manba: {source_escaped}</i>"

        lines = [header, source_line]

        if desc_escaped and desc_escaped != title_escaped:
            lines.append("")
            lines.append(desc_escaped)

        lines.append("")
        lines.append(f"🔗 <a href=\"{post.url}\">Batafsil o‘qish</a>")

        return "\n".join(lines)


# Global singleton instance
distribution_service = PostDistributionService()
