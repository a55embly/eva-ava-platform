# ADR 0003: Use local EmbeddingGemma embeddings

## Status

Accepted — 2026-08-10.

## Context

The demo needs semantic retrieval while keeping document ingestion independent
from the hosted answer model. Indexing and queries must use the same embedding
model. Changing that model must not create a new document version or citation.

## Decision

Use Ollama's local `embeddinggemma` model behind `EmbeddingProvider`. Store its
model identifier beside every chunk vector. Reindex missing vectors and vectors
made by another model in place, preserving document version and stable citation
IDs. If Ollama is unavailable, retrieval falls back explicitly to permission-
filtered keyword search and returns a warning.

The fictional demo corpus is small, so PostgreSQL performs exact cosine search.
An ANN index is deferred until measurements on a representative corpus justify
its operational and recall trade-offs.

## Consequences

- Document text used for embeddings remains on the local machine.
- Local setup must install Ollama and pull `embeddinggemma`.
- Semantic and keyword rankings are combined with Reciprocal Rank Fusion.
- A model change causes vector reindexing, not content versioning.
- Production model choice and retrieval evaluation remain customer-specific.
