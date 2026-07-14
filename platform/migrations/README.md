# Database migrations

Apply migrations in lexical order with a role that owns the application schema.

`0001_demo_knowledge_rag.sql` enables pgvector and creates versioned documents,
chunks, access metadata and stable citation identifiers. Vector dimensionality
is intentionally not constrained until an embedding provider is selected.

Migrations are applied once to each database. A dedicated migration runner and
history table will track applied migrations before production rollout; until
then, use a disposable database or schema when verifying migration changes.
