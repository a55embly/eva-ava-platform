"""Authenticated question-answering HTTP endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.auth.demo_tokens import DemoTokenAuthorizer, Principal
from app.integrations.providers.ollama import ProviderUnavailableError
from app.services.answer_question import QuestionAnsweringService

_bearer = HTTPBearer(auto_error=False)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


def create_question_router(
    authorizer: DemoTokenAuthorizer,
    question_service: QuestionAnsweringService | None = None,
    tenant_id: str = "demo-company",
) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["questions"])

    def authenticate(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> Principal:
        principal = None
        if credentials is not None and credentials.scheme.lower() == "bearer":
            principal = authorizer.authorize(credentials.credentials)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return principal

    @router.post("/questions")
    async def answer_question(
        request: QuestionRequest,
        principal: Annotated[Principal, Depends(authenticate)],
    ) -> dict[str, object]:
        if question_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="question service unavailable",
            )
        try:
            result = question_service.ask(
                tenant_id, principal.access_level, request.question
            )
        except ProviderUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="answer provider unavailable",
            ) from exc
        return {
            "answer": result.answer,
            "answerable": result.answerable,
            "citations": [
                {
                    "citation_id": citation.citation_id,
                    "document_title": citation.document_title,
                    "document_version": citation.document_version,
                    "section": citation.section,
                    "supporting_snippet": citation.supporting_snippet,
                    "source_url": citation.source_url,
                }
                for citation in result.citations
            ],
            "warnings": list(result.warnings),
        }

    return router
