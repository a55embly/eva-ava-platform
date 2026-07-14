# ADR 0003: Embedding provider remains unselected

## Status

Proposed — decision required.

## Context

The demo RAG stores optional pgvector embeddings behind an `EmbeddingProvider`
interface. Keyword retrieval works without embeddings, so selecting cost,
privacy and operational trade-offs is not required to validate authorization,
versioning and citations.

## Options

1. Hosted embeddings API: simplest operations and usually strongest baseline,
   but introduces per-use cost and sends fictional document text to a provider.
2. Small local embedding model: keeps data local and avoids per-call fees, but
   adds model files, inference dependencies and resource ownership.
3. Compatible customer-managed endpoint: preserves the interface and may fit
   production governance, but requires an endpoint contract and operations.

No option is selected in this feature. Vector dimensionality remains open until
the owner approves a provider and evaluation criteria.

Selecting and enabling a provider will require an explicit reindexing mechanism.
Documents ingested without embeddings are not automatically rebuilt merely
because an embedding provider is configured later.
