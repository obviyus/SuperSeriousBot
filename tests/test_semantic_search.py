from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

semantic_search = importlib.import_module("management.chat_semantic_search")
chat_aliases = importlib.import_module("management.chat_aliases")
chat_search = importlib.import_module("management.chat_search")
search_cache = importlib.import_module("management.chat_search_cache")
search_index = importlib.import_module("management.chat_search_index")
openrouter_embeddings = importlib.import_module("openrouter_embeddings")
commands_ai = importlib.import_module("commands.ai")
db = importlib.import_module("config.db")
libsql = importlib.import_module("libsql")
migrate = importlib.import_module("migrate")


class SemanticSearchTests(unittest.TestCase):
    def test_utterance_migration_matches_the_index_record(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = libsql.connect(
                f"{directory}/migration.db",
                autocommit=True,
                _check_same_thread=False,
            )
            connection.execute(
                "CREATE TABLE group_settings "
                "(chat_id INTEGER PRIMARY KEY, search_model TEXT)"
            )
            migration = migrate.load_migration(
                Path("migrations/20260808000000_chat_search_utterances.py")
            )
            migration.upgrade(connection)
            columns = {
                row[1]: row[2]
                for row in connection.execute(
                    "PRAGMA table_info(chat_search_utterances)"
                ).fetchall()
            }
            connection.close()

        self.assertEqual(columns["message_count"], "INTEGER")
        self.assertEqual(columns["embedding"], "F32_BLOB(256)")

    def test_telegram_message_link_uses_private_supergroup_link(self):
        self.assertEqual(
            semantic_search.telegram_message_link(-1001234567890, 42),
            "https://t.me/c/1234567890/42",
        )

    def test_build_windows_uses_overlapping_chat_windows(self):
        messages = [
            search_index.SourceMessage(
                i, f"2026-06-07 00:00:{i:02d}", f"@u{i}", f"m{i}"
            )
            for i in range(1, 30)
        ]

        windows = search_index.build_windows(-1001, messages, set())

        self.assertEqual(windows[0].start_message_id, 1)
        self.assertEqual(windows[0].end_message_id, 24)
        self.assertIn("1 2026-06-07 00:00:01 @u1: m1", windows[0].text)
        self.assertEqual(windows[1].start_message_id, 9)
        self.assertEqual(windows[1].end_message_id, 29)

    def test_build_windows_skips_indexed_ranges(self):
        messages = [
            search_index.SourceMessage(
                i, f"2026-06-07 00:00:{i:02d}", f"@u{i}", f"m{i}"
            )
            for i in range(1, 30)
        ]

        windows = search_index.build_windows(-1001, messages, {(1, 24)})

        self.assertEqual(windows[0].start_message_id, 9)

    def test_build_windows_replaces_a_growing_tail(self):
        messages = [
            search_index.SourceMessage(
                i, f"2026-06-07 00:00:{i:02d}", f"@u{i}", f"m{i}"
            )
            for i in range(9, 41)
        ]

        windows = search_index.build_windows(
            -1001,
            messages,
            {(9, 30), (17, 30), (25, 30)},
        )

        self.assertEqual(
            [(window.start_message_id, window.end_message_id) for window in windows],
            [(9, 32), (17, 40), (25, 40), (33, 40)],
        )

    def test_build_utterances_preserves_speaker_ownership(self):
        messages = [
            search_index.SourceMessage(1, "2026-08-08 10:00:00", "@alice", "first", 1),
            search_index.SourceMessage(2, "2026-08-08 10:01:00", "@alice", "second", 1),
            search_index.SourceMessage(3, "2026-08-08 10:02:00", "@bob", "reply", 2),
        ]

        utterances = search_index.build_utterances(-1001, messages, set())

        self.assertEqual(
            [
                (item.user_id, item.start_message_id, item.end_message_id, item.text)
                for item in utterances
            ],
            [
                (1, 1, 2, "1 first\n2 second"),
                (2, 3, 3, "3 reply"),
            ],
        )

    def test_build_utterances_caps_long_single_speaker_runs(self):
        messages = [
            search_index.SourceMessage(
                index,
                f"2026-08-08 10:00:{index:02d}",
                "@alice",
                f"m{index}",
                1,
            )
            for index in range(1, 14)
        ]

        utterances = search_index.build_utterances(-1001, messages, set())

        self.assertEqual(
            [(item.start_message_id, item.end_message_id) for item in utterances],
            [(1, 12), (13, 13)],
        )

    def test_select_evidence_removes_overlaps(self):
        evidence = semantic_search.SearchEvidence
        windows = [
            evidence(-1001, 1, 24, 24, "v1", 0.8),
            evidence(-1001, 9, 32, 32, "v2", 0.7),
            evidence(-1001, 100, 124, 124, "v3", 0.6),
            evidence(-1001, 200, 224, 224, "v4", 0.5),
        ]

        selected = semantic_search.select_evidence(windows)

        self.assertEqual([item.text for item in selected], ["v1", "v3", "v4"])

    def test_render_search_answer_owns_citation_links(self):
        evidence = [
            semantic_search.SearchEvidence(-1001234567890, 1, 24, 20, "first", 0.8),
            semantic_search.SearchEvidence(-1001234567890, 25, 48, 40, "second", 0.7),
        ]

        answer = semantic_search.render_search_answer(
            semantic_search.SearchAnswerOutput(
                answer="@user has the strongest receipts.",
                citations=[2, 2, 3, 1],
            ),
            evidence,
        )

        self.assertEqual(
            answer,
            "@user has the strongest receipts.\n\n"
            "[2](https://t.me/c/1234567890/40) "
            "[1](https://t.me/c/1234567890/20)",
        )

    def test_render_search_answer_rejects_uncited_claims(self):
        evidence = [
            semantic_search.SearchEvidence(-1001234567890, 1, 24, 20, "first", 0.8)
        ]

        answer = semantic_search.render_search_answer(
            semantic_search.SearchAnswerOutput(
                answer="@user definitely has the most hours.", citations=[]
            ),
            evidence,
        )

        self.assertEqual(answer, semantic_search.NO_SOLID_ANSWER)

    def test_render_search_answer_preserves_no_answer(self):
        answer = semantic_search.render_search_answer(
            semantic_search.SearchAnswerOutput(
                answer=semantic_search.NO_SOLID_ANSWER, citations=[1]
            ),
            [semantic_search.SearchEvidence(-1001234567890, 1, 24, 20, "first", 0.8)],
        )

        self.assertEqual(answer, semantic_search.NO_SOLID_ANSWER)


class ChatSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_question_routing_uses_search_model(self):
        search_model = chat_search.ai.Model(
            id="openai/gpt-5.6-luna",
            provider=commands_ai.openrouter_provider(),
        )
        with patch.object(
            chat_search,
            "generate_search_object",
            AsyncMock(return_value=chat_search.RouteOutput(lane="fact")),
        ) as generate:
            lane = await chat_search.route_question(search_model, "What does Nathu do?")

        self.assertEqual(lane, "fact")
        self.assertIs(generate.call_args.args[0], search_model)

    async def test_query_expansion_has_room_for_reasoning(self):
        expansion = chat_search.QueryExpansion(
            semantic_queries=["who likes being hit"],
        )
        with patch.object(
            chat_search,
            "generate_search_object",
            AsyncMock(return_value=expansion),
        ) as generate:
            await chat_search.plan_search(
                chat_search.ai.Model(
                    id="test",
                    provider=commands_ai.openrouter_provider(),
                ),
                "which person is most likely to be into being physically abused",
                [],
            )

        self.assertEqual(generate.call_args.kwargs["max_tokens"], 2000)

    def test_alias_matching_prefers_bigrams_and_preserves_question_order(self):
        boss = chat_aliases.Participant(1, "@boss", "Boss")
        big_boss = chat_aliases.Participant(2, "@bigboss", "Big Boss")
        nathu = chat_aliases.Participant(3, "@nathu", "Nathu")

        matched = chat_aliases.match_participants(
            "Is BIG boss tighter with Nathu or boss?",
            [
                chat_aliases.ParticipantAlias("boss", boss),
                chat_aliases.ParticipantAlias("big boss", big_boss),
                chat_aliases.ParticipantAlias("nathu", nathu),
            ],
        )

        self.assertEqual(matched, [big_boss, nathu, boss])

    def test_lore_ranking_uses_question_overlap(self):
        lore = [
            chat_search.LoreRow("chai-war", "Alice declared tea illegal", (1,)),
            chat_search.LoreRow("gym-arc", "Bob started lifting", (2,)),
            chat_search.LoreRow("chai-cup", "The ceremonial chai cup", (3,)),
        ]

        ranked = chat_search.rank_lore("Who started the chai war?", lore)

        self.assertEqual(
            [item.topic for item in ranked],
            ["chai-war", "chai-cup", "gym-arc"],
        )

    def test_quote_validation_and_rendering_drop_unknown_receipts(self):
        quotes = chat_search.valid_quotes(
            [
                chat_search.Quote(message_id=12, text="Chai is soup."),
                chat_search.Quote(message_id=99, text="Invented quote"),
                chat_search.Quote(message_id=12, text="Duplicate"),
            ],
            {12, 13},
        )

        rendered = chat_search.render_memory_answer(
            "@alice wins. Nobody else made tea this weird.",
            quotes,
            {12: "@alice"},
            -1001234567890,
        )

        self.assertEqual(
            rendered,
            "@alice wins. Nobody else made tea this weird.\n\n"
            "“Chai is soup.” — @alice [link](https://t.me/c/1234567890/12)",
        )

    def test_lane_falls_back_to_fact_without_persona_sheets(self):
        self.assertEqual(chat_search.lane_for_memory("persona", 0), "fact")
        self.assertEqual(chat_search.lane_for_memory("creative", 2), "creative")


class SearchCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_vector_search_reads_local_cache_and_scopes_chat(self):
        def vector(first: int) -> str:
            return f"[{first}," + ",".join(["0"] * 1023) + "]"

        columns = {
            name: index
            for index, name in enumerate(
                (
                    "id",
                    "chat_id",
                    "start_message_id",
                    "end_message_id",
                    "embedding",
                    "embedding_model",
                    "embedding_dimension",
                )
            )
        }
        rows = [
            search_cache.TursoRow(
                (1, -1001, 1, 24, vector(1), "model", 1024),
                columns,
            ),
            search_cache.TursoRow(
                (2, -1001, 25, 48, vector(-1), "model", 1024),
                columns,
            ),
            search_cache.TursoRow(
                (3, -1002, 1, 24, vector(1), "model", 1024),
                columns,
            ),
        ]

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"SEARCH_CACHE_PATH": f"{directory}/search.db"},
            ),
        ):
            search_cache.initialize_search_cache_file()
            search_cache.store_search_cache_rows(rows)
            with (
                patch.object(semantic_search, "EMBEDDING_MODEL", "model"),
                patch.object(semantic_search, "get_db", side_effect=AssertionError),
            ):
                candidates = await semantic_search.vector_search_candidates(
                    -1001,
                    vector(1),
                    12,
                )

        self.assertEqual([item.remote_id for item in candidates], [1, 2])

    async def test_evidence_fetch_preserves_author_filter(self):
        class ConnectionContext:
            def __init__(self, connection):
                self.connection = connection

            async def __aenter__(self):
                return self.connection

            async def __aexit__(self, *_args):
                return None

        with tempfile.TemporaryDirectory() as directory:
            connection = libsql.connect(
                f"{directory}/remote.db",
                autocommit=True,
                _check_same_thread=False,
            )
            connection.execute(
                """
                CREATE TABLE chat_search_windows (
                    id INTEGER PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    start_message_id INTEGER NOT NULL,
                    end_message_id INTEGER NOT NULL,
                    message_text TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE chat_stats (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    create_time TEXT NOT NULL,
                    message_text TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE user_stats (
                    user_id INTEGER NOT NULL,
                    username TEXT
                )
                """
            )
            connection.executemany(
                "INSERT INTO chat_search_windows VALUES (?, -1001, ?, ?, ?)",
                [(1, 1, 24, "first"), (2, 25, 48, "second")],
            )
            connection.executemany(
                "INSERT INTO chat_stats VALUES (-1001, ?, ?, ?, ?)",
                [
                    (7, 10, "2026-07-26 10:00:00", "target message"),
                    (8, 11, "2026-07-26 10:01:00", "other message"),
                    (7, 12, "2026-07-26 10:02:00", "/command"),
                    (8, 30, "2026-07-26 10:03:00", "second window"),
                ],
            )
            connection.executemany(
                "INSERT INTO user_stats VALUES (?, ?)",
                [(7, "alice"), (8, "bob")],
            )
            wrapped = db.TursoConnection(connection)
            candidates = [
                semantic_search.SearchCandidate(1, 0.9),
                semantic_search.SearchCandidate(2, 0.8),
            ]
            try:
                with patch.object(
                    semantic_search,
                    "get_db",
                    return_value=ConnectionContext(wrapped),
                ):
                    evidence = await semantic_search.fetch_search_evidence(
                        candidates,
                        author_id=7,
                    )
            finally:
                await wrapped.close()

        self.assertEqual(
            [(item.text, item.citation_message_id, item.score) for item in evidence],
            [("10 2026-07-26 10:00:00 @alice: target message", 10, 0.9)],
        )

    def test_new_tail_window_replaces_stale_cached_range(self):
        vector = "[1," + ",".join(["0"] * 1023) + "]"
        columns = {
            name: index
            for index, name in enumerate(
                (
                    "id",
                    "chat_id",
                    "start_message_id",
                    "end_message_id",
                    "embedding",
                    "embedding_model",
                    "embedding_dimension",
                )
            )
        }
        rows = [
            search_cache.TursoRow(
                (1, -1001, 1, 10, vector, "model", 1024),
                columns,
            ),
            search_cache.TursoRow(
                (2, -1001, 1, 20, vector, "model", 1024),
                columns,
            ),
        ]

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"SEARCH_CACHE_PATH": f"{directory}/search.db"},
            ),
        ):
            search_cache.initialize_search_cache_file()
            search_cache.store_search_cache_rows(rows)
            connection = search_cache.open_search_cache()
            try:
                cached = connection.execute(
                    "SELECT end_message_id, remote_id FROM search_windows"
                ).fetchall()
            finally:
                connection.close()

            self.assertEqual(cached, [(20, 2)])

    def test_new_tail_utterance_replaces_stale_cached_text(self):
        vector = "[1," + ",".join(["0"] * 255) + "]"
        columns = {
            name: index
            for index, name in enumerate(
                (
                    "id",
                    "chat_id",
                    "start_message_id",
                    "end_message_id",
                    "user_id",
                    "author",
                    "start_time",
                    "end_time",
                    "message_text",
                    "embedding",
                    "embedding_model",
                    "embedding_dimension",
                )
            )
        }
        rows = [
            search_cache.TursoRow(
                (
                    1,
                    -1001,
                    1,
                    1,
                    7,
                    "@alice",
                    "2026-08-08 10:00:00",
                    "2026-08-08 10:00:00",
                    "1 first",
                    vector,
                    "model",
                    256,
                ),
                columns,
            ),
            search_cache.TursoRow(
                (
                    2,
                    -1001,
                    1,
                    2,
                    7,
                    "@alice",
                    "2026-08-08 10:00:00",
                    "2026-08-08 10:01:00",
                    "1 first\n2 second",
                    vector,
                    "model",
                    256,
                ),
                columns,
            ),
        ]

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(
                os.environ,
                {"SEARCH_CACHE_PATH": f"{directory}/search.db"},
            ),
        ):
            search_cache.initialize_search_cache_file()
            search_cache.store_search_utterance_cache_rows(rows)
            connection = search_cache.open_search_cache()
            try:
                cached = connection.execute(
                    "SELECT remote_id, end_message_id, message_text "
                    "FROM search_utterances"
                ).fetchall()
            finally:
                connection.close()

        self.assertEqual(cached, [(2, 2, "1 first\n2 second")])


