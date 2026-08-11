"""Orchestrate the authorized question-answering flow."""

from dataclasses import dataclass
from typing import Protocol

from app.rag.models import AccessLevel, Citation, StoredChunk
from app.rag.retrieval import RetrievalService

_NO_EVIDENCE_ANSWER = (
    "Nie znalazłem wystarczających informacji w zatwierdzonych dokumentach."
)


class AnswerProvider(Protocol):
    """Generate an answer from already-authorized evidence."""

    def answer(self, question: str, evidence: tuple[StoredChunk, ...]) -> str: ...


@dataclass(frozen=True)
class QuestionAnswer:
    answer: str
    answerable: bool
    citations: tuple[Citation, ...]
    warnings: tuple[str, ...]


class QuestionAnsweringService:
    """Retrieve authorized evidence before invoking a replaceable model provider."""

    def __init__(
        self, retrieval: RetrievalService, answer_provider: AnswerProvider
    ) -> None:
        self._retrieval = retrieval
        self._answer_provider = answer_provider

    def ask(
        self, tenant_id: str, access_level: AccessLevel, question: str
    ) -> QuestionAnswer:
        retrieval = self._retrieval.retrieve(tenant_id, access_level, question)
        if not retrieval.answerable:
            return QuestionAnswer(_NO_EVIDENCE_ANSWER, False, (), retrieval.warnings)
        answer = self._answer_provider.answer(question, retrieval.evidence)
        return QuestionAnswer(answer, True, retrieval.citations, retrieval.warnings)
