from datetime import UTC, datetime

import pytest

from app.rag.chunking import chunk_document
from app.rag.embedding import EmbeddingProvider
from app.rag.ingestion import IngestionService
from app.rag.models import AccessLevel, SourceDocument
from app.rag.repositories import InMemoryKnowledgeRepository
from app.rag.retrieval import RetrievalService


class MutableSource:
    name = "test-source"

    def __init__(self, documents: list[SourceDocument]) -> None:
        self.documents = documents

    def list_documents(self, tenant_id: str) -> list[SourceDocument]:
        return self.documents


class SemanticEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_id: str = "semantic-demo-v1") -> None:
        self._model_id = model_id

    @property
    def model_id(self) -> str:
        return self._model_id

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [1.0, 0.0]
            if "spoza biura" in text.lower() or "z domu" in text.lower()
            else [0.0, 1.0]
            for text in texts
        ]


def document(
    source_id: str,
    content: str,
    access: AccessLevel = AccessLevel.EMPLOYEE,
    *,
    title: str | None = None,
    metadata: dict[str, str] | None = None,
    modified_at: datetime | None = None,
    tenant_id: str = "demo",
    source_name: str = "test-source",
) -> SourceDocument:
    return SourceDocument(
        tenant_id=tenant_id,
        source_name=source_name,
        source_id=source_id,
        title=title or source_id,
        content=content,
        access_level=access,
        modified_at=modified_at or datetime(2026, 1, 1, tzinfo=UTC),
        source_url=f"https://demo.invalid/{source_id}",
        metadata=metadata or {},
    )


def test_chunking_is_deterministic_and_tracks_sections() -> None:
    content = "# Dokument\n\n## Sekcja A\n\nPierwszy akapit.\n\nDrugi akapit."
    first = chunk_document(content, max_chars=100)
    assert first == chunk_document(content, max_chars=100)
    assert first[0].section == "Sekcja A"
    assert first[0].index == 0


def test_ingestion_is_idempotent_versions_updates_and_marks_deleted() -> None:
    repository = InMemoryKnowledgeRepository()
    source = MutableSource([document("leave", "Wniosek urlopowy wymaga akceptacji.")])
    ingestion = IngestionService(repository, source)

    assert ingestion.run("demo").updated == 1
    assert ingestion.run("demo").unchanged == 1

    source.documents = [document("leave", "Wniosek urlopowy wymaga dwóch akceptacji.")]
    assert ingestion.run("demo").updated == 1
    result = RetrievalService(repository).retrieve(
        "demo", AccessLevel.EMPLOYEE, "dwóch akceptacji"
    )
    assert result.evidence[0].document_version == 2

    source.documents = []
    assert ingestion.run("demo").deleted == 1
    assert not RetrievalService(repository).retrieve(
        "demo", AccessLevel.ADMIN, "akceptacji"
    ).answerable


def test_employee_never_receives_admin_content_but_admin_can() -> None:
    repository = InMemoryKnowledgeRepository()
    source = MutableSource(
        [
            document("employee", "Portal urlopowy dla pracowników."),
            document("admin", "Poufny budżet administratora.", AccessLevel.ADMIN),
        ]
    )
    IngestionService(repository, source).run("demo")
    retrieval = RetrievalService(repository)

    employee = retrieval.retrieve("demo", AccessLevel.EMPLOYEE, "poufny budżet")
    admin = retrieval.retrieve("demo", AccessLevel.ADMIN, "poufny budżet")

    assert not employee.answerable
    assert admin.answerable
    assert all(hit.access_level is AccessLevel.ADMIN for hit in admin.evidence)


