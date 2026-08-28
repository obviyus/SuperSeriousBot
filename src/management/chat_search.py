import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

import ai
import pydantic

from chat_search_config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    QUERY_INSTRUCTION,
    UTTERANCE_EMBEDDING_DIMENSIONS,
    VECTOR_RESULT_COUNT,
)
from commands.ai import model
from config.db import get_db
from config.logger import logger
from management.chat_aliases import Participant, resolve_participants
from management.chat_search_cache import open_search_cache
from management.chat_semantic_search import (
    NO_SOLID_ANSWER,
    SearchAnswerOutput,
    SearchEvidence,
    fetch_search_evidence,
    render_search_answer,
    select_evidence,
    telegram_message_link,
    vector_search_candidates,
)
from openrouter_embeddings import openrouter_embeddings, vector32_json

MAX_LEXICAL_TERMS = 10
MAX_EVIDENCE = 24
LEXICAL_RESULT_COUNT = 12
PAIR_RESULT_COUNT = 12
UTTERANCE_CANDIDATE_COUNT = 300
UTTERANCE_AUTHOR_COUNT = 8
UTTERANCES_PER_AUTHOR = 3
MODEL_TIMEOUT_SECONDS = 30
MEMORY_PROMPT_CHAR_LIMIT = 140_000
NON_FOCUS_SHEET_CHAR_LIMIT = 2_000
UTTERANCE_QUERY_INSTRUCTION = (
    "Instruct: Retrieve Telegram utterances that directly show which participant "
    "said, did, liked, disliked, or repeatedly demonstrated the behavior in the "
    "question. Prefer first-person statements and direct descriptions over generic "
    "topic mentions.\nQuery: "
)

ANSWER_PROMPT = f"""Answer the question from the supplied Telegram evidence only.

This is a fun group-memory feature. For subjective, social, hypothetical, superlative,
and ranking questions, make the best-supported call instead of demanding mathematical
proof. Explain the observed chat behavior behind the choice. A ranking may use recorded
interaction totals as candidate evidence and messages as qualitative receipts.

Keep factual claims strict. Preserve @handles exactly. Respect who said each message and
who they addressed. Do not turn a statement about someone into a fact about its speaker.
For a requested list, return the requested number when the evidence provides enough
candidates. For a "who" superlative, the first sentence must name one participant as the
verdict; do not substitute a list of observations. Use evidence indexes only in citations.
Use no citations only when submitting
exactly '{NO_SOLID_ANSWER}'. Choose that result only when there is no relevant evidence.
Do not put citation markers, message IDs, or URLs in the answer text."""

ROUTER_PROMPT = """Route this Telegram group-memory request into exactly one lane.

persona: superlatives; "most likely"; "who is the X"; X's best friend; describing a
member; why a member acts a certain way; rankings; opinions about members.
creative: essays, stories, nickname lists, roleplay, and rewrites.
fact: concrete factual lookups such as jobs, dates, what X said about Y, and links.

Default to persona when uncertain. Do not answer the request."""

PERSONA_ANSWER_PROMPT = """Answer from the supplied friend-group dossiers and receipts.
Write 2-5 punchy sentences. The first sentence states the answer outright, naming the
person by @handle; never label it "Verdict:". Keep the tone playful and roast-like,
never moralising. Speak as a friend who simply knows the group: never mention dossiers,
lore, receipts, evidence, records, retrieval, "documented", "recorded totals", or how
you know. When interaction totals are supplied, let them decide who is close to whom,
and you may cite the number itself. Return at most four short verbatim quotes copied
from message text in the supplied context, never lore topic names or summaries. Use
only their real message IDs. Do not put links or message IDs in the answer."""

CREATIVE_ANSWER_PROMPT = """Create the requested artefact from the supplied friend-group
dossiers and receipts. Keep the answer at or below 1200 characters. Never mention
dossiers, lore, receipts, evidence, or how you know things; write as a friend who knows
the group. Return at most four short verbatim quotes copied from message text in the
supplied context when useful. Use only their real message IDs. Do not put links or
message IDs in the answer."""

type Lane = Literal["persona", "creative", "fact"]


