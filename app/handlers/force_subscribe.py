"""
Force Subscribe callback handler.

Handles the "✅ Obunani tekshirish" inline button callback.

Callback data format:  fsub_check:{user_id}:{chat_id}

Security model:
  - The callback is owned by *user_id* encoded in the data.
  - If someone else presses the button, they see a silent answer.
  - Re-checking subscription always fetches live data from Telegram API.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from app.services import group_service, subscription_service
from app.keyboards.fsub import fsub_keyboard
from app.utils.logger import logger
from app.services.rate_limit_service import rate_limit_service

router = Router(name="force_subscribe")


@router.callback_query(F.data.startswith("fsub_check:"))
async def handle_fsub_check(callback: CallbackQuery) -> None:
    """
    Process the 'Obunani tekshirish' button press.

    Steps:
      1. Validate ownership (callback sender == user encoded in data).
      2. Re-fetch fsub settings from Firestore.
      3. Check all channel subscriptions live (no cache on subscription status).
      4. If all subscribed → unrestrict + update message.
      5. If still missing → update keyboard with remaining channels.
    """
    if callback.from_user is None or callback.message is None:
        await callback.answer()
        return

    # ---- Parse callback data ----
    try:
        _, uid_str, cid_str = callback.data.split(":")  # type: ignore[union-attr]
        expected_user_id = int(uid_str)
        chat_id = int(cid_str)
    except (ValueError, AttributeError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return

    actual_user_id: int = callback.from_user.id

    if not rate_limit_service.allow_subscription(actual_user_id):
        await callback.answer("⏳ Juda ko'p so'rov yuborildi. Biroz kuting.", show_alert=True)
        return

    # ---- Security: only the original user may verify ----
    if actual_user_id != expected_user_id:
        await callback.answer(
            "⛔ Bu tugma siz uchun emas.",
            show_alert=True,
        )
        return

    bot = callback.bot  # type: ignore[union-attr]

    # ---- Fetch current channel list ----
    try:
        channels = await group_service.get_channels(chat_id)
    except Exception as exc:
        logger.error("Failed to fetch channels for group %s: %s", chat_id, exc)
        await callback.answer("❌ Xatolik yuz berdi. Keyinroq urinib ko'ring.", show_alert=True)
        return

    if not channels:
        # Admin removed all channels while user was waiting
        unrestricted = await subscription_service.unrestrict_user(bot, chat_id, actual_user_id)
        if not unrestricted:
            await callback.answer("❌ Cheklovni olib bo'lmadi. Bot permissionlarini tekshiring.", show_alert=True)
            return
        await callback.message.edit_text(  # type: ignore[union-attr]
            "✅ Obuna tizimi o'chirildi. Endi guruhda yozishingiz mumkin."
        )
        await callback.answer()
        return

    # ---- Live subscription check (no cache) ----
    try:
        all_ok, missing = await subscription_service.check_all_subscriptions(
            bot=bot,
            user_id=actual_user_id,
            channels=channels,
            fresh=True,
        )
    except Exception as exc:
        logger.error("Subscription check failed for user %s: %s", actual_user_id, exc)
        await callback.answer("❌ Tekshirib bo'lmadi. Keyinroq urinib ko'ring.", show_alert=True)
        return

    if all_ok:
        # ---- SUCCESS ----
        await subscription_service.unrestrict_user(bot, chat_id, actual_user_id)
        logger.info(
            "User %s confirmed all subscriptions in group %s.",
            actual_user_id, chat_id,
        )
        try:
            await callback.message.edit_text(  # type: ignore[union-attr]
                "✅ <b>Obunangiz tasdiqlandi!</b>\n\nEndi guruhda xabar yuborishingiz mumkin. 👍",
                parse_mode="HTML",
            )
        except Exception:
            pass
        await callback.answer("✅ Tasdiqlandi!", show_alert=False)

    else:
        # ---- Still missing some channels ----
        remaining_names = ", ".join(
            ch.get("title") or str(ch["channel_id"]) for ch in missing
        )
        logger.info(
            "User %s still missing %d channel(s) in group %s.",
            actual_user_id, len(missing), chat_id,
        )
        await callback.answer(
            f"❌ Siz hali quyidagi kanalga obuna bo'lmagansiz:\n{remaining_names}",
            show_alert=True,
        )
        # Update keyboard to show only the remaining channels
        try:
            await callback.message.edit_reply_markup(  # type: ignore[union-attr]
                reply_markup=fsub_keyboard(
                    channels=missing,
                    user_id=actual_user_id,
                    chat_id=chat_id,
                )
            )
        except Exception:
            pass
