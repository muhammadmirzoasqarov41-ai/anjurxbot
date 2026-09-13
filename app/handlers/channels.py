"""
Destination Channel Management Handlers for AnjurX | Obuna Bot.
Implements:
- my_chat_member: Automatic bot admin status detection and posting permission verification
- [➕ Kanal qo‘shish]: Guided wizard with admin permission deep link
- [📢 Mening kanallarim]: Channel list and management dashboard
- [📰 Manbalar]: Multi-select checkboxes for admin-verified sources
- [⏰ Post vaqti]: 1, 2, 3 posts/day frequency & instant vs scheduled modes
- Contract plan info & direct admin contact for extra limits
- Strict ownership verification on every action to prevent IDOR
"""
import logging
from typing import Optional
from aiogram import Router, Bot, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from app.config import config
from app.services.permission_service import is_super_admin
from app.services.rss_storage import rss_storage
from app.keyboards.rss import (
    get_main_menu_keyboard,
    get_channels_list_keyboard,
    get_channel_detail_keyboard,
    get_channel_sources_keyboard,
    get_channel_schedule_keyboard,
    get_contract_contact_keyboard,
    get_disconnect_confirm_keyboard,
    get_connect_channel_guide_keyboard,
)

logger = logging.getLogger("anjurxbot.channels")
router = Router(name="channels_router")


# ==============================================================================
# 1. BOT ADMIN STATUS DETECTION (my_chat_member)
# ==============================================================================

