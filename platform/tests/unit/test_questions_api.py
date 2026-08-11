"""HTTP behavior for the authenticated question-answering API."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import create_app
from app.auth.demo_tokens import DemoTokenAuthorizer
from app.integrations.providers.ollama import ProviderUnavailableError
from app.rag.ingestion import IngestionService
from app.rag.repositories import InMemoryKnowledgeRepository
from app.rag.retrieval import RetrievalService
from app.rag.models import AccessLevel, SourceDocument, StoredChunk
from app.services.answer_question import AnswerProvider, QuestionAnsweringService

_EMPLOYEE_TOKEN = "employee-token-that-is-at-least-32-characters"
_ADMIN_TOKEN = "administrator-token-that-is-at-least-32-characters"


class FailingAnswerProvider(AnswerProvider):
    def answer(self, question: str, evidence: tuple[StoredChunk, ...]) -> str:
        raise AssertionError("provider must not be called without evidence")


class StaticAnswerProvider(AnswerProvider):
    def answer(self, question: str, evidence: tuple[StoredChunk, ...]) -> str:
        assert question == "Jaki jest poufny budżet?"
        assert evidence[0].access_level is AccessLevel.ADMIN
        return "Budżet opisano w dokumencie administracyjnym [1]."


class UnavailableAnswerProvider(AnswerProvider):
    def answer(self, question: str, evidence: tuple[StoredChunk, ...]) -> str:
        raise ProviderUnavailableError("answer provider unavailable")


class SingleDocumentSource:
    name = "test-source"

    def __init__(self, document: SourceDocument) -> None:
        self._document = document

    def list_documents(self, tenant_id: str) -> list[SourceDocument]:
        return [self._document]


def _admin_repository() -> InMemoryKnowledgeRepository:
    repository = InMemoryKnowledgeRepository()
    item = SourceDocument(
        "demo-company",
        "test-source",
        "budget",
        "Budżet administracyjny",
        "Poufny budżet wynosi sto tysięcy złotych.",
        AccessLevel.ADMIN,
        datetime(2026, 8, 1, tzinfo=UTC),
        metadata={"status": "outdated"},
    )
    IngestionService(repository, SingleDocumentSource(item)).run("demo-company")
    return repository


def test_question_endpoint_rejects_missing_bearer_token() -> None:
    client = TestClient(create_app())

    response = client.post("/v1/questions", json={"question": "Jak zgłosić urlop?"})

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid authentication credentials"}


def test_question_without_evidence_returns_safe_answer_without_calling_model() -> None:
    service = QuestionAnsweringService(
        RetrievalService(InMemoryKnowledgeRepository()), FailingAnswerProvider()
    )
    client = TestClient(
        create_app(
            authorizer=DemoTokenAuthorizer(employee_token=_EMPLOYEE_TOKEN),
            question_service=service,
            tenant_id="demo-company",
        )
    )

    response = client.post(
        "/v1/questions",
        headers={"Authorization": f"Bearer {_EMPLOYEE_TOKEN}"},
        json={"question": "Jaka jest polityka podróży na Marsa?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Nie znalazłem wystarczających informacji w zatwierdzonych dokumentach.",
        "answerable": False,
        "citations": [],
        "warnings": [],
    }


def test_employee_cannot_retrieve_admin_evidence_but_admin_can() -> None:
    repository = _admin_repository()
    authorizer = DemoTokenAuthorizer(_EMPLOYEE_TOKEN, _ADMIN_TOKEN)
    employee_client = TestClient(
        create_app(
            authorizer,
            QuestionAnsweringService(RetrievalService(repository), FailingAnswerProvider()),
        )
    )
    admin_client = TestClient(
        create_app(
            authorizer,
            QuestionAnsweringService(RetrievalService(repository), StaticAnswerProvider()),
        )
    )

    employee = employee_client.post(
        "/v1/questions",
        headers={"Authorization": f"Bearer {_EMPLOYEE_TOKEN}"},
        json={"question": "Jaki jest poufny budżet?"},
    )
    admin = admin_client.post(
        "/v1/questions",
        headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"},
        json={"question": "Jaki jest poufny budżet?"},
    )

    assert employee.json()["answerable"] is False
    assert employee.json()["citations"] == []
    assert admin.status_code == 200
    assert admin.json()["answerable"] is True
    assert admin.json()["citations"][0]["document_title"] == "Budżet administracyjny"
    assert "outdated" in admin.json()["warnings"][0]


def test_provider_failure_returns_service_unavailable_without_details() -> None:
    client = TestClient(
        create_app(
            DemoTokenAuthorizer(admin_token=_ADMIN_TOKEN),
            QuestionAnsweringService(
                RetrievalService(_admin_repository()), UnavailableAnswerProvider()
            ),
        ),
        raise_server_exceptions=False,
    )

    response = client.post(
        "/v1/questions",
        headers={"Authorization": f"Bearer {_ADMIN_TOKEN}"},
        json={"question": "Jaki jest poufny budżet?"},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "answer provider unavailable"}
