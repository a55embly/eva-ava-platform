"""Replaceable embedding boundary; no production provider is selected yet."""

from typing import Protocol


class EmbeddingProviderError(RuntimeError):
    """Raised when embeddings cannot be generated safely."""


class EmbeddingProvider(Protocol):
    @property
    def model_id(self) -> str:
        """Return the stable model identifier used for reindex decisions."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text in the same order."""
