import asyncio
import re
from collections.abc import Awaitable, Callable

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
from management.chat_search_cache import open_search_cache
from management.chat_semantic_search import (
    NO_SOLID_ANSWER,
    SearchAnswerOutput,
    SearchEvidence,
    fetch_search_evidence,
    render_search_answer,
    select_evidence,
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


class SearchPlan(pydantic.BaseModel):
    semantic_queries: list[str] = pydantic.Field(min_length=1, max_length=4)
    lexical_terms: list[str] = pydantic.Field(default_factory=list, max_length=10)
    resolved_handles: list[str] = pydantic.Field(default_factory=list, max_length=3)
    include_interaction_pairs: bool = False


class QueryExpansion(pydantic.BaseModel):
    semantic_queries: list[str] = pydantic.Field(min_length=1, max_length=3)
    lexical_terms: list[str] = pydantic.Field(default_factory=list, max_length=10)
    resolved_handles: list[str] = pydantic.Field(default_factory=list, max_length=3)


class CandidateAssessment(pydantic.BaseModel):
    subject: str
    quote: str = pydantic.Field(description="Exact quote without the message ID.")
    message_id: int = pydantic.Field(
        description="Numeric message ID at the start of the quoted line."
    )
    reason: str
    citations: list[int] = pydantic.Field(
        min_length=1,
        description="Bracketed Evidence numbers, never message IDs.",
    )
    strength: int = pydantic.Field(ge=1, le=3)


class ComparativeAssessment(pydantic.BaseModel):
    candidates: list[CandidateAssessment]


class EvidenceDecision(pydantic.BaseModel):
    evidence: int
    valid: bool
    reason: str


class EvidenceVerification(pydantic.BaseModel):
    decisions: list[EvidenceDecision]


class ComparativeAnswerOutput(pydantic.BaseModel):
    verdict: str = pydantic.Field(
        description="Direct participant verdict, or the requested ranked list."
    )
    explanation: str = pydantic.Field(
        description="One or two sentences explaining the evidence behind the verdict."
    )
    citations: list[int]


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
COMPARATIVE_PATTERN = re.compile(
    r"\b(most|biggest|top\s+\d+|best|fattest|baldest|horniest)\b",
    re.IGNORECASE,
)


def display_author(author: object) -> str:
    value = str(author)
    return value if value.startswith(("@", "user:")) else f"@{value}"


def message_author(evidence: SearchEvidence, message_id: int) -> str | None:
    prefix = f"{message_id} "
    line = next(
        (line for line in evidence.text.splitlines() if line.startswith(prefix)),
        None,
    )
    if line is None:
        return None
    match = re.search(r"(?:^|\s)(@[^\s:]+|user:\d+):", line)
    return match.group(1) if match else None


def claim_owns_subject(
    candidate: CandidateAssessment,
    evidence: SearchEvidence,
) -> bool:
    subject = candidate.subject.casefold().lstrip("@").strip()
    quote = candidate.quote.casefold()
    if re.search(r"\b(i|i'm|i've|i'd|me|my|mine)\b", quote):
        author = message_author(evidence, candidate.message_id)
        return author is not None and author.casefold().lstrip("@") == subject
    return subject in quote


async def generate_search_object[OutputT: pydantic.BaseModel](
    search_model: ai.Model,
    messages: list[ai.messages.Message],
    output_type: type[OutputT],
    *,
    max_tokens: int,
) -> OutputT:
    params = ai.InferenceRequestParams(
        output=ai.OutputParams(max_tokens=max_tokens)
    ).with_temperature(0)
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
    expansion = await generate_search_object(
        search_model,
        [
            ai.system_message(
                "Expand a Telegram chat-memory question for retrieval. Return up to "
                "three short semantic paraphrases using concrete observable language, "
                "plus exact names, handles, phrases, slang variants, and synonyms for "
                "lexical matching. Preserve the original predicate: someone doing, "
                "liking, or being something must not become merely discussing or "
                "mentioning it. Use any supplied identity clues to replace a person's "
                "real name or nickname with their @handle in semantic queries. Do not "
                "answer the question."
            ),
            ai.user_message(evidence_prompt(question, identity_clues)),
        ],
        QueryExpansion,
        max_tokens=2000,
    )
    return SearchPlan(
        semantic_queries=list(
            dict.fromkeys((question, *expansion.semantic_queries))
        )[:4],
        lexical_terms=list(
            dict.fromkeys((*direct_terms, *expansion.lexical_terms))
        )[:MAX_LEXICAL_TERMS],
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
                f'{row["message_id"]} {row["create_time"]} '
                f'{display_author(row["author"])}: {row["message_text"]}'
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
        *(fetch_search_evidence(candidates, author_id) for candidates in candidate_lists)
    )
    return merge_evidence(
        item
        for results in result_lists
        for item in select_evidence(results)
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
            score
            for score, _row in sorted(author_items[1], reverse=True)[:5]
        ),
        reverse=True,
    )[:UTTERANCE_AUTHOR_COUNT]

    aggregates = []
    examples = []
    for _user_id, author_rows in ranked_authors:
        rows = sorted(author_rows, reverse=True)
        score, row = rows[0]
        author = str(row[4])
        aggregates.append(
            SearchEvidence(
                chat_id=chat_id,
                start_message_id=row[1],
                end_message_id=row[2],
                citation_message_id=row[2],
                text=(
                    f"{row[2]} Semantic retrieval count: "
                    f"{display_author(author)} has "
                    f"{len(rows)} distinct utterances among the strongest matches."
                ),
                score=score,
            )
        )
        for score, row in rows[:UTTERANCES_PER_AUTHOR]:
            author = str(row[4])
            examples.append(
                SearchEvidence(
                    chat_id=chat_id,
                    start_message_id=row[1],
                    end_message_id=row[2],
                    citation_message_id=row[2],
                    text=(
                        f"{row[2]} {row[5]} "
                        f"{display_author(author)}: "
                        f"{row[6]}"
                    ),
                    score=score,
                )
            )
    return [*aggregates, *examples]