def test_in_memory_repository_isolates_tenants_for_employee_and_admin() -> None:
    repository = InMemoryKnowledgeRepository()
    tenant_b_document = document(
        "tenant-b-policy",
        "Izolowana instrukcja tenanta beta.",
        tenant_id="tenant-b",
    )
    IngestionService(repository, MutableSource([tenant_b_document])).run("tenant-b")
    retrieval = RetrievalService(repository)

    assert not retrieval.retrieve(
        "tenant-a", AccessLevel.EMPLOYEE, "izolowana instrukcja"
    ).answerable
    assert not retrieval.retrieve(
        "tenant-a", AccessLevel.ADMIN, "izolowana instrukcja"
    ).answerable
    assert retrieval.retrieve(
        "tenant-b", AccessLevel.EMPLOYEE, "izolowana instrukcja"
    ).answerable


@pytest.mark.parametrize(
    ("tenant_id", "source_name"),
    [("other-tenant", "test-source"), ("demo", "other-source")],
)
def test_ingestion_rejects_mismatched_identity_without_soft_delete(
    tenant_id: str, source_name: str
) -> None:
    repository = InMemoryKnowledgeRepository()
    source = MutableSource([document("active", "Aktywna instrukcja.")])
    ingestion = IngestionService(repository, source)
    assert ingestion.run("demo").updated == 1

    source.documents = [
        document(
            "foreign",
            "Obca instrukcja.",
            tenant_id=tenant_id,
            source_name=source_name,
        )
    ]
    with pytest.raises(ValueError):
        ingestion.run("demo")

    assert RetrievalService(repository).retrieve(
        "demo", AccessLevel.ADMIN, "aktywna instrukcja"
    ).answerable


def test_ingestion_rejects_duplicate_source_ids_without_writing_documents() -> None:
    repository = InMemoryKnowledgeRepository()
    duplicate = document("duplicate", "Pierwsza wersja.")
    source = MutableSource([duplicate, document("duplicate", "Druga wersja.")])

    with pytest.raises(ValueError, match="duplicate source_id"):
        IngestionService(repository, source).run("demo")

    assert not RetrievalService(repository).retrieve(
        "demo", AccessLevel.ADMIN, "pierwsza wersja"
    ).answerable


