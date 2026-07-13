"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.health import router as health_router


def create_app() -> FastAPI:
    """Create the HTTP application."""
    app = FastAPI(title="Aitegrate Enterprise Chatbot")
    app.include_router(health_router)
    return app


app = create_app()
