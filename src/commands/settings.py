from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from config.db import get_db
from utils.admin import is_admin
from utils.decorators import command
from utils.messages import get_message

CALLBACK_PREFIX = "st"
WHITELIST_TYPE = "chat"


@dataclass(frozen=True)
class SettingToggle:
    key: str
    label: str
    table: str
    value: str


TOGGLES = (
    SettingToggle("fts", "Message search", "group_settings", "fts"),
    SettingToggle("auto_dl", "Auto download", "group_settings", "auto_dl"),
    SettingToggle("ask", "/ask", "command_whitelist", "ask"),
    SettingToggle("edit", "/edit", "command_whitelist", "edit"),
    SettingToggle("tr", "/tr", "command_whitelist", "tr"),
    SettingToggle("cron", "/cron", "command_whitelist", "cron"),
    SettingToggle("song", "/song", "command_whitelist", "song"),
)
TOGGLE_BY_KEY = {toggle.key: toggle for toggle in TOGGLES}


async def _can_manage_settings(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return False
    if is_admin(user.id):
        return True
    if chat.type == ChatType.PRIVATE:
        return False

    admins = await context.bot.get_chat_administrators(chat.id)
    return user.id in {admin.user.id for admin in admins}


async def _setting_states(chat_id: int) -> dict[str, bool]:
    states = {toggle.key: False for toggle in TOGGLES}
    command_names = tuple(
        toggle.value for toggle in TOGGLES if toggle.table == "command_whitelist"
    )
    placeholders = ", ".join("?" for _ in command_names)

    async with get_db() as conn:
        async with conn.execute(
            "SELECT fts, auto_dl FROM group_settings WHERE chat_id = ?",
            (chat_id,),
        ) as cursor:
            row = await cursor.fetchone()
            states["fts"] = bool(row and row["fts"])
            states["auto_dl"] = bool(row and row["auto_dl"])

        async with conn.execute(
            f"""
            SELECT command
            FROM command_whitelist
            WHERE whitelist_type = ?
            AND whitelist_id = ?
            AND command IN ({placeholders})
            """,
            (WHITELIST_TYPE, chat_id, *command_names),
        ) as cursor:
            rows = await cursor.fetchall()
            enabled_commands = {row["command"] for row in rows}

    for toggle in TOGGLES:
        if toggle.table == "command_whitelist":
            states[toggle.key] = toggle.value in enabled_commands
    return states


def _settings_keyboard(chat_id: int, states: dict[str, bool]) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'On' if states[toggle.key] else 'Off'} - {toggle.label}",
                callback_data=f"{CALLBACK_PREFIX}:{chat_id}:{toggle.key}",
            )
        ]
        for toggle in TOGGLES
    ]
    return InlineKeyboardMarkup(keyboard)


async def _send_settings(message: Message, chat_id: int) -> None:
    states = await _setting_states(chat_id)
    await message.reply_text(
        f"<b>Group settings</b>\n<code>{chat_id}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=_settings_keyboard(chat_id, states),
    )


async def _edit_settings(query, chat_id: int) -> None:
    states = await _setting_states(chat_id)
    await query.edit_message_text(
        f"<b>Group settings</b>\n<code>{chat_id}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=_settings_keyboard(chat_id, states),
    )


async def _set_toggle(chat_id: int, toggle: SettingToggle, enabled: bool) -> None:
    async with get_db() as conn:
        if toggle.table == "group_settings":
            await conn.execute(
                f"""
                INSERT INTO group_settings (chat_id, {toggle.value})
                VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET {toggle.value} = excluded.{toggle.value}
                """,
                (chat_id, int(enabled)),
            )
            return

        if enabled:
            await conn.execute(
                """
                INSERT OR IGNORE INTO command_whitelist (
                    command, whitelist_type, whitelist_id
                )
                VALUES (?, ?, ?)
                """,
                (toggle.value, WHITELIST_TYPE, chat_id),
            )
            return

        await conn.execute(
            """
            DELETE FROM command_whitelist
            WHERE command = ? AND whitelist_type = ? AND whitelist_id = ?
            """,
            (toggle.value, WHITELIST_TYPE, chat_id),
        )


@command(
    triggers=["settings"],
    usage="/settings",
    example="/settings",
    description="Manage this group's bot settings.",
)
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message:
        return
    if not update.effective_chat or update.effective_chat.type == ChatType.PRIVATE:
        await message.reply_text("Use /settings inside a group.")
        return
    if not await _can_manage_settings(update, context):
        await message.reply_text("Only group admins can change settings.")
        return

    await _send_settings(message, update.effective_chat.id)


async def settings_button_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    if not await _can_manage_settings(update, context):
        await query.answer("Only group admins can change settings.")
        return

    _, chat_id_text, key = query.data.split(":", 2)
    chat_id = int(chat_id_text)
    if not update.effective_chat or update.effective_chat.id != chat_id:
        await query.answer("Open settings in this group.")
        return

    toggle = TOGGLE_BY_KEY.get(key)
    if not toggle:
        await query.answer("Unknown setting.")
        return

    states = await _setting_states(chat_id)
    enabled = not states[key]
    await _set_toggle(chat_id, toggle, enabled)
    await query.answer(f"{toggle.label}: {'on' if enabled else 'off'}")
    await _edit_settings(query, chat_id)
