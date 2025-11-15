"""Helpers for launching background coroutines without blocking handlers."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from config.logger import logger

_T = TypeVar("_T")


def schedule_background_task[T](
    coro: Coroutine[Any, Any, T],
    label: str,
) -> None:
    """Fire-and-forget a coroutine while bubbling failures to the logs."""

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    task = loop.create_task(coro)

    def _log_task_result(completed: asyncio.Task[T]) -> None:
        try:
            completed.result()
        except asyncio.CancelledError:
            logger.debug("Background task '%s' cancelled", label)
        except Exception as exc:
            logger.warning("Background task '%s' failed: %s", label, exc, exc_info=exc)

    task.add_done_callback(_log_task_result)
