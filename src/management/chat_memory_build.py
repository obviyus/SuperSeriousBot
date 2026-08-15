import asyncio
import json
import re
from dataclasses import dataclass

import ai
import pydantic

from chat_search_config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    MEMORY_MODEL,
    UTTERANCE_EMBEDDING_DIMENSIONS,
)
from commands.ai import openrouter_provider
from config.db import get_db
from config.logger import logger
from config.options import config
from management.chat_search_index import searchable_chat_ids

MEMBER_UTTERANCE_MINIMUM = 200
PERSONA_BATCH_SIZE = 400
RELATED_UTTERANCE_LIMIT = 40
LORE_BATCH_CHARS = 240_000
RECEIPT_PATTERN = re.compile(r"\[(?:msg:\s*\d+)(?:,\s*msg:\s*\d+)*\]")
MESSAGE_ID_PATTERN = re.compile(r"(?m)^(\d+) ")

TONE = (
    "Write a concise dossier for a friend-group roast bot. Be concrete, never "
    "moralise, and use only verbatim quotes. Hinglish is fine."
)


class Alias(pydantic.BaseModel):
    alias: str
    confidence: float = pydantic.Field(ge=0, le=1)


class AliasOutput(pydantic.RootModel[list[Alias]]):
    pass


class PersonaOutput(pydantic.BaseModel):
    sheet: str


class LoreItem(pydantic.BaseModel):
    topic: str = pydantic.Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    summary: str
    receipts: list[int]


class LoreOutput(pydantic.RootModel[list[LoreItem]]):
    pass


@dataclass(frozen=True)
class Member:
    user_id: int
    username: str
    first_name: str | None


@dataclass(frozen=True)
class Utterance:
    start_message_id: int
    end_message_id: int
    end_time: str
    author: str
    text: str


@dataclass(frozen=True)
class LoreWindow:
    start_message_id: int
    end_message_id: int
    month: str
    text: str


@dataclass(frozen=True)
class StoredAlias:
    user_id: int
    alias: str
    confidence: float


@dataclass(frozen=True)
class StoredLore:
    topic: str
    summary: str
    receipts: tuple[int, ...]
    source_end_message_id: int


@dataclass(frozen=True)
class BuildCounts:
    aliases: int
    personas: int
    lore: int


