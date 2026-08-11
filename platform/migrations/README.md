# Database migrations

`python -m worker.jobs.migrate` applies SQL files in lexical order and records
each filename in `schema_migrations`. Compose runs this command as the one-shot
`migrate` service before ingestion and API startup.

- `0001_demo_knowledge_rag.sql` enables pgvector and creates versioned
  documents, chunks, access metadata and stable citations.
- `0002_embedding_model.sql` records the embedding model for safe vector
  reindexing without changing document versions or citation IDs.

Run migrations with the schema-owner role. A failed file is not recorded and
must be fixed before rerunning. Never edit an already-applied migration; add a
new numbered file.
