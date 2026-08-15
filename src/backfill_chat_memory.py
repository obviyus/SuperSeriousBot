import argparse
import asyncio

from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("chat_ids", type=int, nargs="*")
    return parser.parse_args()


async def backfill() -> None:
    args = parse_args()
    load_dotenv(".env")
    from commands.ai import close_ai_provider
    from management.chat_memory_build import build_chat_memories

    await build_chat_memories(args.chat_ids or None, bootstrap=True)
    await close_ai_provider()


if __name__ == "__main__":
    asyncio.run(backfill())
