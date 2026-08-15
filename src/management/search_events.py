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
    lane: str,
    citation_message_ids: list[int],
    duration_ms: int,
) -> None:
    async with get_db() as connection:
        await connection.execute(
            """
            INSERT INTO search_events (
                chat_id, user_id, message_id, question, answer, model,
                lane, citation_message_ids, duration_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                message_id,
                question,
                answer,
                model,
                lane,
                json.dumps(citation_message_ids),
                duration_ms,
            ),
        )
