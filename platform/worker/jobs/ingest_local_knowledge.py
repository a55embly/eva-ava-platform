"""One-shot local knowledge ingestion command for the fictional demo."""

from pathlib import Path

import psycopg

from app.config import Settings, psycopg_database_url
from app.integrations.providers.ollama import OllamaEmbeddingProvider
from app.rag.ingestion import IngestionService
from app.rag.postgres_repository import PostgresKnowledgeRepository
from app.rag.sources import LocalDirectorySource


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]  # populated by pydantic-settings
    database_url = psycopg_database_url(settings.database_url)
    with psycopg.connect(database_url) as connection:
        report = IngestionService(
            PostgresKnowledgeRepository(connection),
            LocalDirectorySource(Path(settings.local_knowledge_path)),
            OllamaEmbeddingProvider(
                settings.ollama_base_url,
                settings.ollama_embedding_model,
                api_key=settings.ollama_api_key,
            ),
        ).run(settings.tenant_id)
    print(
        f"knowledge ingestion: scanned={report.scanned} updated={report.updated} "
        f"unchanged={report.unchanged} deleted={report.deleted}"
    )


if __name__ == "__main__":
    main()
