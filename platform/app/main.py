"""FastAPI application entry point."""

from collections.abc import Awaitable, Callable
import logging
import re
from uuid import uuid4

import psycopg
from fastapi import FastAPI, Request, Response
from pydantic import ValidationError

from app.api.questions import create_question_router
from app.api.health import create_health_router
from app.auth.demo_tokens import DemoTokenAuthorizer
from app.config import Settings, psycopg_database_url
from app.integrations.providers.ollama import (
    OllamaAnswerProvider,
    OllamaEmbeddingProvider,
)
from app.rag.postgres_repository import PostgresKnowledgeSearchRepository
from app.rag.retrieval import RetrievalService
from app.services.answer_question import QuestionAnsweringService

_request_logger = logging.getLogger("app.requests")
_safe_request_id = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def create_app(
    authorizer: DemoTokenAuthorizer | None = None,
    question_service: QuestionAnsweringService | None = None,
    tenant_id: str = "demo-company",
    readiness_check: Callable[[], bool] | None = None,
) -> FastAPI:
    """Create the HTTP application."""
    app = FastAPI(title="Aitegrate Enterprise Chatbot")

    @app.middleware("http")
    async def correlate_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        supplied_id = request.headers.get("X-Request-ID", "")
        request_id = supplied_id if _safe_request_id.fullmatch(supplied_id) else uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        _request_logger.info(
            "request_completed request_id=%s method=%s path=%s status=%s",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
        )
        return response

    app.include_router(create_health_router(readiness_check))
    app.include_router(
        create_question_router(
            authorizer or DemoTokenAuthorizer(), question_service, tenant_id
        )
    )
    return app


def create_environment_app() -> FastAPI:
    """Build production dependencies from environment-backed settings."""
    try:
        settings = Settings()  # type: ignore[call-arg]
    except ValidationError:
        return create_app(readiness_check=lambda: False)
    database_url = psycopg_database_url(settings.database_url)
    embedding_provider = OllamaEmbeddingProvider(
        settings.ollama_base_url,
        settings.ollama_embedding_model,
        api_key=settings.ollama_api_key,
    )
    question_service = QuestionAnsweringService(
        RetrievalService(
            PostgresKnowledgeSearchRepository(database_url), embedding_provider
        ),
        OllamaAnswerProvider(
            settings.ollama_base_url,
            settings.ollama_chat_model,
            settings.ollama_chat_fallback_model,
            api_key=settings.ollama_api_key,
        ),
    )

    def database_ready() -> bool:
        with psycopg.connect(database_url, connect_timeout=2) as connection:
            return connection.execute("SELECT 1").fetchone() == (1,)

    return create_app(
        DemoTokenAuthorizer(
            settings.demo_employee_api_token, settings.demo_admin_api_token
        ),
        question_service,
        settings.tenant_id,
        database_ready,
    )


app = create_environment_app()
