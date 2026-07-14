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
