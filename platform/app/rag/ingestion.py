"""Idempotent ingestion use case."""

from dataclasses import dataclass

from app.rag.chunking import chunk_document
from app.rag.embedding import EmbeddingProvider
from app.rag.repositories import KnowledgeRepository
from app.rag.sources import KnowledgeSource


@dataclass(frozen=True)
class IngestionReport:
    scanned: int
    updated: int
    unchanged: int
    deleted: int


class IngestionService:
    def __init__(
        self,
        repository: KnowledgeRepository,
        source: KnowledgeSource,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._repository = repository
        self._source = source
        self._embedding_provider = embedding_provider

    def run(self, tenant_id: str) -> IngestionReport:
        documents = list(self._source.list_documents(tenant_id))
        seen: set[str] = set()
        for document in documents:
            if document.tenant_id != tenant_id:
                raise ValueError(
                    "knowledge source returned a document for a different tenant"
                )
            if document.source_name != self._source.name:
                raise ValueError(
                    "knowledge source returned a document with a different source name"
                )
            if document.source_id in seen:
                raise ValueError(
                    f"knowledge source returned duplicate source_id: {document.source_id}"
                )
            seen.add(document.source_id)

        scanned = updated = 0
        for document in documents:
            chunks = chunk_document(document.content)
            embeddings = None
            if self._embedding_provider is not None:
                embeddings = self._embedding_provider.embed([chunk.content for chunk in chunks])
                if len(embeddings) != len(chunks):
                    raise ValueError("embedding provider returned a mismatched vector count")
            if self._repository.sync_document(document, chunks, embeddings):
                updated += 1
            scanned += 1
        deleted = self._repository.mark_missing_deleted(tenant_id, self._source.name, seen)
        return IngestionReport(scanned, updated, scanned - updated, deleted)
