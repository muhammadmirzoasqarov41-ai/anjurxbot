"""
Admin panel handler — navigation callbacks (ap: prefix).
Handles: /panel, /start (admin path), groups list, group detail,
guard panel, fsub panel, stats, config.
"""
from __future__ import annotations
from html import escape
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.handlers.admin_helpers import (
    build_main_text, build_groups_text, build_group_detail_text,
    build_guard_text, build_fsub_text, build_stats_text,
    build_flood_text, build_config_text, build_badwords_text,
    build_daily_stats_text, build_admin_logs_text, build_guard_logs_text,
    build_help_text, is_global_admin,
)
from app.keyboards.admin import (
    admin_main_keyboard, groups_list_keyboard, group_detail_keyboard,
    guard_panel_keyboard, fsub_panel_keyboard, fsub_del_keyboard,
    flood_settings_keyboard, config_panel_keyboard,
    bad_words_keyboard, stats_keyboard, logs_pagination_keyboard,
)
from app.services import group_service, guard_service, log_service
from app.services.permission_service import permission_service
from app.services.firebase import firebase_service
from app.utils.logger import logger
from app.services.rate_limit_service import rate_limit_service
from app.services.stats_service import get_stats

router = Router(name="admin_panel")


# ------------------------------------------------------------------ #
# Auth helper
# ------------------------------------------------------------------ #

async def _deny(callback: CallbackQuery) -> None:
    await callback.answer("❌ Sizda bu amalni bajarish huquqi yo'q.", show_alert=True)


async def _check_admin(callback: CallbackQuery) -> bool:
    if callback.from_user is None:
        return False
    if is_global_admin(callback.from_user.id):
        return True
    # Inline callbacks carry the target group ID after the action prefix.
    # This allows real group administrators to manage their own group.
    if callback.data:
        for value in callback.data.split(":")[2:]:
            try:
                group_id = int(value)
            except ValueError:
                continue
            if await permission_service.is_group_admin(callback.bot, group_id, callback.from_user.id):
                return True
            break
    await _deny(callback)
    return False


# ------------------------------------------------------------------ #
# /panel and /start (admin entry)
# ------------------------------------------------------------------ #

async def _show_main(message: Message) -> None:
    name = message.from_user.first_name if message.from_user else "Admin"
    text = await build_main_text(name)
    await message.answer(text, reply_markup=admin_main_keyboard(), parse_mode="HTML")


@router.message(Command("panel"))
async def cmd_panel(message: Message) -> None:
    if message.from_user and not rate_limit_service.allow("panel", message.from_user.id, 3, 30.0):
        await message.answer("⏳ Juda ko'p so'rov yuborildi. Biroz kuting.")
        return
    if message.from_user is None or not is_global_admin(message.from_user.id):
        await message.answer("⛔ Sizda bu buyruq uchun ruxsat yo'q.")
        return
    await _show_main(message)


# ------------------------------------------------------------------ #
# Main menu callback
# ------------------------------------------------------------------ #

@router.callback_query(F.data == "ap:mn")
async def cb_main_menu(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    name = callback.from_user.first_name if callback.from_user else "Admin"
    text = await build_main_text(name)
    try:
        await callback.message.edit_text(text, reply_markup=admin_main_keyboard(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=admin_main_keyboard(), parse_mode="HTML")
    await callback.answer()


# ------------------------------------------------------------------ #
# Groups list
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:gs"))
async def cb_groups_list(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    section = callback.data.split(":")[2] if len(callback.data.split(":")) > 2 else ""
    groups = [g for g in await firebase_service.list_groups() if g.get("is_active", True)]
    text = await build_groups_text(groups)
    kb = groups_list_keyboard(groups, section)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "ap:help")
async def cb_help(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    text = await build_help_text()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏠 Bosh menyu", callback_data="ap:mn")
    ]])
    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


