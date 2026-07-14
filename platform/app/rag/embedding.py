"""Replaceable embedding boundary; no production provider is selected yet."""

from typing import Protocol


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int:
        """Return the vector dimension produced by this provider."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text in the same order."""
