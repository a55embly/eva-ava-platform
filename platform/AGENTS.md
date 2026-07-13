# Platform-specific agent instructions

These instructions refine the parent `AGENTS.md` for files inside `platform/`.

## Architecture

- Keep this MVP a modular monolith.
- Telegram handlers call application services instead of databases, RAG, Hermes, or Honcho directly.
- Backend authorization runs before document retrieval or tool execution.
- Treat Hermes, Honcho, Google Drive, Telegram, and model providers as replaceable integrations.
- Do not place customer-specific behavior in shared Python code.
- Keep runtime data and secrets outside Git.

## Module boundaries

- `app/api/` exposes HTTP endpoints.
- `app/auth/` owns identity, roles, and authorization.
- `app/rag/` owns ingestion, retrieval, citations, and document lifecycle.
- `app/conversations/` owns sessions and retention-aware conversation state.
- `app/services/` coordinates application use cases.
- `app/integrations/` contains external-system adapters.
- `app/repositories/` provides persistence boundaries.
- `worker/` runs asynchronous synchronization and retention jobs.

## Quality

- Use English in code and developer documentation.
- Test authorization and data isolation before happy paths.
- Do not create empty abstractions speculatively.
- Keep provider-specific models out of application services.
