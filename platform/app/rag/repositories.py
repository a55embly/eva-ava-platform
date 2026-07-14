"""Persistence boundary plus a deterministic in-memory implementation."""

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Protocol

from app.rag.models import AccessLevel, ChunkDraft, SourceDocument, StoredChunk

_TOKEN = re.compile(r"[\wąćęłńóśźż]+", re.IGNORECASE)


def keyword_stems(value: str) -> set[str]:
    """Return conservative prefixes for a provider-free Polish keyword fallback."""
    return {token[:5] for token in _TOKEN.findall(value.lower()) if len(token) >= 3}


class KnowledgeRepository(Protocol):
    def sync_document(
        self,
        document: SourceDocument,
        chunks: list[ChunkDraft],
        embeddings: list[list[float]] | None,
    ) -> bool: ...

    def mark_missing_deleted(
        self, tenant_id: str, source_name: str, seen_source_ids: set[str]
    ) -> int: ...

    def search(
        self, tenant_id: str, access_level: AccessLevel, query: str, limit: int
    ) -> list[StoredChunk]: ...


@dataclass
class _DocumentRecord:
    document: SourceDocument
    content_hash: str
    version: int
    chunks: list[ChunkDraft]
    embeddings: list[list[float]] | None
    deleted: bool = False


class InMemoryKnowledgeRepository:
    """Test/demo repository with the same authorization contract as PostgreSQL."""

    def __init__(self) -> None:
        self._documents: dict[tuple[str, str, str], _DocumentRecord] = {}

    def sync_document(
        self,
        document: SourceDocument,
        chunks: list[ChunkDraft],
        embeddings: list[list[float]] | None,
    ) -> bool:
        key = (document.tenant_id, document.source_name, document.source_id)
        content_hash = hashlib.sha256(document.content.encode()).hexdigest()
        existing = self._documents.get(key)
        content_changed = existing is None or existing.content_hash != content_hash
        metadata_changed = existing is None or _document_metadata(existing.document) != (
            _document_metadata(document)
        )
        if existing and not content_changed:
            if not metadata_changed and not existing.deleted:
                return False
            existing.document = document
            existing.deleted = False
            return True
        version = 1 if existing is None else existing.version + 1
        self._documents[key] = _DocumentRecord(
            document, content_hash, version, chunks, embeddings
        )
        return True

    def mark_missing_deleted(
        self, tenant_id: str, source_name: str, seen_source_ids: set[str]
    ) -> int:
        count = 0
        for (record_tenant, record_source, source_id), record in self._documents.items():
            if (
                record_tenant == tenant_id
                and record_source == source_name
                and source_id not in seen_source_ids
                and not record.deleted
            ):
                record.deleted = True
                count += 1
        return count

    def search(
        self, tenant_id: str, access_level: AccessLevel, query: str, limit: int
    ) -> list[StoredChunk]:
        query_terms = keyword_stems(query)
        hits: list[StoredChunk] = []
        for (record_tenant, _, _), record in self._documents.items():
            if record_tenant != tenant_id or record.deleted:
                continue
            if not access_level.allows(record.document.access_level):
                continue
            for chunk in record.chunks:
                terms = keyword_stems(
                    " ".join(
                        part
                        for part in (record.document.title, chunk.section, chunk.content)
                        if part
                    )
                )
                score = len(query_terms & terms) / max(len(query_terms), 1)
                if score <= 0:
                    continue
                citation_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{record_tenant}:{record.document.source_name}:"
                        f"{record.document.source_id}:{record.version}:{chunk.index}",
                    )
                )
                hits.append(
                    StoredChunk(
                        citation_id,
                        record.document.title,
                        record.version,
                        chunk.content,
                        chunk.section,
                        record.document.source_url,
                        record.document.access_level,
                        record.document.metadata,
                        score,
                    )
                )
        return sorted(
            hits,
            key=lambda hit: (
                hit.metadata.get("status") == "outdated",
                -hit.score,
                hit.citation_id,
            ),
        )[:limit]


def _document_metadata(document: SourceDocument) -> tuple[object, ...]:
    """Return source fields whose changes do not create a content version."""
    return (
        document.title,
        document.access_level,
        document.source_url,
        document.modified_at,
        document.metadata,
    )
