# Aitegrate Enterprise Chatbot

Reusable, single-tenant company assistant platform developed by Aitegrate.

The repository is organized as an umbrella project:

- `AGENTS.md` defines product-wide decisions and operating rules;
- `platform/` contains the deployable chatbot platform;
- `notes.md` contains early product notes.

The first MVP is an internal Polish-language Telegram assistant backed by approved company documents. Hermes is a replaceable agent runtime, while authorization, RAG, document lifecycle, and audit remain in the Aitegrate backend.

See `platform/docs/architecture/project-structure.md` for the initial structure.