@router.my_chat_member()
async def on_my_chat_member_updated(event: ChatMemberUpdated, bot: Bot):
    """
    Triggers when the bot is added to a channel or its admin permissions change.
    Verifies 'can_post_messages' permission and notifies the channel owner.
    """
    chat = event.chat
    new_member = event.new_chat_member
    from_user = event.from_user

    # Only channels
    if chat.type != "channel":
        return

    is_admin = new_member.status in ("administrator", "creator")
    can_post = False

    if is_admin:
        can_post = getattr(new_member, "can_post_messages", False) is True

        # Register channel in storage
        channel = await rss_storage.register_or_update_channel(
            chat_id=chat.id,
            title=chat.title or f"Kanal {chat.id}",
            username=chat.username,
            owner_user_id=from_user.id if from_user else 0,
            can_post=can_post,
        )

        logger.info(
            f"Bot added to channel '{chat.title}' ({chat.id}): "
            f"is_admin={is_admin}, can_post={can_post}, owner={from_user.id if from_user else 0}"
        )

        # Notify channel owner in private DM
        if from_user and from_user.id > 0:
            try:
                if can_post:
                    text = (
                        "✅ <b>Kanal muvaffaqiyatli ulandi!</b>\n\n"
                        f"📢 <b>{chat.title}</b>\n\n"
                        "Endi ushbu kanal uchun manbalarni tanlashingiz va kunlik postlar "
                        "chastotasini sozlashingiz mumkin."
                    )
                    kb = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="📰 Manbalarni tanlash",
                                    callback_data=f"ch_sources:{channel.chat_id}",
                                ),
                                InlineKeyboardButton(
                                    text="⏰ Post vaqti",
                                    callback_data=f"ch_schedule:{channel.chat_id}",
                                ),
                            ],
                            [
                                InlineKeyboardButton(
                                    text="📢 Mening kanallarim",
                                    callback_data="btn_my_channels",
                                ),
                            ],
                        ]
                    )
                else:
                    text = (
                        "⚠️ <b>Botga kanalga post yuborish huquqi berilmagan!</b>\n\n"
                        f"📢 <b>{chat.title}</b>\n\n"
                        "Iltimos, kanal sozlamalariga kirib, bot uchun <b>Post Messages</b> "
                        "(Xabarlar yozish) huquqini yoqing."
                    )
                    kb = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="🔄 Qayta tekshirish",
                                    callback_data=f"ch_recheck:{channel.chat_id}",
                                ),
                                InlineKeyboardButton(
                                    text="🔙 Bosh menyu",
                                    callback_data="menu_main",
                                ),
                            ]
                        ]
                    )
                await bot.send_message(
                    chat_id=from_user.id,
                    text=text,
                    reply_markup=kb,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.debug(f"Could not send notification to channel owner {from_user.id}: {e}")

    elif new_member.status in ("left", "kicked"):
        # Bot was removed from channel
        ch = await rss_storage.get_channel(chat.id)
        if ch:
            ch.can_post = False
            ch.active = False
            await rss_storage.update_channel_settings(
                chat_id=chat.id,
                user_id=ch.owner_user_id,
                active=False,
                is_super_admin=True,
            )
        logger.info(f"Bot was removed from channel '{chat.title}' ({chat.id})")


# ==============================================================================
# 2. [➕ KANAL QO‘SHISH]
# ==============================================================================

@router.callback_query(F.data == "btn_add_channel")
async def cb_add_channel(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Shows channel connection instructions and deep link."""
    await state.clear()
    bot_info = await bot.get_me()
    bot_username = bot_info.username or config.bot_username or "AnjurXBot"

    text = (
        "📢 <b>Kanal ulash bo‘yicha qo‘llanma</b>\n\n"
        "AnjurX botini Telegram kanalingizga ulash uchun quyidagi 2 ta oddiy qadamni bajaring:\n\n"
        "1️⃣ <b>Quyidagi tugmani bosing</b> va botni kanalingizga qo‘shing.\n"
        "2️⃣ Botga <b>Administrator</b> huquqini va <b>Post Messages</b> (Xabarlar yozish) ruxsatini bering.\n\n"
        "Bot kanalga qo‘shilishi bilan ushbu bot sizga xabar beradi va kanal <b>Mening kanallarim</b> ro‘yxatida paydo bo‘ladi."
    )
    keyboard = get_connect_channel_guide_keyboard(bot_username)

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "btn_check_channel")
async def cb_check_channel(callback: CallbackQuery, bot: Bot):
    """Prompts user to verify channel connection or lists existing."""
    user_id = callback.from_user.id if callback.from_user else 0
    channels = await rss_storage.get_channels_for_user(user_id)

    if channels:
        text = (
            f"✅ Sizda <b>{len(channels)} ta kanal</b> ulangan!\n\n"
            "Ulardan birini tanlab, sozlamalarini boshqaring:"
        )
        kb = get_channels_list_keyboard(channels)
    else:
        text = (
            "ℹ️ <b>Hozircha ulangan kanallar topilmadi.</b>\n\n"
            "Botni kanalingizga administrator qilib qo‘shganingizga ishonch hosil qiling."
        )
        bot_info = await bot.get_me()
        bot_username = bot_info.username or config.bot_username or "AnjurXBot"
        kb = get_connect_channel_guide_keyboard(bot_username)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==============================================================================
# 3. [📢 MENING KANALLARIM]
# ==============================================================================

@router.callback_query(F.data == "btn_my_channels")
async def cb_my_channels(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Displays all channels owned by the user."""
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else 0
    channels = await rss_storage.get_channels_for_user(user_id)

    if not channels:
        text = (
            "📢 <b>Mening kanallarim</b>\n\n"
            "Sizda hali ulangan kanallar mavjud emas.\n\n"
            "Botni kanalingizga administrator qilib qo‘shing va avtomatik yangiliklar tarqatishni boshlang!"
        )
        bot_info = await bot.get_me()
        bot_username = bot_info.username or config.bot_username or "AnjurXBot"
        kb = get_connect_channel_guide_keyboard(bot_username)
    else:
        text = (
            f"📢 <b>Mening kanallarim ({len(channels)} ta)</b>\n\n"
            "Boshqarmoqchi bo‘lgan kanalingiz ustiga bosing:"
        )
        kb = get_channels_list_keyboard(channels)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==============================================================================
# 4. KANAL DASHBOARDI (ch_view:{chat_id})
# ==============================================================================

@router.callback_query(F.data.startswith("ch_view:"))
async def cb_view_channel(callback: CallbackQuery, bot: Bot):
    """Opens individual channel control panel with ownership verification."""
    user_id = callback.from_user.id if callback.from_user else 0
    chat_id = int(callback.data.split(":")[1])

    channel = await rss_storage.get_channel(chat_id)
    if not channel or (channel.owner_user_id != user_id and not is_super_admin(user_id)):
        await callback.answer("⛔ Kanal topilmadi yoki unga ruxsatingiz yo‘q.", show_alert=True)
        return

    channel.reset_daily_if_needed()

    status_str = "🟢 Faol" if (channel.active and channel.can_post) else ("⏸ To‘xtatilgan" if not channel.active else "⚠️ Huquq yetarli emas")
    mode_str = "⚡ Darhol" if channel.schedule_mode == "instant" else "🕐 Belgilangan vaqt"
    plan_badge = "💼 Shartnoma" if channel.plan == "contract" else "Standart (Bepul)"

    text = (
        f"📢 <b>Kanal: {channel.title}</b>\n\n"
        f"• <b>Holat:</b> {status_str}\n"
        f"• <b>Tarif:</b> {plan_badge}\n"
        f"• <b>Tanlangan manbalar:</b> {len(channel.selected_sources)} ta\n"
        f"• <b>Bugun yuborilgan:</b> {channel.today_delivered_count}/{channel.daily_limit} ta\n"
        f"• <b>Kunlik limit:</b> {channel.daily_limit} ta post\n"
        f"• <b>Jadval rejimi:</b> {mode_str}\n"
        f"• <b>Jami yuborilgan:</b> {channel.total_delivered_count} ta post\n\n"
        "Quyidagi tugmalar orqali sozlamalarni o‘zgartiring:"
    )
    kb = get_channel_detail_keyboard(channel)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==============================================================================
# 5. [📰 MANBALAR] (Super Admin Verified Sources Multi-Select)
# ==============================================================================

@router.callback_query(F.data.startswith("ch_sources:"))
async def cb_channel_sources(callback: CallbackQuery, bot: Bot):
    """Displays verified sources for user to toggle for this channel."""
    user_id = callback.from_user.id if callback.from_user else 0
    chat_id = int(callback.data.split(":")[1])

    channel = await rss_storage.get_channel(chat_id)
    if not channel or (channel.owner_user_id != user_id and not is_super_admin(user_id)):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    all_sources = await rss_storage.get_active_sources()
    text = (
        f"📰 <b>Manbalarni tanlash — {channel.title}</b>\n\n"
        "Kanalingizga qaysi manbalardan postlar yuborilishini belgilang:\n"
        "(Ustiga bosib faollashtiring yoki o‘chiring)"
    )
    kb = get_channel_sources_keyboard(channel.chat_id, all_sources, channel.selected_sources)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("ch_src_toggle:"))
async def cb_toggle_channel_source(callback: CallbackQuery, bot: Bot):
    """Toggles source selection on/off for a channel."""
    user_id = callback.from_user.id if callback.from_user else 0
    parts = callback.data.split(":")
    chat_id = int(parts[1])
    source_id = parts[2]

    channel = await rss_storage.get_channel(chat_id)
    if not channel or (channel.owner_user_id != user_id and not is_super_admin(user_id)):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    current = list(channel.selected_sources)
    if source_id in current:
        current.remove(source_id)
        action_msg = "Manba o‘chirildi"
    else:
        current.append(source_id)
        action_msg = "Manba tanlandi"

    await rss_storage.update_channel_sources(chat_id, current, user_id)

    all_sources = await rss_storage.get_active_sources()
    kb = get_channel_sources_keyboard(channel.chat_id, all_sources, current)

    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer(action_msg)


# ==============================================================================
# 6. [⏰ POST VAQTI & CHASTOTASI]
# ==============================================================================

@router.callback_query(F.data.startswith("ch_schedule:"))
async def cb_channel_schedule(callback: CallbackQuery, bot: Bot):
    """Shows frequency (1, 2, 3 posts/day) and schedule mode settings."""
    user_id = callback.from_user.id if callback.from_user else 0
    chat_id = int(callback.data.split(":")[1])

    channel = await rss_storage.get_channel(chat_id)
    if not channel or (channel.owner_user_id != user_id and not is_super_admin(user_id)):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    text = (
        f"⏰ <b>Post vaqti va chastotasi — {channel.title}</b>\n\n"
        f"• Hozirgi kunlik limit: <b>{channel.daily_limit} ta post/kun</b> (Maksimal 3 ta)\n"
        f"• Bugun yuborilgan: <b>{channel.today_delivered_count}/{channel.daily_limit}</b>\n"
        f"• Rejim: <b>{'⚡ Darhol' if channel.schedule_mode == 'instant' else '🕐 Belgilangan vaqt'}</b>\n\n"
        "<b>Kuniga nechta post yuborilsin?</b>"
    )
    kb = get_channel_schedule_keyboard(channel)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("ch_set_limit:"))
