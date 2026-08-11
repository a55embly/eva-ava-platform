# Development

## Initial prerequisites

- Python 3.12 or newer
- Docker with Compose
- PostgreSQL with pgvector, supplied by Compose

Copy `.env.example` to `.env` and provide local secrets. Never commit `.env`.

## Dependency locking

The general application dependency lock remains a separate platform task. The
Hermes contract spike backend has a deliberately narrow, cross-platform exact
lock in `requirements-hermes-spike.lock`. Its Dockerfile installs only that
resolved FastAPI/Uvicorn closure instead of resolving the unconstrained project
dependencies during every build. Package names and versions are platform
independent; pip selects the matching Linux or Windows wheel for the exact
version.

When upgrading the spike backend, resolve its direct dependencies in a clean
Python 3.12 environment, update the complete closure in the lock, install it on
both Windows and Linux, and rerun the contract suite plus the Docker build. Do
not replace this lock with a workstation-wide `pip freeze`.

The idempotent Hermes config helper uses `PyYAML==6.0.3`, matching the pinned
upstream release. Developer type checking also pins the corresponding
`types-PyYAML` package in `pyproject.toml`.

## Hermes contract verification

Set `HERMES_SOURCE_ROOT` to a clean checkout at commit
`3c231eb3979ab9c57d5cd6d02f1d577a3b718b43`, then run:

    pytest tests/contract -q

The upstream tests verify the checkout commit, gateway hook ordering, session
and task identifiers, end-hook arguments, both ContextVar executor bridges and
real pinned `ToolRegistry.dispatch` without invoking a model.

## Demo knowledge ingestion

Install Ollama, sign in to the account used for cloud models and make the local
embedding model available:

    ollama signin
    ollama pull embeddinggemma
    ollama pull gemma4:31b-cloud
    ollama pull gemma4:cloud

Copy `.env.example` to `.env`, replace both demo tokens with different random
values of at least 32 characters, then start the complete stack:

    docker compose up --build

Compose waits for PostgreSQL, applies every migration once, ingests the
fictional Markdown corpus once and starts the API. The containers reach the
host Ollama process through the configurable `OLLAMA_BASE_URL`, which defaults
to `http://host.docker.internal:11434`.

Without Compose, apply migrations and import the corpus with:

    python -m worker.jobs.migrate

    python -m worker.jobs.ingest_local_knowledge

Both commands are idempotent. Ingestion versions changed documents, marks
missing local documents as deleted and reindexes vectors made by another model
without changing the document version or citation ID.

## Q&A demo

Check process and dependency health:

    curl http://127.0.0.1:8000/health/live
    curl http://127.0.0.1:8000/health/ready

Ask an employee-visible question using the token from `.env`:

    curl -X POST http://127.0.0.1:8000/v1/questions \
      -H "Authorization: Bearer <employee-token>" \
      -H "Content-Type: application/json" \
      -d '{"question":"Jak zgłosić urlop?"}'

Repeat with the admin token and a question about the fictional service
agreement to demonstrate role isolation. Authentication happens before
retrieval. Citations and stale/conflicting-source warnings are backend-owned.

Stop containers without deleting the persistent database:

    docker compose down

Use `docker compose down --volumes` only when deliberately resetting all local
demo data.
