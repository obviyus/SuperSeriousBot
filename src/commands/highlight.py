import html

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import KeyboardButtonStyle, ParseMode
from telegram.error import Forbidden
from telegram.ext import ContextTypes

from config.db import get_db
from config.logger import logger
from utils.decorators import command
from utils.messages import get_message


def delete_highlight_button(highlight_id: int, user_id: int) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        "Delete Highlight",
        callback_data=f"hl:{highlight_id},{user_id}",
        style=KeyboardButtonStyle.DANGER,
    )


def start_dm_button(bot_username: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        "Start DM",
        url=f"https://t.me/{bot_username}",
        style=KeyboardButtonStyle.PRIMARY,
    )


async def highlight_keyboard_builder(
    chat_id: int,
    user_id: int,
    *,
    bot_username: str | None = None,
) -> InlineKeyboardMarkup:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT * FROM 'highlights' WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        ) as cursor:
            result = await cursor.fetchall()

    keyboard = [
        [
            InlineKeyboardButton(
                f"{row['string']} 🗑",
                callback_data=f"hl:{row['id']},{user_id}",
                style=KeyboardButtonStyle.DANGER,
            )
        ]
        for row in result
    ]
    if bot_username:
        keyboard.append([start_dm_button(bot_username)])
    return InlineKeyboardMarkup(keyboard)


async def highlight_button_handler(
    update: Update, _: ContextTypes.DEFAULT_TYPE
) -> None:
    message = get_message(update)

    if not message:
        return
    query = update.callback_query
    if not query or not query.data or not query.from_user or not query.message:
        return

    highlight_id, user_id = query.data.replace("hl:", "").split(",")

    if int(user_id) != query.from_user.id:
        await query.answer("You can only delete your own highlights.")
        return

    async with get_db() as conn:
        await conn.execute(
            """
            DELETE FROM 'highlights' WHERE id = ?
            """,
            (highlight_id,),
        )

    await query.answer("Deleted highlight.")

    await query.edit_message_reply_markup(
        reply_markup=await highlight_keyboard_builder(message.chat_id, query.from_user.id)
    )


@command(
    triggers=["highlight", "hl"],
    usage="/highlight Elden Ring",
    example="/highlight",
    description="Get a DM when a certain text is seen by the bot in this chat.",
)
async def highlighter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user:
        return

    bot_username = None
    text = "Your highlights in this chat.\n\nAdd new highlights by: \n\n<pre>/highlight [STRING]</pre>"
    if context.args:
        highlight_string = " ".join(context.args)
        if len(highlight_string) > 100:
            await message.reply_text("Highlight cannot be greater than 100 characters.")
            return

        async with get_db() as conn:
            result = await conn.execute(
                """
                INSERT OR IGNORE INTO highlights (chat_id, string, user_id)
                VALUES (?, ?, ?)
                """,
                (message.chat_id, highlight_string, message.from_user.id),
            )
            if not result.rowcount:
                await message.reply_text("Highlight already exists.")
                return

        bot_username = context.bot.username
        text = (
            f"Added highlight: <code>{html.escape(highlight_string)}</code>.\n\n"
            "⚠️ Make sure you've messaged me first, otherwise I can't DM you!\n\n"
            "Your highlights in this chat:"
        )

    await message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=await highlight_keyboard_builder(
            message.chat_id,
            message.from_user.id,
            bot_username=bot_username,
        ),
    )


async def highlight_worker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)

    if not message:
        return
    if not message.text or not message.from_user:
        return

    async with get_db() as conn:
        async with conn.execute(
            """SELECT * FROM highlights WHERE chat_id = ?""", (message.chat_id,)
        ) as cursor:
            result = await cursor.fetchall()

    for row in result:
        if row["string"].lower() in message.text.lower():
            try:
                await context.bot.send_message(
                    row["user_id"],
                    f"Your highlight <code>{html.escape(row['string'])}</code> was mentioned "
                    f"in <b>{html.escape(message.chat.title or str(message.chat_id))}</b> by "
                    f"<a href='tg://user?id={message.from_user.id}'>{html.escape(message.from_user.first_name)}</a>."
                    f"\n\n🔗 <a href='{html.escape(message.link or '', quote=True)}'>Link</a>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(
                        [[delete_highlight_button(row["id"], row["user_id"])]]
                    ),
                )
            except Forbidden:
                # Do not leak highlight keywords or owner identity into the group.
                logger.info(
                    "Highlight DM forbidden for user %s in chat %s",
                    row["user_id"],
                    message.chat_id,
                )

