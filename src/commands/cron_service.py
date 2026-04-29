import datetime
import html
import json
from dataclasses import dataclass
from typing import Literal
from zoneinfo import ZoneInfo

import aiohttp
from apscheduler.triggers.cron import CronTrigger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import KeyboardButtonStyle
from telegram.ext import ContextTypes, JobQueue

import utils
from commands.ai import (
    JsonObject,
    first_message_content,
    openrouter_json,
    openrouter_payload,
)
from config.db import get_db
from config.logger import logger

DEFAULT_TIMEZONE = "Asia/Kolkata"
CRON_JOB_PREFIX = "cron:"

SCHEDULER_SYSTEM_PROMPT = f"""Convert a Telegram user's natural-language request into one durable cron task.

Return only the task metadata. Do not perform the task.
Use standard five-field crontab syntax: minute hour day-of-month month day-of-week.
Use 24-hour time. If no timezone is explicit, use {DEFAULT_TIMEZONE}.
Timezone must be an IANA timezone like Asia/Kolkata or America/New_York.
The title must be short and specific. The task must be a complete instruction for a future run."""

RUNNER_SYSTEM_PROMPT = """You are @SuperSeriousBot running a scheduled task.

Use the saved title, task, and previous run history. Complete the task now.
Be concise. Return the Telegram message to send. No scheduling metadata."""

CRON_RESPONSE_FORMAT: JsonObject = {
    "type": "json_schema",
    "json_schema": {
        "name": "cron_task",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short title for the scheduled task.",
                },
                "task": {
                    "type": "string",
                    "description": "Complete instruction to execute on each run.",
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Five-field crontab expression.",
                },
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone.",
                },
            },
            "required": ["title", "task", "cron_expr", "timezone"],
            "additionalProperties": False,
        },
    },
}


@dataclass(frozen=True, slots=True)
class CronDraft:
    title: str
    task: str
    cron_expr: str
    timezone: str


@dataclass(frozen=True, slots=True)
class CronTask:
    id: int
    chat_id: int
    user_id: int
    title: str
    task: str
    cron_expr: str
    timezone: str


@dataclass(frozen=True, slots=True)
class CronRun:
    status: str
    result_text: str | None
    error_text: str | None
    start_time: str
    finish_time: str


@dataclass(frozen=True, slots=True)
class CronJobData:
    task_id: int


def cron_job_name(task_id: int) -> str:
    return f"{CRON_JOB_PREFIX}{task_id}"


def cron_delete_keyboard(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🗑️ Delete",
                    callback_data=f"cr:{task_id}",
                    style=KeyboardButtonStyle.DANGER,
                )
            ]
        ]
    )


def validate_cron_expression(cron_expr: str, timezone: str) -> CronTrigger:
    zone = ZoneInfo(timezone)
    trigger = CronTrigger.from_crontab(cron_expr, timezone=zone)
    if trigger.get_next_fire_time(None, datetime.datetime.now(zone)) is None:
        raise RuntimeError("Cron expression never fires.")
    return trigger


def _required_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"AI returned invalid {key}.")
    return value.strip()


def _parse_cron_draft(content: str) -> CronDraft:
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise RuntimeError("AI returned invalid cron metadata.")

    draft = CronDraft(
        title=_required_string(parsed, "title"),
        task=_required_string(parsed, "task"),
        cron_expr=_required_string(parsed, "cron_expr"),
        timezone=_required_string(parsed, "timezone"),
    )
    validate_cron_expression(draft.cron_expr, draft.timezone)
    return draft


async def generate_cron_draft(user_request: str) -> CronDraft:
    now = datetime.datetime.now(ZoneInfo(DEFAULT_TIMEZONE)).isoformat()
    payload = await openrouter_payload(
        "ask",
        [
            {"role": "system", "content": SCHEDULER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Current time: {now}\n\nRequest:\n{user_request}",
            },
        ],
        max_tokens=500,
    )
    payload["response_format"] = CRON_RESPONSE_FORMAT

    async with aiohttp.ClientSession() as session:
        response = await openrouter_json(session, payload)

    content = first_message_content(response)
    if not isinstance(content, str):
        raise RuntimeError("AI returned no cron metadata.")
    return _parse_cron_draft(content)


