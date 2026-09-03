"""
Admin handler scaffold.

Admin-only commands will live here. Currently only contains the admin check
guard so it can be imported and tested without Phase 3 being complete.

Convention: every admin handler should call ``require_admin`` first.
"""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import settings
from app.services.permission_service import permission_service
from app.utils.logger import logger
from app.services import punishment_service

router = Router(name="admin")


async def require_admin(message: Message) -> bool:
    """
    Return True and proceed if the sender is an admin.
    Return False and send a refusal message otherwise.

    Usage inside a handler::

        if not await require_admin(message):
            return
    """
    user_id = message.from_user.id if message.from_user else None
    is_group_admin = False
    if user_id is not None and message.chat.type in {"group", "supergroup"}:
        is_group_admin = await permission_service.is_group_admin(
            message.bot, message.chat.id, user_id
        )
    if user_id is None or (not settings.is_admin(user_id) and not is_group_admin):
        logger.warning(
            "Unauthorised admin access attempt from user_id=%s",
            user_id,
        )
        await message.answer("⛔ Siz admin emassiz.")
        return False
    return True


@router.message(Command("admin"))
async def handle_admin(message: Message) -> None:
    """
    Placeholder /admin command.

    Will be replaced with a full inline admin panel in Phase 3.
    """
    if not await require_admin(message):
        return

    logger.info("/admin called by user_id=%s", message.from_user.id)  # type: ignore[union-attr]
    await message.answer(
        "🔧 Admin paneli tez orada ishga tushadi.\n\n"
        "Hozircha siz admin sifatida tasdiqlangansiz ✅"
    )


@router.message(Command("clearwarns"))
async def handle_clear_warnings(message: Message) -> None:
    """Clear warnings for a replied-to user or an explicit numeric user ID."""
    if not await require_admin(message):
        return
    target_id: int | None = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
    else:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) == 2 and parts[1].strip().lstrip("-").isdigit():
            target_id = int(parts[1].strip())
    if target_id is None:
        await message.answer("ℹ️ Buyruqni foydalanuvchi xabariga reply qilib yuboring yoki user ID kiriting.")
        return
    await punishment_service.clear_warnings(message.chat.id, target_id, message.from_user.id)
    await message.answer(f"✅ Foydalanuvchi <code>{target_id}</code> warninglari tozalandi.")
