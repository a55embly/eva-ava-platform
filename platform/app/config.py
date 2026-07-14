"""Environment-backed application configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    app_env: str = "development"
    app_log_level: str = "INFO"
    database_url: str
    tenant_id: str = "demo-company"
    local_knowledge_path: str = "knowledge/demo"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
