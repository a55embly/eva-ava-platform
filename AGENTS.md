# Aitegrate Enterprise Chatbot — Agent Instructions

## 1. Purpose and ownership

This repository contains Aitegrate's reusable enterprise chatbot product. Keep the technical core standardized so a new company can be deployed in one to two weeks, with customer-specific work limited mainly to configuration, documents, permissions, branding, prompts, and evaluation.

Maksymilian is currently the sole CEO/CTO and final decision-maker. Consult him before decisions that materially affect product scope, architecture, cost, security, privacy/RODO, production deployment, external systems, or real customer data.

## 2. Product direction

The long-term product is one branded package supporting three authorization contexts:

- external customer;
- authenticated employee;
- administrator.

These are authorization contexts, not merely prompt personas. The backend must identify the user and enforce permissions before retrieval or actions.

The first MVP is the internal employee bot. The external website bot and broader administrator experience are later phases. The product should reduce phone calls, speed up service, improve document discovery and onboarding, and provide measurable quality. Track resolution and escalation rates, latency, citation quality, satisfaction, usage, cost, and deployment time.

## 3. Internal MVP scope

Build a Polish-language Telegram bot for employees and administrators. It must:

- answer questions using approved company documents;
- search and summarize documents;
- cite material factual answers with document name and, where available, section, page, supporting snippet, version, and source link;
- use multiple sources when appropriate;
- identify conflicting or outdated information;
- state uncertainty and refuse to invent information when evidence is missing;
- offer escalation and a way to report an incorrect answer;
- support private chats and explicitly approved Telegram groups.

In groups, respond only when mentioned or explicitly invoked. Validate both sender and group. Move sensitive answers to a private conversation.

Initial formats are Google Docs, PDF, DOCX, TXT, and Markdown. OCR, spreadsheets, and email ingestion are later extensions.

The MVP is read-only. The bot must not autonomously add, update, delete, approve, or publish canonical documents. Future write actions must be separately authorized, explicitly confirmed, and audited.

## 4. Explicit non-goals for the MVP

- No Kubernetes unless measured operational needs justify it.
- No requirement for a local language model.
- No customer-facing administration panel initially.
- No write access to Google Drive.
- No signed contracts, employee files, customer records, or other high-risk personal data until fine-grained authorization and privacy controls are reviewed.
- No production dependency on personal OAuth until contractual, privacy, continuity, and support implications are accepted.
- No automatic promotion of chat content into the corporate knowledge base.

## 5. Deployment and isolation

Use one codebase and repeatable container images, but deploy a separate single-tenant environment for every company. Isolate containers, database, vector index, secrets, memory workspace, logs, retention jobs, and backups per tenant.

Start locally with Docker Compose and later move the same containers to AWS. Target Linux x86_64. A preliminary 2 vCPU and 4 GB RAM is acceptable for a small pilot, but measure ingestion, retrieval, model latency, and concurrency before treating it as a production requirement.

Run containers as non-root, expose only required ports, use health checks and resource limits, and never mount the Docker socket. Keep administrative interfaces such as the Hermes dashboard private through local access, SSH, or VPN.

Do not use Kubernetes initially. Reconsider it only when multi-host scheduling, high availability, automatic scaling, or fleet operations clearly justify it.

When adding an external bot, run separate internal and external agent profiles/processes with separate credentials, sessions, memory, and knowledge scopes. The external process must never receive internal document credentials.

## 6. Preferred architecture

Use Python, FastAPI, PostgreSQL with pgvector, a background Google Drive synchronization worker, Docker Compose, and explicit database migrations.

Keep the domain layer independent from Telegram, Hermes, Honcho, Google Drive, and model providers. Use replaceable adapters. Do not hard-code configuration, permissions, retention, or provider selection for one company.

## 7. Hermes and model providers

Use Hermes Agent initially as the agent runtime, Telegram gateway, and operator/development interface. Hermes is not the source of truth for authorization, document permissions, retention, or data lifecycle; those controls belong to Aitegrate's backend.

For development and the fictional demo, support Hermes with the `openai-codex` provider through ChatGPT OAuth. Preserve a configuration-only path to an API-key provider for a safer, more controllable production option. Keep providers interchangeable, including OpenAI API, an approved business subscription, Nous-hosted models, or another compatible endpoint.

Codex App Server may be evaluated separately, but is not required for the MVP.

Never commit secrets, bake them into images, or log them. Use ignored local environment files in development and a secrets manager on AWS.

## 8. Knowledge and RAG

RAG is a core capability. A large context window does not replace permission-aware retrieval, freshness, deletion, version tracking, or citations.

Use three information layers:

1. stable policies and behavior in repository instructions, prompts, or skills;
2. mutable company knowledge in the RAG index;
3. per-user conversation state and optional personal memory.

Do not store contracts, procedures, or frequently changing operational content in `AGENTS.md`, Hermes global memory, or a global system prompt.

Google Drive is the initial source of truth. Synchronize selected shared folders read-only. Start with scopes equivalent to `public`, `internal`, and `admin`, while allowing future department and group scopes.

The ingestion pipeline must detect additions, updates, deletions, and lost access; export and parse supported files; chunk content; build embeddings and keyword search; and attach tenant, source ID, title, folder, scope, version, modification time, page or section, and source URL. It must invalidate obsolete chunks and be idempotent, retryable, observable, and expose sync status.

Filter retrieval by tenant, role, identity, group, and document scope before any content reaches the model. Prefer hybrid semantic and keyword retrieval. For explicit full-document summaries or comparisons, retrieve the complete authorized document.

Prefer content explicitly marked current or approved. If authorized sources conflict and precedence is unclear, show the conflict, cite both, and recommend escalation.

## 9. Conversation memory and Honcho

