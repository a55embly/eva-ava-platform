import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest

from app.rag.chunking import chunk_document
from app.rag.models import AccessLevel, SourceDocument
from app.rag.postgres_repository import PostgresKnowledgeRepository


@pytest.fixture(scope="module", autouse=True)
def migrated_database() -> Iterator[None]:
    database_url = os.getenv("RAG_TEST_DATABASE_URL")
    if database_url is None:
        yield
        return
    with psycopg.connect(database_url) as connection:
        migrations = Path(__file__).parents[2] / "migrations"
        for migration in sorted(migrations.glob("*.sql")):
            connection.execute(migration.read_text(encoding="utf-8"))
    yield


@pytest.mark.skipif(
    not os.getenv("RAG_TEST_DATABASE_URL"),
    reason="RAG_TEST_DATABASE_URL must point to a disposable PostgreSQL database",
)
def test_postgres_repository_idempotency_and_role_isolation() -> None:
    database_url = os.environ["RAG_TEST_DATABASE_URL"]
    with psycopg.connect(database_url) as connection:
        connection.execute("TRUNCATE rag_documents CASCADE")
        repository = PostgresKnowledgeRepository(connection)
        employee = SourceDocument(
            "demo", "integration", "employee", "Urlopy", "Urlop wymaga akceptacji.",
            AccessLevel.EMPLOYEE, datetime.now(UTC),
        )
        admin = SourceDocument(
            "demo", "integration", "admin", "Budżet", "Poufny budżet administratora.",
            AccessLevel.ADMIN, datetime.now(UTC),
        )
        assert repository.sync_document(employee, chunk_document(employee.content), None)
        assert not repository.sync_document(employee, chunk_document(employee.content), None)
        assert repository.sync_document(admin, chunk_document(admin.content), None)
        assert repository.search("demo", AccessLevel.EMPLOYEE, "budżet", 5) == []
        assert repository.search("demo", AccessLevel.ADMIN, "budżet", 5)


@pytest.mark.skipif(
    not os.getenv("RAG_TEST_DATABASE_URL"),
    reason="RAG_TEST_DATABASE_URL must point to a disposable PostgreSQL database",
)
def test_postgres_metadata_updates_preserve_version_and_citation() -> None:
    database_url = os.environ["RAG_TEST_DATABASE_URL"]
    with psycopg.connect(database_url) as connection:
        connection.execute("TRUNCATE rag_documents CASCADE")
        repository = PostgresKnowledgeRepository(connection)
        modified_at = datetime(2026, 1, 1, tzinfo=UTC)
        employee = SourceDocument(
            "demo",
            "integration",
            "policy",
            "Stara nazwa",
            "Wspólna treść procedury.",
            AccessLevel.EMPLOYEE,
            modified_at,
            "https://demo.invalid/old",
            {"department": "service"},
        )
        assert repository.sync_document(employee, chunk_document(employee.content), None)
        before = repository.search("demo", AccessLevel.EMPLOYEE, "wspólna treść", 5)
        citation_id = before[0].citation_id

        admin = SourceDocument(
            "demo",
            "integration",
            "policy",
            "Nowa nazwa",
            employee.content,
            AccessLevel.ADMIN,
            datetime(2026, 2, 1, tzinfo=UTC),
            "https://demo.invalid/new",
            {"department": "operations"},
        )
        assert repository.sync_document(admin, chunk_document(admin.content), None)
        assert repository.search("demo", AccessLevel.EMPLOYEE, "wspólna treść", 5) == []
        visible = repository.search("demo", AccessLevel.ADMIN, "wspólna treść", 5)
        assert visible[0].document_title == "Nowa nazwa"
        assert visible[0].metadata == {"department": "operations"}
        assert visible[0].document_version == 1
        assert visible[0].citation_id == citation_id
        assert not repository.sync_document(admin, chunk_document(admin.content), None)

        assert repository.mark_missing_deleted("demo", "integration", set()) == 1
        assert repository.sync_document(admin, chunk_document(admin.content), None)
        restored = repository.search("demo", AccessLevel.ADMIN, "wspólna treść", 5)
        assert restored[0].document_version == 1
        assert restored[0].citation_id == citation_id


