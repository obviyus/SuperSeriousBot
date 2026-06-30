import asyncio
import importlib
import json
import os
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self
from urllib import error, parse, request

from config import logger

_init_lock = asyncio.Lock()
DB_OPEN_ATTEMPTS = 3
DB_OPEN_RETRY_DELAY_SECONDS = 0.2
HRANA_CLOSED_MESSAGE = "connection closed before message completed"


def is_retryable_open_error(exc: Exception) -> bool:
    return isinstance(exc, ValueError) and "Hrana:" in str(exc) and HRANA_CLOSED_MESSAGE in str(exc)


def open_sync_connection():
    database_url = os.environ["TURSO_DATABASE_URL"]
    if database_url.startswith("libsql://"):
        return TursoHttpConnection(database_url, os.environ["TURSO_AUTH_TOKEN"])

    libsql_connect: Any = vars(importlib.import_module("libsql"))["connect"]
    return libsql_connect(
        database_url,
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


class TursoHttpCursor:
    def __init__(
        self,
        rows: list[tuple[Any, ...]],
        columns: list[str],
        rowcount: int,
        lastrowid: int | None,
    ):
        self._rows = rows
        self._offset = 0
        self.description = [(column,) for column in columns]
        self.rowcount = rowcount
        self.lastrowid = lastrowid

    def fetchone(self) -> tuple[Any, ...] | None:
        if self._offset >= len(self._rows):
            return None
        row = self._rows[self._offset]
        self._offset += 1
        return row

    def fetchall(self) -> list[tuple[Any, ...]]:
        rows = self._rows[self._offset:]
        self._offset = len(self._rows)
        return rows

    def close(self) -> None:
        return None


class TursoHttpConnection:
    needs_foreign_key_init = False

    def __init__(self, database_url: str, auth_token: str):
        hostname = parse.urlparse(database_url).hostname
        if not hostname:
            raise ValueError("TURSO_DATABASE_URL must include a host")
        self._endpoint = f"https://{hostname}/v2/pipeline"
        self._headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

    def execute(self, sql: str, params: object = None) -> TursoHttpCursor:
        result = self._request([self._statement(sql, params)])[0]
        return self._cursor(result)

    def executemany(self, sql: str, params: object) -> TursoHttpCursor:
        statements = [self._statement(sql, batch) for batch in self._many_params(params)]
        if not statements:
            return TursoHttpCursor([], [], 0, None)

        results = [self._cursor(result) for result in self._request(statements)]
        return TursoHttpCursor(
            results[-1].fetchall(),
            [column[0] for column in results[-1].description],
            sum(result.rowcount for result in results),
            results[-1].lastrowid,
        )

    def close(self) -> None:
        return None

    def _request(self, statements: list[dict[str, object]]) -> list[dict[str, Any]]:
        body = json.dumps(
            {
                "requests": [
                    {
                        "type": "execute",
                        "stmt": statement,
                    }
                    for statement in statements
                ] + [{"type": "close"}]
            }
        ).encode()
        req = request.Request(
            self._endpoint,
            data=body,
            headers=self._headers,
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode())
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", "replace")
            raise ValueError(
                f"Hrana: `api error: `status={exc.code} {exc.reason}, body={response_body}``"
            ) from exc
        except error.URLError as exc:
            raise ValueError(f"Hrana: `http error: `{exc.reason}``") from exc

        responses = []
        for result in payload["results"]:
            if result["type"] != "ok":
                raise ValueError(f"Hrana: `stream error: `{result}``")
            response = result["response"]
            if response["type"] == "close":
                continue
            if response["type"] != "execute":
                raise ValueError(f"Hrana: `stream error: `{response}``")
            responses.append(response["result"])
        return responses

    def _statement(self, sql: str, params: object = None) -> dict[str, object]:
        statement: dict[str, object] = {"sql": sql}
        if params is not None:
            statement["args"] = [
                self._value(value) for value in self._params(bind_params(params))
            ]
        return statement

    def _params(self, params: object) -> list[object]:
        if isinstance(params, dict):
            raise ValueError("Named SQL parameters are not supported")
        if isinstance(params, list | tuple):
            return list(params)
        return [params]

    def _many_params(self, params: object) -> list[object]:
        if isinstance(params, list | tuple):
            return list(params)
        raise ValueError("executemany parameters must be a list or tuple")

    def _cursor(self, result: dict[str, Any]) -> TursoHttpCursor:
        columns = [column["name"] for column in result["cols"]]
        rows = [
            tuple(self._result_value(value) for value in row)
            for row in result["rows"]
        ]
        lastrowid = result["last_insert_rowid"]
        return TursoHttpCursor(
            rows,
            columns,
            result["affected_row_count"],
            int(lastrowid) if lastrowid is not None else None,
        )

    def _value(self, value: object) -> dict[str, object]:
        if value is None:
            return {"type": "null"}
        if isinstance(value, bool):
            return {"type": "integer", "value": "1" if value else "0"}
        if isinstance(value, int):
            return {"type": "integer", "value": str(value)}
        if isinstance(value, float):
            return {"type": "float", "value": value}
        if isinstance(value, str):
            return {"type": "text", "value": value}
        raise ValueError(f"Unsupported Turso value: {type(value).__name__}")

    def _result_value(self, value: dict[str, Any]) -> object:
        kind = value["type"]
        if kind == "null":
            return None
        if kind == "integer":
            return int(value["value"])
        if kind == "float":
            return float(value["value"])
        if kind == "text":
            return value["value"]
        raise ValueError(f"Unsupported Hrana value type: {kind}")


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


async def _open_connection() -> TursoConnection:
    for attempt in range(DB_OPEN_ATTEMPTS):
        conn = open_sync_connection()
        wrapper = TursoConnection(conn)
        try:
            if getattr(conn, "needs_foreign_key_init", True):
                await wrapper.execute("PRAGMA foreign_keys = ON;")
            return wrapper
        except Exception as exc:
            with suppress(Exception):
                await wrapper.close()
            if not is_retryable_open_error(exc) or attempt == DB_OPEN_ATTEMPTS - 1:
                raise
            logger.warning(
                "Turso connection initialization failed; retrying (%d/%d): %s",
                attempt + 1,
                DB_OPEN_ATTEMPTS,
                exc,
            )
            await asyncio.sleep(DB_OPEN_RETRY_DELAY_SECONDS * (attempt + 1))
    raise RuntimeError("Turso connection initialization failed")


async def init_db() -> None:
    async with _init_lock:
        async with get_db() as conn:
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
