"""
Admin command handlers and callback routers.
Includes /panel, manual moderation tools (/warn, /mute, /unmute, /kick, /ban),
and administrative stats inspection.
"""
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app.services.permission_service import permission_service
from app.services.group_service import group_service
from app.services.warning import warning_service
from app.services.moderation import moderation_service
from app.services.stats_service import stats_service
from app.services.firebase import firebase_service
from app.keyboards.admin import get_admin_panel_keyboard, get_global_admin_keyboard
from app.handlers.admin_helpers import verify_admin_callback, extract_group_id_from_callback
from app.config import config

router = Router(name="admin_router")


@router.message(Command("panel"))
async def cmd_panel(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ Bu buyruq faqat guruhlarda ishlaydi.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    is_admin = await permission_service.is_user_admin(bot, chat_id, user_id)
    if not is_admin:
        await message.reply("❌ Bu panel faqat guruh administratorlari uchun ochiq.")
        return

    # Check bot permissions
    is_bot_adm, can_del, can_rst = await permission_service.get_bot_permissions(bot, chat_id)
    warning_note = ""
    if not is_bot_adm or not can_del or not can_rst:
        warning_note = (
            "\n\n⚠️ <i>Diqqat: Bot to'liq ishlashi uchun barcha admin ruxsatlariga "
            "(xabarlarni o'chirish, foydalanuvchilarni bloklash) ega bo'lishi kerak!</i>"
        )

    keyboard = get_admin_panel_keyboard(chat_id)
    await message.reply(
        f"⚙️ <b>Guruh Boshqaruv Paneli:</b> {message.chat.title}\n"
        f"Kerakli bo'limni tanlang:{warning_note}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.message(Command("admin"))
async def cmd_global_admin(message: Message):
    """Global bot superadmin dashboard."""
    user = message.from_user
    if not user or not config.is_admin(user.id):
        await message.reply("❌ Sizda global administrator huquqlari yo'q.")
        return

    keyboard = get_global_admin_keyboard()
    await message.reply(
        "👑 <b>AnjurXBot Super Admin Paneli:</b>\n"
        "Global statistika va barcha guruhlar holati:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callbackQuery(F.data == "global:stats")
async def cb_global_stats(callback: CallbackQuery):
    if not config.is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q.", show_alert=True)
        return

    summary = await stats_service.get_summary()
    runtime = summary.get("runtime", {})
    all_groups = await firebase_service.get_all_groups(limit=200)
    all_users = await firebase_service.get_all_users(limit=200)

    text = (
        "📊 <b>Global Tizim Statistikasi:</b>\n\n"
        f"👥 Guruhlar soni: <b>{len(all_groups)}</b> ta\n"
        f"👤 Foydalanuvchilar: <b>{len(all_users)}</b> ta\n\n"
        f"🔍 Tekshirilgan xabarlar: <b>{runtime.get('messages_checked', 0)}</b>\n"
        f"🔗 O'chirilgan linklar: <b>{runtime.get('links_deleted', 0)}</b>\n"
        f"🚫 To'xtatilgan spamlar: <b>{runtime.get('spam_blocked', 0)}</b>\n"
        f"🌊 To'xtatilgan flood: <b>{runtime.get('flood_stopped', 0)}</b>\n"
        f"🤬 Bloklangan so'kishlar: <b>{runtime.get('bad_words_blocked', 0)}</b>\n"
        f"⚠️ Berilgan ogohlantirishlar: <b>{runtime.get('warnings_issued', 0)}</b>\n"
        f"🔇 Mute qilinganlar: <b>{runtime.get('users_muted', 0)}</b>\n"
    )
    await callback.message.reply(text, parse_mode="HTML")
    await callback.answer()


@router.callbackQuery(F.data.startswith("admin:stats:"))
async def cb_admin_stats(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    summary = await stats_service.get_summary()
    runtime = summary.get("runtime", {})
    text = (
        f"📊 <b>Guruh Statistikasi:</b>\n\n"
        f"🔍 Tekshirilgan xabarlar: <b>{runtime.get('messages_checked', 0)}</b>\n"
        f"🔗 O'chirilgan linklar: <b>{runtime.get('links_deleted', 0)}</b>\n"
        f"🚫 To'xtatilgan spamlar: <b>{runtime.get('spam_blocked', 0)}</b>\n"
        f"🌊 To'xtatilgan flood: <b>{runtime.get('flood_stopped', 0)}</b>\n"
        f"⚠️ Ogohlantirishlar: <b>{runtime.get('warnings_issued', 0)}</b>\n"
    )
    await callback.message.reply(text, parse_mode="HTML")
    await callback.answer()


@router.callbackQuery(F.data.startswith("admin:panel:"))
async def cb_back_to_panel(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    keyboard = get_admin_panel_keyboard(group_id)
    try:
        await callback.message.edit_text(
            "⚙️ <b>Guruh Boshqaruv Paneli:</b>\nKerakli bo'limni tanlang:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


# --- Manual Moderation Commands (Reply-based) ---

@router.message(Command("warn"))
async def cmd_warn(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        return

    if not await permission_service.is_user_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Bu amal faqat guruh adminlari uchun.")
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("⚠️ Foydalanuvchiga ogohlantirish berish uchun uning xabariga reply qiling.")
        return

    target = message.reply_to_message.from_user
    if target.is_bot:
        await message.reply("Botlarga ogohlantirish berilmaydi.")
        return

    if await permission_service.is_user_admin(bot, message.chat.id, target.id):
        await message.reply("Adminlarga ogohlantirish berib bo'lmaydi.")
        return

    group_config = await group_service.get_or_register_group(message.chat.id)
    warn_limit = group_config.get("guard_settings", {}).get("warn_limit", 3)
    punishment_type = group_config.get("guard_settings", {}).get("punishment", "mute")

    new_count, reached = warning_service.add_warning(message.chat.id, target.id, warn_limit)

    if reached:
        if punishment_type == "mute":
            await moderation_service.mute_user(bot, message.chat.id, target.id, 900)
            await message.reply(
                f"🚫 <b>{target.first_name}</b> ogohlantirishlar soni ({warn_limit}/{warn_limit}) to'ldi.\n"
                f"Guruhda 15 daqiqaga mute qilindi.",
                parse_mode="HTML"
            )
        elif punishment_type == "kick":
            await moderation_service.kick_user(bot, message.chat.id, target.id)
            await message.reply(
                f"👞 <b>{target.first_name}</b> ogohlantirishlar soni to'lgani uchun guruhdan chiqarildi.",
                parse_mode="HTML"
            )
        elif punishment_type == "ban":
            await moderation_service.ban_user(bot, message.chat.id, target.id)
            await message.reply(
                f"🔨 <b>{target.first_name}</b> ogohlantirishlar to'lgani uchun guruhdan bloklandi.",
                parse_mode="HTML"
            )
    else:
        await message.reply(
            f"⚠️ <b>{target.first_name}</b> ogohlantirish oldi!\n"
            f"Ogohlantirishlar: <b>{new_count}/{warn_limit}</b>",
            parse_mode="HTML"
        )


@router.message(Command("mute"))
async def cmd_mute(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        return

    if not await permission_service.is_user_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Bu amal faqat guruh adminlari uchun.")
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("⚠️ Foydalanuvchini mute qilish uchun uning xabariga reply qiling.")
        return

    target = message.reply_to_message.from_user
    if await permission_service.is_user_admin(bot, message.chat.id, target.id):
        await message.reply("Adminlarni mute qilib bo'lmaydi.")
        return

    # Parse duration if provided (e.g. /mute 30m, /mute 1h, default 15m)
    args = message.text.split()[1:] if message.text else []
    duration = 900
    if args:
        val = args[0].lower()
        if val.endswith("m") and val[:-1].isdigit():
            duration = int(val[:-1]) * 60
        elif val.endswith("h") and val[:-1].isdigit():
            duration = int(val[:-1]) * 3600
        elif val.isdigit():
            duration = int(val) * 60

    success = await moderation_service.mute_user(bot, message.chat.id, target.id, duration)
    if success:
        mins = duration // 60
        await message.reply(f"🔇 <b>{target.first_name}</b> {mins} daqiqaga mute qilindi.", parse_mode="HTML")
    else:
        await message.reply("❌ Foydalanuvchini mute qilib bo'lmadi. Botda kerakli admin huquqlari borligini tekshiring.")


@router.message(Command("unmute"))
async def cmd_unmute(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        return

    if not await permission_service.is_user_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Bu amal faqat guruh adminlari uchun.")
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("⚠️ Foydalanuvchini un-mute qilish uchun uning xabariga reply qiling.")
        return

    target = message.reply_to_message.from_user
    success = await moderation_service.unmute_user(bot, message.chat.id, target.id)
    if success:
        warning_service.clear_warnings(message.chat.id, target.id)
        await message.reply(f"🔊 <b>{target.first_name}</b> uchun cheklovlar bekor qilindi.", parse_mode="HTML")
    else:
        await message.reply("❌ Cheklovni bekor qilishda xatolik yuz berdi.")


@router.callbackQuery(F.data == "common:close")
async def cb_close(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer()
