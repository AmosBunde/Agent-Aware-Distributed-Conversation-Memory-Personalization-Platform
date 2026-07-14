"""Minimal SQL migration runner.

Numbered ``*.sql`` files in ``scripts/migrations/`` are applied in order;
applied versions are recorded in ``schema_migrations`` so each file runs
exactly once per database — including on volumes that predate this runner
(the baseline uses IF NOT EXISTS throughout, so stamping it is a no-op).

This is a deliberate lightweight alternative to Alembic: no SQLAlchemy
dependency, plain SQL files as the single source of truth. The memory
service owns the schema and runs this on startup, guarded by an advisory
lock so concurrent replicas cannot race.
"""

from pathlib import Path

import asyncpg

MIGRATION_LOCK_ID = 715_001  # arbitrary, unique to this runner


async def run_migrations(dsn: str, migrations_dir: Path) -> list[str]:
    """Apply pending migrations; returns the filenames newly applied."""
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("SELECT pg_advisory_lock($1)", MIGRATION_LOCK_ID)
        try:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version    TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            applied = {
                r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations")
            }
            newly_applied: list[str] = []
            for path in sorted(migrations_dir.glob("*.sql")):
                if path.name in applied:
                    continue
                async with conn.transaction():
                    await conn.execute(path.read_text())
                    await conn.execute(
                        "INSERT INTO schema_migrations (version) VALUES ($1)", path.name
                    )
                newly_applied.append(path.name)
            return newly_applied
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", MIGRATION_LOCK_ID)
    finally:
        await conn.close()