async def cb_set_channel_limit(callback: CallbackQuery, bot: Bot):
    """Sets daily post limit (enforces max 3 for free users)."""
    user_id = callback.from_user.id if callback.from_user else 0
    parts = callback.data.split(":")
    chat_id = int(parts[1])
    limit_val = int(parts[2])

    channel = await rss_storage.get_channel(chat_id)
    if not channel or (channel.owner_user_id != user_id and not is_super_admin(user_id)):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    # Backend enforcement: clamp at 3 for non-contract users
    if channel.plan != "contract" and not is_super_admin(user_id):
        limit_val = min(max(1, limit_val), 3)

    await rss_storage.update_channel_settings(
        chat_id=chat_id,
        user_id=user_id,
        daily_limit=limit_val,
        is_super_admin=is_super_admin(user_id),
    )

    await callback.answer(f"✅ Kunlik limit o‘rnatildi: {limit_val} ta post", show_alert=False)
    await cb_channel_schedule(callback, bot)


@router.callback_query(F.data.startswith("ch_set_sched:"))
async def cb_set_channel_schedule_mode(callback: CallbackQuery, bot: Bot):
    """Sets schedule mode between instant and scheduled."""
    user_id = callback.from_user.id if callback.from_user else 0
    parts = callback.data.split(":")
    chat_id = int(parts[1])
    mode = parts[2]

    channel = await rss_storage.get_channel(chat_id)
    if not channel or (channel.owner_user_id != user_id and not is_super_admin(user_id)):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    await rss_storage.update_channel_settings(
        chat_id=chat_id,
        user_id=user_id,
        schedule_mode=mode,
        is_super_admin=is_super_admin(user_id),
    )

    msg = "⚡ Rejim o‘rnatildi: Darhol" if mode == "instant" else "🕐 Rejim o‘rnatildi: Belgilangan vaqt"
    await callback.answer(msg, show_alert=False)
    await cb_channel_schedule(callback, bot)


