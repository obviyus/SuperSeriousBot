import importlib
import importlib.util
import logging
import os
from pathlib import Path
from typing import Any

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
logger = logging.getLogger("migrate")


def migration_version(path: Path) -> str:
    return path.stem.split("_", 1)[0]


def load_migration(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def current_version(conn) -> str:
    conn.execute("CREATE TABLE IF NOT EXISTS migration_version (version text)")
    row = conn.execute("SELECT version FROM migration_version").fetchone()
    if row:
        return row[0]
    conn.execute("INSERT INTO migration_version (version) VALUES ('')")
    return ""


def set_version(conn, version: str) -> None:
    conn.execute("DELETE FROM migration_version")
    conn.execute("INSERT INTO migration_version (version) VALUES (?)", (version,))


def open_connection():
    libsql_connect: Any = importlib.import_module("libsql").__dict__["connect"]
    return libsql_connect(
        database=os.environ["TURSO_DATABASE_URL"],
        auth_token=os.environ["TURSO_AUTH_TOKEN"],
        autocommit=True,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    conn = open_connection()
    version = current_version(conn)
    applied = 0

    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        next_version = migration_version(path)
        if next_version <= version:
            continue
        migration = load_migration(path)
        logger.info("Applying migration %s", next_version)
        migration.upgrade(conn)
        set_version(conn, next_version)
        version = next_version
        applied += 1

    conn.close()
    logger.info("Applied %d migrations; current version %s", applied, version)


if __name__ == "__main__":
    main()
