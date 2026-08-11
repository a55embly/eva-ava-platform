BEGIN;

ALTER TABLE rag_chunks
    ADD COLUMN IF NOT EXISTS embedding_model text;

COMMIT;
