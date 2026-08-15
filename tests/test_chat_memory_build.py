import os

os.environ.setdefault("TELEGRAM_TOKEN", "test-token")
os.environ.setdefault("QUOTE_CHANNEL_ID", "1")
os.environ.setdefault("TURSO_DATABASE_URL", ":memory:")
os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")

from management.chat_memory_build import (
    Alias,
    LoreItem,
    LoreWindow,
    StoredLore,
    batch_lore_windows,
    batches,
    disjoint_windows,
    filter_aliases,
    merge_lore,
    strip_invalid_receipts,
)


def test_batches_preserve_order_and_tail() -> None:
    assert batches(list(range(7)), 3) == [[0, 1, 2], [3, 4, 5], [6]]


def test_filter_aliases_normalizes_filters_and_resolves_collisions() -> None:
    aliases = filter_aliases(
        [
            (2, Alias(alias="  BOSS  ", confidence=0.8)),
            (1, Alias(alias="boss", confidence=0.8)),
            (3, Alias(alias="maybe", confidence=0.49)),
        ]
    )

    assert [(item.user_id, item.alias, item.confidence) for item in aliases] == [
        (1, "boss", 0.8)
    ]


def test_strip_invalid_receipts_keeps_only_supplied_ids() -> None:
    sheet, receipts = strip_invalid_receipts(
        "- Likes chai [msg:1, msg:99]\n- Old claim [msg:88]", {1, 2}
    )

    assert sheet == "- Likes chai [msg:1]\n- Old claim "
    assert receipts == [1]


def test_lore_batches_split_by_month_and_size() -> None:
    windows = [
        LoreWindow(1, 2, "2026-01", "12345"),
        LoreWindow(3, 4, "2026-01", "67890"),
        LoreWindow(5, 6, "2026-02", "x"),
    ]

    assert batch_lore_windows(windows, max_chars=9) == [
        [windows[0]],
        [windows[1]],
        [windows[2]],
    ]


def test_merge_lore_replaces_summary_and_appends_valid_receipts() -> None:
    existing = {
        "chai-war": StoredLore("chai-war", "old", (1, 2), 2),
    }
    merged = merge_lore(
        existing,
        [LoreItem(topic="chai-war", summary="new", receipts=[2, 3, 99])],
        {3},
        10,
    )

    assert merged == [StoredLore("chai-war", "new", (1, 2, 3), 10)]


def test_disjoint_windows_drops_overlapping_stride_windows() -> None:
    windows = [
        LoreWindow(1, 24, "2026-01", "a"),
        LoreWindow(9, 32, "2026-01", "b"),
        LoreWindow(17, 40, "2026-01", "c"),
        LoreWindow(25, 48, "2026-01", "d"),
        LoreWindow(33, 56, "2026-01", "e"),
    ]

    assert disjoint_windows(windows) == [windows[0], windows[3]]
