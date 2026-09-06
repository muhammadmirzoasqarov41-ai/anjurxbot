"""
Subscription Service for checking user membership in mandatory channels (Majburiy Obuna).
"""
import time
import logging
from typing import List, Dict, Any, Tuple, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

logger = logging.getLogger("anjurxbot.subscription")


class SubscriptionService:
    def __init__(self):
        # (user_id, channel_id) -> (is_subscribed, timestamp)
        self._cache: Dict[Tuple[int, str], Tuple[bool, float]] = {}
        self._ttl: float = 60.0

    async def check_channel_subscription(
        self,
        bot: Bot,
        channel_id: Any,
        user_id: int,
        use_cache: bool = True
    ) -> bool:
        """
        Check if user is a member of the given channel.
        """
        now = time.time()
        ch_key = str(channel_id)
        cache_key = (user_id, ch_key)

        if use_cache and cache_key in self._cache:
            sub, ts = self._cache[cache_key]
            if now - ts < self._ttl:
                return sub

        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            status = getattr(member, "status", "").lower()
            is_sub = status in ("creator", "administrator", "member", "restricted")
            self._cache[cache_key] = (is_sub, now)
            return is_sub
        except (TelegramBadRequest, TelegramForbiddenError) as e:
            logger.debug(f"User {user_id} check in channel {channel_id} failed: {e}")
            self._cache[cache_key] = (False, now)
            return False
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=check_channel_subscription channel={channel_id}")
            return False

    async def verify_user_subscriptions(
        self,
        bot: Bot,
        channels: List[Dict[str, Any]],
        user_id: int,
        force_fresh: bool = False
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Verifies membership in all required channels.
        Returns (is_all_subscribed, list_of_missing_channels).
        """
        missing = []
        for ch in channels:
            cid = ch.get("channel_id")
            if not cid:
                continue
            is_sub = await self.check_channel_subscription(
                bot=bot,
                channel_id=cid,
                user_id=user_id,
                use_cache=not force_fresh
            )
            if not is_sub:
                missing.append(ch)

        return (len(missing) == 0, missing)

    def invalidate_user(self, user_id: int) -> None:
        keys = [k for k in self._cache if k[0] == user_id]
        for k in keys:
            self._cache.pop(k, None)


subscription_service = SubscriptionService()
