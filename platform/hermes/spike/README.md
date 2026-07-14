# Hermes contract spike

This spike tests one question only: can a Telegram event be authorized by the
Aitegrate backend and carry a model-invisible capability into a Hermes plugin
tool without mixing concurrent users?

## Pinned upstream

- release: v2026.6.5;
- source commit: 3c231eb3979ab9c57d5cd6d02f1d577a3b718b43;
- Linux amd64 image:
  nousresearch/hermes-agent:v2026.6.5@sha256:94da6ebb770200580d37c9f6caca70aa9c19caa252d28ac953b7cb42634728ab;
- license: MIT.

The image's official entrypoint is preserved. Its s6 initialization runs as
root and supervised application processes drop to the hermes user.

The mock backend has no authorization defaults. Its instance ID, shared secret
and non-empty user allowlist must be supplied explicitly. The shared secret must
contain at least 32 bytes, and administrators must also be allowed users.

Service requests sign the uppercase HTTP method, exact request path, Hermes
instance ID, timestamp, nonce and SHA-256 body digest with HMAC-SHA256. Telegram
authorization accepts only `dm`, `group` and the `forum` value emitted by this
pinned Hermes release. Channels and unknown chat types fail closed.

## Local contract tests

Create the project environment and run:

    $env:HERMES_SOURCE_ROOT='D:\path\to\hermes-agent-v2026.6.5'
    pytest tests/contract -q

The upstream source checks are skipped when HERMES_SOURCE_ROOT is absent.
They must pass against the exact commit above before changing the pin.

## Repeatable Hermes volume setup

Do not mount `/opt/data/config.yaml` read-only. Hermes owns that writable file
and its migrations. Initialize the named volume and enable the plugin using the
pinned image's supported commands:

    docker compose --env-file .env -f compose.hermes-spike.yaml run --rm --no-deps hermes setup --non-interactive
    docker compose --env-file .env -f compose.hermes-spike.yaml run --rm --no-deps hermes plugins enable aitegrate-auth-bridge

Then apply and verify the narrow Telegram tool policy:

    docker compose --env-file .env -f compose.hermes-spike.yaml run --rm --no-deps hermes python /opt/aitegrate/setup_config.py /opt/data/config.yaml
    docker compose --env-file .env -f compose.hermes-spike.yaml run --rm --no-deps hermes python /opt/aitegrate/setup_config.py /opt/data/config.yaml --check
    docker compose --env-file .env -f compose.hermes-spike.yaml run --rm --no-deps hermes tools list --platform telegram

The setup script rejects duplicate YAML keys, preserves unrelated config,
creates `config.yaml.aitegrate-backup` before a change, writes atomically and is
idempotent. It does not implement Hermes migrations. It sets Telegram to exactly
the `aitegrate` toolset, excluding terminal, files, web, browser, cron,
delegation, global memory and outbound communication tools.

## Live Telegram test

1. Copy .env.example to the ignored .env.
2. Set a fictional/test Telegram bot token, numeric user IDs and a long random
   AITEGRATE_HERMES_SHARED_SECRET.
3. Start Docker Desktop.
4. Run the repeatable volume setup and validation commands above.
5. Start the gateway:

       docker compose --env-file .env -f compose.hermes-spike.yaml up

6. Verify the pinned image, backend health, gateway health using only an
   endpoint or command confirmed in the pinned source, and the tool list.
7. From two approved test accounts, invoke `aitegrate_contract_lookup`
   concurrently in DMs and in one approved group. Repeat with an unapproved
   account and group, with and without the required mention, across a gateway
   restart, multiple tool calls and a new turn after revocation.

Never place a real customer token, personal data, or production OAuth session
in this spike.

## Required evidence

The gateway can be accepted only when logs and tests show all of the following:

- unauthorized events fail closed before the model is invoked;
- tool arguments and results never contain the opaque capability;
- each token binds atomically to the first Hermes session that consumes it;
- parallel sessions receive only their own token;
- expiry, use limits, replay protection and end-of-turn revocation work;
- no token appears in Hermes transcripts, the mock backend response, or logs.

The current status is recorded in ADR 0002. A static test result alone is not
enough to accept the gateway.

If `on_session_end` cannot reach the backend, immediate revocation is not
guaranteed. The remaining defense is the short 120-second TTL, session binding
and three-use limit. Treat this as a spike limitation, not as assured cleanup.
