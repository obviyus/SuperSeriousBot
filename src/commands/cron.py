import datetime
import html

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

import commands
from commands.cron_service import (
    create_cron_task,
    delete_owned_cron_task,
    generate_cron_draft,
    list_user_cron_tasks,
    load_enabled_cron_task,
    load_owned_cron_task,
    register_cron_task,
    run_cron_task,
    validate_cron_expression,
)
from commands.runtime import ensure_command_available
from utils.decorators import command
from utils.messages import get_message


def _parse_task_id(value: str) -> int:
    try:
        task_id = int(value)
    except ValueError as exc:
        raise ValueError("Cron task id must be a number.") from exc
    if task_id < 1:
        raise ValueError("Cron task id must be a positive number.")
    return task_id


def _next_run_text(cron_expr: str, timezone: str) -> str:
    trigger = validate_cron_expression(cron_expr, timezone)
    now = datetime.datetime.now(datetime.UTC)
    next_run = trigger.get_next_fire_time(None, now)
    if next_run is None:
        raise RuntimeError("Cron expression never fires.")
    return next_run.astimezone(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")


@command(
    triggers=["cron"],
    usage="/cron [schedule + task]\n/cron del [id]\n/cron run [id]",
    example="/cron daily 9am check and inform if dji osmo pocket 4 is now available on amazon",
    description="Create and manage scheduled AI tasks.",
    api_key="OPENROUTER_API_KEY",
)
async def cron(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = get_message(update)
    if not message or not message.from_user:
        return

    if not await ensure_command_available(
        message,
        message.from_user.id,
        "cron",
        allow_private_whitelist=True,
    ):
        return

    if context.job_queue is None:
        raise RuntimeError("Job queue not initialized.")

    if not context.args:
        tasks = await list_user_cron_tasks(message.chat_id, message.from_user.id)
        if not tasks:
            await commands.usage_string(message, cron)
            return

        lines = ["<b>Your cron tasks in this chat:</b>"]
        for task in tasks:
            lines.append(
                "\n"
                f"<code>{task.id}</code>. <b>{html.escape(task.title)}</b>\n"
                f"<code>{html.escape(task.cron_expr)}</code> "
                f"<code>{html.escape(task.timezone)}</code>\n"
                f"Next: <code>{html.escape(_next_run_text(task.cron_expr, task.timezone))}</code>"
            )
        await message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    action = context.args[0].lower()
    if action == "del":
        if len(context.args) != 2:
            await message.reply_text(
                "Usage: <code>/cron del [id]</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        try:
            task_id = _parse_task_id(context.args[1])
        except ValueError as exc:
            await message.reply_text(str(exc))
            return
        deleted = await delete_owned_cron_task(
            context.job_queue,
            task_id,
            message.chat_id,
            message.from_user.id,
        )
        if not deleted:
            await message.reply_text("Cron task not found.")
            return
        await message.reply_text(
            f"Deleted cron task <code>{task_id}</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    if action == "run":
        if len(context.args) != 2:
            await message.reply_text(
                "Usage: <code>/cron run [id]</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        try:
            task_id = _parse_task_id(context.args[1])
        except ValueError as exc:
            await message.reply_text(str(exc))
            return
        task = await load_owned_cron_task(
            task_id,
            message.chat_id,
            message.from_user.id,
        )
        if task is None:
            await message.reply_text("Cron task not found.")
            return
        await message.reply_text(
            f"Running cron task <code>{task_id}</code>...",
            parse_mode=ParseMode.HTML,
        )
        await run_cron_task(context, task_id)
        return

    user_request = " ".join(context.args).strip()
    status_message = await message.reply_text("Creating cron task...")
    try:
        draft = await generate_cron_draft(user_request)
    except Exception as exc:
        await status_message.edit_text(f"Could not create cron task: {exc}")
        return

    task = await create_cron_task(message.chat_id, message.from_user.id, draft)
    register_cron_task(context.job_queue, task)

    await status_message.edit_text(
        text=(
            f"Created cron task <code>{task.id}</code>.\n\n"
            f"<b>{html.escape(task.title)}</b>\n"
            f"<code>{html.escape(task.cron_expr)}</code> "
            f"<code>{html.escape(task.timezone)}</code>\n"
            f"Next: <code>{html.escape(_next_run_text(task.cron_expr, task.timezone))}</code>"
        ),
        parse_mode=ParseMode.HTML,
    )


async def cron_button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    message = get_message(update)
    query = update.callback_query
    if not message or not query or not query.data or not query.from_user:
        return

    if context.job_queue is None:
        raise RuntimeError("Job queue not initialized.")

    try:
        task_id = _parse_task_id(query.data.removeprefix("cr:"))
    except ValueError:
        await query.answer("Invalid cron task.")
        return

    task = await load_enabled_cron_task(task_id)
    if task is None:
        await query.answer("Cron task already deleted.")
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if task.user_id != query.from_user.id:
        await query.answer("You can only delete your own cron tasks.")
        return

    deleted = await delete_owned_cron_task(
        context.job_queue,
        task.id,
        message.chat_id,
        query.from_user.id,
    )
    if not deleted:
        await query.answer("Cron task already deleted.")
        await query.edit_message_reply_markup(reply_markup=None)
        return

    await query.answer("Deleted cron task.")
    await query.edit_message_reply_markup(reply_markup=None)