def _task_from_row(row) -> CronTask:
    return CronTask(
        id=row["id"],
        chat_id=row["chat_id"],
        user_id=row["user_id"],
        title=row["title"],
        task=row["task"],
        cron_expr=row["cron_expr"],
        timezone=row["timezone"],
    )


def _run_from_row(row) -> CronRun:
    return CronRun(
        status=row["status"],
        result_text=row["result_text"],
        error_text=row["error_text"],
        start_time=row["start_time"],
        finish_time=row["finish_time"],
    )


async def create_cron_task(chat_id: int, user_id: int, draft: CronDraft) -> CronTask:
    async with get_db() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO cron_tasks (chat_id, user_id, title, task, cron_expr, timezone)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id, chat_id, user_id, title, task, cron_expr, timezone;
            """,
            (
                chat_id,
                user_id,
                draft.title,
                draft.task,
                draft.cron_expr,
                draft.timezone,
            ),
        )
        row = await cursor.fetchone()
    if row is None:
        raise RuntimeError("Cron task insert failed.")
    return _task_from_row(row)


async def list_user_cron_tasks(chat_id: int, user_id: int) -> list[CronTask]:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT id, chat_id, user_id, title, task, cron_expr, timezone
            FROM cron_tasks
            WHERE chat_id = ? AND user_id = ? AND enabled = 1
            ORDER BY id;
            """,
            (chat_id, user_id),
        ) as cursor:
            rows = await cursor.fetchall()
    return [_task_from_row(row) for row in rows]


async def load_owned_cron_task(
    task_id: int,
    chat_id: int,
    user_id: int,
) -> CronTask | None:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT id, chat_id, user_id, title, task, cron_expr, timezone
            FROM cron_tasks
            WHERE id = ? AND chat_id = ? AND user_id = ? AND enabled = 1;
            """,
            (task_id, chat_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
    return _task_from_row(row) if row else None


async def load_enabled_cron_task(task_id: int) -> CronTask | None:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT id, chat_id, user_id, title, task, cron_expr, timezone
            FROM cron_tasks
            WHERE id = ? AND enabled = 1;
            """,
            (task_id,),
        ) as cursor:
            row = await cursor.fetchone()
    return _task_from_row(row) if row else None


