import argparse
import asyncio

from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chat-id", type=int, action="append")
    parser.add_argument("--limit-utterances", type=int)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    if args.refresh and args.limit_utterances is not None:
        parser.error("--refresh cannot be combined with --limit-utterances")
    return args


async def backfill() -> None:
    args = parse_args()
    load_dotenv(".env")
    from management.chat_search_index import (
        INDEX_BATCH_WINDOWS,
        index_pending_utterances,
        refresh_utterances,
        source_chat_ids,
    )

    chat_ids = args.chat_id or await source_chat_ids()
    if args.refresh:
        print(f"indexed_utterances={await refresh_utterances(chat_ids):,}")
        return

    total_inserted = 0
    while args.limit_utterances is None or total_inserted < args.limit_utterances:
        batch_limit = INDEX_BATCH_WINDOWS
        if args.limit_utterances is not None:
            batch_limit = min(
                batch_limit,
                args.limit_utterances - total_inserted,
            )
        inserted = await index_pending_utterances(
            chat_ids=chat_ids,
            utterance_limit=batch_limit,
        )
        if not inserted:
            break
        total_inserted += inserted
        print(f"indexed_utterances={total_inserted:,}")


if __name__ == "__main__":
    asyncio.run(backfill())