def fts_query(terms: list[str]) -> str:
    return " OR ".join(f'"{term.strip().replace(chr(34), chr(34) * 2)}"' for term in terms)


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
                f'{row["message_id"]} {row["create_time"]} '
                f'@{row["author"]}: {row["message_text"]}'
                if not str(row["author"]).startswith("user:")
                else f'{row["message_id"]} {row["create_time"]} '
                f'{row["author"]}: {row["message_text"]}'
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
                f'Recorded mutual interaction: @{row["left_name"]} and '
                f'@{row["right_name"]} — {row["total"]:,} replies/mentions '
                f'({row["left_to_right"]:,} one way, '
                f'{row["right_to_left"]:,} the other).'
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


async def attributed_evidence(
    search_model: ai.Model,
    question: str,
    evidence: list[SearchEvidence],
) -> list[SearchEvidence]:
    assessment = await generate_search_object(
        search_model,
        [
            ai.system_message(
                "Attribute retrieved evidence to the people it is actually about. "
                "Extract only claims that directly help answer the question. "
                "First-person statements apply to the speaker. Third-person "
                "statements apply to the named subject. A question, a generic "
                "observation, a term match about someone else, or merely discussing "
                "the topic is not evidence. 'I think', 'I am pretty sure', and similar "
                "opinion markers do not make the discussed behavior apply to the "
                "speaker. Include an exact supporting quote and the numeric message ID "
                "at the start of its line. For comparisons, consolidate each candidate "
                "without choosing a winner. Return at most 8 relevant subjects or "
                "claims, strongest first."
            ),
            ai.user_message(raw_evidence_prompt(question, evidence)),
        ],
        ComparativeAssessment,
        max_tokens=1200,
    )

    attributed = []
    for candidate in assessment.candidates[:8]:
        citations = [
            citation
            for citation in candidate.citations
            if 1 <= citation <= len(evidence)
        ]
        if not citations:
            continue
        source = next(
            (
                evidence[citation - 1]
                for citation in citations
                if evidence[citation - 1].start_message_id
                <= candidate.message_id
                <= evidence[citation - 1].end_message_id
            ),
            None,
        )
        if source is None:
            continue
        if not claim_owns_subject(candidate, source):
            continue
        attributed.append(
            SearchEvidence(
                chat_id=source.chat_id,
                start_message_id=source.start_message_id,
                end_message_id=source.end_message_id,
                citation_message_id=candidate.message_id,
                text=(
                    f"Subject: {candidate.subject}\n"
                    f'Exact quote: "{candidate.quote}"\n'
                    f"Proposed reason: {candidate.reason}"
                ),
                score=float(candidate.strength),
            )
        )
    return attributed


async def verified_evidence(
    search_model: ai.Model,
    question: str,
    evidence: list[SearchEvidence],
) -> list[SearchEvidence]:
    verification = await generate_search_object(
        search_model,
        [
            ai.system_message(
                "Audit every attributed claim against the exact question and quote. "
                "Judge only the characters inside Exact quote; ignore Proposed reason "
                "and do not fill gaps from the question. A claim is valid only when "
                "the quote directly supports that the named "
                "subject has the asked property or personally performs the asked "
                "behavior. First-person behavior supports the speaker. Second-person "
                "behavior is invalid unless the quote names or @mentions its target. "
                "Reject questions, generic observations, opinions about generic "
                "frequencies, topic discussion, and unsupported inference. Return one "
                "decision for every numbered claim. For a 'why is PERSON the "
                "CHARACTER' analogy, a quote may be valid when it explicitly names the "
                "person and grounds a concrete analogous trait; never transfer a trait "
                "from another person."
            ),
            ai.user_message(evidence_prompt(question, evidence)),
        ],
        EvidenceVerification,
        max_tokens=700,
    )
    valid = {
        decision.evidence
        for decision in verification.decisions
        if decision.valid and 1 <= decision.evidence <= len(evidence)
    }
    return [item for index, item in enumerate(evidence, 1) if index in valid]


