"""Behavior of the Ollama HTTP provider boundary."""

import json

import httpx
import pytest

from app.integrations.providers.ollama import (
    OllamaAnswerProvider,
    OllamaEmbeddingProvider,
    ProviderUnavailableError,
)
from app.rag.models import AccessLevel, StoredChunk


def test_embedding_provider_returns_one_vector_per_input() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        assert json.loads(request.content) == {
            "model": "embeddinggemma",
            "input": ["urlop", "praca zdalna"],
        }
        return httpx.Response(200, json={"embeddings": [[1.0, 0.0], [0.0, 1.0]]})

    provider = OllamaEmbeddingProvider(
        "http://ollama.invalid",
        "embeddinggemma",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.model_id == "embeddinggemma"
    assert provider.embed(["urlop", "praca zdalna"]) == [[1.0, 0.0], [0.0, 1.0]]


def test_answer_provider_retries_transient_failure_with_fallback_model() -> None:
    requested_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requested_models.append(payload["model"])
        if payload["model"] == "gemma4:31b-cloud":
            return httpx.Response(502, json={"error": "cloud unavailable"})
        assert "Zasady urlopu" in payload["messages"][1]["content"]
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "Złóż wniosek [1]."}},
        )

    provider = OllamaAnswerProvider(
        "http://ollama.invalid",
        "gemma4:31b-cloud",
        "gemma4:cloud",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    evidence = (
        StoredChunk(
            "citation-1",
            "Zasady urlopu",
            1,
            "Wniosek składa się w portalu.",
            "Wniosek",
            None,
            AccessLevel.EMPLOYEE,
            {},
            1.0,
        ),
    )

    assert provider.answer("Jak zgłosić urlop?", evidence) == "Złóż wniosek [1]."
    assert requested_models == ["gemma4:31b-cloud", "gemma4:cloud"]


def test_answer_provider_does_not_retry_non_transient_http_error() -> None:
    requested_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_models.append(json.loads(request.content)["model"])
        return httpx.Response(401, json={"error": "not authenticated"})

    provider = OllamaAnswerProvider(
        "http://ollama.invalid",
        "gemma4:31b-cloud",
        "gemma4:cloud",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(ProviderUnavailableError):
        provider.answer("Pytanie", ())

    assert requested_models == ["gemma4:31b-cloud"]
