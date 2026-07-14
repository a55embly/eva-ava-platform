"""Deterministic text chunking for local demo documents."""

import re

from app.rag.models import ChunkDraft

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$")


def chunk_document(content: str, *, max_chars: int = 900) -> list[ChunkDraft]:
    if max_chars < 100:
        raise ValueError("max_chars must be at least 100")
    chunks: list[ChunkDraft] = []
    section: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        text = "\n\n".join(buffer).strip()
        if text:
            chunks.append(ChunkDraft(len(chunks), text, section))
        buffer.clear()

    for block in re.split(r"\n\s*\n", content.replace("\r\n", "\n")):
        block = block.strip()
        if not block:
            continue
        heading = _HEADING.match(block)
        if heading:
            flush()
            section = heading.group(1)
            continue
        if buffer and len("\n\n".join((*buffer, block))) > max_chars:
            flush()
        if len(block) <= max_chars:
            buffer.append(block)
            continue
        flush()
        for start in range(0, len(block), max_chars):
            part = block[start : start + max_chars].strip()
            if part:
                chunks.append(ChunkDraft(len(chunks), part, section))
    flush()
    return chunks
