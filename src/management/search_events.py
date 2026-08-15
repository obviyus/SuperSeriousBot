import json

from config.db import get_db


async def record_search_event(
    *,
    chat_id: int,
    user_id: int,
    message_id: int,
    question: str,
    answer: str,
    model: str,
    citation_message_ids: list[int],
    duration_ms: int,
) -> int:
    async with get_db() as connection:
        cursor = await connection.execute(
            """
            INSERT INTO search_events (
                chat_id, user_id, message_id, question, answer, model,
                citation_message_ids, duration_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                message_id,
                question,
                answer,
                model,
                json.dumps(citation_message_ids),
                duration_ms,
            ),
        )
    return cursor.lastrowid


async def set_search_answer_message_id(event_id: int, answer_message_id: int) -> None:
    async with get_db() as connection:
        await connection.execute(
            "UPDATE search_events SET answer_message_id = ? WHERE id = ?",
            (answer_message_id, event_id),
        )


async def record_search_feedback(event_id: int, user_id: int, vote: int) -> None:
    async with get_db() as connection:
        await connection.execute(
            """
            INSERT INTO search_feedback (event_id, user_id, vote)
            VALUES (?, ?, ?)
            ON CONFLICT(event_id, user_id) DO UPDATE SET
                vote = excluded.vote,
                create_time = CURRENT_TIMESTAMP
            """,
            (event_id, user_id, vote),
        )
