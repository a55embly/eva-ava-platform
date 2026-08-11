"""Provider-neutral domain models for permission-aware knowledge retrieval."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class AccessLevel(StrEnum):
    """Document access levels supported by the first demo."""

    EMPLOYEE = "employee"
    ADMIN = "admin"

    def allows(self, required: "AccessLevel") -> bool:
        return self is AccessLevel.ADMIN or required is AccessLevel.EMPLOYEE


@dataclass(frozen=True)
class SourceDocument:
    tenant_id: str
    source_name: str
    source_id: str
    title: str
    content: str
    access_level: AccessLevel
    modified_at: datetime
    source_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkDraft:
    index: int
    content: str
    section: str | None


@dataclass(frozen=True)
class StoredChunk:
    citation_id: str
    document_title: str
    document_version: int
    content: str
    section: str | None
    source_url: str | None
    access_level: AccessLevel
    metadata: dict[str, Any]
    score: float


@dataclass(frozen=True)
class Citation:
    citation_id: str
    document_title: str
    document_version: int
    section: str | None
    supporting_snippet: str
    source_url: str | None


@dataclass(frozen=True)
class RetrievalResponse:
    query: str
    evidence: tuple[StoredChunk, ...]
    citations: tuple[Citation, ...]
    answerable: bool
    warnings: tuple[str, ...] = ()