async def load_enabled_cron_tasks() -> list[CronTask]:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT id, chat_id, user_id, title, task, cron_expr, timezone
            FROM cron_tasks
            WHERE enabled = 1
            ORDER BY id;
            """
        ) as cursor:
            rows = await cursor.fetchall()
    return [_task_from_row(row) for row in rows]


async def disable_owned_cron_task(task_id: int, chat_id: int, user_id: int) -> bool:
    async with get_db() as conn:
        cursor = await conn.execute(
            """
            UPDATE cron_tasks
            SET enabled = 0, update_time = CURRENT_TIMESTAMP
            WHERE id = ? AND chat_id = ? AND user_id = ? AND enabled = 1;
            """,
            (task_id, chat_id, user_id),
        )
    return cursor.rowcount == 1


async def delete_owned_cron_task(
    job_queue: JobQueue,
    task_id: int,
    chat_id: int,
    user_id: int,
) -> bool:
    deleted = await disable_owned_cron_task(task_id, chat_id, user_id)
    if deleted:
        remove_registered_cron_task(job_queue, task_id)
    return deleted


async def load_recent_cron_runs(task_id: int) -> list[CronRun]:
    async with get_db() as conn:
        async with conn.execute(
            """
            SELECT status, result_text, error_text, start_time, finish_time
            FROM cron_runs
            WHERE cron_task_id = ?
            ORDER BY id DESC
            LIMIT 5;
            """,
            (task_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    ordered_rows = list(rows)
    ordered_rows.reverse()
    return [_run_from_row(row) for row in ordered_rows]


async def record_cron_run(
    task_id: int,
    status: Literal["success", "error"],
    result_text: str | None,
    error_text: str | None,
    start_time: datetime.datetime,
) -> None:
    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO cron_runs (
                cron_task_id,
                status,
                result_text,
                error_text,
                start_time,
                finish_time
            )
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                task_id,
                status,
                result_text,
                error_text,
                start_time.isoformat(),
                datetime.datetime.now(datetime.UTC).isoformat(),
            ),
        )


def format_run_history(runs: list[CronRun]) -> str:
    if not runs:
        return "No previous runs."

    lines: list[str] = []
    for index, run in enumerate(runs, start=1):
        body = run.result_text if run.status == "success" else run.error_text
        lines.append(
            f"{index}. {run.finish_time} [{run.status}]\n"
            f"{body or 'No output recorded.'}"
        )
    return "\n\n".join(lines)


def build_runner_messages(task: CronTask, runs: list[CronRun]) -> list[JsonObject]:
    return [
        {"role": "system", "content": RUNNER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Title: {task.title}\n\n"
                f"Task:\n{task.task}\n\n"
                f"Previous runs:\n{format_run_history(runs)}"
            ),
        },
    ]


async def execute_cron_task(task: CronTask, runs: list[CronRun]) -> str:
    payload = await openrouter_payload(
        "ask",
        build_runner_messages(task, runs),
        max_tokens=1000,
    )
    async with aiohttp.ClientSession() as session:
        response = await openrouter_json(session, payload)

    content = first_message_content(response)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("AI returned no cron task result.")
    return content.strip()


def remove_registered_cron_task(job_queue: JobQueue, task_id: int) -> None:
    for job in job_queue.get_jobs_by_name(cron_job_name(task_id)):
        job.schedule_removal()


def register_cron_task(job_queue: JobQueue, task: CronTask) -> None:
    remove_registered_cron_task(job_queue, task.id)
    job_queue.run_custom(
        cron_job_callback,
        {
            "trigger": validate_cron_expression(task.cron_expr, task.timezone),
            "id": cron_job_name(task.id),
            "replace_existing": True,
            "max_instances": 1,
            "coalesce": True,
            "misfire_grace_time": 300,
        },
        data=CronJobData(task.id),
        name=cron_job_name(task.id),
        chat_id=task.chat_id,
        user_id=task.user_id,
    )


async def register_enabled_cron_tasks(job_queue: JobQueue | None) -> None:
    if job_queue is None:
        raise RuntimeError("Job queue not initialized.")

    tasks = await load_enabled_cron_tasks()
    for task in tasks:
        register_cron_task(job_queue, task)
    logger.info("Registered %s cron tasks", len(tasks))


async def cron_job_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.job is None or not isinstance(context.job.data, CronJobData):
        raise RuntimeError("Cron job missing task data.")
    await run_cron_task(context, context.job.data.task_id)


async def run_cron_task(context: ContextTypes.DEFAULT_TYPE, task_id: int) -> None:
    task = await load_enabled_cron_task(task_id)
    if task is None:
        return

    start_time = datetime.datetime.now(datetime.UTC)
    try:
        runs = await load_recent_cron_runs(task.id)
        result_text = await execute_cron_task(task, runs)
        username = await utils.get_username(task.user_id, context)
        await context.bot.send_message(
            chat_id=task.chat_id,
            text=(
                f"⏰ <b>{html.escape(task.title)}</b>\n\n"
                f"{html.escape(result_text)}\n\n"
                f"@{html.escape(username)}"
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=cron_delete_keyboard(task.id),
        )
        await record_cron_run(task.id, "success", result_text, None, start_time)
    except Exception as exc:
        logger.exception("Cron task %s failed", task.id)
        error_text = str(exc)
        await record_cron_run(task.id, "error", None, error_text, start_time)
        await context.bot.send_message(
            chat_id=task.chat_id,
            text=f"❌ Cron task failed: <code>{html.escape(task.title)}</code>",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
