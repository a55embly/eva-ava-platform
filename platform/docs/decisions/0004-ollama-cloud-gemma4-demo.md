# ADR 0004: Use Gemma 4 through Ollama Cloud for the Q&A demo

## Status

Accepted — 2026-08-10.

## Context

The interview MVP needs a replaceable answer generator without coupling the
domain and authorization layers to a provider. Ollama Cloud currently does not
support structured outputs, so correctness cannot depend on provider-generated
JSON or citations.

## Decision

Use `gemma4:31b-cloud` as the primary answer model and `gemma4:cloud` for one
fallback attempt after a timeout, HTTP 429, HTTP 502 or transport failure. The
backend passes only permission-filtered evidence, builds citations itself and
returns a deterministic Polish refusal without calling a model when there is no
evidence.

Only the repository's fictional demo corpus may be sent to Ollama Cloud. Real
company, employee and customer data are outside this demo. Tokens, API keys,
full prompts and document bodies must not be logged.

## Consequences

- The provider can be replaced through the application-level protocol.
- The demo depends on an existing Ollama account, its limits and model access;
  no automatic subscription purchase is part of the system.
- Local EmbeddingGemma remains available even though generation is hosted.
- Backend-owned citations and authorization do not rely on model compliance.
- A second provider failure becomes a generic HTTP 503 response.