class OpenRouterEmbeddingTests(unittest.IsolatedAsyncioTestCase):
    async def test_embeddings_prefer_low_latency_provider(self):
        response = SimpleNamespace(
            data=[SimpleNamespace(embedding=[1.0, 0.0])],
        )
        create = AsyncMock(return_value=response)
        provider = SimpleNamespace(
            sdk_client=SimpleNamespace(
                embeddings=SimpleNamespace(create=create),
            )
        )

        with patch(
            "commands.ai.openrouter_provider",
            return_value=provider,
        ):
            embeddings = await openrouter_embeddings.openrouter_embeddings(
                "model",
                ["query"],
                dimensions=2,
            )

        self.assertEqual(embeddings, [[1.0, 0.0]])
        self.assertEqual(
            create.await_args.kwargs["extra_body"],
            {"provider": {"sort": "latency"}},
        )


class SearchIndexTests(unittest.IsolatedAsyncioTestCase):
    async def test_store_windows_cleans_each_growing_tail(self):
        connection = SimpleNamespace(executemany=AsyncMock())
        context = AsyncMock()
        context.__aenter__.return_value = connection
        windows = [
            search_index.SearchWindow(
                -1001,
                start,
                end,
                "2026-08-09 10:00:00",
                "2026-08-09 10:01:00",
                end - start + 1,
                "messages",
            )
            for start, end in ((1, 24), (9, 32))
        ]

        with patch.object(search_index, "get_db", return_value=context):
            await search_index.store_windows(windows, [[1.0], [2.0]])

        cleanup_params = connection.executemany.await_args_list[1].args[1]
        self.assertEqual(
            cleanup_params,
            [
                (
                    -1001,
                    1,
                    search_index.EMBEDDING_MODEL,
                    search_index.EMBEDDING_DIMENSIONS,
                    24,
                ),
                (
                    -1001,
                    9,
                    search_index.EMBEDDING_MODEL,
                    search_index.EMBEDDING_DIMENSIONS,
                    32,
                ),
            ],
        )

    async def test_pending_indexing_allocates_each_chat_a_share(self):
        index_chat_windows = AsyncMock(side_effect=lambda _chat_id, limit: limit)
        with (
            patch.object(
                search_index,
                "index_chat_windows",
                index_chat_windows,
            ),
            patch.object(search_index, "sync_search_cache", AsyncMock()),
        ):
            indexed = await search_index.index_pending_windows(
                chat_ids=[-1002, -1001],
                window_limit=6,
            )

        self.assertEqual(indexed, 6)
        self.assertEqual(
            [
                (call.args[0], call.args[1])
                for call in index_chat_windows.await_args_list
            ],
            [(-1002, 3), (-1001, 3)],
        )

    async def test_pending_utterances_allocates_each_chat_a_share(self):
        index_chat_utterances = AsyncMock(side_effect=lambda _chat_id, limit: limit)
        with (
            patch.object(
                search_index,
                "index_chat_utterances",
                index_chat_utterances,
            ),
            patch.object(search_index, "sync_search_cache", AsyncMock()),
        ):
            indexed = await search_index.index_pending_utterances(
                chat_ids=[-1002, -1001],
                utterance_limit=6,
            )

        self.assertEqual(indexed, 6)
        self.assertEqual(
            [
                (call.args[0], call.args[1])
                for call in index_chat_utterances.await_args_list
            ],
            [(-1002, 3), (-1001, 3)],
        )

    async def test_refresh_advances_without_clearing_existing_windows(self):
        index_window_batch = AsyncMock(side_effect=[(64, 100), (2, 200)])
        with (
            patch.object(
                search_index,
                "index_window_batch",
                index_window_batch,
            ),
            patch.object(search_index, "reset_search_cache"),
            patch.object(search_index, "sync_search_cache", AsyncMock()),
        ):
            refreshed = await search_index.refresh_windows([-1001])

        self.assertEqual(refreshed, 66)
        self.assertEqual(
            [call.args[1] for call in index_window_batch.await_args_list],
            [search_index.MIN_MESSAGE_ID, 100],
        )


if __name__ == "__main__":
    unittest.main()