@router.callback_query(F.data.startswith("ch_contract_info:"))
async def cb_contract_info(callback: CallbackQuery, bot: Bot):
    """Displays info when user wants > 3 posts/day, directing to admin."""
    chat_id = int(callback.data.split(":")[1])

    text = (
        "💼 <b>Ko‘proq post yuborish (Shartnoma asosida)</b>\n\n"
        "AnjurX standart bepul tarifida har bir kanal uchun kunlik "
        "<b>maksimal 3 ta post</b> qat’iy belgilangan.\n\n"
        "Agar kanalingizga kuniga <b>10 ta, 20 ta yoki undan ko‘p</b> post yuborishni "
        "istasangiz, administrator bilan maxsus shartnoma qilishingiz kerak.\n\n"
        "Shartnoma tuzish uchun quyidagi tugma orqali admin bilan bog‘laning:"
    )
    kb = get_contract_contact_keyboard(channel_id=chat_id)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==============================================================================
# 7. TO‘XTATISH / DAVOM ETTIRISH & STATISTIKA & UZISH
# ==============================================================================

@router.callback_query(F.data.startswith("ch_toggle:"))
async def cb_toggle_channel_status(callback: CallbackQuery, bot: Bot):
    """Pauses or resumes posting to this channel."""
    user_id = callback.from_user.id if callback.from_user else 0
    chat_id = int(callback.data.split(":")[1])

    channel = await rss_storage.get_channel(chat_id)
    if not channel or (channel.owner_user_id != user_id and not is_super_admin(user_id)):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    new_active = not channel.active
    await rss_storage.update_channel_settings(
        chat_id=chat_id,
        user_id=user_id,
        active=new_active,
        is_super_admin=is_super_admin(user_id),
    )

    action = "▶️ Kanal faollashtirildi" if new_active else "⏸ Kanal to‘xtatildi"
    await callback.answer(action, show_alert=False)
    await cb_view_channel(callback, bot)


