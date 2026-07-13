# Development

## Initial prerequisites

- Python 3.12 or newer
- Docker with Compose
- PostgreSQL with pgvector, supplied by Compose

Copy `.env.example` to `.env` and provide local secrets. Never commit `.env`.

The initial commit establishes structure only. Runtime installation, dependency locking, migrations, and provider configuration will be added in focused changes with tests.
