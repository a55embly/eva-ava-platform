"""Permission-aware retrieval use case."""

from app.rag.embedding import EmbeddingProvider, EmbeddingProviderError
from app.rag.models import AccessLevel, Citation, RetrievalResponse
from app.rag.repositories import KnowledgeSearchRepository


class RetrievalService:
    def __init__(
        self,
        repository: KnowledgeSearchRepository,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._repository = repository
        self._embedding_provider = embedding_provider

    def retrieve(
        self, tenant_id: str, access_level: AccessLevel, query: str, *, limit: int = 5
    ) -> RetrievalResponse:
        if not query.strip():
            raise ValueError("query cannot be empty")
        query_embedding = None
        embedding_model = None
        provider_warnings: tuple[str, ...] = ()
        if self._embedding_provider is not None:
            try:
                vectors = self._embedding_provider.embed([query])
                if len(vectors) != 1:
                    raise EmbeddingProviderError("query embedding count mismatch")
                query_embedding = vectors[0]
                embedding_model = self._embedding_provider.model_id
            except EmbeddingProviderError:
                provider_warnings = (
                    "Wyszukiwanie semantyczne jest niedostępne; użyto wyszukiwania słów kluczowych.",
                )
        evidence = tuple(
            self._repository.search(
                tenant_id,
                access_level,
                query,
                limit,
                query_embedding=query_embedding,
                embedding_model=embedding_model,
            )
        )
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
        warnings = provider_warnings + tuple(
            f"Źródło oznaczone jako {hit.metadata['status']}: {hit.document_title}"
            for hit in evidence
            if hit.metadata.get("status") in {"outdated", "conflicting"}
        )
        return RetrievalResponse(query, evidence, citations, bool(evidence), warnings)
