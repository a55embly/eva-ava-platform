"""Permission-aware retrieval use case."""

from app.rag.models import AccessLevel, Citation, RetrievalResponse
from app.rag.repositories import KnowledgeRepository


class RetrievalService:
    def __init__(self, repository: KnowledgeRepository) -> None:
        self._repository = repository

    def retrieve(
        self, tenant_id: str, access_level: AccessLevel, query: str, *, limit: int = 5
    ) -> RetrievalResponse:
        if not query.strip():
            raise ValueError("query cannot be empty")
        evidence = tuple(self._repository.search(tenant_id, access_level, query, limit))
        citations = tuple(
            Citation(
                hit.citation_id,
                hit.document_title,
                hit.document_version,
                hit.section,
                hit.content[:240],
                hit.source_url,
            )
            for hit in evidence
        )
        warnings = tuple(
            f"Źródło oznaczone jako {hit.metadata['status']}: {hit.document_title}"
            for hit in evidence
            if hit.metadata.get("status") in {"outdated", "conflicting"}
        )
        return RetrievalResponse(query, evidence, citations, bool(evidence), warnings)
