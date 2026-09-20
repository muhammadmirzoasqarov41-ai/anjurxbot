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
from typing import List, Optional, Dict, Tuple, Any
from aiogram import Bot
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InputMediaPhoto,
    InputMediaVideo,
    InputMediaDocument,
    InputMediaAudio,
)
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
    PremiumPostItem,
    get_tashkent_now,
    get_today_tashkent_str,
)
from app.services.feed_fetcher import feed_fetcher
from app.services.feed_parser import escape_tg_html, truncate_text
from app.services.gemini_translator import (
    gemini_translator,
    TranslationNotConfiguredError,
    TranslationTemporaryError,
)

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
            logger.info(f"[Post Pool] Added {new_items_count} new articles to pool. Enforcing 500 limit...")
            await rss_storage.cleanup_post_pool(500)
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
        Translates post content according to channel.post_language ('uz', 'ru', 'en', 'auto')
        using Gemini API with cache (post_id:post_language) and error handling.
        Strict requirement: Destination is channel.chat_id. User DM is NEVER used.
        """
        target_lang = getattr(channel, "post_language", "uz") or "uz"
        title_to_post = post.title
        desc_to_post = post.description or ""

        # Find source language if available from registered sources
        source = rss_storage.get_source(post.source_id)
        source_lang = getattr(source, "language", None) if source else None

        # Translate post if needed
        try:
            translated = await gemini_translator.translate_post(
                post_id=post.post_id,
                title=post.title,
                description=desc_to_post,
                target_language=target_lang,
                channel_id=channel.chat_id,
                source_language=source_lang,
            )
            title_to_post = translated.title
            desc_to_post = translated.description
        except TranslationNotConfiguredError:
            # Check if user explicitly allowed fallback to original when API key is missing
            allow_fallback = os.getenv("TRANSLATION_FALLBACK_TO_ORIGINAL", "false").lower() in ("true", "1", "yes")
            if allow_fallback:
                logger.info(
                    f"[TRANSLATOR] API key not configured, delivering original post for channel {channel.title} ({channel.chat_id}) as fallback."
                )
            else:
                logger.warning(
                    f"[TRANSLATOR] Gemini translator: API key not configured for post {post.post_id} "
                    f"destined for channel {channel.title} ({channel.chat_id}) [target_lang={target_lang}]. "
                    "Retaining post in pool as translation_pending without delivering untranslated text."
                )
                await rss_storage.update_post_status(
                    post.post_id,
                    status="translation_pending",
                    error="Gemini translator: API key not configured",
                )
                return False
        except TranslationTemporaryError as tte:
            logger.warning(
                f"[TRANSLATOR] Temporary translation backoff for post {post.post_id} [{target_lang}]: {tte}. "
                "Retaining post in pool for scheduled retry."
            )
            await rss_storage.update_post_status(
                post.post_id,
                status="queued",
                error=str(tte),
            )
            return False
        except Exception as trans_err:
            logger.error(
                f"[TRANSLATOR] Failed translating post {post.post_id} to '{target_lang}' "
                f"for channel {channel.title} ({channel.chat_id}): {trans_err}. "
                "Retaining post in pool without sending malformed text."
            )
            await rss_storage.update_post_status(
                post.post_id,
                status="queued",
                error=str(trans_err),
            )
            return False

        formatted_text = self._format_channel_post(
            title=title_to_post,
            description=desc_to_post,
            url=post.url,
            source_name=post.source_name,
            target_lang=target_lang,
        )

        # Check if channel has inline button footer
        reply_markup = None
        if getattr(channel, "footer_type", "none") == "button" and getattr(channel, "footer_url", None):
            btn_txt = getattr(channel, "footer_text", "") or "Batafsil"
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=btn_txt, url=channel.footer_url)
            ]])

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
                        reply_markup=reply_markup,
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
                    reply_markup=reply_markup,
                )

            msg_id = sent_msg.message_id if sent_msg else None

            # Record delivery for duplicate protection and channel stats
            await rss_storage.record_delivery(
                source_id=post.source_id,
                external_post_id=post.external_post_id,
                channel_id=channel.chat_id,
                title=title_to_post,
                url=post.url,
                telegram_message_id=msg_id,
                target_language=target_lang,
                post_id=post.post_id,
            )
            # Mark post as delivered
            await rss_storage.update_post_status(
                post.post_id,
                status="delivered",
                assigned_channel_id=channel.chat_id,
            )

            logger.info(
                f"[Delivery Success] '{title_to_post[:35]}' [{target_lang}] → Kanal: '{channel.title}' "
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
    def _format_channel_post(
        title: str,
        description: str,
        url: str,
        source_name: str,
        target_lang: str = "uz",
    ) -> str:
        """Formats news item into an elegant, clean Telegram HTML message in the selected language."""
        title_escaped = escape_tg_html(title)
        source_escaped = escape_tg_html(source_name)
        clean_desc = truncate_text(description or "", 350)
        desc_escaped = escape_tg_html(clean_desc)

        # Localized read more label
        read_more_labels = {
            "uz": "Batafsil o‘qish",
            "ru": "Читать полностью",
            "en": "Read full article",
            "auto": "Batafsil o‘qish",
        }
        source_prefix_labels = {
            "uz": "Manba",
            "ru": "Источник",
            "en": "Source",
            "auto": "Manba",
        }

        read_more = read_more_labels.get(target_lang, "Batafsil o‘qish")
        source_prefix = source_prefix_labels.get(target_lang, "Manba")

        header = f"📰 <b><a href=\"{url}\">{title_escaped}</a></b>"
        source_line = f"📡 <i>{source_prefix}: {source_escaped}</i>"

        lines = [header, source_line]

        if desc_escaped and desc_escaped != title_escaped:
            lines.append("")
            lines.append(desc_escaped)

        lines.append("")
        lines.append(f"🔗 <a href=\"{url}\">{read_more}</a>")

        return "\n".join(lines)

    # ==========================================================================
    # 5. PREMIUM CONTENT DISTRIBUTION ENGINE
    # ==========================================================================

    async def distribute_premium_posts(self, bot: Bot) -> int:
        """
        Distributes human-curated premium content to eligible channels:
        - Independent from RSS 500-post pool limit.
        - Only for channels where is_premium_eligible=True AND premium_enabled=True.
        - Respects daily_limit, schedule, and duplicate prevention.
        - Supports all media formats, custom footers, and AI translation.
        """
        ready_posts = await rss_storage.get_ready_premium_posts()
        if not ready_posts:
            return 0

        all_channels = await rss_storage.get_all_channels()
        # Channels must be active, can_post, status == 'ACTIVE', premium, and NOT central post base
        prem_channels = [
            c for c in all_channels
            if c.active and c.can_post and (
                getattr(c, "premium", False) or getattr(c, "is_premium_eligible", False) or getattr(c, "premium_enabled", False)
            ) and getattr(c, "status", "ACTIVE") == "ACTIVE" and c.chat_id != -1004373620008
        ]
        if not prem_channels:
            return 0

        delivered_total = 0
        today_str = get_today_tashkent_str()

        for post in ready_posts:
            # Find eligible channels for this premium post
            eligible_for_post: List[ChannelItem] = []
            for ch in prem_channels:
                ch.reset_daily_if_needed(today_str)
                # Respect daily limit
                if ch.today_delivered_count >= ch.daily_limit:
                    continue
                # Respect schedule
                if not self.is_channel_schedule_ready(ch):
                    continue
                # Check duplicate protection
                if await rss_storage.is_premium_post_delivered(post.id, ch.chat_id):
                    continue
                eligible_for_post.append(ch)

            if not eligible_for_post:
                continue

            # Deliver to each eligible channel that hasn't received this post yet
            for target_channel in eligible_for_post:
                # Re-check daily limit in case it changed in this loop
                if target_channel.today_delivered_count >= target_channel.daily_limit:
                    continue
                if await rss_storage.is_premium_post_delivered(post.id, target_channel.chat_id):
                    continue

                success = await self._deliver_premium_post_to_channel(bot, post, target_channel)
                if success:
                    delivered_total += 1
                    await asyncio.sleep(0.3)

        return delivered_total

    async def _deliver_premium_post_to_channel(
        self,
        bot: Bot,
        post: PremiumPostItem,
        channel: ChannelItem,
    ) -> bool:
        """Delivers a single premium post with optional translation and footer to destination channel."""
        logger.info(f"[DISTRIBUTION] Starting: postId={post.id}")
        logger.info(f"[DISTRIBUTION] Target: channelId={channel.chat_id}")
        target_lang = getattr(channel, "post_language", "uz") or "uz"
        text_to_send = post.text or ""

        # 1. Translate if requested and language differs
        if text_to_send and target_lang != "auto":
            try:
                translated = await gemini_translator.translate_post(
                    post_id=post.id,
                    title="Premium Post",
                    description=text_to_send,
                    target_language=target_lang,
                    channel_id=channel.chat_id,
                )
                text_to_send = translated.description or text_to_send
            except Exception as e:
                logger.debug(f"[Premium Translate] Fallback to original text for {post.id}: {e}")

        # 2. Append text footer if configured
        footer_type = getattr(channel, "footer_type", "none")
        footer_text = getattr(channel, "footer_text", "") or ""
        footer_url = getattr(channel, "footer_url", "") or ""

        if footer_type == "text" and footer_text:
            text_to_send = f"{text_to_send}\n\n{escape_tg_html(footer_text)}"
        elif footer_type == "link" and footer_text and footer_url:
            text_to_send = f"{text_to_send}\n\n👉 <a href=\"{footer_url}\">{escape_tg_html(footer_text)}</a>"

        # 3. Build inline button reply_markup if configured
        reply_markup = None
        if footer_type == "button" and footer_url:
            btn_label = footer_text or "Batafsil"
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=btn_label, url=footer_url)
            ]])

        # 4. Dispatch based on media_type
        sent_msg_id = None
        try:
            mtype = post.media_type
            if mtype == "text":
                res = await bot.send_message(
                    chat_id=channel.chat_id,
                    text=text_to_send,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    disable_web_page_preview=False,
                )
                sent_msg_id = res.message_id
            elif mtype == "photo" and post.media_file_id:
                caption = truncate_text(text_to_send, 1000)
                res = await bot.send_photo(
                    chat_id=channel.chat_id,
                    photo=post.media_file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                sent_msg_id = res.message_id
            elif mtype == "video" and post.media_file_id:
                caption = truncate_text(text_to_send, 1000)
                res = await bot.send_video(
                    chat_id=channel.chat_id,
                    video=post.media_file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                sent_msg_id = res.message_id
            elif mtype == "document" and post.media_file_id:
                caption = truncate_text(text_to_send, 1000)
                res = await bot.send_document(
                    chat_id=channel.chat_id,
                    document=post.media_file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                sent_msg_id = res.message_id
            elif mtype == "audio" and post.media_file_id:
                caption = truncate_text(text_to_send, 1000)
                res = await bot.send_audio(
                    chat_id=channel.chat_id,
                    audio=post.media_file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                sent_msg_id = res.message_id
            elif mtype == "voice" and post.media_file_id:
                caption = truncate_text(text_to_send, 1000)
                res = await bot.send_voice(
                    chat_id=channel.chat_id,
                    voice=post.media_file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                sent_msg_id = res.message_id
            elif mtype == "animation" and post.media_file_id:
                caption = truncate_text(text_to_send, 1000)
                res = await bot.send_animation(
                    chat_id=channel.chat_id,
                    animation=post.media_file_id,
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                sent_msg_id = res.message_id
            elif mtype == "media_group" and post.media_items:
                media_list = []
                for idx, itm in enumerate(post.media_items):
                    cap = truncate_text(text_to_send, 1000) if idx == 0 else None
                    pm = "HTML" if cap else None
                    if itm.get("type") == "video":
                        media_list.append(InputMediaVideo(media=itm["file_id"], caption=cap, parse_mode=pm))
                    elif itm.get("type") == "document":
                        media_list.append(InputMediaDocument(media=itm["file_id"], caption=cap, parse_mode=pm))
                    elif itm.get("type") == "audio":
                        media_list.append(InputMediaAudio(media=itm["file_id"], caption=cap, parse_mode=pm))
                    else:
                        media_list.append(InputMediaPhoto(media=itm["file_id"], caption=cap, parse_mode=pm))

                album_res = await bot.send_media_group(chat_id=channel.chat_id, media=media_list)
                sent_msg_id = album_res[0].message_id if album_res else None
                # If button footer exists for media group, send a follow-up link message
                if reply_markup:
                    try:
                        await bot.send_message(
                            chat_id=channel.chat_id,
                            text="🔗 Havola:",
                            reply_markup=reply_markup,
                        )
                    except Exception:
                        pass
            else:
                # Fallback to text message
                res = await bot.send_message(
                    chat_id=channel.chat_id,
                    text=text_to_send or "[Media content]",
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                sent_msg_id = res.message_id

            # 5. Record delivery
            await rss_storage.record_premium_delivery(
                post=post,
                channel=channel,
                telegram_message_id=sent_msg_id,
                target_language=target_lang,
            )
            logger.info(f"[DISTRIBUTION] SUCCESS: postId={post.id} channelId={channel.chat_id}")
            logger.info(f"[Premium Delivery] Post {post.id} ({post.media_type}) → Channel '{channel.title}'")
            return True

        except TelegramRetryAfter as e:
            logger.error(f"[DISTRIBUTION] FAILED: postId={post.id} channelId={channel.chat_id} error={e}")
            logger.warning(f"[Premium Delivery] Rate limited. Retry after {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
            return False
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.error(f"[DISTRIBUTION] FAILED: postId={post.id} channelId={channel.chat_id} error={e}")
            logger.warning(f"[Premium Delivery] Failed for channel {channel.title} ({channel.chat_id}): {e}")
            if "not a member" in str(e).lower() or "bot was kicked" in str(e).lower():
                await rss_storage.update_channel(channel.chat_id, can_post=False, active=False)
            return False
        except Exception as e:
            logger.error(f"[DISTRIBUTION] FAILED: postId={post.id} channelId={channel.chat_id} error={e}")
            logger.error(f"[Premium Delivery] Unexpected error for {post.id}: {e}")
            return False


# Global singleton instance
distribution_service = PostDistributionService()
