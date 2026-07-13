# Project structure

The MVP uses a small modular monolith. It favors delivery speed while preserving boundaries needed for a later move to domain-oriented modules.

```text
platform/
├── app/
│   ├── api/
│   ├── auth/
│   ├── conversations/
│   ├── integrations/
│   │   ├── google_drive/
│   │   ├── hermes/
│   │   ├── honcho/
│   │   ├── providers/
│   │   └── telegram/
│   ├── models/
│   ├── rag/
│   ├── repositories/
│   └── services/
├── worker/
├── hermes/
├── migrations/
├── deployments/
├── tests/
└── docs/
```

## Request flow

`channel -> application service -> authorization -> retrieval/tool -> agent -> response`

Channel adapters never access persistence, RAG, or Hermes directly. Application services coordinate use cases. Authorization filters data before it reaches a model.

## Migration path

If the codebase grows, each feature directory can be split into `domain/`, `application/`, and `infrastructure/` without changing the external API. Consider that migration after adding another channel, the external bot, complex departmental permissions, or several concurrent development teams.
