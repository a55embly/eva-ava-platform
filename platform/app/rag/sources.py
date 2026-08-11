"""Knowledge source adapters."""

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.rag.models import AccessLevel, SourceDocument


class KnowledgeSource(Protocol):
    @property
    def name(self) -> str: ...

    def list_documents(self, tenant_id: str) -> Iterable[SourceDocument]: ...


class LocalDirectorySource:
    """Read Markdown and TXT files from employee/admin subdirectories."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    @property
    def name(self) -> str:
        return "local-files"

    def list_documents(self, tenant_id: str) -> Iterable[SourceDocument]:
        if not self._root.exists():
            raise FileNotFoundError(f"knowledge source directory does not exist: {self._root}")
        if not self._root.is_dir():
            raise NotADirectoryError(f"knowledge source path is not a directory: {self._root}")
        for path in sorted(self._root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
                continue
            relative = path.relative_to(self._root)
            content = path.read_text(encoding="utf-8")
            metadata = {"relative_path": relative.as_posix()}
            for marker in ("outdated", "conflicting"):
                if marker in path.stem.lower().split("."):
                    metadata["status"] = marker
            yield SourceDocument(
                tenant_id=tenant_id,
                source_name=self.name,
                source_id=relative.as_posix(),
                title=self._title(content, path.stem),
                content=content,
                access_level=self._access_for(relative),
                modified_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
                source_url=None,
                metadata=metadata,
            )

    @staticmethod
    def _access_for(relative: Path) -> AccessLevel:
        if not relative.parts:
            raise ValueError("document path has no access directory")
        try:
            return AccessLevel(relative.parts[0].lower())
        except ValueError as exc:
            raise ValueError(f"unsupported access directory: {relative.parts[0]}") from exc

    @staticmethod
    def _title(content: str, fallback: str) -> str:
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return fallback.replace("_", " ").title()
