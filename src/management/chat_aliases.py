import re
from dataclasses import dataclass

from config.db import get_db

TOKEN_PATTERN = re.compile(r"\w+")


@dataclass(frozen=True)
class Participant:
    user_id: int
    handle: str
    display: str


@dataclass(frozen=True)
class ParticipantAlias:
    alias: str
    participant: Participant


def alias_tokens(value: str) -> tuple[str, ...]:
    return tuple(match.group().casefold() for match in TOKEN_PATTERN.finditer(value))


def match_participants(
    question: str, aliases: list[ParticipantAlias]
) -> list[Participant]:
    question_tokens = alias_tokens(question)
    by_tokens: dict[tuple[str, ...], list[Participant]] = {}
    for item in aliases:
        tokens = alias_tokens(item.alias)
        if 1 <= len(tokens) <= 2:
            by_tokens.setdefault(tokens, []).append(item.participant)

    matched: list[Participant] = []
    matched_ids: set[int] = set()
    index = 0
    while index < len(question_tokens):
        participant = None
        matched_length = 0
        for length in (2, 1):
            candidates = by_tokens.get(question_tokens[index : index + length])
            if candidates:
                participant = min(candidates, key=lambda item: item.user_id)
                matched_length = length
                break
        if participant is None:
            index += 1
            continue
        if participant.user_id not in matched_ids:
            matched.append(participant)
            matched_ids.add(participant.user_id)
        index += matched_length
    return matched


async def resolve_participants(chat_id: int, question: str) -> list[Participant]:
    async with (
        get_db() as connection,
        connection.execute(
            """
            WITH members AS (
                SELECT user_id FROM chat_personas WHERE chat_id = ?
                UNION
                SELECT user_id FROM chat_aliases WHERE chat_id = ?
            )
            SELECT members.user_id, users.username, users.first_name, aliases.alias
            FROM members
            LEFT JOIN user_stats users ON users.user_id = members.user_id
            LEFT JOIN chat_aliases aliases
                ON aliases.chat_id = ? AND aliases.user_id = members.user_id
            ORDER BY members.user_id, aliases.alias
            """,
            (chat_id, chat_id, chat_id),
        ) as cursor,
    ):
        rows = await cursor.fetchall()

    participant_by_id: dict[int, Participant] = {}
    candidate_values: set[tuple[str, int]] = set()
    for row in rows:
        user_id = row["user_id"]
        handle = f"@{row['username']}" if row["username"] else f"user:{user_id}"
        participant_by_id[user_id] = Participant(
            user_id,
            handle,
            row["first_name"] or handle,
        )
        for value in (row["alias"], row["username"], row["first_name"]):
            if value:
                candidate_values.add((value, user_id))

    return match_participants(
        question,
        [
            ParticipantAlias(value, participant_by_id[user_id])
            for value, user_id in sorted(candidate_values)
        ],
    )
