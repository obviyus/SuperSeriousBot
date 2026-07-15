from __future__ import annotations

import importlib
import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

semantic_search = importlib.import_module("management.chat_semantic_search")
search_index = importlib.import_module("management.chat_search_index")


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
        ):
            refreshed = await search_index.refresh_windows("key", [-1001])

        self.assertEqual(refreshed, 66)
        self.assertEqual(
            [call.args[3] for call in index_window_batch.await_args_list],
            [None, 100],
        )


if __name__ == "__main__":
    unittest.main()
