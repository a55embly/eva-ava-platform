"""PostgreSQL/pgvector implementation of the knowledge repository."""

import hashlib
import uuid
from dataclasses import replace
from typing import Any

import psycopg
from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.rag.models import AccessLevel, ChunkDraft, SourceDocument, StoredChunk
from app.rag.repositories import keyword_stems, reciprocal_rank_fusion


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
        *,
        embedding_model: str | None = None,
    ) -> bool:
        if embeddings is not None and len(embeddings) != len(chunks):
            raise ValueError("embedding count must equal chunk count")
        content_hash = hashlib.sha256(document.content.encode()).hexdigest()
        with self._connection.transaction(), self._connection.cursor() as cursor:
            cursor.execute(
                """SELECT d.id, d.title, d.access_level, d.source_url,
                          d.source_metadata, d.source_modified_at, d.is_deleted,
                          v.id AS version_id, v.version_number, v.content_sha256,
                          (SELECT bool_and(
                              c.embedding IS NOT NULL AND c.embedding_model = %s
                           ) FROM rag_chunks c WHERE c.version_id = v.id
                          ) AS embeddings_current
                FROM rag_documents d LEFT JOIN rag_document_versions v
                  ON v.document_id = d.id AND v.is_current
                WHERE d.tenant_id = %s AND d.source_name = %s AND d.source_id = %s
                FOR UPDATE OF d""",
                (
                    embedding_model,
                    document.tenant_id,
                    document.source_name,
                    document.source_id,
                ),
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
            embeddings_changed = (
                embeddings is not None
                and current is not None
                and not bool(current["embeddings_current"])
            )
            if (
                current
                and not content_changed
                and not metadata_changed
                and not current["is_deleted"]
                and not embeddings_changed
            ):
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
                assert current is not None
                if embeddings_changed:
                    for chunk, current_embedding in zip(
                        chunks, embeddings or [], strict=True
                    ):
                        cursor.execute(
                            """UPDATE rag_chunks
                               SET embedding = %s, embedding_model = %s
                               WHERE version_id = %s AND chunk_index = %s""",
                            (
                                current_embedding,
                                embedding_model,
                                current["version_id"],
                                chunk.index,
                            ),
                        )
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
                chunk_embedding = (
                    None if embeddings is None else embeddings[chunk.index]
                )
                cursor.execute(
                    """INSERT INTO rag_chunks
                        (version_id, chunk_index, content, section, citation_id,
                         embedding, embedding_model)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        version_id,
                        chunk.index,
                        chunk.content,
                        chunk.section,
                        citation_id,
                        chunk_embedding,
                        embedding_model,
                    ),
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
        self,
        tenant_id: str,
        access_level: AccessLevel,
        query: str,
        limit: int,
        *,
        query_embedding: list[float] | None = None,
        embedding_model: str | None = None,
    ) -> list[StoredChunk]:
        allowed = [AccessLevel.EMPLOYEE.value]
        if access_level is AccessLevel.ADMIN:
            allowed.append(AccessLevel.ADMIN.value)
        tsquery = " | ".join(f"{stem}:*" for stem in sorted(keyword_stems(query)))
        keyword_hits: list[StoredChunk] = []
        semantic_hits: list[StoredChunk] = []
        candidate_limit = max(limit * 2, limit)
        with self._connection.cursor() as cursor:
            if tsquery:
                cursor.execute(
                    """SELECT c.citation_id, d.title, v.version_number, c.content,
                              c.section, d.source_url, d.access_level, d.source_metadata,
                              greatest(
                                  ts_rank(c.search_vector, to_tsquery('simple', %s)),
                                  ts_rank(d.title_search_vector, to_tsquery('simple', %s))
                              ) AS score
                       FROM rag_chunks c
                       JOIN rag_document_versions v
                         ON v.id = c.version_id AND v.is_current
                       JOIN rag_documents d ON d.id = v.document_id AND NOT d.is_deleted
                       WHERE d.tenant_id = %s AND d.access_level = ANY(%s)
                         AND (c.search_vector @@ to_tsquery('simple', %s)
                              OR d.title_search_vector @@ to_tsquery('simple', %s))
                       ORDER BY score DESC, c.citation_id LIMIT %s""",
                    (
                        tsquery,
                        tsquery,
                        tenant_id,
                        allowed,
                        tsquery,
                        tsquery,
                        candidate_limit,
                    ),
                )
                keyword_hits = _stored_chunks(cursor.fetchall())
            if query_embedding is not None and embedding_model is not None:
                cursor.execute(
                    """SELECT c.citation_id, d.title, v.version_number, c.content,
                              c.section, d.source_url, d.access_level, d.source_metadata,
                              1 - (c.embedding <=> %s::vector) AS score
                       FROM rag_chunks c
                       JOIN rag_document_versions v
                         ON v.id = c.version_id AND v.is_current
                       JOIN rag_documents d ON d.id = v.document_id AND NOT d.is_deleted
                       WHERE d.tenant_id = %s AND d.access_level = ANY(%s)
                         AND c.embedding IS NOT NULL AND c.embedding_model = %s
                       ORDER BY c.embedding <=> %s::vector, c.citation_id LIMIT %s""",
                    (
                        query_embedding,
                        tenant_id,
                        allowed,
                        embedding_model,
                        query_embedding,
                        candidate_limit,
                    ),
                )
                semantic_hits = _stored_chunks(cursor.fetchall())
        return reciprocal_rank_fusion(keyword_hits, semantic_hits, limit)


class PostgresKnowledgeSearchRepository:
    """Open a short-lived PostgreSQL connection for each API retrieval."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def search(
        self,
        tenant_id: str,
        access_level: AccessLevel,
        query: str,
        limit: int,
        *,
        query_embedding: list[float] | None = None,
        embedding_model: str | None = None,
    ) -> list[StoredChunk]:
        with psycopg.connect(self._database_url) as connection:
            return PostgresKnowledgeRepository(connection).search(
                tenant_id,
                access_level,
                query,
                limit,
                query_embedding=query_embedding,
                embedding_model=embedding_model,
            )


def _stored_chunks(rows: list[dict[str, Any]]) -> list[StoredChunk]:
    return [
        replace(
            StoredChunk(
                str(row["citation_id"]),
                row["title"],
                row["version_number"],
                row["content"],
                row["section"],
                row["source_url"],
                AccessLevel(row["access_level"]),
                row["source_metadata"],
                0.0,
            ),
            score=float(row["score"]),
        )
        for row in rows
    ]
