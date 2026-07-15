from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

semantic_search = importlib.import_module("management.chat_semantic_search")
search_cache = importlib.import_module("management.chat_search_cache")
search_index = importlib.import_module("management.chat_search_index")
db = importlib.import_module("config.db")
libsql = importlib.import_module("libsql")


class SemanticSearchTests(unittest.TestCase):
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

    def test_select_evidence_removes_overlaps(self):
        evidence = semantic_search.SearchEvidence
        windows = [
            evidence(-1001, 1, 24, "v1", 0.8),
            evidence(-1001, 9, 32, "v2", 0.7),
            evidence(-1001, 100, 124, "v3", 0.6),
            evidence(-1001, 200, 224, "v4", 0.5),
        ]

        selected = semantic_search.select_evidence(windows)

        self.assertEqual([item.text for item in selected], ["v1", "v3", "v4"])

    def test_answer_prompt_requires_playful_best_guess(self):
        messages = semantic_search.answer_messages(
            "most likely to bring snacks on a road trip",
            [semantic_search.SearchEvidence(-1001, 1, 24, "chat", 0.8)],
        )

        self.assertIn("always make", messages[0]["content"])
        self.assertIn("Weak or indirect receipts are enough", messages[0]["content"])
        self.assertIn("Never answer 'I cannot tell'", messages[0]["content"])

    def test_link_citations_links_only_citations_in_answer(self):
        evidence = [
            semantic_search.SearchEvidence(-1001234567890, 1, 24, "first", 0.8),
            semantic_search.SearchEvidence(-1001234567890, 25, 48, "second", 0.7),
        ]

        answer = semantic_search.link_citations(
            "Best guess: @user [2:30]. Unsupported [3:50].",
            evidence,
        )

        self.assertEqual(
            answer,
            "Best guess: @user [2](https://t.me/c/1234567890/30). Unsupported [3:50].",
        )


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
                    message_id INTEGER NOT NULL
                )
                """
            )
            connection.executemany(
                "INSERT INTO chat_search_windows VALUES (?, -1001, ?, ?, ?)",
                [(1, 1, 24, "first"), (2, 25, 48, "second")],
            )
            connection.executemany(
                "INSERT INTO chat_stats VALUES (-1001, ?, ?)",
                [(7, 10), (8, 30)],
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
            [(item.text, item.score) for item in evidence], [("first", 0.9)]
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


class SearchIndexTests(unittest.IsolatedAsyncioTestCase):
    async def test_pending_indexing_allocates_each_chat_a_share(self):
        class SessionContext:
            async def __aenter__(self):
                return object()

            async def __aexit__(self, *_: object):
                return None

        index_chat_windows = AsyncMock(
            side_effect=lambda _session, _key, _chat_id, limit: limit
        )
        with (
            patch.object(
                search_index.aiohttp,
                "ClientSession",
                return_value=SessionContext(),
            ),
            patch.object(
                search_index,
                "index_chat_windows",
                index_chat_windows,
            ),
            patch.object(search_index, "sync_search_cache", AsyncMock()),
        ):
            indexed = await search_index.index_pending_windows(
                "key",
                chat_ids=[-1002, -1001],
                window_limit=6,
            )

        self.assertEqual(indexed, 6)
        self.assertEqual(
            [
                (call.args[2], call.args[3])
                for call in index_chat_windows.await_args_list
            ],
            [(-1002, 3), (-1001, 3)],
        )

    async def test_refresh_advances_without_clearing_existing_windows(self):
        class SessionContext:
            async def __aenter__(self):
                return object()

            async def __aexit__(self, *_: object):
                return None

        index_window_batch = AsyncMock(side_effect=[(64, 100), (2, 200)])
        with (
            patch.object(
                search_index.aiohttp,
                "ClientSession",
                return_value=SessionContext(),
            ),
            patch.object(
                search_index,
                "index_window_batch",
                index_window_batch,
            ),
            patch.object(search_index, "reset_search_cache"),
            patch.object(search_index, "sync_search_cache", AsyncMock()),
        ):
            refreshed = await search_index.refresh_windows("key", [-1001])

        self.assertEqual(refreshed, 66)
        self.assertEqual(
            [call.args[3] for call in index_window_batch.await_args_list],
            [None, 100],
        )


if __name__ == "__main__":
    unittest.main()