class SearchPlan(pydantic.BaseModel):
    semantic_queries: list[str] = pydantic.Field(min_length=1, max_length=4)
    lexical_terms: list[str] = pydantic.Field(default_factory=list, max_length=10)
    resolved_handles: list[str] = pydantic.Field(default_factory=list, max_length=3)
    include_interaction_pairs: bool = False


@dataclass(frozen=True)
class SearchResult:
    answer: str
    model: str
    citation_message_ids: list[int]
    lane: str


class QueryExpansion(pydantic.BaseModel):
    semantic_queries: list[str] = pydantic.Field(min_length=1, max_length=3)
    lexical_terms: list[str] = pydantic.Field(default_factory=list, max_length=10)
    resolved_handles: list[str] = pydantic.Field(default_factory=list, max_length=3)


class RouteOutput(pydantic.BaseModel):
    lane: Lane


class Quote(pydantic.BaseModel):
    message_id: int
    text: str


class MemoryAnswerOutput(pydantic.BaseModel):
    answer: str = pydantic.Field(max_length=1200)
    quotes: list[Quote] = pydantic.Field(default_factory=list, max_length=4)


@dataclass(frozen=True)
class PersonaSheet:
    user_id: int
    handle: str
    display: str
    sheet: str
    receipts: tuple[int, ...]


@dataclass(frozen=True)
class LoreRow:
    topic: str
    summary: str
    receipts: tuple[int, ...]


SEARCH_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "does",
    "do",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "most",
    "of",
    "the",
    "this",
    "to",
    "who",
    "why",
}
PAIR_PATTERN = re.compile(
    r"\b(best friend|bestie|bff|friend pair|pair|duo|couple|bros|worst enem)\b",
    re.IGNORECASE,
)


def display_author(author: object) -> str:
    value = str(author)
    return value if value.startswith(("@", "user:")) else f"@{value}"


async def generate_search_object[OutputT: pydantic.BaseModel](
    search_model: ai.Model,
    messages: list[ai.messages.Message],
    output_type: type[OutputT],
    *,
    max_tokens: int,
    reasoning_effort: str | ai.ModelProviderDefault | None = ai.DEFAULT,
) -> OutputT:
    params = (
        ai.InferenceRequestParams(output=ai.OutputParams(max_tokens=max_tokens))
        .with_temperature(0)
        .with_reasoning_effort(reasoning_effort)
    )

    async def attempt() -> OutputT:
        async with asyncio.timeout(MODEL_TIMEOUT_SECONDS):
            async with ai.stream(
                search_model,
                messages,
                output_type=output_type,
                params=params,
            ) as stream:
                async for _ in stream:
                    pass
        return stream.output

    try:
        return await attempt()
    except pydantic.ValidationError:
        # Gemini flash sometimes whitespace-loops until max_tokens truncates the
        # structured output mid-JSON (observed 2026-08); one retry clears it.
        return await attempt()


async def plan_search(
    search_model: ai.Model,
    question: str,
    identity_clues: list[SearchEvidence],
) -> SearchPlan:
    direct_terms = [
        token
        for token in re.findall(r"[@\w'-]+", question.casefold())
        if len(token) > 2 and token not in SEARCH_STOP_WORDS
    ]
    try:
        expansion = await generate_search_object(
            search_model,
            [
                ai.system_message(
                    "Expand a Telegram chat-memory question for retrieval. Return up "
                    "to three short semantic paraphrases using concrete observable "
                    "language, plus exact names, handles, phrases, slang variants, and "
                    "synonyms for lexical matching. Preserve the original predicate: "
                    "someone doing, liking, or being something must not become merely "
                    "discussing or mentioning it. Use any supplied identity clues to "
                    "replace a person's real name or nickname with their @handle in "
                    "semantic queries. Do not answer the question."
                ),
                ai.user_message(evidence_prompt(question, identity_clues)),
            ],
            QueryExpansion,
            max_tokens=2000,
        )
    except pydantic.ValidationError:
        # Expansion is best-effort: the raw question and its direct terms already
        # make a searchable plan.
        logger.warning("Query expansion failed twice; searching unexpanded")
        expansion = QueryExpansion(semantic_queries=[question])
    return SearchPlan(
        semantic_queries=list(dict.fromkeys((question, *expansion.semantic_queries)))[
            :4
        ],
        lexical_terms=list(dict.fromkeys((*direct_terms, *expansion.lexical_terms)))[
            :MAX_LEXICAL_TERMS
        ],
        resolved_handles=list(dict.fromkeys(expansion.resolved_handles))[:3],
        include_interaction_pairs=bool(PAIR_PATTERN.search(question)),
    )


