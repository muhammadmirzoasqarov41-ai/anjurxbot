"""
Punishment service.

Centralises all user-punishment actions: delete, mute, warn.
Every Guard filter calls this service, never the Telegram API directly.

Supported actions (Phase 3):
  delete  — remove a message
  mute    — restrict user from sending messages for N seconds
  warn    — increment warning counter; auto-mute on threshold

Future phases can add:
  ban     — kick + ban
  kick    — remove without ban

Warning system:
  Warnings are stored in Firestore under:
    users/{user_id}/groups/{group_id}/warnings  (int)

  On bot restart the in-memory fallback is cleared, but Firestore
  persists warnings across restarts.

  Default: 3 warnings → auto-mute (5 minutes).
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import ChatPermissions

from app.utils.logger import logger

# Default mute duration when none specified (seconds)
_DEFAULT_MUTE_SECONDS = 300  # 5 minutes

# Warning threshold before auto-mute
_WARN_THRESHOLD = 3

# In-memory fallback warning store  (resets on restart)
# Firestore is the source of truth; this is a write-through cache
_warn_counts: dict[tuple[int, int], int] = {}


# ------------------------------------------------------------------ #
# Delete
# ------------------------------------------------------------------ #

async def delete_message(bot: Bot, chat_id: int, message_id: int, _retried: bool = False) -> bool:
    """
    Delete a single message.

    Returns True on success, False if the bot has no permission or message is gone.
    """
    if not await _permission_allowed(chat_id, "can_delete_messages"):
        logger.warning("Skipping delete in group %s: bot permission is unavailable.", chat_id)
        return False
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info("MESSAGE_DELETED group=%s msg=%s", chat_id, message_id)
        # Track stat (fire-and-forget)
        import asyncio
        from app.services import stats_service
        asyncio.create_task(stats_service.inc_deleted(chat_id))
        return True
    except TelegramRetryAfter as exc:
        if _retried:
            logger.warning("Delete still rate-limited in group %s.", chat_id)
            return False
        await asyncio.sleep(exc.retry_after)
        return await delete_message(bot, chat_id, message_id, _retried=True)
    except TelegramForbiddenError:
        logger.warning(
            "Cannot delete msg %s in group %s — bot lacks 'Delete messages' permission.",
            message_id, chat_id,
        )
        return False
    except TelegramAPIError as exc:
        logger.warning("Failed to delete msg %s in group %s: %s", message_id, chat_id, exc)
        return False


# ------------------------------------------------------------------ #
# Mute
# ------------------------------------------------------------------ #

async def mute_user(
    bot: Bot,
    chat_id: int,
    user_id: int,
    seconds: int = _DEFAULT_MUTE_SECONDS,
    reason: str = "",
    _retried: bool = False,
) -> bool:
    """
    Restrict *user_id* from sending messages for *seconds*.

    Returns True on success.
    """
    until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=seconds)
    if not await _permission_allowed(chat_id, "can_restrict_members"):
        logger.warning("Skipping mute in group %s: bot permission is unavailable.", chat_id)
        return False
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        logger.info(
            "USER_MUTED group=%s user=%s duration=%ss reason=%s",
            chat_id, user_id, seconds, reason or "no reason",
        )
        # Track stat (fire-and-forget)
        import asyncio
        from app.services import stats_service
        asyncio.create_task(stats_service.inc_muted(chat_id))
        from app.services import log_service
        asyncio.create_task(log_service.log_moderation_action(
            chat_id, user_id, "mute", reason, seconds
        ))
        return True
    except TelegramRetryAfter as exc:
        if _retried:
            logger.warning("Mute still rate-limited in group %s.", chat_id)
            return False
        await asyncio.sleep(exc.retry_after)
        return await mute_user(bot, chat_id, user_id, seconds, reason, _retried=True)
    except TelegramForbiddenError:
        logger.warning(
            "Cannot mute user %s in group %s — bot lacks 'Restrict members' permission.",
            user_id, chat_id,
        )
        return False
    except TelegramAPIError as exc:
        logger.warning("Failed to mute user %s in group %s: %s", user_id, chat_id, exc)
        return False


# ------------------------------------------------------------------ #
# Warn  (Firestore-persisted)
# ------------------------------------------------------------------ #

async def _permission_allowed(group_id: int, permission: str) -> bool:
    """Use persisted onboarding state to avoid predictable permission errors."""
    try:
        from app.services import group_service
        group = await group_service.get_group(group_id)
        if group is None or "permissions" not in group:
            return True
        return bool(group.get("permissions", {}).get(permission, False))
    except Exception:
        return True

async def warn_user(
    bot: Bot,
    chat_id: int,
    user_id: int,
    mute_seconds: int = _DEFAULT_MUTE_SECONDS,
    reason: str = "Noma'lum sabab",
) -> int:
    """
    Increment the warning counter for *user_id* in *chat_id*.

    - Reads current count from Firestore (with in-memory cache fallback).
    - Adds a record to the warning history.
    - If the count reaches _WARN_THRESHOLD, the user is muted.
    - Returns the current warning count after incrementing.
    """
    from app.services.firebase import firebase_service
    from app.services import stats_service
    import datetime

    key = (chat_id, user_id)

    # ---- Read current count from Firestore ----
    try:
        doc = await firebase_service.db.collection("users").document(str(user_id)) \
            .collection("groups").document(str(chat_id)).get()
        if doc.exists:
            count = int((doc.to_dict() or {}).get("warnings", 0))
        else:
            count = _warn_counts.get(key, 0)
    except Exception as exc:
        logger.error("Failed to read warnings for user %s in group %s: %s", user_id, chat_id, exc)
        count = _warn_counts.get(key, 0)

    count += 1
    _warn_counts[key] = count

    now = datetime.datetime.now(stats_service.TZ_UZ)

    # ---- Write back to Firestore and add history ----
    try:
        db = firebase_service.db
        batch = db.batch()

        # Update counter
        user_group_ref = db.collection("users").document(str(user_id)) \
            .collection("groups").document(str(chat_id))
        batch.set(user_group_ref, {
            "warnings": count,
            "updated_at": now.isoformat()
        }, merge=True)

        # Add warning history
        history_ref = user_group_ref.collection("warning_logs").document()
        batch.set(history_ref, {
            "user_id": user_id,
            "group_id": chat_id,
            "reason": reason,
            "admin_or_bot": "bot",
            "created_at": now.isoformat(),
            "timestamp": now.timestamp()
        })

        await batch.commit()
    except Exception as exc:
        logger.error("Failed to write warnings for user %s in group %s: %s", user_id, chat_id, exc)

    logger.info(
        "WARNED user=%s group=%s count=%d/%d reason=%s",
        user_id, chat_id, count, _WARN_THRESHOLD, reason
    )

    import asyncio
    asyncio.create_task(stats_service.inc_warnings(chat_id))

    # ---- Auto-mute on threshold ----
    if count >= _WARN_THRESHOLD:
        await mute_user(bot, chat_id, user_id, seconds=mute_seconds, reason="Warnings exceeded")
        return count

    return count


async def reset_warnings(chat_id: int, user_id: int) -> None:
    """Reset the warning counter for *user_id* in *chat_id* (after mute or admin clear)."""
    from app.services.firebase import firebase_service
    from app.services import stats_service
    import datetime

    key = (chat_id, user_id)
    _warn_counts[key] = 0

    try:
        now = datetime.datetime.now(stats_service.TZ_UZ)
        await firebase_service.db.collection("users").document(str(user_id)) \
            .collection("groups").document(str(chat_id)).set(
                {"warnings": 0, "updated_at": now.isoformat()}, merge=True
            )
    except Exception as exc:
        logger.error("Failed to reset warnings for user %s in group %s: %s", user_id, chat_id, exc)


async def clear_warnings(chat_id: int, user_id: int, admin_id: int | None = None) -> None:
    """Clear the active warning count while retaining immutable history."""
    await reset_warnings(chat_id, user_id)
    from app.services import log_service
    asyncio.create_task(log_service.log_admin_action(
        chat_id, admin_id or 0, "warning_cleared", f"user_id={user_id}"
    ))


async def get_warnings(chat_id: int, user_id: int) -> int:
    """Return the current warning count for *user_id* in *chat_id*."""
    from app.services.firebase import firebase_service

    key = (chat_id, user_id)

    # Try Firestore first
    try:
        doc = await firebase_service.db.collection("users").document(str(user_id)) \
            .collection("groups").document(str(chat_id)).get()
        if doc.exists:
            count = int((doc.to_dict() or {}).get("warnings", 0))
            _warn_counts[key] = count
            return count
    except Exception as exc:
        logger.error("Failed to read warnings for user %s in group %s: %s", user_id, chat_id, exc)

    return _warn_counts.get(key, 0)


async def get_warning_history(chat_id: int, user_id: int, limit: int = 10) -> list[dict]:
    """Get warning history for a user in a group."""
    from app.services.firebase import firebase_service
    from google.cloud.firestore_v1.query import Query

    try:
        query = firebase_service.db.collection("users").document(str(user_id)) \
            .collection("groups").document(str(chat_id)) \
            .collection("warning_logs").order_by("timestamp", direction=Query.DESCENDING).limit(limit)

        results = []
        async for doc in query.stream():
            results.append(doc.to_dict())
        return results
    except Exception as exc:
        logger.error("Failed to get warning history for user %s in group %s: %s", user_id, chat_id, exc)
        return []


# ------------------------------------------------------------------ #
# Send notice
# ------------------------------------------------------------------ #

async def send_notice(
    bot: Bot,
    chat_id: int,
    text: str,
    auto_delete_after: Optional[int] = None,
) -> None:
    """
    Send a short notice to the group.

    If *auto_delete_after* is given (seconds), the message will be deleted
    after that delay — used for transient warnings to keep the group clean.
    (Deletion scheduling is fire-and-forget via asyncio.)
    """
    try:
        msg = await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        if auto_delete_after and auto_delete_after > 0:
            asyncio.create_task(_delayed_delete(bot, chat_id, msg.message_id, auto_delete_after))
    except TelegramAPIError as exc:
        logger.warning("Failed to send notice to group %s: %s", chat_id, exc)


async def _delayed_delete(bot: Bot, chat_id: int, message_id: int, delay: int) -> None:
    """Delete *message_id* after *delay* seconds (fire-and-forget helper)."""
    await asyncio.sleep(delay)
    await delete_message(bot, chat_id, message_id)
