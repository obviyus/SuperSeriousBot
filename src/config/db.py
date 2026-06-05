import asyncio
import importlib
import os
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self

from config import logger

_init_lock = asyncio.Lock()


def open_sync_connection():
    libsql_connect: Any = vars(importlib.import_module("libsql"))["connect"]
    return libsql_connect(
        os.environ["TURSO_DATABASE_URL"],
        auth_token=os.environ["TURSO_AUTH_TOKEN"],
        autocommit=True,
        _check_same_thread=False,
    )


def bind_params(params: object) -> object:
    if isinstance(params, datetime):
        return str(params)
    if isinstance(params, tuple):
        return tuple(bind_params(value) for value in params)
    if isinstance(params, list):
        return [bind_params(value) for value in params]
    if isinstance(params, dict):
        return {key: bind_params(value) for key, value in params.items()}
    return params


@dataclass(frozen=True)
class TursoRow:
    values: tuple[Any, ...]
    columns: dict[str, int]

    def __getitem__(self, key: int | str) -> Any:
        if isinstance(key, str):
            return self.values[self.columns[key]]
        return self.values[key]

    def __iter__(self) -> Iterator[Any]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


class TursoCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._columns = {
            column[0]: index
            for index, column in enumerate(cursor.description or ())
        }

    @property
    def lastrowid(self) -> int:
        return self._cursor.lastrowid

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await asyncio.to_thread(self._cursor.close)

    async def fetchone(self) -> TursoRow | None:
        row = await asyncio.to_thread(self._cursor.fetchone)
        return self._row(row) if row is not None else None

    async def fetchall(self) -> list[TursoRow]:
        rows = await asyncio.to_thread(self._cursor.fetchall)
        return [self._row(row) for row in rows]

    def _row(self, row: tuple[Any, ...]) -> TursoRow:
        return TursoRow(row, self._columns)


class TursoOperation:
    def __init__(
        self,
        connection,
        sql: str,
        params: object,
        *,
        many: bool,
    ):
        self._connection = connection
        self._sql = sql
        self._params = params
        self._many = many
        self._cursor: TursoCursor | None = None

    def __await__(self):
        return self._execute().__await__()

    async def __aenter__(self) -> TursoCursor:
        self._cursor = await self._execute()
        return self._cursor

    async def __aexit__(self, *_: object) -> None:
        if self._cursor:
            await self._cursor.__aexit__()

    async def _execute(self) -> TursoCursor:
        if self._many:
            cursor = await asyncio.to_thread(
                self._connection.executemany,
                self._sql,
                bind_params(self._params or []),
            )
        elif self._params is None:
            cursor = await asyncio.to_thread(self._connection.execute, self._sql)
        else:
            cursor = await asyncio.to_thread(
                self._connection.execute,
                self._sql,
                bind_params(self._params),
            )
        return TursoCursor(cursor)


class TursoConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(
        self,
        sql: str,
        params: object = None,
    ) -> TursoOperation:
        return TursoOperation(self._connection, sql, params, many=False)

    def executemany(
        self,
        sql: str,
        params: object,
    ) -> TursoOperation:
        return TursoOperation(self._connection, sql, params, many=True)

    async def close(self) -> None:
        await asyncio.to_thread(self._connection.close)

    async def sync(self) -> None:
        await asyncio.to_thread(self._connection.sync)


async def _open_connection() -> TursoConnection:
    conn = open_sync_connection()
    wrapper = TursoConnection(conn)
    await wrapper.execute("PRAGMA foreign_keys = ON;")
    return wrapper


async def init_db() -> None:
    async with _init_lock:
        async with get_db() as conn:
            await conn.sync()
            await conn.execute("SELECT 1;")
        logger.info("Turso connection initialized")


async def close_db() -> None:
    logger.info("Turso connection closed")


@asynccontextmanager
async def get_db() -> AsyncGenerator[TursoConnection]:
    conn = await _open_connection()
    try:
        yield conn
    finally:
        await conn.close()
