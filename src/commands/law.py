from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from config.db import sqlite_conn_law_database
from utils.decorators import description, example, triggers, usage

cursor = sqlite_conn_law_database.cursor()


@usage("/ipc [SECTION_CODE]")
@example("/ipc 295")
@triggers(["ipc"])
@description(
    "Query the India Penal Code database for the description of a section code."
)
async def ipc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Query the India Penal Code database for the description of a section code."""
    if not context.args:
        await commands.usage_string(update.message, ipc)
        return

    section_code = context.args[0]
    cursor.execute(
        """SELECT * FROM 'IPC' WHERE Section = ?""",
        (section_code,),
    )

    result = cursor.fetchone()
    if result is None:
        await update.message.reply_text(f"No results for {section_code}.")
        return

    await update.message.reply_text(
        f"<u>Chapter {result['chapter']}: {result['chapter_title'].title().strip()}</u>"
        f"\n\n<b>Section {result['Section']}</b>: {result['section_title'].title().strip()}"
        f"\n\n{result['section_desc']}",
        parse_mode=ParseMode.HTML,
    )


@usage("/crpc [SECTION_CODE]")
@example("/crpc 234")
@triggers(["crpc"])
@description(
    "Query the Code of Criminal Procedure database for the description of a section code."
)
async def crpc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Query the Code of Criminal Procedure database for the description of a section code."""
    if not context.args:
        await commands.usage_string(update.message, crpc)
        return

    section_code = context.args[0]
    cursor.execute(
        """SELECT * FROM 'CRPC' WHERE Section = ?""",
        (section_code,),
    )

    result = cursor.fetchone()
    if result is None:
        await update.message.reply_text(f"No results for {section_code}.")
        return

    await update.message.reply_text(
        f"<u>Chapter {result['chapter']}</u>"
        f"\n\n<b>Section {result['Section']}</b>: {result['section_title'].title().strip()}"
        f"\n\n{result['section_desc']}",
        parse_mode=ParseMode.HTML,
    )


@usage("/cpc [SECTION_CODE]")
@example("/cpc 24")
@triggers(["cpc"])
@description(
    "Query the Civil Procedure Code database for the description of a section code."
)
async def cpc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Query the Civil Procedure Code database for the description of a section code."""
    if not context.args:
        await commands.usage_string(update.message, cpc)
        return

    section_code = context.args[0]
    cursor.execute(
        """SELECT * FROM 'CPC' WHERE Section = ?""",
        (section_code,),
    )

    result = cursor.fetchone()
    if result is None:
        await update.message.reply_text(f"No results for {section_code}.")
        return

    await update.message.reply_text(
        f"\n\n<b>Section {result['section']}</b>: {result['title'].title().strip()}"
        f"\n\n{result['description']}",
        parse_mode=ParseMode.HTML,
    )