def top_author_evidence(evidence: list[SearchEvidence]) -> list[SearchEvidence]:
    if not evidence:
        return []
    top = evidence[0]
    match = re.search(r"(@[^ ]+|user:\d+) has ", top.text)
    if match is None:
        return [top]
    author = match.group(1)
    examples = [
        item
        for item in evidence[1:]
        if f"{author}:" in item.text
    ][:UTTERANCES_PER_AUTHOR]
    return [top, *examples]


async def persona_evidence(
    search_model: ai.Model,
    chat_id: int,
    handle: str,
    author_id: int | None,
) -> list[SearchEvidence]:
    question = f"What is {handle}'s role, personality, and behavior in this group?"
    queries = [
        question,
        f"{handle} notable chat persona and habits",
        f"what group members say about {handle}",
    ]
    semantic_result, utterance_result = await asyncio.gather(
        semantic_evidence(chat_id, queries, author_id),
        utterance_evidence(chat_id, queries, author_id),
    )
    evidence = merge_evidence((*utterance_result[:16], *semantic_result[:8]))
    attributed = await attributed_evidence(search_model, question, evidence)
    if not attributed:
        return []
    return await verified_evidence(search_model, question, attributed)


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


def evidence_prompt(question: str, evidence: list[SearchEvidence]) -> str:
    formatted = "\n\n".join(
        f"[Evidence {index}]\n{without_raw_message_ids(item.text)}"
        for index, item in enumerate(evidence, 1)
    )
    return f"Question: {question}\n\nEvidence:\n{formatted}"


def raw_evidence_prompt(question: str, evidence: list[SearchEvidence]) -> str:
    formatted = "\n\n".join(
        f"[Evidence {index}]\n{item.text}"
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
) -> str:
    status = on_status or _ignore_status
    await status("Planning searches")
    search_model, identity_result = await asyncio.gather(
        model("search"),
        identity_evidence(chat_id, identity_terms(question)),
    )
    plan = await plan_search(search_model, question, identity_result)
    await status("Searching messages")

    semantic_result, utterance_result, lexical_result, pair_result = await asyncio.gather(
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
    attributed = []
    playful_inference = False
    if not plan.include_interaction_pairs:
        attributed = await attributed_evidence(search_model, question, evidence)
        if attributed:
            attributed = await verified_evidence(
                search_model,
                question,
                attributed,
            )
        evidence = attributed
    if not evidence and COMPARATIVE_PATTERN.search(question):
        evidence = top_author_evidence(utterance_result)
        attributed = evidence
    elif (
        not evidence
        and question.casefold().startswith("why")
        and plan.resolved_handles
    ):
        await status("Trying a broader angle")
        evidence = await persona_evidence(
            search_model,
            chat_id,
            plan.resolved_handles[0],
            author_id,
        )
        playful_inference = bool(evidence)
    if not evidence:
        return NO_SOLID_ANSWER

    await status("Reading the strongest evidence")
    if attributed and COMPARATIVE_PATTERN.search(question):
        comparative_output = await generate_search_object(
            search_model,
            [
                ai.system_message(
                    ANSWER_PROMPT
                    + "\nReturn the direct verdict separately from its explanation. "
                    "The verdict must answer the comparison even when it is subjective."
                ),
                ai.user_message(evidence_prompt(question, evidence)),
            ],
            ComparativeAnswerOutput,
            max_tokens=500,
        )
        output = SearchAnswerOutput(
            answer=(
                f"{comparative_output.verdict} — "
                f"{comparative_output.explanation}"
            ),
            citations=comparative_output.citations,
        )
    else:
        output = await generate_search_object(
            search_model,
            [
                ai.system_message(
                    ANSWER_PROMPT
                    + (
                        "\nNo direct explanation of the nickname was found. Make a "
                        "playful analogy from the participant's grounded persona, and "
                        "state it as an inference rather than a recorded fact."
                        if playful_inference
                        else ""
                    )
                ),
                ai.user_message(evidence_prompt(question, evidence)),
            ],
            SearchAnswerOutput,
            max_tokens=500,
        )
    return render_answer(output, evidence)


async def _ignore_status(_status: str) -> None:
    return None


async def _empty_evidence() -> list[SearchEvidence]:
    return []