@router.callback_query(F.data.startswith("ch_stats:"))
async def cb_channel_stats(callback: CallbackQuery, bot: Bot):
    """Shows delivery statistics for this channel."""
    user_id = callback.from_user.id if callback.from_user else 0
    chat_id = int(callback.data.split(":")[1])

    channel = await rss_storage.get_channel(chat_id)
    if not channel or (channel.owner_user_id != user_id and not is_super_admin(user_id)):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    channel.reset_daily_if_needed()
    last_del = channel.last_delivered_at or "Hali post yuborilmagan"

    text = (
        f"📊 <b>Statistika — {channel.title}</b>\n\n"
        f"• <b>Bugun yetkazilgan:</b> {channel.today_delivered_count}/{channel.daily_limit}\n"
        f"• <b>Jami yetkazilgan postlar:</b> {channel.total_delivered_count} ta\n"
        f"• <b>Oxirgi yetkazish vaqti:</b> <code>{last_del}</code>\n"
        f"• <b>Ulanish sanasi:</b> <code>{channel.created_at[:10]}</code>\n"
        f"• <b>Kanal ID:</b> <code>{channel.chat_id}</code>\n"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Kanal boshqaruvi", callback_data=f"ch_view:{chat_id}")],
        ]
    )

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("ch_disconnect_ask:"))
async def cb_disconnect_ask(callback: CallbackQuery, bot: Bot):
    """Confirmation prompt before disconnecting channel."""
    user_id = callback.from_user.id if callback.from_user else 0
    chat_id = int(callback.data.split(":")[1])

    channel = await rss_storage.get_channel(chat_id)
    if not channel or (channel.owner_user_id != user_id and not is_super_admin(user_id)):
        await callback.answer("⛔ Ruxsat berilmagan.", show_alert=True)
        return

    text = (
        f"⚠️ <b>Kanalni uzishni tasdiqlaysizmi?</b>\n\n"
        f"📢 <b>{channel.title}</b>\n\n"
        "Kanal uzilsa, unga avtomatik yangiliklar yuborilishi butunlay to‘xtatiladi."
    )
    kb = get_disconnect_confirm_keyboard(chat_id)

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("ch_disconnect_do:"))
async def cb_disconnect_do(callback: CallbackQuery, bot: Bot):
    """Executes channel disconnection."""
    user_id = callback.from_user.id if callback.from_user else 0
    chat_id = int(callback.data.split(":")[1])

    success = await rss_storage.disconnect_channel(chat_id, user_id)
    if success:
        await callback.answer("✅ Kanal muvaffaqiyatli uzildi.", show_alert=True)
        await cb_my_channels(callback, bot, None)
    else:
        await callback.answer("❌ Kanal uzib bo‘lmadi.", show_alert=True)
