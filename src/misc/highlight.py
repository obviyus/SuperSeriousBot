from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config.db import sqlite_conn
from utils.decorators import description, example, triggers, usage


async def highlight_keyboard_builder(
    chat_id: int, user_id: int
) -> InlineKeyboardMarkup:
    """Build the highlight keyboard."""
    cursor = sqlite_conn.cursor()
    result = cursor.execute(
        """
        SELECT * FROM 'highlights' WHERE chat_id = ? AND user_id = ?
        """,
        (chat_id, user_id),
    ).fetchall()

    keyboard = []
    for row in result:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{row['string']} 🗑",
                    callback_data=f"hl:{row['id']},{user_id}",
                ),
            ],
        )

    return InlineKeyboardMarkup(keyboard)


async def highlight_button_handler(
    update: Update, _: ContextTypes.DEFAULT_TYPE
) -> None:
    """Remove a highlight from the database."""
    query = update.callback_query
    highlight_id, user_id = query.data.replace("hl:", "").split(",")

    if int(user_id) != query.from_user.id:
        await query.answer("You can only delete your own highlights.")
        return

    cursor = sqlite_conn.cursor()
    cursor.execute(
        """
        DELETE FROM 'highlights' WHERE id = ?
        """,
        (highlight_id,),
    )

    await query.answer(f"Deleted highlight.")
    await query.edit_message_reply_markup(
        reply_markup=await highlight_keyboard_builder(
            query.message.chat_id, query.from_user.id
        )
    )


@usage("/highlight Elden Ring")
@example("/highlight")
@triggers(["highlight", "hl"])
@description("Get a DM when a certain text is seen by the bot in this chat.")
async def highlighter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a DM when a certain text is seen by the bot in this chat."""
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text(
            "Your highlights in this chat."
            "\n\nAdd new highlights by: \n\n<code>/highlight [STRING]</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=await highlight_keyboard_builder(
                update.message.chat_id, update.message.from_user.id
            ),
        )
        return

    highlight_string = " ".join(context.args)
    if len(highlight_string) > 100:
        await update.message.reply_text(
            "Highlight cannot be greater than 100 characters."
        )
        return

    cursor = sqlite_conn.cursor()
    result = cursor.execute(
        """SELECT * FROM highlights WHERE chat_id = ? AND string = ? COLLATE NOCASE""",
        (update.message.chat_id, highlight_string),
    ).fetchone()

    if result:
        await update.message.reply_text("Highlight already exists in this chat.")
        return

    cursor.execute(
        """INSERT INTO highlights (chat_id, string, user_id) VALUES (?, ?, ?)""",
        (update.message.chat_id, highlight_string, update.message.from_user.id),
    )

    await update.message.reply_text(
        f"Added highlight: <code>{highlight_string}</code>. \n\nYour highlights in this chat:",
        parse_mode=ParseMode.HTML,
        reply_markup=await highlight_keyboard_builder(
            update.message.chat_id, update.message.from_user.id
        ),
    )


async def highlight_worker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check if a highlight is mentioned."""
    if not update.message or not update.message.text:
        return

    cursor = sqlite_conn.cursor()
    result = cursor.execute(
        """SELECT * FROM highlights WHERE chat_id = ?""",
        (update.message.chat_id,),
    ).fetchall()

    for row in result:
        if row["string"] in update.message.text.lower():
            await context.bot.send_message(
                row["user_id"],
                f"Your highlight <code>{row['string']}</code> was mentioned "
                f"in <b>{update.message.chat.title}</b> by "
                f"<a href='tg://user?id={update.message.from_user.id}'>{update.message.from_user.first_name}</a>."
                f"\n\n🔗 <a href='{update.message.link}'>Link</a>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Delete Highlight",
                                callback_data=f"hl:{row['id']},{row['user_id']}",
                            ),
                        ],
                    ]
                ),
            )