def test_permission_and_metadata_updates_preserve_content_version_and_citation() -> None:
    repository = InMemoryKnowledgeRepository()
    source = MutableSource(
        [document("policy", "Wspólna treść procedury.", title="Stara nazwa")]
    )
    ingestion = IngestionService(repository, source)
    retrieval = RetrievalService(repository)

    assert ingestion.run("demo").updated == 1
    before = retrieval.retrieve("demo", AccessLevel.EMPLOYEE, "wspólna treść")
    citation_id = before.citations[0].citation_id

    source.documents = [
        document(
            "policy",
            "Wspólna treść procedury.",
            AccessLevel.ADMIN,
            title="Nowa nazwa",
            metadata={"department": "operations"},
            modified_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
    ]
    assert ingestion.run("demo").updated == 1
    assert not retrieval.retrieve(
        "demo", AccessLevel.EMPLOYEE, "wspólna treść"
    ).answerable
    admin = retrieval.retrieve("demo", AccessLevel.ADMIN, "wspólna treść")
    assert admin.answerable
    assert admin.evidence[0].document_title == "Nowa nazwa"
    assert admin.evidence[0].metadata == {"department": "operations"}
    assert admin.evidence[0].document_version == 1
    assert admin.citations[0].citation_id == citation_id
    assert ingestion.run("demo").unchanged == 1


def test_restoring_deleted_unchanged_content_preserves_version() -> None:
    repository = InMemoryKnowledgeRepository()
    original = document("policy", "Aktywna procedura.")
    source = MutableSource([original])
    ingestion = IngestionService(repository, source)

    assert ingestion.run("demo").updated == 1
    source.documents = []
    assert ingestion.run("demo").deleted == 1
    source.documents = [original]
    assert ingestion.run("demo").updated == 1
    restored = RetrievalService(repository).retrieve(
        "demo", AccessLevel.EMPLOYEE, "aktywna procedura"
    )
    assert restored.evidence[0].document_version == 1


def test_current_sources_rank_before_outdated_and_conflicts_remain_visible() -> None:
    repository = InMemoryKnowledgeRepository()
    source = MutableSource(
        [
            document(
                "old",
                "Procedura awaryjna procedura.",
                metadata={"status": "outdated"},
            ),
            document("current", "Procedura awaryjna."),
            document(
                "conflict",
                "Procedura awaryjna.",
                metadata={"status": "conflicting"},
            ),
        ]
    )
    IngestionService(repository, source).run("demo")

    result = RetrievalService(repository).retrieve(
        "demo", AccessLevel.EMPLOYEE, "procedura awaryjna"
    )

    assert result.evidence[-1].metadata["status"] == "outdated"
    assert any(hit.metadata.get("status") == "conflicting" for hit in result.evidence)
    assert any("outdated" in warning for warning in result.warnings)


def test_search_matches_word_present_only_in_title() -> None:
    repository = InMemoryKnowledgeRepository()
    source = MutableSource(
        [document("manual", "Neutralna treść dokumentu.", title="Kalibracja urządzeń")]
    )
    IngestionService(repository, source).run("demo")

    result = RetrievalService(repository).retrieve(
        "demo", AccessLevel.EMPLOYEE, "kalibracja"
    )

    assert result.answerable
    assert result.evidence[0].document_title == "Kalibracja urządzeń"


def test_retrieval_returns_real_stable_citations_and_no_data_state() -> None:
    repository = InMemoryKnowledgeRepository()
    source = MutableSource([document("leave", "Urlop wymaga akceptacji przełożonego.")])
    IngestionService(repository, source).run("demo")
    retrieval = RetrievalService(repository)

    first = retrieval.retrieve("demo", AccessLevel.EMPLOYEE, "urlop akceptacji")
    second = retrieval.retrieve("demo", AccessLevel.EMPLOYEE, "urlop akceptacji")
    missing = retrieval.retrieve("demo", AccessLevel.EMPLOYEE, "nieistniejący temat")

    assert first.answerable
    assert first.citations[0].citation_id == second.citations[0].citation_id
    assert first.citations[0].document_version == 1
    assert not missing.answerable
    assert missing.citations == ()


def test_semantic_retrieval_finds_a_paraphrase_without_keyword_overlap() -> None:
    repository = InMemoryKnowledgeRepository()
    embeddings = SemanticEmbeddingProvider()
    source = MutableSource(
        [document("remote", "Praca spoza biura wymaga zgody przełożonego.")]
    )
    IngestionService(repository, source, embeddings).run("demo")

    result = RetrievalService(repository, embeddings).retrieve(
        "demo", AccessLevel.EMPLOYEE, "Czy mogę wykonywać obowiązki z domu?"
    )

    assert result.answerable
    assert result.evidence[0].document_title == "remote"


def test_embedding_model_change_reindexes_without_new_document_version() -> None:
    repository = InMemoryKnowledgeRepository()
    source = MutableSource(
        [document("remote", "Praca spoza biura wymaga zgody przełożonego.")]
    )
    first_provider = SemanticEmbeddingProvider("semantic-demo-v1")
    second_provider = SemanticEmbeddingProvider("semantic-demo-v2")

    first_report = IngestionService(repository, source, first_provider).run("demo")
    before = RetrievalService(repository, first_provider).retrieve(
        "demo", AccessLevel.EMPLOYEE, "obowiązki z domu"
    )
    second_report = IngestionService(repository, source, second_provider).run("demo")
    after = RetrievalService(repository, second_provider).retrieve(
        "demo", AccessLevel.EMPLOYEE, "obowiązki z domu"
    )

    assert first_report.updated == 1
    assert second_report.updated == 1
    assert after.evidence[0].document_version == 1
    assert after.citations[0].citation_id == before.citations[0].citation_id
