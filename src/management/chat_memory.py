from datetime import UTC, datetime

import ijson
from telegram import Message, MessageEntity

from config.db import get_db
from utils.string import get_user_id_from_username

type ChatImportRow = tuple[int, str, int, str, str]


async def save_message_stats(message: Message) -> None:
    if not message.from_user or not message.from_user.username:
        return

    user = message.from_user
    chat_id = message.chat_id

    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO user_stats (user_id, username, last_seen, last_message_link)
                VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                last_seen = excluded.last_seen,
                last_message_link = excluded.last_message_link
            """,
            (
                user.id,
                user.username,
                datetime.now(),
                message.link if message.link else None,
            ),
        )

        message_text = None
        if message.text:
            async with conn.execute(
                "SELECT fts FROM group_settings WHERE chat_id = ?;",
                (chat_id,),
            ) as cursor:
                result = await cursor.fetchone()
            if result and result["fts"]:
                message_text = message.text

        await conn.execute(
            """
            INSERT OR IGNORE INTO chat_stats (chat_id, user_id, message_id, message_text)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, user.id, message.message_id, message_text),
        )


async def save_mention(
    mentioning_user_id: int,
    mentioned_user_id: int,
    message: Message,
) -> None:
    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO chat_mentions (mentioning_user_id, mentioned_user_id, chat_id, message_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                mentioning_user_id,
                mentioned_user_id,
                message.chat.id,
                message.message_id,
            ),
        )


async def process_mentions(message: Message) -> None:
    if not message.from_user:
        return

    mentioning_user_id = message.from_user.id
    mentioned_users: set[int] = set()

    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntity.TEXT_MENTION and entity.user:
                if entity.user.id not in mentioned_users:
                    mentioned_users.add(entity.user.id)
                    await save_mention(mentioning_user_id, entity.user.id, message)
            elif entity.type == MessageEntity.MENTION and message.text:
                mentioned_username = message.text[
                    entity.offset + 1 : entity.offset + entity.length
                ]
                user_id = await get_user_id_from_username(mentioned_username)
                if user_id is not None and user_id not in mentioned_users:
                    mentioned_users.add(user_id)
                    await save_mention(mentioning_user_id, user_id, message)

    if message.reply_to_message and message.reply_to_message.from_user:
        replied_user_id = message.reply_to_message.from_user.id
        if replied_user_id not in mentioned_users:
            await save_mention(mentioning_user_id, replied_user_id, message)


async def chat_search(
    chat_id: int,
    query: str,
    author_id: int | None,
) -> list:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT fts FROM group_settings WHERE chat_id = ?;",
            (chat_id,),
        ) as cursor:
            setting = await cursor.fetchone()

        if not setting or not setting["fts"]:
            return []

        async with conn.execute(
            """
            SELECT cs.message_id
                FROM chat_stats_fts csf
                INNER JOIN chat_stats cs ON cs.id = csf.rowid
            WHERE csf.message_text MATCH ?
                AND csf.chat_id = ?
                AND (? IS NULL OR cs.user_id = ?)
                AND cs.message_text NOT LIKE '/%';
            """,
            (query, chat_id, author_id, author_id),
        ) as cursor:
            return list(await cursor.fetchall())


async def is_fts_enabled(chat_id: int) -> bool:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT fts FROM group_settings WHERE chat_id = ?;",
            (chat_id,),
        ) as cursor:
            setting = await cursor.fetchone()
    return bool(setting and setting["fts"])


async def enable_fts(chat_id: int) -> None:
    async with get_db() as conn:
        await conn.execute(
            """
            INSERT INTO group_settings (chat_id, fts) VALUES (?, 1)
            ON CONFLICT(chat_id) DO UPDATE SET fts = 1;
            """,
            (chat_id,),
        )


async def chat_stats_summary(chat_id: int, *, today_only: bool) -> tuple[list, int]:
    time_clause = (
        "AND create_time >= DATE('now', 'localtime') AND create_time < DATE('now', '+1 day', 'localtime')"
        if today_only
        else ""
    )
    async with get_db() as conn:
        async with conn.execute(
            f"""
            SELECT create_time, user_id, COUNT(user_id) AS user_count
            FROM chat_stats
            WHERE chat_id = ? {time_clause}
            GROUP BY user_id
            ORDER BY COUNT(user_id) DESC
            LIMIT 10;
            """,
            (chat_id,),
        ) as cursor:
            rows = list(await cursor.fetchall())
        async with conn.execute(
            f"""
            SELECT COUNT(id) AS total_count
            FROM chat_stats
            WHERE chat_id = ? {time_clause};
            """,
            (chat_id,),
        ) as cursor:
            result = await cursor.fetchone()
            total_count = result["total_count"] if result else 0
    return rows, total_count


async def last_seen_by_username(username: str):
    async with get_db() as conn:
        async with conn.execute(
            "SELECT username, last_seen, last_message_link FROM user_stats WHERE LOWER(username) = ?",
            (username.lower(),),
        ) as cursor:
            return await cursor.fetchone()


def parse_export_file(filepath: str, chat_id: int) -> list[ChatImportRow]:
    batch = []
    with open(filepath, "rb") as f:
        for msg in ijson.items(f, "messages.item"):
            if msg["type"] != "message" or not msg["text"] or not (from_id := msg.get("from_id")):
                continue

            text = "".join(
                part.get("text", "")
                if isinstance(part, dict) and part.get("type") == "bot_command"
                else part if isinstance(part, str)
                else ""
                for part in msg["text"]
            )
            if not text:
                continue

            raw = msg["date"]
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(raw)
            except ValueError:
                dt = datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")
            if dt.tzinfo is not None:
                dt = dt.astimezone(UTC).replace(tzinfo=None)

            batch.append(
                (
                    chat_id,
                    from_id.replace("user", ""),
                    msg["id"],
                    dt.strftime("%Y-%m-%d %H:%M:%S"),
                    text,
                )
            )

    return batch


async def import_chat_stats_rows(chat_id: int, batch: list[ChatImportRow]) -> None:
    async with get_db() as conn:
        await conn.execute("PRAGMA synchronous = OFF;")
        await conn.execute("PRAGMA journal_mode = MEMORY;")
        await conn.execute("DROP TRIGGER IF EXISTS chat_stats_ai;")
        await conn.executemany(
            """
            INSERT INTO chat_stats (chat_id, user_id, message_id, create_time, message_text)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, user_id, message_id) DO NOTHING;
            """,
            batch,
        )

        await conn.execute(
            """
            CREATE TRIGGER chat_stats_ai AFTER INSERT ON chat_stats BEGIN
                INSERT INTO chat_stats_fts (rowid, message_text, chat_id)
                VALUES (new.id, new.message_text, new.chat_id);
            END
            """
        )

        await conn.execute(
            """
            INSERT INTO chat_stats_fts (rowid, message_text, chat_id)
            SELECT cs.id, cs.message_text, cs.chat_id
            FROM chat_stats cs
            WHERE cs.chat_id = ?
            AND NOT EXISTS (
                SELECT 1 FROM chat_stats_fts WHERE rowid = cs.id
            )
            """,
            (chat_id,),
        )

        await conn.execute("PRAGMA synchronous = FULL;")
        await conn.execute("PRAGMA journal_mode = WAL;")
