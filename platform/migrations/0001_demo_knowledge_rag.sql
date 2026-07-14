BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL,
    source_name text NOT NULL,
    source_id text NOT NULL,
    title text NOT NULL,
    title_search_vector tsvector GENERATED ALWAYS AS
        (to_tsvector('simple', title)) STORED,
    access_level text NOT NULL CHECK (access_level IN ('employee', 'admin')),
    source_url text,
    source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_modified_at timestamptz NOT NULL,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, source_name, source_id)
);

CREATE TABLE rag_document_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES rag_documents(id) ON DELETE CASCADE,
    version_number integer NOT NULL CHECK (version_number > 0),
    content_sha256 text NOT NULL CHECK (length(content_sha256) = 64),
    is_current boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, version_number)
);

CREATE UNIQUE INDEX rag_one_current_version
    ON rag_document_versions(document_id) WHERE is_current;

CREATE TABLE rag_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id uuid NOT NULL REFERENCES rag_document_versions(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL CHECK (chunk_index >= 0),
    content text NOT NULL CHECK (length(content) > 0),
    section text,
    citation_id uuid NOT NULL UNIQUE,
    embedding vector,
    search_vector tsvector GENERATED ALWAYS AS
        (to_tsvector('simple', coalesce(section, '') || ' ' || content)) STORED,
    UNIQUE (version_id, chunk_index)
);

CREATE INDEX rag_documents_access
    ON rag_documents(tenant_id, access_level) WHERE NOT is_deleted;
CREATE INDEX rag_documents_title_search
    ON rag_documents USING gin(title_search_vector);
CREATE INDEX rag_chunks_search ON rag_chunks USING gin(search_vector);

COMMIT;
