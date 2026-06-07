from __future__ import annotations

import importlib
import os
import unittest

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

semantic_search = importlib.import_module("management.chat_semantic_search")
backfill = importlib.import_module("backfill_chat_search_windows")


class SemanticSearchTests(unittest.TestCase):
    def test_build_fts_query_keeps_domain_terms(self):
        self.assertEqual(
            semantic_search.build_fts_query("what job does @Nathu do"),
            '"job" OR "nathu"',
        )

    def test_telegram_message_link_uses_private_supergroup_link(self):
        self.assertEqual(
            semantic_search.telegram_message_link(-1001118116449, 3305660),
            "https://t.me/c/1118116449/3305660",
        )

    def test_build_windows_uses_overlapping_chat_windows(self):
        messages = [
            backfill.SourceMessage(i, f"2026-06-07 00:00:{i:02d}", f"@u{i}", f"m{i}")
            for i in range(1, 30)
        ]

        windows = backfill.build_windows(-1001, messages, set())

        self.assertEqual(windows[0].start_message_id, 1)
        self.assertEqual(windows[0].end_message_id, 24)
        self.assertIn("1 2026-06-07 00:00:01 @u1: m1", windows[0].text)
        self.assertEqual(windows[1].start_message_id, 9)
        self.assertEqual(windows[1].end_message_id, 29)

    def test_build_windows_skips_indexed_ranges(self):
        messages = [
            backfill.SourceMessage(i, f"2026-06-07 00:00:{i:02d}", f"@u{i}", f"m{i}")
            for i in range(1, 30)
        ]

        windows = backfill.build_windows(-1001, messages, {(1, 24)})

        self.assertEqual(windows[0].start_message_id, 9)


if __name__ == "__main__":
    unittest.main()
