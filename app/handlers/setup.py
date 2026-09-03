"""Group onboarding, setup wizard, and bot status updates."""

from __future__ import annotations

import datetime
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message
from aiogram.exceptions import TelegramAPIError

from app.handlers.admin_helpers import build_fsub_text, build_guard_text
from app.keyboards.admin import fsub_panel_keyboard, guard_panel_keyboard
from app.keyboards.setup import setup_keyboard
from app.services import group_service, guard_service
from app.services.firebase import firebase_service
from app.services.permission_service import permission_service
from app.utils.logger import logger
from app.services.rate_limit_service import rate_limit_service
from app.config import settings

router = Router(name="setup")
_GROUP_TYPES = {"group", "supergroup"}
_ADMIN_STATUSES = {"administrator", "creator"}


def _status_line(checked: bool, label: str) -> str:
    return f"{'✅' if checked else '❌'} {label}"


async def _firebase_check(group_id: int) -> bool:
    """Perform a harmless read/write/delete health check in Firestore."""
    try:
        ref = firebase_service.db.collection("health_checks").document(str(group_id))
        await ref.set({"checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        await ref.get()
        await ref.delete()
        return True
    except Exception as exc:
        logger.error("Firebase setup check failed for group %s: %s", group_id, exc)
        return False


async def _setup_report(
    bot: Bot, group_id: int, title: str, user_id: int, test_mode: bool = False
) -> tuple[str, Any]:
    await group_service.ensure_group_exists(group_id, title)
    permissions = await permission_service.verify_bot(bot, group_id)
    firebase_ok = await _firebase_check(group_id)
    fsub = await group_service.get_fsub_settings(group_id)
    guard = await guard_service.get_guard_settings(group_id)
    group_ok = permissions["bot_status"] in _ADMIN_STATUSES
    delete_ok = permissions["permissions"]["can_delete_messages"]
    restrict_ok = permissions["permissions"]["can_restrict_members"]
    if test_mode:
        lines = ["🧪 <b>TIZIM TESTI</b>", "", "Telegram:"]
        lines.append(_status_line(group_ok, "Bot API va admin status"))
        lines.append(_status_line(delete_ok, "Delete permission"))
        lines.append(_status_line(restrict_ok, "Restrict permission"))
        lines.extend(["", "Firebase:", _status_line(firebase_ok, "Read / Write / Delete")])
        lines.extend(["", "📢 Force Subscribe: " + ("✅" if fsub.get("channels") else "⚠️ Sozlanmagan")])
        lines.extend(["🛡 Guard: ✅ Tayyor", "", "Umumiy holat: " + ("🟢 TAYYOR" if group_ok and delete_ok and restrict_ok and firebase_ok else "🟡 SOZLASH KERAK")])
        return "\n".join(lines), setup_keyboard(group_id, user_id)
    lines = ["🛠 <b>SETUP NATIJASI</b>", ""]
    lines.append(_status_line(group_ok, "Bot guruhda admin" if group_ok else "Bot guruhda admin emas"))
    lines.append(_status_line(delete_ok, "Xabarlarni o‘chirish huquqi"))
    lines.append(_status_line(restrict_ok, "Foydalanuvchilarni cheklash huquqi"))
    lines.append(_status_line(firebase_ok, "Firebase ulanishi"))
    lines.append("✅ Majburiy obuna sozlangan" if fsub.get("channels") else "⚠️ Majburiy obuna sozlanmagan")
    lines.append(_status_line(bool(guard), "Qorovul tizimi tayyor"))
    lines.append("")
    lines.append("🟢 <b>Tayyor</b>" if group_ok and delete_ok and restrict_ok and firebase_ok else "🟡 <b>Qo‘shimcha sozlash kerak</b>")
    return "\n".join(lines), setup_keyboard(group_id, user_id)


async def _is_group_admin(bot: Any, group_id: int, user_id: int) -> bool:
    return settings.is_admin(user_id) or await permission_service.is_group_admin(bot, group_id, user_id)


@router.message(Command("setup"))
async def setup_command(message: Message) -> None:
    if message.from_user and not rate_limit_service.allow_setup(message.from_user.id):
        await message.answer("⏳ Juda ko'p so'rov yuborildi. Biroz kuting.")
        return
    if message.chat.type not in _GROUP_TYPES:
        await message.answer("⚠️ /setup buyrug‘i faqat guruhda ishlaydi.")
        return
    if message.from_user is None or not await _is_group_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer("⛔ Faqat guruh administratori setup ishlatishi mumkin.")
        return
    try:
        text, keyboard = await _setup_report(
            message.bot, message.chat.id, message.chat.title or str(message.chat.id), message.from_user.id
        )
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except TelegramAPIError as exc:
        logger.warning("Setup Telegram error in group %s: %s", message.chat.id, exc)
        await message.answer("❌ Telegram tekshiruvi bajarilmadi. Bot adminligini tekshiring.")
    except Exception as exc:
        logger.error("Setup failed for group %s: %s", message.chat.id, exc)
        await message.answer("❌ Setup bajarilmadi. Firebase va bot permissionlarini tekshiring.")


@router.callback_query(F.data.startswith("setup:"))
async def setup_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None or callback.data is None:
        await callback.answer()
        return
    parts = callback.data.split(":")
    try:
        group_id, owner_id = int(parts[1]), int(parts[2])
        action = parts[3]
    except (ValueError, IndexError):
        await callback.answer("❌ Noto‘g‘ri setup so‘rovi.", show_alert=True)
        return
    if callback.from_user.id != owner_id:
        await callback.answer("⛔ Bu setup oynasi boshqa admin uchun.", show_alert=True)
        return
    if not await _is_group_admin(callback.bot, group_id, callback.from_user.id):
        await callback.answer("⛔ Siz endi bu guruh administratori emassiz.", show_alert=True)
        return
    if action in {"perm", "refresh", "test"}:
        try:
            text, keyboard = await _setup_report(
                callback.bot, group_id, callback.message.chat.title or str(group_id), owner_id,
                test_mode=action == "test",
            )
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await callback.answer("✅ Tekshiruv yakunlandi.")
        except Exception as exc:
            logger.error("Setup callback failed for group %s: %s", group_id, exc)
            await callback.answer("❌ Tekshiruv bajarilmadi.", show_alert=True)
        return
    if action == "fsub":
        await callback.message.edit_text(await build_fsub_text(group_id), reply_markup=fsub_panel_keyboard(await group_service.get_fsub_settings(group_id), group_id), parse_mode="HTML")
    elif action == "guard":
        await callback.message.edit_text(await build_guard_text(group_id), reply_markup=guard_panel_keyboard(await guard_service.get_guard_settings(group_id), group_id), parse_mode="HTML")
    elif action == "done":
        await callback.message.edit_text("✅ <b>Setup yakunlandi.</b> Bot guruh himoyasiga tayyor.", parse_mode="HTML")
    await callback.answer()


@router.my_chat_member()
async def bot_membership_updated(event: ChatMemberUpdated) -> None:
    if event.chat.type not in _GROUP_TYPES:
        return
    status = event.new_chat_member.status
    group_id = event.chat.id
    title = event.chat.title or str(group_id)
    try:
        previous = await group_service.get_group(group_id)
        await group_service.ensure_group_exists(group_id, title, event.chat.username or "", event.chat.type)
        if status in _ADMIN_STATUSES:
            health = await permission_service.verify_bot(event.bot, group_id)
            await firebase_service.update_group(group_id, {"title": title, "type": event.chat.type, "is_active": True, "bot_status": status, **health})
            if status == "administrator" and (not previous or previous.get("bot_status") not in _ADMIN_STATUSES):
                await event.bot.send_message(group_id, "👋 Assalomu alaykum!\n\nBot guruhga muvaffaqiyatli ulandi.\n\n🛡 Qorovul va 📢 Majburiy obuna tizimlarini sozlash uchun /setup buyrug‘idan foydalaning.")
        elif status in {"left", "kicked"}:
            await firebase_service.update_group(group_id, {"is_active": False, "bot_status": "removed", "permissions_valid": False, "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        else:
            await firebase_service.update_group(group_id, {"is_active": False, "bot_status": "demoted", "permissions_valid": False, "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        group_service._cache_invalidate(group_id)
    except Exception as exc:
        logger.error("Failed to process bot membership update for group %s: %s", group_id, exc)