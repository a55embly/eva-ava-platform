"""Apply SQL migrations exactly once in lexical order."""

from pathlib import Path

import psycopg

from app.config import Settings, psycopg_database_url


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    migrations = Path(__file__).parents[2] / "migrations"
    with psycopg.connect(
        psycopg_database_url(settings.database_url), autocommit=True
    ) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                   filename text PRIMARY KEY,
                   applied_at timestamptz NOT NULL DEFAULT now()
               )"""
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT filename FROM schema_migrations"
            ).fetchall()
        }
        for migration in sorted(migrations.glob("*.sql")):
            if migration.name in applied:
                continue
            connection.execute(migration.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (migration.name,),
            )
            print(f"applied migration: {migration.name}")


if __name__ == "__main__":
    main()
