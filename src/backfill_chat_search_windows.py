import argparse
import asyncio
import os

from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-id", type=int, action="append")
    parser.add_argument("--limit-windows", type=int)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.refresh and args.limit_windows is not None:
        parser.error("--refresh cannot be combined with --limit-windows")
    return args


async def backfill() -> None:
    args = parse_args()
    load_dotenv(".env")
    from management.chat_search_index import (
        INDEX_BATCH_WINDOWS,
        index_pending_windows,
        refresh_windows,
        source_chat_ids,
    )

    api_key = os.environ["OPENROUTER_API_KEY"]
    chat_ids = args.chat_id or await source_chat_ids()
    if args.refresh:
        print(f"indexed_windows={await refresh_windows(api_key, chat_ids):,}")
        return

    total_inserted = 0
    while args.limit_windows is None or total_inserted < args.limit_windows:
        batch_limit = INDEX_BATCH_WINDOWS
        if args.limit_windows is not None:
            batch_limit = min(batch_limit, args.limit_windows - total_inserted)
        inserted = await index_pending_windows(
            api_key,
            chat_ids=chat_ids,
            window_limit=batch_limit,
        )
        if not inserted:
            break
        total_inserted += inserted
        print(f"indexed_windows={total_inserted:,}")


if __name__ == "__main__":
    asyncio.run(backfill())