# ------------------------------------------------------------------ #
# Group detail
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:g:"))
async def cb_group_detail(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    try:
        parts = callback.data.split(":")
        group_id = int(parts[2])
        section = parts[3] if len(parts) > 3 else ""
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    if section == "guard":
        await callback.message.edit_text(
            await build_guard_text(group_id),
            reply_markup=guard_panel_keyboard(await guard_service.get_guard_settings(group_id), group_id),
            parse_mode="HTML",
        )
        await callback.answer()
        return
    if section == "fsub":
        await callback.message.edit_text(
            await build_fsub_text(group_id),
            reply_markup=fsub_panel_keyboard(await group_service.get_fsub_settings(group_id), group_id),
            parse_mode="HTML",
        )
        await callback.answer()
        return
    if section == "stats":
        await callback.message.edit_text(await build_stats_text(group_id), reply_markup=stats_keyboard(group_id), parse_mode="HTML")
        await callback.answer()
        return
    if section == "config":
        await callback.message.edit_text(await build_config_text(group_id), reply_markup=config_panel_keyboard(group_id), parse_mode="HTML")
        await callback.answer()
        return
    text = await build_group_detail_text(group_id)
    kb = group_detail_keyboard(group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("ap:pv:"))
async def cb_permission_refresh(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    try:
        group_id = int(callback.data.split(":")[2])
        health = await permission_service.verify_bot(callback.bot, group_id)
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    except Exception:
        await callback.answer("❌ Permission tekshirilmadi.", show_alert=True)
        return
    if health.get("permissions_valid"):
        await callback.answer("✅ Permissionlar yetarli.")
    else:
        await callback.answer("⚠️ Bot permissionlari yetarli emas.", show_alert=True)
    text = await build_group_detail_text(group_id)
    try:
        await callback.message.edit_text(text, reply_markup=group_detail_keyboard(group_id), parse_mode="HTML")
    except Exception:
        pass


# ------------------------------------------------------------------ #
# Guard panel
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:gu:"))
async def cb_guard_panel(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    guard = await guard_service.get_guard_settings(group_id)
    text = await build_guard_text(group_id)
    kb = guard_panel_keyboard(guard, group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# Guard feature toggle
@router.callback_query(F.data.startswith("ap:gt:"))
async def cb_guard_toggle(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    try:
        group_id = int(parts[2])
        feature = parts[3]
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    guard = await guard_service.get_guard_settings(group_id)
    new_val = not guard.get(feature, False)
    await guard_service.toggle_guard_feature(group_id, feature, new_val)
    status = "yoqildi ✅" if new_val else "o'chirildi ❌"
    await callback.answer(f"{feature} {status}")
    admin_id = callback.from_user.id
    import asyncio
    asyncio.create_task(log_service.log_admin_action(group_id, admin_id, f"{feature} toggle", status))

    guard[feature] = new_val
    text = await build_guard_text(group_id)
    guard_updated = await guard_service.get_guard_settings(group_id)
    kb = guard_panel_keyboard(guard_updated, group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


# Guard master toggle
@router.callback_query(F.data.startswith("ap:gm:"))
async def cb_guard_master(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    parts = callback.data.split(":")
    try:
        group_id = int(parts[2])
        enable = parts[3] == "on"
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    if not enable:
        confirm = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Ha", callback_data=f"ap:gc:{group_id}:yes"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"ap:gu:{group_id}"),
        ]])
        await callback.message.edit_text(
            "⚠️ <b>Qorovulni o‘chirmoqchimisiz?</b>\n\nBot spam va floodni nazorat qilmaydi.",
            reply_markup=confirm,
            parse_mode="HTML",
        )
        await callback.answer()
        return
    await guard_service.set_guard_enabled(group_id, enable)
    lbl = "yoqildi ✅" if enable else "o'chirildi ❌"
    await callback.answer(f"Qorovul {lbl}")
    admin_id = callback.from_user.id
    import asyncio
    asyncio.create_task(log_service.log_admin_action(group_id, admin_id, "Qorovul master", lbl))

    guard = await guard_service.get_guard_settings(group_id)
    text = await build_guard_text(group_id)
    kb = guard_panel_keyboard(guard, group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data.startswith("ap:gc:"))
async def cb_guard_confirm_disable(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    parts = callback.data.split(":")
    try:
        group_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    await guard_service.set_guard_enabled(group_id, False)
    await callback.answer("✅ Qorovul o'chirildi.")
    guard = await guard_service.get_guard_settings(group_id)
    try:
        await callback.message.edit_text(
            await build_guard_text(group_id),
            reply_markup=guard_panel_keyboard(guard, group_id),
            parse_mode="HTML",
        )
    except Exception:
        pass


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if message.chat.type not in {"group", "supergroup"} or message.from_user is None:
        await message.answer("⚠️ Bu buyruq guruh administratorlari uchun.")
        return
    if not is_global_admin(message.from_user.id) and not await permission_service.is_group_admin(message.bot, message.chat.id, message.from_user.id):
        await message.answer("⛔ Bu buyruq faqat guruh adminlari uchun.")
        return
    await message.answer(await build_stats_text(message.chat.id), parse_mode="HTML")


# ------------------------------------------------------------------ #
# Force Subscribe panel
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:fs:"))
async def cb_fsub_panel(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    fsub = await group_service.get_fsub_settings(group_id)
    text = await build_fsub_text(group_id)
    kb = fsub_panel_keyboard(fsub, group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# FSub toggle
@router.callback_query(F.data.startswith("ap:fsT:"))
async def cb_fsub_toggle(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    parts = callback.data.split(":")
    try:
        group_id = int(parts[2])
        enable = parts[3] == "on"
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    if enable:
        channels = await group_service.get_channels(group_id)
        if not channels:
            await callback.answer("⚠️ Avval kanal qo'shing!", show_alert=True)
            return
    await group_service.set_fsub_enabled(group_id, enable)
    lbl = "yoqildi ✅" if enable else "o'chirildi ❌"
    await callback.answer(f"Majburiy obuna {lbl}")
    admin_id = callback.from_user.id
    import asyncio
    asyncio.create_task(log_service.log_admin_action(group_id, admin_id, "FSub master", lbl))

    fsub = await group_service.get_fsub_settings(group_id)
    text = await build_fsub_text(group_id)
    kb = fsub_panel_keyboard(fsub, group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


# FSub channel delete list
@router.callback_query(F.data.startswith("ap:fdl:"))
async def cb_fsub_del_list(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    channels = await group_service.get_channels(group_id)
    if not channels:
        await callback.answer("📭 Kanallar ro'yxati bo'sh.", show_alert=True)
        return
    lines = ["📋 <b>Kanallar ro'yxati:</b>\n"]
    for ch in channels:
        name = ch.get("username") or ch.get("title") or str(ch.get("channel_id",""))
        lines.append(f"  📢 {escape(name)}")
    text = "\n".join(lines) + "\n\nO'chirish uchun kanalga bosing:"
    kb = fsub_del_keyboard(channels, group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# FSub delete specific channel
@router.callback_query(F.data.startswith("ap:fdc:"))
async def cb_fsub_del_channel(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    parts = callback.data.split(":")
    try:
        group_id = int(parts[2])
        channel_id = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    confirm = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o‘chirish", callback_data=f"ap:fcc:{group_id}:{channel_id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"ap:fs:{group_id}"),
    ]])
    await callback.message.edit_text(
        "⚠️ <b>Bu kanalni o‘chirmoqchimisiz?</b>",
        reply_markup=confirm,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ap:fcc:"))
async def cb_fsub_confirm_delete(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    parts = callback.data.split(":")
    try:
        group_id = int(parts[2])
        channel_id = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    removed = await group_service.remove_channel(group_id, channel_id)
    if removed:
        await callback.answer("✅ Kanal o'chirildi.")
        admin_id = callback.from_user.id
        import asyncio
        asyncio.create_task(log_service.log_admin_action(group_id, admin_id, "FSub kanal o'chirildi", f"ID: {channel_id}"))
    else:
        await callback.answer("⚠️ Kanal topilmadi.", show_alert=True)
        return
    fsub = await group_service.get_fsub_settings(group_id)
    text = await build_fsub_text(group_id)
    kb = fsub_panel_keyboard(fsub, group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


# ------------------------------------------------------------------ #
# Stats panel
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:st:"))
async def cb_stats_panel(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    text = await build_stats_text(group_id)
    kb = stats_keyboard(group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ------------------------------------------------------------------ #
# Config panel
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:cf:"))
async def cb_config_panel(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    text = await build_config_text(group_id)
    kb = config_panel_keyboard(group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ------------------------------------------------------------------ #
# Flood settings panel
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:fw:"))
async def cb_flood_panel(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    text = await build_flood_text(group_id)
    kb = flood_settings_keyboard(group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ------------------------------------------------------------------ #
# Bad words panel
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:bw:"))
async def cb_badwords_panel(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    guard = await guard_service.get_guard_settings(group_id)
    text = await build_badwords_text(group_id)
    kb = bad_words_keyboard(guard, group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# Bad words toggle
@router.callback_query(F.data.startswith("ap:bwT:"))
async def cb_badwords_toggle(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    parts = callback.data.split(":")
    try:
        group_id = int(parts[2])
        enable = parts[3] == "on"
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    await guard_service.toggle_guard_feature(group_id, "bad_words", enable)
    lbl = "yoqildi ✅" if enable else "o'chirildi ❌"
    await callback.answer(f"So'z filtri {lbl}")
    admin_id = callback.from_user.id
    import asyncio
    asyncio.create_task(log_service.log_admin_action(group_id, admin_id, "So'z filtri master", lbl))

    guard = await guard_service.get_guard_settings(group_id)
    text = await build_badwords_text(group_id)
    kb = bad_words_keyboard(guard, group_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


# Bad words list view
@router.callback_query(F.data.startswith("ap:bwl:"))
async def cb_badwords_list(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    words = await guard_service.get_bad_words(group_id)
    if not words:
        await callback.answer("📭 Ro'yxat bo'sh.", show_alert=True)
        return
    lines = [f"🚫 <b>Taqiqlangan so'zlar</b> ({len(words)} ta):\n"]
    for i, w in enumerate(words[:50], 1):
        lines.append(f"  {i}. <code>{escape(w)}</code>")
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data=f"ap:bw:{group_id}"))
    try:
        await callback.message.edit_text(
            "\n".join(lines), reply_markup=b.as_markup(), parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            "\n".join(lines), reply_markup=b.as_markup(), parse_mode="HTML"
        )
    await callback.answer()


# ------------------------------------------------------------------ #
# Logs panels
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("ap:td:"))
async def cb_daily_stats_panel(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    try:
        group_id = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    text = await build_daily_stats_text(group_id)
    kb = stats_keyboard(group_id, show_daily_button=False)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("ap:la:"))
async def cb_admin_logs_panel(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    parts = callback.data.split(":")
    try:
        group_id = int(parts[2])
        page = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    limit = 10
    offset = page * limit
    logs = await log_service.get_admin_logs(group_id, limit=limit + 1, offset=offset)
    has_next = len(logs) > limit
    logs = logs[:limit]

    text = await build_admin_logs_text(logs, page)
    kb = logs_pagination_keyboard(group_id, "la", page, has_next)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("ap:lg:"))
async def cb_guard_logs_panel(callback: CallbackQuery) -> None:
    if not await _check_admin(callback):
        return
    parts = callback.data.split(":")
    try:
        group_id = int(parts[2])
        page = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("❌ Noto'g'ri so'rov.", show_alert=True)
        return
    limit = 10
    offset = page * limit
    logs = await log_service.get_guard_logs(group_id, limit=limit + 1, offset=offset)
    has_next = len(logs) > limit
    logs = logs[:limit]

    text = await build_guard_logs_text(logs, page)
    kb = logs_pagination_keyboard(group_id, "lg", page, has_next)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

# ------------------------------------------------------------------ #
# Cancel FSM
# ------------------------------------------------------------------ #

@router.callback_query(F.data == "ap:cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("❌ Bekor qilindi.")
    name = callback.from_user.first_name if callback.from_user else "Admin"
    text = await build_main_text(name)
    try:
        await callback.message.edit_text(
            text, reply_markup=admin_main_keyboard(), parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text, reply_markup=admin_main_keyboard(), parse_mode="HTML"
        )