def identity_terms(question: str) -> list[str]:
    return [
        token
        for token in re.findall(r"\b[A-Z][\w'-]{2,}\b", question)
        if token.casefold() not in SEARCH_STOP_WORDS and not token.isupper()
    ][:3]


async def identity_evidence(
    chat_id: int,
    terms: list[str],
) -> list[SearchEvidence]:
    if not terms:
        return []
    async with (
        get_db() as connection,
        connection.execute(
            """
            SELECT
                messages.message_id,
                messages.create_time,
                COALESCE(users.username, 'user:' || messages.user_id) AS author,
                messages.message_text,
                bm25(chat_stats_fts) AS rank
            FROM chat_stats_fts
            JOIN chat_stats messages ON messages.id = chat_stats_fts.rowid
            LEFT JOIN user_stats users ON users.user_id = messages.user_id
            WHERE chat_stats_fts.message_text MATCH ?
            AND chat_stats_fts.chat_id = ?
            AND messages.message_text LIKE '%@%'
            ORDER BY rank
            LIMIT 8
            """,
            (fts_query(terms), chat_id),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return [
        SearchEvidence(
            chat_id=chat_id,
            start_message_id=row["message_id"],
            end_message_id=row["message_id"],
            citation_message_id=row["message_id"],
            text=(
                f"{row['message_id']} {row['create_time']} "
                f"{display_author(row['author'])}: {row['message_text']}"
            ),
            score=1 / (1 + abs(row["rank"])),
        )
        for row in rows
    ]


async def semantic_evidence(
    chat_id: int,
    queries: list[str],
    author_id: int | None,
) -> list[SearchEvidence]:
    embeddings = await openrouter_embeddings(
        EMBEDDING_MODEL,
        [QUERY_INSTRUCTION + query for query in queries],
        dimensions=EMBEDDING_DIMENSIONS,
    )
    candidate_count = 512 if author_id is not None else VECTOR_RESULT_COUNT
    candidate_lists = await asyncio.gather(
        *(
            vector_search_candidates(
                chat_id,
                vector32_json(embedding),
                candidate_count,
            )
            for embedding in embeddings
        )
    )
    result_lists = await asyncio.gather(
        *(
            fetch_search_evidence(candidates, author_id)
            for candidates in candidate_lists
        )
    )
    return merge_evidence(
        item for results in result_lists for item in select_evidence(results)
    )


async def utterance_evidence(
    chat_id: int,
    queries: list[str],
    author_id: int | None,
) -> list[SearchEvidence]:
    embeddings = await openrouter_embeddings(
        EMBEDDING_MODEL,
        [UTTERANCE_QUERY_INSTRUCTION + query for query in queries],
        dimensions=UTTERANCE_EMBEDDING_DIMENSIONS,
    )

    def search(query_vector: str):
        connection = open_search_cache()
        try:
            return connection.execute(
                """
                SELECT
                    remote_id,
                    start_message_id,
                    end_message_id,
                    user_id,
                    author,
                    start_time,
                    message_text,
                    vector_distance_cos(embedding, vector32(?)) AS distance
                FROM search_utterances
                WHERE chat_id = ?
                AND embedding_model = ?
                AND embedding_dimension = ?
                AND (? IS NULL OR user_id = ?)
                ORDER BY distance
                LIMIT ?
                """,
                (
                    query_vector,
                    chat_id,
                    EMBEDDING_MODEL,
                    UTTERANCE_EMBEDDING_DIMENSIONS,
                    author_id,
                    author_id,
                    UTTERANCE_CANDIDATE_COUNT,
                ),
            ).fetchall()
        finally:
            connection.close()

    result_lists = await asyncio.gather(
        *(
            asyncio.to_thread(search, vector32_json(embedding))
            for embedding in embeddings
        )
    )
    best_rows = {}
    for rows in result_lists:
        for row in rows:
            score = 1 - row[7]
            existing = best_rows.get(row[0])
            if existing is None or score > existing[0]:
                best_rows[row[0]] = (score, row)

    by_author = {}
    for score, row in best_rows.values():
        by_author.setdefault(row[3], []).append((score, row))
    ranked_authors = sorted(
        by_author.items(),
        key=lambda author_items: sum(
            score for score, _row in sorted(author_items[1], reverse=True)[:5]
        ),
        reverse=True,
    )[:UTTERANCE_AUTHOR_COUNT]

    examples = []
    for _user_id, author_rows in ranked_authors:
        rows = sorted(author_rows, reverse=True)
        for score, row in rows[:UTTERANCES_PER_AUTHOR]:
            author = str(row[4])
            examples.append(
                SearchEvidence(
                    chat_id=chat_id,
                    start_message_id=row[1],
                    end_message_id=row[2],
                    citation_message_id=row[2],
                    text=(f"{row[2]} {row[5]} {display_author(author)}: {row[6]}"),
                    score=score,
                )
            )
    return examples


def fts_query(terms: list[str]) -> str:
    return " OR ".join(
        f'"{term.strip().replace(chr(34), chr(34) * 2)}"' for term in terms
    )


async def lexical_evidence(
    chat_id: int,
    terms: list[str],
    author_id: int | None,
) -> list[SearchEvidence]:
    terms = [term for term in dict.fromkeys(terms) if term.strip()]
    if not terms:
        return []
    async with (
        get_db() as connection,
        connection.execute(
            """
            SELECT
                messages.message_id,
                messages.create_time,
                COALESCE(users.username, 'user:' || messages.user_id) AS author,
                messages.message_text,
                bm25(chat_stats_fts) AS rank
            FROM chat_stats_fts
            JOIN chat_stats messages ON messages.id = chat_stats_fts.rowid
            LEFT JOIN user_stats users ON users.user_id = messages.user_id
            WHERE chat_stats_fts.message_text MATCH ?
            AND chat_stats_fts.chat_id = ?
            AND (? IS NULL OR messages.user_id = ?)
            AND messages.message_text IS NOT NULL
            AND messages.message_text <> ''
            AND messages.message_text NOT LIKE '/%'
            ORDER BY rank
            LIMIT ?
            """,
            (
                fts_query(terms),
                chat_id,
                author_id,
                author_id,
                LEXICAL_RESULT_COUNT,
            ),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return [
        SearchEvidence(
            chat_id=chat_id,
            start_message_id=row["message_id"],
            end_message_id=row["message_id"],
            citation_message_id=row["message_id"],
            text=(
                f"{row['message_id']} {row['create_time']} "
                f"@{row['author']}: {row['message_text']}"
                if not str(row["author"]).startswith("user:")
                else f"{row['message_id']} {row['create_time']} "
                f"{row['author']}: {row['message_text']}"
            ),
            score=1 / (1 + abs(row["rank"])),
        )
        for row in rows
    ]


async def interaction_pair_evidence(chat_id: int) -> list[SearchEvidence]:
    async with (
        get_db() as connection,
        connection.execute(
            """
            WITH pair_counts AS (
                SELECT
                    MIN(mentioning_user_id, mentioned_user_id) AS left_id,
                    MAX(mentioning_user_id, mentioned_user_id) AS right_id,
                    SUM(mentioning_user_id < mentioned_user_id) AS left_to_right,
                    SUM(mentioning_user_id > mentioned_user_id) AS right_to_left,
                    COUNT(*) AS total,
                    MAX(message_id) AS citation_message_id
                FROM chat_mentions
                WHERE chat_id = ?
                AND mentioning_user_id <> mentioned_user_id
                GROUP BY left_id, right_id
            )
            SELECT
                pair_counts.*,
                COALESCE(left_user.username, 'user:' || left_id) AS left_name,
                COALESCE(right_user.username, 'user:' || right_id) AS right_name
            FROM pair_counts
            LEFT JOIN user_stats left_user ON left_user.user_id = left_id
            LEFT JOIN user_stats right_user ON right_user.user_id = right_id
            WHERE COALESCE(left_user.username, '') <> 'SuperSeriousBot'
            AND COALESCE(right_user.username, '') <> 'SuperSeriousBot'
            ORDER BY
                (2.0 * left_to_right * right_to_left)
                    / NULLIF(left_to_right + right_to_left, 0) DESC
            LIMIT ?
            """,
            (chat_id, PAIR_RESULT_COUNT),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return [
        SearchEvidence(
            chat_id=chat_id,
            start_message_id=row["citation_message_id"],
            end_message_id=row["citation_message_id"],
            citation_message_id=row["citation_message_id"],
            text=(
                f"Recorded mutual interaction: @{row['left_name']} and "
                f"@{row['right_name']} — {row['total']:,} replies/mentions "
                f"({row['left_to_right']:,} one way, "
                f"{row['right_to_left']:,} the other)."
            ),
            score=(
                2
                * row["left_to_right"]
                * row["right_to_left"]
                / (row["left_to_right"] + row["right_to_left"])
            ),
        )
        for row in rows
    ]


def merge_evidence(items, limit: int = MAX_EVIDENCE) -> list[SearchEvidence]:
    merged = []
    for item in items:
        if any(
            item.chat_id == existing.chat_id
            and item.start_message_id == existing.start_message_id
            and item.end_message_id == existing.end_message_id
            for existing in merged
        ):
            continue
        merged.append(item)
        if len(merged) == limit:
            break
    return merged


async def route_question(search_model: ai.Model, question: str) -> Lane:
    output = await generate_search_object(
        search_model,
        [ai.system_message(ROUTER_PROMPT), ai.user_message(question)],
        RouteOutput,
        max_tokens=100,
        # Small reasoning models return empty structured output when their
        # default reasoning is on (observed 2026-08).
        reasoning_effort=None,
    )
    return output.lane


def lane_for_memory(routed_lane: Lane, persona_count: int) -> Lane:
    return routed_lane if persona_count else "fact"


async def load_persona_sheets(chat_id: int) -> list[PersonaSheet]:
    async with (
        get_db() as connection,
        connection.execute(
            """
            SELECT personas.user_id, personas.sheet, personas.receipts,
                users.username, users.first_name
            FROM chat_personas personas
            LEFT JOIN user_stats users ON users.user_id = personas.user_id
            WHERE personas.chat_id = ?
            ORDER BY personas.user_id
            """,
            (chat_id,),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return [
        PersonaSheet(
            row["user_id"],
            f"@{row['username']}" if row["username"] else f"user:{row['user_id']}",
            row["first_name"]
            or (f"@{row['username']}" if row["username"] else f"user:{row['user_id']}"),
            row["sheet"],
            tuple(json.loads(row["receipts"])),
        )
        for row in rows
    ]


async def load_lore(chat_id: int) -> list[LoreRow]:
    async with (
        get_db() as connection,
        connection.execute(
            "SELECT topic, summary, receipts FROM chat_lore WHERE chat_id = ?",
            (chat_id,),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return [
        LoreRow(
            row["topic"],
            row["summary"],
            tuple(json.loads(row["receipts"])),
        )
        for row in rows
    ]


def lexical_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\w]+", value.casefold())
        if len(token) > 1 and token not in SEARCH_STOP_WORDS
    }


def rank_lore(question: str, lore: list[LoreRow]) -> list[LoreRow]:
    question_tokens = lexical_tokens(question)
    scored = [
        (
            len(question_tokens & lexical_tokens(f"{item.topic} {item.summary}")),
            item,
        )
        for item in lore
    ]
    return [
        item
        for score, item in sorted(scored, key=lambda pair: (-pair[0], pair[1].topic))
        if score
    ][:8]


def utterance_message_ids(evidence: SearchEvidence) -> set[int]:
    return {
        evidence.citation_message_id,
        *(int(value) for value in re.findall(r"(?m)(?:^|:\s)(-?\d+)\s", evidence.text)),
    }


def memory_context(
    question: str,
    sheets: list[PersonaSheet],
    focus_ids: set[int],
    participants: list[Participant],
    lore: list[LoreRow],
    utterances: list[SearchEvidence],
) -> tuple[str, set[int]]:
    allowed_ids: set[int] = set()
    sections = [
        f"Question: {question}",
        "Resolved participants: "
        + (", ".join(item.handle for item in participants) or "(none)"),
    ]
    context_chars = sum(map(len, sections)) + 2 * (len(sections) - 1)

    def add_section(section: str, receipt_ids: tuple[int, ...] | set[int]) -> bool:
        nonlocal context_chars
        added_chars = len(section) + 2
        if context_chars + added_chars > MEMORY_PROMPT_CHAR_LIMIT:
            return False
        sections.append(section)
        context_chars += added_chars
        allowed_ids.update(receipt_ids)
        return True

    sheet_chars = 0
    ordered_sheets = sorted(
        sheets,
        key=lambda item: (item.user_id not in focus_ids, item.user_id),
    )
    for sheet in ordered_sheets:
        focus = " | FOCUS" if sheet.user_id in focus_ids else ""
        body = (
            sheet.sheet
            if sheet.user_id in focus_ids
            else sheet.sheet[:NON_FOCUS_SHEET_CHAR_LIMIT]
        )
        section = (
            f"[Persona: {sheet.handle} | {sheet.display}{focus}]\n"
            f"Receipt IDs: {', '.join(map(str, sheet.receipts)) or '(none)'}\n{body}"
        )
        if sheet_chars + len(section) > MEMORY_PROMPT_CHAR_LIMIT - 20_000:
            break
        if not add_section(section, sheet.receipts):
            break
        sheet_chars += len(section)

    for item in lore:
        section = (
            f"[Lore: {item.topic}]\nReceipt IDs: "
            f"{', '.join(map(str, item.receipts)) or '(none)'}\n{item.summary}"
        )
        if not add_section(section, item.receipts):
            break

    for evidence in utterances:
        if not add_section(
            f"[Receipt]\n{evidence.text}",
            utterance_message_ids(evidence),
        ):
            break

    return "\n\n".join(sections), allowed_ids


def valid_quotes(quotes: list[Quote], allowed_ids: set[int]) -> list[Quote]:
    valid = []
    seen: set[int] = set()
    for quote in quotes:
        if quote.message_id not in allowed_ids or quote.message_id in seen:
            continue
        valid.append(quote)
        seen.add(quote.message_id)
        if len(valid) == 4:
            break
    return valid


def render_memory_answer(
    answer: str,
    quotes: list[Quote],
    handles: dict[int, str],
    chat_id: int,
) -> str:
    rendered_quotes = []
    for quote in quotes:
        link = telegram_message_link(chat_id, quote.message_id)
        linked_receipt = f" [link]({link})" if link else ""
        rendered_quotes.append(
            f"“{quote.text}” — {handles[quote.message_id]}{linked_receipt}"
        )
    return "\n\n".join((answer.strip(), *rendered_quotes))


async def quote_handles(chat_id: int, quotes: list[Quote]) -> dict[int, str]:
    message_ids = [quote.message_id for quote in quotes]
    if not message_ids:
        return {}
    placeholders = ", ".join("?" for _ in message_ids)
    async with (
        get_db() as connection,
        connection.execute(
            f"""
            SELECT messages.message_id, messages.user_id, users.username
            FROM chat_stats messages
            LEFT JOIN user_stats users ON users.user_id = messages.user_id
            WHERE messages.chat_id = ? AND messages.message_id IN ({placeholders})
            """,
            (chat_id, *message_ids),
        ) as cursor,
    ):
        rows = await cursor.fetchall()
    return {
        row["message_id"]: (
            f"@{row['username']}" if row["username"] else f"user:{row['user_id']}"
        )
        for row in rows
    }


async def memory_answer(
    search_model: ai.Model,
    chat_id: int,
    question: str,
    author_id: int | None,
    participants: list[Participant],
    sheets: list[PersonaSheet],
    lane: Literal["persona", "creative"],
) -> SearchResult | None:
    lore, utterances, pairs = await asyncio.gather(
        load_lore(chat_id),
        utterance_evidence(chat_id, [question], author_id),
        interaction_pair_evidence(chat_id)
        if PAIR_PATTERN.search(question)
        else _empty_evidence(),
    )
    focus_ids = {item.user_id for item in participants}
    if author_id is not None:
        focus_ids.add(author_id)
    context, allowed_ids = memory_context(
        question,
        sheets,
        focus_ids,
        participants,
        rank_lore(question, lore),
        [*pairs[:8], *utterances[:10]],
    )
    if lane == "persona" and not allowed_ids:
        return None

    output = await generate_search_object(
        search_model,
        [
            ai.system_message(
                PERSONA_ANSWER_PROMPT if lane == "persona" else CREATIVE_ANSWER_PROMPT
            ),
            ai.user_message(context),
        ],
        MemoryAnswerOutput,
        max_tokens=1200,
    )
    quotes = valid_quotes(output.quotes, allowed_ids)
    handles = await quote_handles(chat_id, quotes)
    quotes = [quote for quote in quotes if quote.message_id in handles]
    return SearchResult(
        render_memory_answer(output.answer, quotes, handles, chat_id),
        search_model.id,
        [quote.message_id for quote in quotes],
        lane,
    )


def evidence_prompt(question: str, evidence: list[SearchEvidence]) -> str:
    formatted = "\n\n".join(
        f"[Evidence {index}]\n{without_raw_message_ids(item.text)}"
        for index, item in enumerate(evidence, 1)
    )
    return f"Question: {question}\n\nEvidence:\n{formatted}"


def without_raw_message_ids(text: str) -> str:
    lines = []
    for line in text.splitlines():
        first, separator, rest = line.partition(" ")
        lines.append(rest if separator and first.isdigit() else line)
    return "\n".join(lines)


def render_answer(
    output: SearchAnswerOutput,
    evidence: list[SearchEvidence],
) -> str:
    if any(not 1 <= citation <= len(evidence) for citation in output.citations):
        return NO_SOLID_ANSWER
    return render_search_answer(output, evidence)


async def search_answer(
    chat_id: int,
    question: str,
    author_id: int | None = None,
    on_status: Callable[[str], Awaitable[None]] | None = None,
) -> SearchResult:
    status = on_status or _ignore_status
    await status("Working out who you mean")
    search_model, participants = await asyncio.gather(
        model("search"),
        resolve_participants(chat_id, question),
    )
    await status("Picking an approach")
    routed_lane, sheets = await asyncio.gather(
        route_question(search_model, question),
        load_persona_sheets(chat_id),
    )
    lane = lane_for_memory(routed_lane, len(sheets))
    if lane in ("persona", "creative"):
        await status("Reading the dossiers")
        result = await memory_answer(
            search_model,
            chat_id,
            question,
            author_id,
            participants,
            sheets,
            lane,
        )
        if result is not None:
            return result

    await status("Planning searches")
    identity_result = await identity_evidence(chat_id, identity_terms(question))
    plan = await plan_search(search_model, question, identity_result)
    await status("Searching messages")

    (
        semantic_result,
        utterance_result,
        lexical_result,
        pair_result,
    ) = await asyncio.gather(
        semantic_evidence(chat_id, plan.semantic_queries, author_id),
        utterance_evidence(chat_id, plan.semantic_queries, author_id),
        lexical_evidence(chat_id, plan.lexical_terms, author_id),
        interaction_pair_evidence(chat_id)
        if plan.include_interaction_pairs
        else _empty_evidence(),
    )
    evidence = merge_evidence(
        (
            *pair_result[:8],
            *identity_result[:4],
            *utterance_result[:16],
            *semantic_result[:6],
            *lexical_result[:2],
        )
    )
    if not evidence:
        return SearchResult(NO_SOLID_ANSWER, search_model.id, [], "fact")

    await status("Reading the strongest evidence")
    output = await generate_search_object(
        search_model,
        [
            ai.system_message(ANSWER_PROMPT),
            ai.user_message(evidence_prompt(question, evidence)),
        ],
        SearchAnswerOutput,
        max_tokens=500,
    )
    answer = render_answer(output, evidence)
    citation_message_ids = (
        list(
            dict.fromkeys(
                evidence[citation - 1].citation_message_id
                for citation in output.citations
            )
        )
        if answer != NO_SOLID_ANSWER
        else []
    )
    return SearchResult(answer, search_model.id, citation_message_ids, "fact")


async def _ignore_status(_status: str) -> None:
    return None


async def _empty_evidence() -> list[SearchEvidence]:
    return []
