"""
Force Subscribe (Majburiy obuna) handlers.
Handles checking user subscription and admin channel management.
"""
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.services.permission_service import permission_service
from app.services.group_service import group_service
from app.services.subscription_service import subscription_service
from app.keyboards.fsub import get_force_sub_admin_keyboard, get_force_sub_user_keyboard
from app.states.admin_states import ChannelAddState
from app.handlers.admin_helpers import verify_admin_callback, extract_group_id_from_callback

router = Router(name="fsub_router")


@router.message(Command("fsub"))
async def cmd_fsub(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ Bu buyruq faqat guruhlarda ishlaydi.")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    is_admin = await permission_service.is_user_admin(bot, chat_id, user_id)
    if not is_admin:
        await message.reply("❌ Bu sozlama faqat guruh adminlari uchun ruxsat etilgan.")
        return

    group_config = await group_service.get_or_register_group(chat_id, message.chat.title or "")
    fsub_settings = group_config.get("force_sub", {})
    is_enabled = fsub_settings.get("is_enabled", False)
    channels = fsub_settings.get("channels", [])

    keyboard = get_force_sub_admin_keyboard(chat_id, channels, is_enabled)
    await message.reply(
        "📢 <b>Majburiy Obuna Sozlamalari:</b>\n\n"
        "Guruh a'zolari xabar yozishdan oldin ko'rsatilgan kanallarga a'zo bo'lishlari kerak bo'ladi.\n"
        "<i>Eslatma: Bot ushbu kanallarda administrator bo'lishi shart!</i>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@router.callbackQuery(F.data.startswith("fsub:menu:"))
async def cb_fsub_menu(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not group_id and callback.message and callback.message.chat:
        group_id = callback.message.chat.id

    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    fsub_settings = group_config.get("force_sub", {})
    is_enabled = fsub_settings.get("is_enabled", False)
    channels = fsub_settings.get("channels", [])

    keyboard = get_force_sub_admin_keyboard(group_id, channels, is_enabled)
    try:
        await callback.message.edit_text(
            "📢 <b>Majburiy Obuna Sozlamalari:</b>\n\n"
            "Guruh a'zolari xabar yozishdan oldin ko'rsatilgan kanallarga a'zo bo'lishlari kerak bo'ladi.\n"
            "<i>Eslatma: Bot ushbu kanallarda administrator bo'lishi shart!</i>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()


@router.callbackQuery(F.data.startswith("fsub:toggle_status:"))
async def cb_fsub_toggle_status(callback: CallbackQuery, bot: Bot):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    fsub_settings = group_config.get("force_sub", {})
    current_status = fsub_settings.get("is_enabled", False)
    new_status = not current_status

    await group_service.update_fsub_setting(group_id, "is_enabled", new_status)
    fsub_settings["is_enabled"] = new_status
    channels = fsub_settings.get("channels", [])

    keyboard = get_force_sub_admin_keyboard(group_id, channels, new_status)
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass

    status_str = "yoqildi ✅" if new_status else "o'chirildi ❌"
    await callback.answer(f"Majburiy obuna {status_str}")


@router.callbackQuery(F.data.startswith("fsub:check:"))
async def cb_fsub_check_user(callback: CallbackQuery, bot: Bot):
    """Callback when regular user clicks 'Obunani tekshirish' button."""
    user = callback.from_user
    if not user:
        await callback.answer("Foydalanuvchi aniqlanmadi.", show_alert=True)
        return

    group_id = extract_group_id_from_callback(callback.data)
    if not group_id and callback.message and callback.message.chat:
        group_id = callback.message.chat.id

    group_config = await group_service.get_or_register_group(group_id)
    channels = group_config.get("force_sub", {}).get("channels", [])

    if not channels:
        await callback.answer("Majburiy kanallar topilmadi. Yozishingiz mumkin! ✅", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    # Invalidate cache to force fresh check
    subscription_service.invalidate_user(user.id)
    is_sub, missing = await subscription_service.verify_user_subscriptions(
        bot=bot,
        channels=channels,
        user_id=user.id,
        force_fresh=True
    )

    if is_sub:
        await callback.answer("Rahmat! Barcha kanallarga obuna bo'lgansiz. Endi xabar yozishingiz mumkin ✅", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
    else:
        missing_titles = ", ".join(ch.get("title", "Kanal") for ch in missing)
        await callback.answer(
            f"❌ Hali quyidagi kanallarga obuna bo'lmagansiz:\n{missing_titles}\n\nIltimos, avval obuna bo'ling!",
            show_alert=True
        )


@router.callbackQuery(F.data.startswith("fsub:del_channel:"))
async def cb_fsub_del_channel(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Xatolik.")
        return

    group_id = int(parts[2])
    channel_id_to_remove = parts[3]

    if not await verify_admin_callback(callback, bot, group_id):
        return

    group_config = await group_service.get_or_register_group(group_id)
    fsub_settings = group_config.get("force_sub", {})
    channels = fsub_settings.get("channels", [])

    new_channels = [ch for ch in channels if str(ch.get("channel_id")) != str(channel_id_to_remove)]
    await group_service.update_fsub_setting(group_id, "channels", new_channels)
    fsub_settings["channels"] = new_channels

    keyboard = get_force_sub_admin_keyboard(group_id, new_channels, fsub_settings.get("is_enabled", False))
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        pass
    await callback.answer("Kanal o'chirildi ✅")


@router.callbackQuery(F.data.startswith("fsub:add_channel:"))
async def cb_fsub_add_channel(callback: CallbackQuery, bot: Bot, state: FSMContext):
    group_id = extract_group_id_from_callback(callback.data)
    if not await verify_admin_callback(callback, bot, group_id):
        return

    await state.set_state(ChannelAddState.waiting_for_channel)
    await state.update_data(group_id=group_id)

    await callback.message.reply(
        "➕ <b>Kanal qo'shish:</b>\n\n"
        "Kanalning username'ini (masalan: <code>@mening_kanalim</code>) yoki "
        "kanal IDsini yuboring.\n\n"
        "<i>Muhim: Bot o'sha kanalda administrator bo'lishi shart!</i>\n"
        "Bekor qilish uchun /cancel yozing.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ChannelAddState.waiting_for_channel)
async def process_channel_input(message: Message, bot: Bot, state: FSMContext):
    text = (message.text or "").strip()
    if text.lower() == "/cancel":
        await state.clear()
        await message.reply("Kanal qo'shish bekor qilindi.")
        return

    data = await state.get_data()
    group_id = data.get("group_id")
    if not group_id:
        await state.clear()
        return

    target = text
    if not target.startswith("@") and not (target.startswith("-100") and target[1:].isdigit()):
        if "/" in target:
            target = "@" + target.split("/")[-1].replace("+", "")
        elif not target.isdigit():
            target = f"@{target}"

    try:
        chat = await bot.get_chat(chat_id=target)
        bot_member = await bot.get_chat_member(chat_id=chat.id, user_id=bot.id)
        if bot_member.status not in ("administrator", "creator"):
            await message.reply(
                f"⚠️ Bot <b>{chat.title}</b> kanalida admin emas!\n"
                f"Iltimos, avval botni kanalga admin qilib qo'shing, so'ng qayta urinib ko'ring.",
                parse_mode="HTML"
            )
            return

        group_config = await group_service.get_or_register_group(group_id)
        channels = list(group_config.get("force_sub", {}).get("channels", []))

        # Check existing
        for existing in channels:
            if str(existing.get("channel_id")) == str(chat.id) or existing.get("username") == chat.username:
                await message.reply("Bu kanal allaqachon qo'shilgan!")
                await state.clear()
                return

        new_entry = {
            "channel_id": chat.id,
            "title": chat.title or str(chat.id),
            "username": chat.username,
            "invite_link": chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else "")
        }
        channels.append(new_entry)
        await group_service.update_fsub_setting(group_id, "channels", channels)

        await message.reply(
            f"✅ <b>{chat.title}</b> kanali muvaffaqiyatli qo'shildi!",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.reply(
            f"❌ Kanalni tekshirishda xatolik yuz berdi: {e}\n"
            f"Bot kanalda mavjudligiga va username to'g'riligiga ishonch hosil qiling."
        )

    await state.clear()
