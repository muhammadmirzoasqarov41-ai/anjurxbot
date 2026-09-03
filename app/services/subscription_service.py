"""
Telegram subscription checker service.

Wraps getChatMember calls and interprets the response status.
All Telegram API calls related to subscription checking live here
so handlers never touch the Bot object for this purpose directly.
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum, auto
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter

from app.utils.logger import logger


class SubStatus(Enum):
    """Result of a single-channel subscription check."""
    SUBSCRIBED = auto()      # member / administrator / creator
    NOT_SUBSCRIBED = auto()  # left / kicked / not found
    ERROR = auto()           # bot has no access, channel not found, etc.


def _status_value(member) -> str:
    raw_status = getattr(member, "status", "")
    value = getattr(raw_status, "value", raw_status)
    return str(value).rsplit(".", 1)[-1].lower()


_STATUS_CACHE_TTL = 15.0
_status_cache: dict[tuple[int, int], tuple[SubStatus, float]] = {}
_member_status_cache: dict[tuple[int, int], tuple[str, float]] = {}


def _cached_status(user_id: int, target_id: int) -> SubStatus | None:
    entry = _status_cache.get((user_id, target_id))
    if entry is None:
        return None
    status, created = entry
    if time.monotonic() - created >= _STATUS_CACHE_TTL:
        _status_cache.pop((user_id, target_id), None)
        return None
    return status


def _cached_member_status(user_id: int, chat_id: int) -> str | None:
    entry = _member_status_cache.get((user_id, chat_id))
    if entry is None:
        return None
    status, created = entry
    if time.monotonic() - created >= _STATUS_CACHE_TTL:
        _member_status_cache.pop((user_id, chat_id), None)
        return None
    return status


async def check_subscription(
    bot: Bot,
    user_id: int,
    channel_id: int,
    fresh: bool = False,
) -> SubStatus:
    """
    Check whether *user_id* is subscribed to *channel_id*.

    Returns:
        SubStatus.SUBSCRIBED      — member/admin/creator
        SubStatus.NOT_SUBSCRIBED  — left/kicked/absent
        SubStatus.ERROR           — bot cannot check (no permission, channel gone, etc.)
    """
    if not fresh:
        cached = _cached_status(user_id, channel_id)
        if cached is not None:
            return cached
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        status = _status_value(member)  # e.g. member, administrator, creator, left, kicked

        if status in ("member", "administrator", "creator"):
            result = SubStatus.SUBSCRIBED
        else:
            result = SubStatus.NOT_SUBSCRIBED
        if not fresh:
            _status_cache[(user_id, channel_id)] = (result, time.monotonic())
        return result

    except TelegramRetryAfter as exc:
        logger.warning("Telegram rate limit for channel %s; retrying after %ss.", channel_id, exc.retry_after)
        await asyncio.sleep(exc.retry_after)
        return await check_subscription(bot, user_id, channel_id, fresh=True)
    except (asyncio.TimeoutError, OSError) as exc:
        logger.warning("Network error checking channel %s: %s", channel_id, exc)
        return SubStatus.ERROR

    except TelegramForbiddenError:
        # Bot was removed from the channel or the channel is private without bot access
        logger.warning(
            "Cannot check subscription for channel %s — bot has no access (Forbidden).",
            channel_id,
        )
        return SubStatus.ERROR

    except TelegramBadRequest as exc:
        logger.warning(
            "Bad request while checking channel %s for user %s: %s",
            channel_id, user_id, exc,
        )
        return SubStatus.ERROR

    except TelegramAPIError as exc:
        logger.error(
            "Telegram API error checking channel %s for user %s: %s",
            channel_id, user_id, exc,
        )
        return SubStatus.ERROR

    except Exception as exc:
        logger.error(
            "Unexpected error checking channel %s for user %s: %s",
            channel_id, user_id, exc, exc_info=exc,
        )
        return SubStatus.ERROR


async def check_all_subscriptions(
    bot: Bot,
    user_id: int,
    channels: list[dict],
    fresh: bool = False,
) -> tuple[bool, list[dict]]:
    """
    Check all *channels* for *user_id*.

    Returns:
        (all_subscribed, missing_channels)
        - all_subscribed: True only when every valid channel returns SUBSCRIBED
        - missing_channels: channels the user is NOT subscribed to
          (ERROR channels are excluded — we don't punish the user for bot config issues)
    """
    missing: list[dict] = []

    for ch in channels:
        channel_id: int = ch["channel_id"]
        status = await check_subscription(bot, user_id, channel_id, fresh=fresh)

        if status == SubStatus.NOT_SUBSCRIBED:
            missing.append(ch)
        elif status == SubStatus.ERROR:
            # Fail closed: a required channel cannot be verified, so do not
            # grant access based on an unavailable Telegram response.
            missing.append(ch)
            logger.warning(
                "Blocking channel %s (check returned ERROR) for user %s.",
                channel_id, user_id,
            )

    return len(missing) == 0, missing


async def restrict_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Remove the user's ability to send messages in *chat_id*.

    Returns True on success, False if the bot lacks permissions.
    """
    from aiogram.types import ChatPermissions

    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
        )
        logger.info("User %s restricted in chat %s (awaiting fsub).", user_id, chat_id)
        return True

    except TelegramForbiddenError:
        logger.warning(
            "Cannot restrict user %s in chat %s — bot lacks permission.",
            user_id, chat_id,
        )
        return False

    except TelegramAPIError as exc:
        logger.warning(
            "Failed to restrict user %s in chat %s: %s",
            user_id, chat_id, exc,
        )
        return False


async def unrestrict_user(bot: Bot, chat_id: int, user_id: int) -> bool:
    """
    Restore the user's ability to send messages in *chat_id*.

    Returns True on success, False if the bot lacks permissions.
    """
    from aiogram.types import ChatPermissions

    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            ),
        )
        logger.info("User %s unrestricted in chat %s (fsub confirmed).", user_id, chat_id)
        return True

    except TelegramForbiddenError:
        logger.warning(
            "Cannot unrestrict user %s in chat %s — bot lacks permission.",
            user_id, chat_id,
        )
        return False

    except TelegramAPIError as exc:
        logger.warning(
            "Failed to unrestrict user %s in chat %s: %s",
            user_id, chat_id, exc,
        )
        return False


async def delete_message_safe(bot: Bot, chat_id: int, message_id: int) -> None:
    """Delete a message, logging any error without raising."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramAPIError as exc:
        logger.warning(
            "Could not delete message %s in chat %s: %s",
            message_id, chat_id, exc,
        )


async def get_member_status(bot: Bot, chat_id: int, user_id: int, fresh: bool = False) -> Optional[str]:
    """
    Return the raw membership status string for *user_id* in *chat_id*.

    Returns None on error.
    """
    if not fresh:
        cached = _cached_member_status(user_id, chat_id)
        if cached is not None:
            return cached
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        status = _status_value(member)
        if not fresh:
            _member_status_cache[(user_id, chat_id)] = (status, time.monotonic())
        return status
    except TelegramRetryAfter as exc:
        await asyncio.sleep(exc.retry_after)
        return await get_member_status(bot, chat_id, user_id, fresh=True)
    except (asyncio.TimeoutError, OSError):
        return None
    except TelegramAPIError:
        return None
