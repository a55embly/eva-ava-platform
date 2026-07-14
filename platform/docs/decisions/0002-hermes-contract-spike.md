# ADR 0002: Hermes authorization bridge remains pending live verification

## Status

Pending live verification.

## Context

The internal bot requires backend authorization before protected document text
reaches a model. The proposed Hermes integration relies on a Telegram
pre_gateway_dispatch hook, a hidden per-turn capability and a custom tool.
That complete data path is not documented as one supported contract.

The spike pins Hermes v2026.6.5, source commit
3c231eb3979ab9c57d5cd6d02f1d577a3b718b43, and the Linux amd64 image digest
recorded in hermes/VERSION.

## Confirmed by local tests

- Required backend settings fail closed; there are no working authorization
  defaults.
- HMAC binds method, path, instance ID, timestamp, nonce and body digest;
  endpoint, method, instance, body, replay and stale timestamp changes fail.
- Telegram DM, group and forum identity rules reject cross-user DMs, foreign
  groups, foreign users, channels, unknown chat types and missing message IDs.
- Capability TTL, use limit, atomic first-session binding, cross-session denial,
  manual revocation and end-hook cleanup are covered.
- Two users and two sessions for one user retain distinct task-local tokens.
- The capability is absent from tool schema, model arguments, tool result and
  ordinary plugin logs. `/consume` returns fictional evidence, not capability
  material.
- Hermes config setup is idempotent, rejects duplicate YAML keys, backs up the
  writable config and restricts Telegram to exactly the `aitegrate` toolset.

## Confirmed by local container checks

- Docker Hub resolves the pinned release to the recorded Linux amd64 digest;
  the image revision label equals the pinned source commit.
- The locked spike backend builds, fails startup without required config, runs
  as UID 1000 and returns health 200 without publishing a host port.
- The official Hermes entrypoint is preserved. Its s6 bootstrap starts as root,
  as documented upstream.
- The real pinned CLI initialized the named volume, enabled the plugin, applied
  and checked the setup idempotently, and reported only `aitegrate` enabled for
  Telegram. Terminal, file, web, browser, code execution, memory, delegation,
  cron and messaging toolsets were disabled.

## Confirmed against the pinned Hermes source

- pre_gateway_dispatch runs before Hermes authorization and session creation.
- The hook receives the normalized event but no Hermes turn_id.
- The gateway copies the hook task context into `run_conversation`, and the
  concurrent tool executor copies it again into the worker dispatching the
  plugin handler. A no-model behavioral test runs both pinned mechanisms and
  the pinned `ToolRegistry.dispatch` with the bridge ContextVar.
- Gateway tool handlers receive task_id equal to the Hermes session_id;
  the registry does not forward turn_id or the separate session_id kwarg.
- on_session_end receives the session, task and turn identifiers after every
  run_conversation call.
- Hermes provides CLI and dashboard session export/delete surfaces.
- The CLI delete path supplies the transcript directory, but the dashboard
  DELETE endpoint calls database deletion without that directory. The HTTP
  lifecycle surface therefore does not yet prove complete artifact deletion.
- The official container intentionally starts its s6 bootstrap as root and
  then drops supervised processes to the hermes user.

## Confirmed by live test

- Docker Desktop ran the exact pinned Linux amd64 image and the locally built
  spike backend together through the supported Compose file.
- Hermes persisted an `openai-codex` OAuth login in its named volume and used
  the selected `gpt-5.6-sol` model.
- One explicitly allowed Telegram user completed a real private-chat `/start`
  turn and a normal model turn. The expected response was delivered.
- The backend recorded successful authorization and end-of-turn revocation for
  the live turns, with no authorization 4xx or 5xx responses.
- A redacted scan found neither the configured Telegram token nor the shared
  HMAC secret in the captured container logs.
- Both services remained running after the test; the backend health check was
  healthy and no host ports were published.

## Still unconfirmed

- Concurrent isolation in a running gateway process and real transcript/log
  redaction.
- Gateway application-process users and availability during a real configured
  gateway run.
- A second allowed user, a denied user, an approved group/forum, mention
  behavior, restart behavior, a live protected-tool `/consume`, multiple tool
  calls and a fresh tool-using turn after revocation.

## Separately blocked session-deletion lifecycle

Hermes exposes CLI and dashboard session deletion, but the pinned dashboard
HTTP deletion path still does not prove removal of transcript files. SQLite
rows, transcript artifacts and any configured memory copies must be verified
end to end before the product can claim complete deletion.

## Spike design

The hook sends platform-provided identifiers to a locally authenticated mock
backend. Requests are HMAC signed over method, path, instance ID, timestamp,
nonce and body digest. The backend checks the allowlists and returns a random
capability whose digest alone is stored server-side.

The plugin stores the raw capability in its own ContextVar. It is absent from
the tool schema and arguments. On first use, the backend atomically binds it to
the handler's task_id/session. The capability lasts at most 120 seconds,
allows three calls in one turn, and is revoked by on_session_end.

Every bridge failure returns skip or a generic tool error. Hook failures must
not inherit Hermes's default fail-open behavior.

## Decision gate

Do not build production authorization or RAG on this bridge yet.

Set the final decision to Hermes gateway accepted only after the live
Telegram and container test in hermes/spike/README.md passes. Choose
Aitegrate gateway required if context is model-visible, sessions mix,
revocation cannot be guaranteed, the hook cannot fail closed, or the solution
requires private Hermes state.

Conversation lifecycle remains separately blocked until deletion is verified
for SQLite rows, transcript files and any other configured artifacts.

## Current limitations

- Live verification currently covers one allowed Telegram user in a private
  chat only; it is not the full acceptance matrix.
- No Telegram token or OAuth credentials are stored in the repository.
- The synchronous plugin hook is acceptable for a local spike only; its
  latency and failure behavior must be measured before production use.
- If end-hook revocation fails, immediate invalidation is not guaranteed. The
  capability remains bounded only by its short TTL, session binding and use
  limit.
