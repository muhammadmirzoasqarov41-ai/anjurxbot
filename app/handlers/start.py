"""
Start, Settings, Help, and Main Navigation Handlers for AnjurX | Obuna Bot.
Implements the exact UI requested:
- [➕ Kanal qo‘shish]
- [📢 Mening kanallarim]
- [⚙️ Sozlamalar]
- [❓ Yordam]
(+ [👑 Super Admin Panel] for Super Admin only)
- Direct contact with Admin via https://t.me/usafes
"""
import logging
from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.config import config
from app.services.permission_service import is_super_admin
from app.services.rss_storage import rss_storage
from app.keyboards.rss import (
    get_main_menu_keyboard,
    get_help_keyboard,
    get_contract_contact_keyboard,
)

logger = logging.getLogger("anjurxbot.start")
router = Router(name="start_router")


def get_welcome_caption() -> str:
    return (
        "<b>AnjurX | Obuna Bot</b>\n\n"
        "📰 <b>Yangiliklarni Telegram kanalingizga avtomatik yetkazish xizmati.</b>\n\n"
        "Tasdiqlangan yangiliklar manbalaridan (Kun.uz, Daryo.uz, Gazeta.uz va h.k.) eng sara "
        "postlar kunlik belgilangan me’yorda kanalingizga avtomatik yuboriladi.\n\n"
        "Quyidagi menyudan kerakli bo‘limni tanlang:"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Presents the streamlined AnjurX main menu and registers user profile."""
    await state.clear()
    user = message.from_user
    user_id = user.id if user else 0
    username = user.username if user else None
    first_name = user.first_name if user else ""

    # Register/update user profile in storage
    await rss_storage.get_or_create_user(user_id=user_id, username=username, first_name=first_name)

    keyboard = get_main_menu_keyboard(user_id=user_id)
    await message.answer(
        get_welcome_caption(),
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("help"))
@router.callback_query(F.data == "btn_help")
async def cmd_help(event, state: FSMContext):
    """Provides user guide and direct admin contact."""
    await state.clear()
    help_text = (
        "❓ <b>Botdan foydalanish bo‘yicha qo‘llanma</b>\n\n"
        "1️⃣ <b>Kanal ulash:</b>\n"
        "• <code>[➕ Kanal qo‘shish]</code> tugmasini bosing;\n"
        "• Botni kanalingizga <b>Administrator</b> qilib qo‘shing;\n"
        "• <b>Post Messages</b> (Xabarlar yozish) ruxsatini yoqing.\n\n"
        "2️⃣ <b>Manbalarni tanlash:</b>\n"
        "• <code>[📢 Mening kanallarim]</code> bo‘limiga kiring;\n"
        "• Kanalingizni tanlang va <code>[📰 Manbalar]</code> tugmasi orqali qaysi saytlardan postlar kelishini belgilang.\n\n"
        "3️⃣ <b>Post vaqti va me’yori:</b>\n"
        "• Standart bepul tarifda kuniga <b>maksimal 3 ta post</b> kanalingizga yuboriladi;\n"
        "• Postlar chastotasini 1 ta, 2 ta yoki 3 ta qilib sozlashingiz mumkin;\n"
        "• Yetkazish rejimini <b>Darhol</b> yoki <b>Belgilangan vaqt</b>ga o‘rnatishingiz mumkin.\n\n"
        "4️⃣ <b>Cheksiz postlar (Shartnoma):</b>\n"
        "• Agar kuniga 10+, 20+ yoki cheksiz postlar yuborishni istasangiz, administrator bilan bog‘laning."
    )
    kb = get_help_keyboard()

    if isinstance(event, Message):
        await event.answer(help_text, reply_markup=kb, parse_mode="HTML")
    else:
        try:
            await event.message.edit_text(help_text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await event.message.answer(help_text, reply_markup=kb, parse_mode="HTML")
        await event.answer()


@router.callback_query(F.data == "btn_settings")
async def cb_settings(callback: CallbackQuery):
    """User profile and account settings."""
    user = callback.from_user
    user_id = user.id if user else 0
    uname = f"@{user.username}" if user.username else user.first_name or f"User {user_id}"

    user_obj = await rss_storage.get_or_create_user(user_id)
    plan_str = f"💼 Shartnoma ({user_obj.custom_limit or 10} ta post/kun)" if user_obj.plan == "contract" else "Standart (Maksimal 3 ta post/kun)"

    channels = await rss_storage.get_channels_for_user(user_id)

    text = (
        "⚙️ <b>Sozlamalar va Profil</b>\n\n"
        f"• <b>Foydalanuvchi:</b> {uname}\n"
        f"• <b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"• <b>Faol tarif:</b> {plan_str}\n"
        f"• <b>Ulangan kanallaringiz:</b> {len(channels)} ta\n"
        f"• <b>Holat:</b> 🟢 Faol\n\n"
        "Tarifni kengaytirish yoki savollar uchun admin bilan bog‘lanishingiz mumkin:"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍💻 Admin bilan bog‘lanish", url="https://t.me/usafes")],
            [InlineKeyboardButton(text="🔙 Bosh menyu", callback_data="menu_main")],
        ]
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "menu_main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    """Returns to main menu."""
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else 0
    keyboard = get_main_menu_keyboard(user_id=user_id)
    try:
        await callback.message.edit_text(
            get_welcome_caption(),
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        await callback.message.answer(
            get_welcome_caption(),
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    await callback.answer()
