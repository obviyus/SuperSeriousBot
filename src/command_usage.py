import argparse
import json

from dotenv import load_dotenv

from migrate import open_connection

type JsonObject = dict[str, object]


def fetch_rows(connection, sql: str, params: tuple[object, ...]) -> list[JsonObject]:
    cursor = connection.execute(sql, params)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def usage_report(
    connection,
    *,
    days: int,
    command: str | None,
    status: str | None,
    limit: int,
) -> JsonObject:
    conditions = ["create_time >= datetime('now', ?)"]
    params: list[object] = [f"-{days} days"]
    if command:
        conditions.append("command = ?")
        params.append(command.removeprefix("/").lower())
    if status:
        conditions.append("status = ?")
        params.append(status)
    where = " AND ".join(conditions)
    query_params = tuple(params)

    summary = fetch_rows(
        connection,
        f"""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(status = 'completed'), 0) AS completed,
            COALESCE(SUM(status = 'blocked'), 0) AS blocked,
            COALESCE(SUM(status = 'failed'), 0) AS failed,
            CAST(AVG(duration_ms) AS INTEGER) AS average_duration_ms
        FROM command_stats
        WHERE {where}
        """,
        query_params,
    )[0]
    by_command = fetch_rows(
        connection,
        f"""
        SELECT command, COUNT(*) AS count
        FROM command_stats
        WHERE {where}
        GROUP BY command
        ORDER BY count DESC, command
        """,
        query_params,
    )
    events = fetch_rows(
        connection,
        f"""
        SELECT
            id, create_time, command, input_text, status, duration_ms,
            username, user_id, chat_id, message_id, error_type, error_message,
            error_traceback
        FROM command_stats
        WHERE {where}
        ORDER BY id DESC
        LIMIT ?
        """,
        (*query_params, limit),
    )
    return {
        "filters": {
            "days": days,
            "command": command,
            "status": status,
            "limit": limit,
        },
        "summary": summary,
        "by_command": by_command,
        "events": events,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query production command usage and failure history."
    )
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--command")
    parser.add_argument(
        "--status",
        choices=("completed", "blocked", "failed"),
    )
    parser.add_argument("--limit", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    connection = open_connection()
    try:
        report = usage_report(
            connection,
            days=args.days,
            command=args.command,
            status=args.status,
            limit=args.limit,
        )
    finally:
        connection.close()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
