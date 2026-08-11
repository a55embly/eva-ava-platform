"""Persistence boundary plus a deterministic in-memory implementation."""

import hashlib
import math
import re
import uuid
from dataclasses import dataclass, replace
from typing import Protocol

from app.rag.models import AccessLevel, ChunkDraft, SourceDocument, StoredChunk

_TOKEN = re.compile(r"[\wąćęłńóśźż]+", re.IGNORECASE)


def keyword_stems(value: str) -> set[str]:
    """Return conservative prefixes for a provider-free Polish keyword fallback."""
    return {token[:5] for token in _TOKEN.findall(value.lower()) if len(token) >= 3}


class KnowledgeSearchRepository(Protocol):
    def search(
        self,
        tenant_id: str,
        access_level: AccessLevel,
        query: str,
        limit: int,
        *,
        query_embedding: list[float] | None = None,
        embedding_model: str | None = None,
    ) -> list[StoredChunk]: ...


class KnowledgeRepository(KnowledgeSearchRepository, Protocol):
    def sync_document(
        self,
        document: SourceDocument,
        chunks: list[ChunkDraft],
        embeddings: list[list[float]] | None,
        *,
        embedding_model: str | None = None,
    ) -> bool: ...

    def mark_missing_deleted(
        self, tenant_id: str, source_name: str, seen_source_ids: set[str]
    ) -> int: ...

@dataclass
class _DocumentRecord:
    document: SourceDocument
    content_hash: str
    version: int
    chunks: list[ChunkDraft]
    embeddings: list[list[float]] | None
    embedding_model: str | None
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
        *,
        embedding_model: str | None = None,
    ) -> bool:
        key = (document.tenant_id, document.source_name, document.source_id)
        content_hash = hashlib.sha256(document.content.encode()).hexdigest()
        existing = self._documents.get(key)
        content_changed = existing is None or existing.content_hash != content_hash
        metadata_changed = existing is None or _document_metadata(existing.document) != (
            _document_metadata(document)
        )
        embeddings_changed = (
            embeddings is not None
            and existing is not None
            and (
                existing.embeddings is None
                or existing.embedding_model != embedding_model
            )
        )
        if existing and not content_changed:
            if embeddings_changed:
                existing.embeddings = embeddings
                existing.embedding_model = embedding_model
            if not metadata_changed and not existing.deleted:
                return embeddings_changed
            existing.document = document
            existing.deleted = False
            return True
        version = 1 if existing is None else existing.version + 1
        self._documents[key] = _DocumentRecord(
            document, content_hash, version, chunks, embeddings, embedding_model
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
        self,
        tenant_id: str,
        access_level: AccessLevel,
        query: str,
        limit: int,
        *,
        query_embedding: list[float] | None = None,
        embedding_model: str | None = None,
    ) -> list[StoredChunk]:
        query_terms = keyword_stems(query)
        keyword_hits: list[StoredChunk] = []
        semantic_hits: list[StoredChunk] = []
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
                keyword_score = len(query_terms & terms) / max(len(query_terms), 1)
                citation_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"{record_tenant}:{record.document.source_name}:"
                        f"{record.document.source_id}:{record.version}:{chunk.index}",
                    )
                )
                hit = StoredChunk(
                    citation_id,
                    record.document.title,
                    record.version,
                    chunk.content,
                    chunk.section,
                    record.document.source_url,
                    record.document.access_level,
                    record.document.metadata,
                    keyword_score,
                )
                if keyword_score > 0:
                    keyword_hits.append(hit)
                if (
                    query_embedding is not None
                    and embedding_model is not None
                    and record.embedding_model == embedding_model
                    and record.embeddings is not None
                ):
                    semantic_score = _cosine_similarity(
                        query_embedding, record.embeddings[chunk.index]
                    )
                    semantic_hits.append(replace(hit, score=semantic_score))
        return reciprocal_rank_fusion(keyword_hits, semantic_hits, limit)


def _document_metadata(document: SourceDocument) -> tuple[object, ...]:
    """Return source fields whose changes do not create a content version."""
    return (
        document.title,
        document.access_level,
        document.source_url,
        document.modified_at,
        document.metadata,
    )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    return 0.0 if denominator == 0 else sum(a * b for a, b in zip(left, right)) / denominator


def reciprocal_rank_fusion(
    keyword_hits: list[StoredChunk], semantic_hits: list[StoredChunk], limit: int
) -> list[StoredChunk]:
    scores: dict[str, float] = {}
    candidates: dict[str, StoredChunk] = {}
    for ranked in (
        sorted(keyword_hits, key=lambda hit: (-hit.score, hit.citation_id)),
        sorted(semantic_hits, key=lambda hit: (-hit.score, hit.citation_id)),
    ):
        for rank, hit in enumerate(ranked, start=1):
            candidates[hit.citation_id] = hit
            scores[hit.citation_id] = scores.get(hit.citation_id, 0.0) + 1 / (60 + rank)
    fused = [replace(hit, score=scores[citation_id]) for citation_id, hit in candidates.items()]
    return sorted(
        fused,
        key=lambda hit: (
            hit.metadata.get("status") == "outdated",
            -hit.score,
            hit.citation_id,
        ),
    )[:limit]
