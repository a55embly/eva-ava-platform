"""PostgreSQL/pgvector implementation of the knowledge repository."""

import hashlib
import uuid
from typing import Any

from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.rag.models import AccessLevel, ChunkDraft, SourceDocument, StoredChunk
from app.rag.repositories import keyword_stems


class PostgresKnowledgeRepository:
    def __init__(self, connection: Connection[Any]) -> None:
        self._connection = connection
        self._connection.row_factory = dict_row
        register_vector(self._connection)

    def sync_document(
        self,
        document: SourceDocument,
        chunks: list[ChunkDraft],
        embeddings: list[list[float]] | None,
    ) -> bool:
        if embeddings is not None and len(embeddings) != len(chunks):
            raise ValueError("embedding count must equal chunk count")
        content_hash = hashlib.sha256(document.content.encode()).hexdigest()
        with self._connection.transaction(), self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT d.id, d.title, d.access_level, d.source_url,
                          d.source_metadata, d.source_modified_at, d.is_deleted,
                          v.version_number, v.content_sha256
                FROM rag_documents d LEFT JOIN rag_document_versions v
                  ON v.document_id = d.id AND v.is_current
                WHERE d.tenant_id = %s AND d.source_name = %s AND d.source_id = %s
                FOR UPDATE OF d""",
                (document.tenant_id, document.source_name, document.source_id),
            )
            current = cursor.fetchone()
            content_changed = current is None or current["content_sha256"] != content_hash
            metadata_changed = current is None or any(
                (
                    current["title"] != document.title,
                    current["access_level"] != document.access_level.value,
                    current["source_url"] != document.source_url,
                    current["source_metadata"] != document.metadata,
                    current["source_modified_at"] != document.modified_at,
                )
            )
            if current and not content_changed and not metadata_changed and not current["is_deleted"]:
                return False
            next_version = 1 if current is None else int(current["version_number"] or 0) + 1
            cursor.execute(
                """INSERT INTO rag_documents
                    (tenant_id, source_name, source_id, title, access_level,
                     source_url, source_metadata, source_modified_at, is_deleted)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, false)
                ON CONFLICT (tenant_id, source_name, source_id) DO UPDATE SET
                    title = EXCLUDED.title, access_level = EXCLUDED.access_level,
                    source_url = EXCLUDED.source_url,
                    source_metadata = EXCLUDED.source_metadata,
                    source_modified_at = EXCLUDED.source_modified_at,
                    is_deleted = false, updated_at = now()
                RETURNING id""",
                (
                    document.tenant_id,
                    document.source_name,
                    document.source_id,
                    document.title,
                    document.access_level.value,
                    document.source_url,
                    Jsonb(document.metadata),
                    document.modified_at,
                ),
            )
            document_row = cursor.fetchone()
            if document_row is None:
                raise RuntimeError("document upsert returned no identifier")
            document_id = document_row["id"]
            if not content_changed:
                return True
            cursor.execute(
                "UPDATE rag_document_versions SET is_current = false "
                "WHERE document_id = %s AND is_current",
                (document_id,),
            )
            cursor.execute(
                """INSERT INTO rag_document_versions
                    (document_id, version_number, content_sha256, is_current)
                VALUES (%s, %s, %s, true) RETURNING id""",
                (document_id, next_version, content_hash),
            )
            version_row = cursor.fetchone()
            if version_row is None:
                raise RuntimeError("version insert returned no identifier")
            version_id = version_row["id"]
            for chunk in chunks:
                citation_id = uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{document.tenant_id}:{document.source_name}:"
                    f"{document.source_id}:{next_version}:{chunk.index}",
                )
                embedding = None if embeddings is None else embeddings[chunk.index]
                cursor.execute(
                    """INSERT INTO rag_chunks
                        (version_id, chunk_index, content, section, citation_id, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s)""",
                    (version_id, chunk.index, chunk.content, chunk.section, citation_id, embedding),
                )
        return True

    def mark_missing_deleted(
        self, tenant_id: str, source_name: str, seen_source_ids: set[str]
    ) -> int:
        with self._connection.transaction(), self._connection.cursor() as cursor:
            cursor.execute(
                """UPDATE rag_documents SET is_deleted = true, updated_at = now()
                WHERE tenant_id = %s AND source_name = %s AND NOT is_deleted
                  AND NOT (source_id = ANY(%s))""",
                (tenant_id, source_name, sorted(seen_source_ids)),
            )
            return cursor.rowcount

    def search(
        self, tenant_id: str, access_level: AccessLevel, query: str, limit: int
    ) -> list[StoredChunk]:
        allowed = [AccessLevel.EMPLOYEE.value]
        if access_level is AccessLevel.ADMIN:
            allowed.append(AccessLevel.ADMIN.value)
        tsquery = " | ".join(f"{stem}:*" for stem in sorted(keyword_stems(query)))
        if not tsquery:
            return []
        with self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT c.citation_id, d.title, v.version_number, c.content, c.section,
                       d.source_url, d.access_level, d.source_metadata,
                       greatest(
                           ts_rank(c.search_vector, to_tsquery('simple', %s)),
                           ts_rank(d.title_search_vector, to_tsquery('simple', %s))
                       ) AS score
                FROM rag_chunks c
                JOIN rag_document_versions v ON v.id = c.version_id AND v.is_current
                JOIN rag_documents d ON d.id = v.document_id AND NOT d.is_deleted
                WHERE d.tenant_id = %s AND d.access_level = ANY(%s)
                  AND (c.search_vector @@ to_tsquery('simple', %s)
                       OR d.title_search_vector @@ to_tsquery('simple', %s))
                ORDER BY (
                             coalesce(d.source_metadata->>'status', '') = 'outdated'
                         ) ASC,
                         score DESC, c.citation_id LIMIT %s""",
                (tsquery, tsquery, tenant_id, allowed, tsquery, tsquery, limit),
            )
            return [
                StoredChunk(
                    str(row["citation_id"]), row["title"], row["version_number"],
                    row["content"], row["section"], row["source_url"],
                    AccessLevel(row["access_level"]), row["source_metadata"],
                    float(row["score"]),
                )
                for row in cursor.fetchall()
            ]
