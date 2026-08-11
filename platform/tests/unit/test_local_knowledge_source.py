from pathlib import Path

import pytest

from app.rag.ingestion import IngestionService
from app.rag.models import AccessLevel
from app.rag.repositories import InMemoryKnowledgeRepository
from app.rag.retrieval import RetrievalService
from app.rag.sources import LocalDirectorySource


def test_local_source_maps_access_directories(tmp_path: Path) -> None:
    employee = tmp_path / "employee"
    admin = tmp_path / "admin"
    employee.mkdir()
    admin.mkdir()
    (employee / "leave.md").write_text("# Urlopy\n\nTreść", encoding="utf-8")
    (employee / "policy.outdated.md").write_text("# Stara polityka", encoding="utf-8")
    (admin / "agreement.txt").write_text("Umowa", encoding="utf-8")

    documents = list(LocalDirectorySource(tmp_path).list_documents("demo"))

    assert [item.access_level for item in documents] == [
        AccessLevel.ADMIN,
        AccessLevel.EMPLOYEE,
        AccessLevel.EMPLOYEE,
    ]
    assert documents[1].title == "Urlopy"
    assert documents[2].metadata["status"] == "outdated"
    assert all(document.source_url is None for document in documents)
    assert all(str(tmp_path.resolve()) not in str(document.source_url) for document in documents)
    assert all("/app/knowledge" not in str(document.source_url) for document in documents)
    assert documents[1].metadata["relative_path"] == "employee/leave.md"


@pytest.mark.parametrize("invalid_kind", ["missing", "file"])
def test_invalid_local_source_aborts_without_deleting_existing_document(
    tmp_path: Path, invalid_kind: str
) -> None:
    valid_root = tmp_path / "valid"
    employee = valid_root / "employee"
    employee.mkdir(parents=True)
    (employee / "policy.md").write_text(
        "# Procedura\n\nAktywna instrukcja.", encoding="utf-8"
    )
    repository = InMemoryKnowledgeRepository()
    assert IngestionService(repository, LocalDirectorySource(valid_root)).run("demo").updated == 1

    invalid_root = tmp_path / "missing"
    if invalid_kind == "file":
        invalid_root.write_text("not a directory", encoding="utf-8")
    with pytest.raises((FileNotFoundError, NotADirectoryError)):
        IngestionService(repository, LocalDirectorySource(invalid_root)).run("demo")

    assert RetrievalService(repository).retrieve(
        "demo", AccessLevel.EMPLOYEE, "aktywna instrukcja"
    ).answerable


def test_existing_empty_local_source_soft_deletes_missing_documents(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    employee = source_root / "employee"
    employee.mkdir(parents=True)
    document = employee / "policy.md"
    document.write_text("# Procedura\n\nAktywna instrukcja.", encoding="utf-8")
    repository = InMemoryKnowledgeRepository()
    ingestion = IngestionService(repository, LocalDirectorySource(source_root))
    assert ingestion.run("demo").updated == 1

    document.unlink()
    assert ingestion.run("demo").deleted == 1
    assert not RetrievalService(repository).retrieve(
        "demo", AccessLevel.ADMIN, "aktywna instrukcja"
    ).answerable