@pytest.mark.skipif(
    not os.getenv("RAG_TEST_DATABASE_URL"),
    reason="RAG_TEST_DATABASE_URL must point to a disposable PostgreSQL database",
)
def test_postgres_prefers_current_sources_and_searches_titles() -> None:
    database_url = os.environ["RAG_TEST_DATABASE_URL"]
    with psycopg.connect(database_url) as connection:
        connection.execute("TRUNCATE rag_documents CASCADE")
        repository = PostgresKnowledgeRepository(connection)
        documents = [
            SourceDocument(
                "demo",
                "integration",
                "old",
                "Archiwum",
                "Procedura awaryjna procedura.",
                AccessLevel.EMPLOYEE,
                datetime(2026, 1, 1, tzinfo=UTC),
                metadata={"status": "outdated"},
            ),
            SourceDocument(
                "demo",
                "integration",
                "current",
                "Instrukcja",
                "Procedura awaryjna.",
                AccessLevel.EMPLOYEE,
                datetime(2026, 2, 1, tzinfo=UTC),
            ),
            SourceDocument(
                "demo",
                "integration",
                "conflict",
                "Alternatywa",
                "Procedura awaryjna.",
                AccessLevel.EMPLOYEE,
                datetime(2026, 2, 1, tzinfo=UTC),
                metadata={"status": "conflicting"},
            ),
            SourceDocument(
                "demo",
                "integration",
                "title",
                "Kalibracja urządzeń",
                "Neutralna treść dokumentu.",
                AccessLevel.EMPLOYEE,
                datetime(2026, 2, 1, tzinfo=UTC),
            ),
        ]
        for item in documents:
            assert repository.sync_document(item, chunk_document(item.content), None)

        ranked = repository.search(
            "demo", AccessLevel.EMPLOYEE, "procedura awaryjna", 5
        )
        assert ranked[-1].metadata["status"] == "outdated"
        assert any(item.metadata.get("status") == "conflicting" for item in ranked)
        title_match = repository.search(
            "demo", AccessLevel.EMPLOYEE, "kalibracja", 5
        )
        assert title_match[0].document_title == "Kalibracja urządzeń"


@pytest.mark.skipif(
    not os.getenv("RAG_TEST_DATABASE_URL"),
    reason="RAG_TEST_DATABASE_URL must point to a disposable PostgreSQL database",
)
def test_postgres_repository_isolates_tenants_for_employee_and_admin() -> None:
    database_url = os.environ["RAG_TEST_DATABASE_URL"]
    with psycopg.connect(database_url) as connection:
        connection.execute("TRUNCATE rag_documents CASCADE")
        repository = PostgresKnowledgeRepository(connection)
        tenant_b_document = SourceDocument(
            "tenant-b",
            "integration",
            "private-policy",
            "Instrukcja beta",
            "Izolowana procedura tenanta beta.",
            AccessLevel.EMPLOYEE,
            datetime(2026, 2, 1, tzinfo=UTC),
        )
        assert repository.sync_document(
            tenant_b_document, chunk_document(tenant_b_document.content), None
        )

        assert repository.search(
            "tenant-a", AccessLevel.EMPLOYEE, "izolowana procedura", 5
        ) == []
        assert repository.search(
            "tenant-a", AccessLevel.ADMIN, "izolowana procedura", 5
        ) == []
        assert repository.search(
            "tenant-b", AccessLevel.EMPLOYEE, "izolowana procedura", 5
        )


@pytest.mark.skipif(
    not os.getenv("RAG_TEST_DATABASE_URL"),
    reason="RAG_TEST_DATABASE_URL must point to a disposable PostgreSQL database",
)
def test_postgres_reindexes_embeddings_without_changing_version_or_citation() -> None:
    database_url = os.environ["RAG_TEST_DATABASE_URL"]
    with psycopg.connect(database_url) as connection:
        connection.execute("TRUNCATE rag_documents CASCADE")
        repository = PostgresKnowledgeRepository(connection)
        item = SourceDocument(
            "demo",
            "integration",
            "remote",
            "Praca zdalna",
            "Praca spoza biura wymaga zgody.",
            AccessLevel.EMPLOYEE,
            datetime(2026, 2, 1, tzinfo=UTC),
        )
        chunks = chunk_document(item.content)
        assert repository.sync_document(
            item, chunks, [[1.0, 0.0]], embedding_model="model-v1"
        )
        before = repository.search(
            "demo",
            AccessLevel.EMPLOYEE,
            "obowiązki z domu",
            5,
            query_embedding=[1.0, 0.0],
            embedding_model="model-v1",
        )

        assert repository.sync_document(
            item, chunks, [[0.0, 1.0]], embedding_model="model-v2"
        )
        after = repository.search(
            "demo",
            AccessLevel.EMPLOYEE,
            "obowiązki z domu",
            5,
            query_embedding=[0.0, 1.0],
            embedding_model="model-v2",
        )

        assert after[0].document_version == 1
        assert after[0].citation_id == before[0].citation_id