def batches[T](items: list[T], size: int) -> list[list[T]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def filter_aliases(candidates: list[tuple[int, Alias]]) -> list[StoredAlias]:
    by_alias: dict[str, StoredAlias] = {}
    for user_id, candidate in candidates:
        alias = " ".join(candidate.alias.casefold().split())
        if not alias or candidate.confidence < 0.5:
            continue
        stored = StoredAlias(user_id, alias, candidate.confidence)
        current = by_alias.get(alias)
        if current is None or (-stored.confidence, stored.user_id) < (
            -current.confidence,
            current.user_id,
        ):
            by_alias[alias] = stored
    return sorted(by_alias.values(), key=lambda item: item.alias)


def strip_invalid_receipts(sheet: str, allowed: set[int]) -> tuple[str, list[int]]:
    kept: list[int] = []

    def replace(match: re.Match[str]) -> str:
        valid = [
            int(value)
            for value in re.findall(r"\d+", match.group())
            if int(value) in allowed
        ]
        kept.extend(valid)
        return f"[{', '.join(f'msg:{value}' for value in valid)}]" if valid else ""

    return RECEIPT_PATTERN.sub(replace, sheet), list(dict.fromkeys(kept))


def disjoint_windows(windows: list[LoreWindow]) -> list[LoreWindow]:
    """Search windows overlap (stride < length); keep a non-overlapping cover."""
    kept: list[LoreWindow] = []
    for window in windows:
        if not kept or window.start_message_id > kept[-1].end_message_id:
            kept.append(window)
    return kept


def batch_lore_windows(
    windows: list[LoreWindow], max_chars: int = LORE_BATCH_CHARS
) -> list[list[LoreWindow]]:
    result: list[list[LoreWindow]] = []
    current: list[LoreWindow] = []
    size = 0
    for window in disjoint_windows(windows):
        if current and (
            window.month != current[0].month or size + len(window.text) > max_chars
        ):
            result.append(current)
            current, size = [], 0
        current.append(window)
        size += len(window.text)
    if current:
        result.append(current)
    return result


def merge_lore(
    existing: dict[str, StoredLore],
    generated: list[LoreItem],
    allowed: set[int],
    source_end_message_id: int,
) -> list[StoredLore]:
    merged = []
    for item in generated:
        previous = existing.get(item.topic)
        receipts = list(previous.receipts) if previous else []
        receipts.extend(receipt for receipt in item.receipts if receipt in allowed)
        merged.append(
            StoredLore(
                item.topic,
                item.summary,
                tuple(dict.fromkeys(receipts)),
                source_end_message_id,
            )
        )
    return merged


def message_ids(text: str, fallback: int) -> set[int]:
    return {fallback, *(int(value) for value in MESSAGE_ID_PATTERN.findall(text))}


def format_utterances(utterances: list[Utterance]) -> str:
    return "\n".join(
        f"{item.end_message_id} {item.end_time} {item.author}: "
        f"{item.text.replace(chr(10), ' / ')}"
        for item in utterances
    )


async def generate_object[OutputT: pydantic.BaseModel](
    model: ai.Model,
    semaphore: asyncio.Semaphore,
    label: str,
    messages: list[ai.messages.Message],
    output_type: type[OutputT],
    max_tokens: int,
) -> OutputT | None:
    for attempt in range(2):
        try:
            async with semaphore:
                params = ai.InferenceRequestParams(
                    output=ai.OutputParams(max_tokens=max_tokens)
                ).with_temperature(0)
                async with ai.stream(
                    model, messages, output_type=output_type, params=params
                ) as stream:
                    async for _ in stream:
                        pass
                return stream.output
        except (ai.AIError, pydantic.ValidationError):
            if attempt == 0:
                logger.warning("Chat memory model call failed; retrying: %s", label)
            else:
                logger.exception(
                    "Chat memory model call failed twice; skipping: %s", label
                )
    return None


async def eligible_members(chat_id: int) -> list[Member]:
    async with (
        get_db() as conn,
        conn.execute(
            """
            SELECT u.user_id,
                COALESCE(s.username, 'user:' || u.user_id) AS username,
                s.first_name
            FROM chat_search_utterances u
            LEFT JOIN user_stats s ON s.user_id = u.user_id
            WHERE u.chat_id = ? AND u.embedding_model = ?
            AND u.embedding_dimension = ?
            GROUP BY u.user_id, s.username, s.first_name
            HAVING COUNT(*) >= ? ORDER BY u.user_id
            """,
            (
                chat_id,
                EMBEDDING_MODEL,
                UTTERANCE_EMBEDDING_DIMENSIONS,
                MEMBER_UTTERANCE_MINIMUM,
            ),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return [Member(row["user_id"], row["username"], row["first_name"]) for row in rows]


def utterance_from_row(row) -> Utterance:
    return Utterance(
        row["start_message_id"],
        row["end_message_id"],
        row["end_time"],
        row["author"],
        row["message_text"],
    )


async def select_utterances(sql: str, params: tuple[object, ...]) -> list[Utterance]:
    async with get_db() as conn, conn.execute(sql, params) as cursor:
        rows = await cursor.fetchall()
    return [utterance_from_row(row) for row in rows]


async def alias_evidence(chat_id: int, member: Member) -> list[Utterance]:
    columns = "start_message_id, end_message_id, end_time, author, message_text"
    own, incoming = await asyncio.gather(
        select_utterances(
            f"""SELECT {columns} FROM chat_search_utterances
                WHERE chat_id = ? AND user_id = ? AND embedding_model = ?
                AND embedding_dimension = ? ORDER BY RANDOM() LIMIT 150""",
            (chat_id, member.user_id, EMBEDDING_MODEL, UTTERANCE_EMBEDDING_DIMENSIONS),
        ),
        select_utterances(
            f"""SELECT {columns} FROM chat_search_utterances u
                WHERE chat_id = ? AND user_id <> ? AND embedding_model = ?
                AND embedding_dimension = ? AND EXISTS (
                    SELECT 1 FROM chat_mentions m WHERE m.chat_id = u.chat_id
                    AND m.mentioned_user_id = ?
                    AND m.message_id BETWEEN u.start_message_id AND u.end_message_id
                ) ORDER BY RANDOM() LIMIT 150""",
            (
                chat_id,
                member.user_id,
                EMBEDDING_MODEL,
                UTTERANCE_EMBEDDING_DIMENSIONS,
                member.user_id,
            ),
        ),
    )
    return own + incoming


async def build_aliases(
    chat_id: int,
    members: list[Member],
    model: ai.Model,
    semaphore: asyncio.Semaphore,
) -> int:
    async def generate(member: Member) -> list[tuple[int, Alias]]:
        evidence = await alias_evidence(chat_id, member)
        output = await generate_object(
            model,
            semaphore,
            f"aliases chat={chat_id} user={member.user_id}",
            [
                ai.system_message(
                    f"{TONE} Extract lowercase nicknames, short names, and spellings "
                    "people use for this member. Return only grounded aliases."
                ),
                ai.user_message(
                    f"username={member.username}\nfirst_name={member.first_name or ''}\n\n"
                    + format_utterances(evidence)
                ),
            ],
            AliasOutput,
            1200,
        )
        return (
            [] if output is None else [(member.user_id, item) for item in output.root]
        )

    aliases = filter_aliases(
        [
            item
            for generated in await asyncio.gather(*(generate(m) for m in members))
            for item in generated
        ]
    )
    async with get_db() as conn:
        await conn.execute("DELETE FROM chat_aliases WHERE chat_id = ?", (chat_id,))
        if aliases:
            await conn.executemany(
                "INSERT INTO chat_aliases VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                [
                    (chat_id, item.user_id, item.alias, item.confidence)
                    for item in aliases
                ],
            )
    return len(aliases)


async def persona_source(
    chat_id: int, member: Member
) -> tuple[str, set[int], list[Utterance], bool]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT sheet, receipts, source_end_message_id FROM chat_personas "
            "WHERE chat_id = ? AND user_id = ?",
            (chat_id, member.user_id),
        ) as cursor:
            previous = await cursor.fetchone()
        watermark = previous["source_end_message_id"] if previous else -(1 << 63)
        async with conn.execute(
            """
            SELECT start_message_id, end_message_id, end_time, author, message_text
            FROM chat_search_utterances WHERE chat_id = ? AND user_id = ?
            AND embedding_model = ? AND embedding_dimension = ?
            AND end_message_id > ? ORDER BY end_message_id
            """,
            (
                chat_id,
                member.user_id,
                EMBEDDING_MODEL,
                UTTERANCE_EMBEDDING_DIMENSIONS,
                watermark,
            ),
        ) as cursor:
            rows = await cursor.fetchall()
    return (
        previous["sheet"] if previous else "",
        set(json.loads(previous["receipts"])) if previous else set(),
        [utterance_from_row(row) for row in rows],
        previous is None,
    )


async def related_utterances(
    chat_id: int, member: Member, start_message_id: int, end_message_id: int
) -> list[Utterance]:
    return await select_utterances(
        """
        SELECT u.start_message_id, u.end_message_id, u.end_time, u.author, u.message_text
        FROM chat_search_utterances u WHERE u.chat_id = ? AND u.user_id <> ?
        AND u.embedding_model = ? AND u.embedding_dimension = ?
        AND u.end_message_id >= ? AND u.start_message_id <= ? AND EXISTS (
            SELECT 1 FROM chat_stats s WHERE s.chat_id = u.chat_id
            AND s.user_id = u.user_id
            AND s.message_id BETWEEN u.start_message_id AND u.end_message_id
            AND (s.reply_to_user_id = ? OR EXISTS (
                SELECT 1 FROM chat_mentions m WHERE m.chat_id = s.chat_id
                AND m.message_id = s.message_id AND m.mentioned_user_id = ?
            ))
        ) ORDER BY u.end_message_id LIMIT ?
        """,
        (
            chat_id,
            member.user_id,
            EMBEDDING_MODEL,
            UTTERANCE_EMBEDDING_DIMENSIONS,
            start_message_id,
            end_message_id,
            member.user_id,
            member.user_id,
            RELATED_UTTERANCE_LIMIT,
        ),
    )


async def build_persona(
    chat_id: int,
    member: Member,
    model: ai.Model,
    semaphore: asyncio.Semaphore,
    bootstrap: bool,
) -> bool:
    sheet, receipts, pending, missing = await persona_source(chat_id, member)
    pending_batches = batches(pending, PERSONA_BATCH_SIZE)
    if not (bootstrap or missing):
        pending_batches = pending_batches[:1]
    updated = False
    for batch in pending_batches:
        related = await related_utterances(
            chat_id, member, batch[0].start_message_id, batch[-1].end_message_id
        )
        context = batch + related
        allowed = receipts | {
            message_id
            for item in context
            for message_id in message_ids(item.text, item.end_message_id)
        }
        output = await generate_object(
            model,
            semaphore,
            f"persona chat={chat_id} user={member.user_id}",
            [
                ai.system_message(
                    f"{TONE} Update the member sheet in at most 700 words. Use these "
                    "sections: Nicknames; Interests & obsessions; Opinions they hold; "
                    "Habits & running behaviour; What others roast them for; Feuds & "
                    "pairings; Signature lines (verbatim). Every bullet must end with "
                    "receipts like [msg:12, msg:34]. Use only supplied receipt IDs."
                ),
                ai.user_message(
                    f"Member: @{member.username}\nPrevious sheet:\n{sheet or '(none)'}"
                    f"\n\nNew utterances:\n{format_utterances(context)}"
                ),
            ],
            PersonaOutput,
            5000,
        )
        if output is None:
            break
        sheet, kept = strip_invalid_receipts(output.sheet, allowed)
        receipts = set(kept)
        watermark = batch[-1].end_message_id
        async with get_db() as conn:
            await conn.execute(
                """
                INSERT INTO chat_personas VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET sheet = excluded.sheet,
                receipts = excluded.receipts,
                source_end_message_id = excluded.source_end_message_id,
                update_time = CURRENT_TIMESTAMP
                """,
                (chat_id, member.user_id, sheet, json.dumps(kept), watermark),
            )
        updated = True
    return updated


async def lore_source(chat_id: int) -> tuple[dict[str, StoredLore], list[LoreWindow]]:
    async with get_db() as conn:
        async with conn.execute(
            "SELECT topic, summary, receipts, source_end_message_id FROM chat_lore "
            "WHERE chat_id = ?",
            (chat_id,),
        ) as cursor:
            lore_rows = await cursor.fetchall()
        watermark = max(
            (row["source_end_message_id"] for row in lore_rows), default=-(1 << 63)
        )
        async with conn.execute(
            """
            SELECT start_message_id, end_message_id, start_time, message_text
            FROM chat_search_windows WHERE chat_id = ? AND embedding_model = ?
            AND embedding_dimension = ? AND end_message_id > ?
            ORDER BY start_message_id
            """,
            (chat_id, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, watermark),
        ) as cursor:
            window_rows = await cursor.fetchall()
    existing = {
        row["topic"]: StoredLore(
            row["topic"],
            row["summary"],
            tuple(json.loads(row["receipts"])),
            row["source_end_message_id"],
        )
        for row in lore_rows
    }
    windows = [
        LoreWindow(
            row["start_message_id"],
            row["end_message_id"],
            str(row["start_time"])[:7],
            row["message_text"],
        )
        for row in window_rows
    ]
    return existing, windows


async def build_lore(
    chat_id: int, model: ai.Model, semaphore: asyncio.Semaphore
) -> int:
    existing, windows = await lore_source(chat_id)
    stored = 0
    for batch in batch_lore_windows(windows):
        source_end = max(window.end_message_id for window in batch)
        allowed = {
            message_id
            for window in batch
            for message_id in message_ids(window.text, window.end_message_id)
        }
        output = await generate_object(
            model,
            semaphore,
            f"lore chat={chat_id} end={source_end}",
            [
                ai.system_message(
                    f"{TONE} Extract running jokes, incidents, coined words, feuds, "
                    "pairings, and memes. Return slug-like topics, summaries of at "
                    "most 80 words, and real message-ID receipts. Merge any matching "
                    "existing topic into one replacement summary."
                ),
                ai.user_message(
                    "Existing lore:\n"
                    + json.dumps(
                        [
                            {
                                "topic": item.topic,
                                "summary": item.summary,
                                "receipts": item.receipts,
                            }
                            for item in existing.values()
                        ]
                    )
                    + "\n\nChat windows:\n"
                    + "\n".join(window.text for window in batch)
                ),
            ],
            LoreOutput,
            5000,
        )
        if output is None:
            break
        if not output.root:
            continue
        merged = merge_lore(existing, output.root, allowed, source_end)
        async with get_db() as conn:
            await conn.executemany(
                """
                INSERT INTO chat_lore VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id, topic) DO UPDATE SET summary = excluded.summary,
                receipts = excluded.receipts,
                source_end_message_id = excluded.source_end_message_id,
                update_time = CURRENT_TIMESTAMP
                """,
                [
                    (
                        chat_id,
                        item.topic,
                        item.summary,
                        json.dumps(item.receipts),
                        item.source_end_message_id,
                    )
                    for item in merged
                ],
            )
        existing.update((item.topic, item) for item in merged)
        stored += len(merged)
    return stored


async def build_chat_memory(
    chat_id: int, model: ai.Model, *, bootstrap: bool
) -> BuildCounts:
    members = await eligible_members(chat_id)
    semaphore = asyncio.Semaphore(4)
    aliases = await build_aliases(chat_id, members, model, semaphore)
    persona_results = await asyncio.gather(
        *(
            build_persona(chat_id, member, model, semaphore, bootstrap)
            for member in members
        )
    )
    lore = await build_lore(chat_id, model, semaphore)
    return BuildCounts(aliases, sum(persona_results), lore)


async def build_chat_memories(
    chat_ids: list[int] | None = None, *, bootstrap: bool = False
) -> None:
    if not config.API.OPENROUTER_API_KEY:
        logger.info("Skipping chat memory build: OPENROUTER_API_KEY is unavailable")
        return
    searchable = await searchable_chat_ids()
    selected = (
        searchable
        if chat_ids is None
        else [item for item in chat_ids if item in searchable]
    )
    model = ai.Model(id=MEMORY_MODEL, provider=openrouter_provider())
    for chat_id in selected:
        counts = await build_chat_memory(chat_id, model, bootstrap=bootstrap)
        logger.info(
            "Built chat memory chat_id=%d aliases=%d personas=%d lore=%d",
            chat_id,
            counts.aliases,
            counts.personas,
            counts.lore,
        )
