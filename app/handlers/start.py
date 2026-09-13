"""
Start, Help, and Main Navigation Handlers for AnjurX | Rss Bot.
Renders the streamlined, user-friendly menu and handles main menu callbacks.
"""
import logging
from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.config import config
from app.services.permission_service import is_super_admin
from app.keyboards.rss import (
    get_main_menu_keyboard,
    get_admin_panel_keyboard,
)

logger = logging.getLogger("anjurxbot.start")
router = Router(name="start_router")


def get_welcome_caption() -> str:
    return (
        "<b>AnjurX | Rss Bot</b>\n\n"
        "📰 <b>Yangiliklarni avtomatik Telegram kanalingizga yetkazing.</b>\n\n"
        "Saytlar (RSS) va Telegram kanallardagi yangi postlarni o‘z kanalingizga "
        "bir zumda va forward yozuvisiz nusxalab boring."
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Presents the streamlined AnjurX | Rss Bot main menu."""
    await state.clear()
    user = message.from_user
    user_id = user.id if user else 0

    keyboard = get_main_menu_keyboard(user_id=user_id)
    await message.answer(
        get_welcome_caption(),
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    """Provides detailed help about bot usage."""
    await state.clear()
    help_text = (
        "❓ <b>Botdan foydalanish bo‘yicha qo‘llanma:</b>\n\n"
        "1️⃣ <b>Kanal ulash (Destination):</b>\n"
        "• Botni o‘z kanalingizga administrator qilib qo‘shing.\n"
        "• <b>Post Messages</b> (Xabarlar yozish) huquqini bering.\n"
        "• Bot kanalni avtomatik taniydi yoki <code>[➕ Kanal ulash]</code> tugmasini bosing.\n\n"
        "2️⃣ <b>Sayt/RSS qo‘shish:</b>\n"
        "• <code>[🌐 Sayt/RSS qo‘shish]</code> tugmasini bosing.\n"
        "• Sayt yoki RSS havolasini yuboring (masalan: <code>kun.uz</code> yoki <code>https://kun.uz/news/rss</code>).\n"
        "• Postlar qaysi kanalga yuborilishini tanlang va tasdiqlang.\n\n"
        "3️⃣ <b>Telegram kanal qo‘shish (Source):</b>\n"
        "• <code>[📢 Telegram kanal qo‘shish]</code> tugmasini bosing.\n"
        "• Manba kanal username'ini (@manba_kanal) yuboring yoki postini forward qiling.\n"
        "• Bot yangi postlarni kanalingizga muallif/forward yozuvisiz toza nusxalab beradi.\n\n"
        "4️⃣ <b>Mening manbalarim:</b>\n"
        "• Barcha ulangan manbalarni ko‘rish va kerak bo‘lsa bir tugma bilan o‘chirish."
    )
    user_id = message.from_user.id if message.from_user else 0
    keyboard = get_main_menu_keyboard(user_id=user_id)
    await message.answer(
        help_text,
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "menu_main")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    """Returns to the main menu."""
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


@router.callback_query(F.data == "menu_help")
async def cb_help_menu(callback: CallbackQuery):
    """Shows help menu from callback."""
    help_text = (
        "❓ <b>Botdan foydalanish bo‘yicha qo‘llanma:</b>\n\n"
        "1️⃣ <b>Kanal ulash:</b>\n"
        "Botni kanalingizga administrator qilib qo‘shing va <b>Post Messages</b> huquqini bering.\n\n"
        "2️⃣ <b>Sayt/RSS ulash:</b>\n"
        "Sayt yoki RSS havolasini yuboring, kanalni tanlang va tasdiqlang.\n\n"
        "3️⃣ <b>Telegram kanal ulash:</b>\n"
        "Manba kanal linki/postini yuboring. Postlar forward yozuvisiz toza ko'chiriladi."
    )
    user_id = callback.from_user.id if callback.from_user else 0
    keyboard = get_main_menu_keyboard(user_id=user_id)
    try:
        await callback.message.edit_text(
            help_text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except Exception:
        await callback.message.answer(
            help_text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    await callback.answer()


@router.callback_query(F.data == "menu_cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancels any active operation and returns to main menu."""
    await state.clear()
    user_id = callback.from_user.id if callback.from_user else 0
    keyboard = get_main_menu_keyboard(user_id=user_id)
    try:
        await callback.message.edit_text(
            "Amal bekor qilindi.\n\n" + get_welcome_caption(),
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
    await callback.answer("Bekor qilindi")