Conversation history must never become corporate knowledge automatically.

For the fictional demo, Honcho may be used as optional per-user memory. Keep users isolated: set `pinUserPeer: false`, use a distinct runtime peer prefix, use aliases only for channels proven to belong to the same person, use a company-specific workspace, and keep the AI peer distinct from humans.

Hermes `USER.md` or `MEMORY.md` files are global to an agent environment. They may contain environment-level facts only, never individual profiles. Gate or disable automatic global-memory writes.

Use Honcho Cloud only with fictional data until its contract, DPA, retention, training policy, subprocessors, and data location are reviewed. Self-hosted Honcho per customer remains a production candidate.

Personal memory must be optional, inspectable, exportable, correctable, and deletable. Default retention targets are 30 days for internal chats and 7 days for external anonymous chats; administrators may shorten them. Honcho-derived memory needs its own consent and lifecycle policy.

## 10. Identity and authorization

A Telegram allowlist is useful for a pilot but is not the complete security model. Aitegrate's backend is authoritative for identity, roles, document permissions, and actions.

For the pilot, manually approve Telegram user IDs and roles. For production, link Telegram to a corporate identity, starting with Google Workspace and retaining an adapter for Microsoft Entra ID or generic OIDC. Verify tokens server-side.

Keep employee authentication separate from the Drive service account used for ingestion. Enforce administrator capabilities in backend policy and database rules, never only through prompts, Hermes configuration, or hidden UI.

## 11. Privacy, security, and data lifecycle

Use fictional data first. Introduce real company data only after reviewing the complete data flow and providers.

Initial production knowledge should contain general procedures, work instructions, regulations, public information, and approved templates. Treat signed contracts, HR records, and customer data as later high-risk categories.

Apply data minimization. A hosted model or memory provider is an external data recipient even with OAuth. Before production, review DPA terms, retention, training use, subprocessors, data location, account ownership, revocation, and incident handling.

Encrypt data in transit and at rest, including backups. Logs must not contain raw prompts, documents, secrets, tokens, or personal data by default. Temporary verbose tracing is allowed only with fictional data and must then be disabled. Redact identifiers where possible.

Provide deletion and export for conversations and optional Honcho memory, including memory opt-out. Administrators should normally see aggregate statistics and reported conversations. Full transcript access requires a separate permission and clear notice.

Audit permission changes, sync events, deletion and retention jobs, and administrative access without retaining content that should be deleted.

Every data category needs an owner, purpose, classification, retention period, deletion path, and backup policy. Test retention regularly. Deletion must cascade through conversations, Honcho, relevant RAG artifacts, caches, and backups according to policy. Define legal hold separately before production.

## 12. Fictional demo company

Create a fictional medium-sized technical and facility-services company suitable for demos and advertising. Include realistic service procedures, health and safety rules, complaints, contract and SLA templates, a service catalog, onboarding, leave and remote-work policies, and `public`, `employee`, and `admin` scopes. Add controlled outdated and conflicting documents to demonstrate freshness and conflict handling.

Verify the fictional company name and brand before advertising. Never copy real customer or employee data.

## 13. Engineering and quality standards

Use English for code identifiers, comments, commit messages, and developer documentation. Use Polish for the initial UI and fictional company documents.

Use formatting, linting, type checking, migrations, tests, CI, secret scanning, and dependency scanning. The initial Python toolset should include `pytest`, Ruff, and an agreed type checker.

At minimum, test:

- tenant, role, identity, and document-scope isolation;
- prevention of sensitive answers in Telegram groups;
- idempotent Drive sync, update, deletion, and access-loss handling;
- authorization before RAG context reaches the model;
- citations, outdated sources, and conflicts;
- retention and cascading deletion;
- Telegram trust boundaries and provider adapters.

Maintain a repeatable evaluation dataset containing answerable, missing, conflicting, obsolete, unauthorized, irrelevant, multi-source, prompt-injection, and escalation cases. Measure correctness, citation support, permission leakage, latency, and cost. AI behavior needs automated evaluations in addition to manual testing.

## 14. Git and GitHub workflow

This directory may begin without Git. Initializing Git, creating the first commit, adding a remote, or publishing code requires Maksymilian's explicit approval.

After initialization, use:

- `main` as the stable branch;
- `dev` as the integration branch;
- short-lived task branches from `dev`, with prefixes such as `feature/`, `fix/`, `refactor/`, or `docs/`;
- a Pull Request for every merge;
- squash merge by default.

Never push directly to `main` or `dev`.

Local implementation and testing are allowed within the requested task, but publication has separate approval gates:

1. implement and test locally, inspect the diff, and report;
2. before committing, show scope, tests, limitations, and proposed message, then ask Maksymilian;
3. permission to commit does not imply permission to push;
4. permission to push does not imply permission to open a Pull Request unless both are explicitly authorized;
5. create Pull Requests as drafts by default;
6. never merge without explicit approval.

Keep commits focused and preserve unrelated user changes. Do not force-push, rewrite published history, delete remote branches, create releases, or perform destructive Git operations without explicit approval.

## 15. Agent autonomy and consultation rules

Agents may inspect the repository, make requested scoped local edits, run relevant local tests, choose reversible implementation details, and propose alternatives.

Consult Maksymilian before:

- changing architecture, product scope, or tenant boundaries;
- introducing paid services or meaningful recurring costs;
- changing privacy, retention, authentication, authorization, or security policy;
- processing real personal, customer, HR, or contract data;
- deploying or mutating cloud resources;
- sending external messages or changing third-party systems;
- committing, pushing, opening or merging a Pull Request, or publishing a release;
- destructive or difficult-to-reverse operations.

Record unresolved decisions explicitly. Do not silently convert assumptions into permanent product policy.
