"""Environment-backed application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    app_env: str = "development"
    app_log_level: str = "INFO"
    database_url: str
    tenant_id: str = "demo-company"
    local_knowledge_path: str = "knowledge/demo"
    demo_employee_api_token: str = ""
    demo_admin_api_token: str = ""
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_embedding_model: str = "embeddinggemma"
    ollama_chat_model: str = "gemma4:31b-cloud"
    ollama_chat_fallback_model: str = "gemma4:cloud"
    ollama_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def psycopg_database_url(database_url: str) -> str:
    """Convert the SQLAlchemy-style URL used in config to a psycopg DSN."""
    return database_url.replace("postgresql+psycopg://", "postgresql://")
