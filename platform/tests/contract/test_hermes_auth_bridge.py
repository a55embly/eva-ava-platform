'''Security-oriented contract tests for the Hermes authorization bridge.'''

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from contextvars import copy_context
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import pytest
import httpx

from hermes.plugins import aitegrate_auth_bridge as bridge
from hermes.spike.mock_auth_backend import (  # noqa: E402
    MAX_TOOL_USES,
    CapabilityStore,
    SpikeBackend,
    backend_from_env,
    create_app,
)
from hermes.spike.setup_config import configure, load_config


@dataclass
class RecordingClient:
    '''Backend double that records hidden token use without exposing it in results.'''

    token_by_user: dict[str, str]

    def __post_init__(self) -> None:
        self.authorizations: list[dict[str, Any]] = []
        self.consumptions: list[tuple[str, str, str]] = []
        self.revocations: list[tuple[str, str]] = []

    def authorize(self, payload: dict[str, Any]) -> str:
        self.authorizations.append(payload)
        return self.token_by_user[payload['sender_id']]

    def consume(self, token: str, session_id: str, query: str) -> dict[str, Any]:
        self.consumptions.append((token, session_id, query))
        return {'answer': f'evidence for {query}', 'citation_id': 'spike-1'}

    def revoke(self, token: str, session_id: str) -> None:
        self.revocations.append((token, session_id))


class BrokenClient:
    def authorize(self, payload: dict[str, Any]) -> str:
        raise RuntimeError('unexpected implementation failure')

    def consume(self, token: str, session_id: str, query: str) -> dict[str, Any]:
        raise RuntimeError('unexpected implementation failure')

    def revoke(self, token: str, session_id: str) -> None:
        raise RuntimeError('unexpected implementation failure')


@pytest.fixture(autouse=True)
def reset_bridge() -> Iterator[None]:
    bridge._turn_context_token.set(None)
    bridge._client_override = None
    yield
    bridge._turn_context_token.set(None)
    bridge._client_override = None


def event(
    user_id: str,
    chat_id: str,
    message_id: str,
    chat_type: str = 'dm',
) -> SimpleNamespace:
    source = SimpleNamespace(
        platform=SimpleNamespace(value='telegram'),
        user_id=user_id,
        chat_id=chat_id,
        chat_type=chat_type,
        thread_id=None,
        message_id=message_id,
    )
    return SimpleNamespace(
        source=source,
        message_id=message_id,
        platform_update_id=123,
    )


def test_model_schema_contains_no_identity_or_capability() -> None:
    properties = bridge.CONTRACT_LOOKUP_SCHEMA['parameters']['properties']
    assert set(properties) == {'query'}
    serialized = json.dumps(bridge.CONTRACT_LOOKUP_SCHEMA).lower()
    assert 'token' not in serialized
    assert 'user_id' not in serialized
    assert 'role' not in serialized
    assert 'scope' not in serialized


def test_hook_tool_and_end_hook_keep_token_out_of_model_visible_data() -> None:
    client = RecordingClient({'1001': 'opaque-secret-token'})
    bridge._client_override = client

    decision = bridge._pre_gateway_dispatch(event('1001', '1001', 'message-a'))
    result_text = bridge._handle_contract_lookup({'query': 'urlop'}, task_id='session-a')
    bridge._on_session_end(session_id='session-a', turn_id='internal-turn-a')

    assert decision == {'action': 'allow'}
    assert json.loads(result_text) == {
        'answer': 'evidence for urlop',
        'citation_id': 'spike-1',
    }
    assert 'opaque-secret-token' not in result_text
    assert client.consumptions == [('opaque-secret-token', 'session-a', 'urlop')]
    assert client.revocations == [('opaque-secret-token', 'session-a')]
    assert bridge._turn_context_token.get() is None


def test_parallel_contexts_do_not_mix_tokens() -> None:
    client = RecordingClient({'1001': 'token-a', '1002': 'token-b'})
    bridge._client_override = client
    context_a = copy_context()
    context_b = copy_context()

    context_a.run(bridge._pre_gateway_dispatch, event('1001', '1001', 'message-a'))
    context_b.run(bridge._pre_gateway_dispatch, event('1002', '1002', 'message-b'))
    result_a = context_a.run(
        bridge._handle_contract_lookup,
        {'query': 'question-a'},
        task_id='session-a',
    )
    result_b = context_b.run(
        bridge._handle_contract_lookup,
        {'query': 'question-b'},
        task_id='session-b',
    )

    assert 'token-a' not in result_a
    assert 'token-b' not in result_b
    assert set(client.consumptions) == {
        ('token-a', 'session-a', 'question-a'),
        ('token-b', 'session-b', 'question-b'),
    }


def test_parallel_sessions_for_same_user_do_not_mix_tokens() -> None:
    client = RecordingClient({'1001': 'unused'})
    bridge._client_override = client
    context_a = copy_context()
    context_b = copy_context()
    client.token_by_user['1001'] = 'token-a'
    context_a.run(bridge._pre_gateway_dispatch, event('1001', '1001', 'message-a'))
    client.token_by_user['1001'] = 'token-b'
    context_b.run(bridge._pre_gateway_dispatch, event('1001', '1001', 'message-b'))

    context_a.run(
        bridge._handle_contract_lookup,
        {'query': 'question-a'},
        task_id='session-a',
    )
    context_b.run(
        bridge._handle_contract_lookup,
        {'query': 'question-b'},
        task_id='session-b',
    )

    assert set(client.consumptions) == {
        ('token-a', 'session-a', 'question-a'),
        ('token-b', 'session-b', 'question-b'),
    }


def test_hook_fails_closed_when_backend_rejects_identity() -> None:
    bridge._client_override = RecordingClient({})
    decision = bridge._pre_gateway_dispatch(event('stranger', 'stranger', 'message-x'))
    assert decision == {'action': 'skip', 'reason': 'aitegrate-authorization-failed'}
    assert bridge._turn_context_token.get() is None


def test_hook_fails_closed_on_unexpected_plugin_exception() -> None:
    bridge._client_override = BrokenClient()
    decision = bridge._pre_gateway_dispatch(event('1001', '1001', 'message-x'))
    assert decision == {'action': 'skip', 'reason': 'aitegrate-authorization-failed'}
    assert bridge._turn_context_token.get() is None


def test_backend_binds_capability_to_first_session_and_limits_use() -> None:
    store = CapabilityStore()
    token = store.issue(
        instance_id='hermes-demo-1',
        user_id='1001',
        role='employee',
        scopes=('public', 'internal'),
        chat_id='1001',
        chat_type='dm',
        message_id='message-a',
        now=100.0,
    )
    capability = store.consume(token, 'session-a', now=101.0)
    assert capability.session_id == 'session-a'
    with pytest.raises(PermissionError, match='another session'):
        store.consume(token, 'session-b', now=101.0)
    for _ in range(MAX_TOOL_USES - 1):
        capability = store.consume(token, 'session-a', now=101.0)
        assert capability.session_id == 'session-a'
    with pytest.raises(PermissionError, match='use limit'):
        store.consume(token, 'session-a', now=101.0)


def test_backend_rejects_expired_and_revoked_capabilities() -> None:
    store = CapabilityStore()
    expired = store.issue(
        instance_id='hermes-demo-1',
        user_id='1001',
        role='employee',
        scopes=('public', 'internal'),
        chat_id='1001',
        chat_type='dm',
        message_id='message-a',
        now=0.0,
    )
    with pytest.raises(PermissionError, match='expired'):
        store.consume(expired, 'session-a', now=121.0)

    revoked = store.issue(
        instance_id='hermes-demo-1',
        user_id='1001',
        role='employee',
        scopes=('public', 'internal'),
        chat_id='1001',
        chat_type='dm',
        message_id='message-b',
        now=100.0,
    )
    store.consume(revoked, 'session-a', now=101.0)
    store.revoke(revoked, 'session-a')
    with pytest.raises(PermissionError, match='revoked'):
        store.consume(revoked, 'session-a', now=102.0)


def signed_headers(
    secret: str,
    instance_id: str,
    body: bytes,
    nonce: str,
    *,
    method: str = 'POST',
    path: str = '/authorize',
    timestamp: str = '100',
) -> dict[str, str]:
    digest = hashlib.sha256(body).hexdigest()
    signing_input = (
        f'{method.upper()}\n{path}\n{instance_id}\n{timestamp}\n{nonce}\n{digest}'
    ).encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).hexdigest()
    return {
        'x-aitegrate-hermes-instance': instance_id,
        'x-aitegrate-timestamp': timestamp,
        'x-aitegrate-nonce': nonce,
        'x-aitegrate-signature': signature,
    }


def test_service_signature_is_instance_bound_and_replay_resistant() -> None:
    secret = 'test-secret-that-is-at-least-32-bytes'
    backend = SpikeBackend(
        instance_id='hermes-demo-1',
        shared_secret=secret,
        allowed_users={'1001'},
        admin_users=set(),
        allowed_groups={'-1002001'},
    )
    body = json.dumps({'platform': 'telegram'}, separators=(',', ':')).encode()
    headers = signed_headers(secret, 'hermes-demo-1', body, 'nonce-a')

    backend.verify_service_request(
        headers,
        body,
        method='POST',
        path='/authorize',
        now=100.0,
    )
    with pytest.raises(PermissionError, match='replayed'):
        backend.verify_service_request(
            headers,
            body,
            method='POST',
            path='/authorize',
            now=100.0,
        )

    wrong_instance = signed_headers(secret, 'other-instance', body, 'nonce-b')
    with pytest.raises(PermissionError, match='untrusted'):
        backend.verify_service_request(
            wrong_instance,
            body,
            method='POST',
            path='/authorize',
            now=100.0,
        )


@pytest.mark.parametrize(
    ('headers', 'body', 'method', 'path', 'error'),
    [
        ('valid', b'{platform:telegram}', 'POST', '/consume', 'signature'),
        ('valid', b'{platform:telegram}', 'GET', '/authorize', 'signature'),
        ('valid', b'{platform:other}', 'POST', '/authorize', 'signature'),
        ('stale', b'{platform:telegram}', 'POST', '/authorize', 'stale'),
    ],
)
def test_service_signature_rejects_changed_request(
    headers: str,
    body: bytes,
    method: str,
    path: str,
    error: str,
) -> None:
    secret = 'test-secret-that-is-at-least-32-bytes'
    original_body = b'{platform:telegram}'
    timestamp = '1' if headers == 'stale' else '100'
    signed = signed_headers(
        secret,
        'hermes-demo-1',
        original_body,
        f'nonce-{method}-{path}-{error}',
        timestamp=timestamp,
    )
    backend = SpikeBackend(
        instance_id='hermes-demo-1',
        shared_secret=secret,
        allowed_users={'1001'},
        admin_users=set(),
        allowed_groups=set(),
    )
    with pytest.raises(PermissionError, match=error):
        backend.verify_service_request(
            signed,
            body,
            method=method,
            path=path,
            now=100.0,
        )


@pytest.mark.asyncio
async def test_consume_response_does_not_expose_capability() -> None:
    secret = 'test-secret-that-is-at-least-32-bytes'
    backend = SpikeBackend(
        instance_id='hermes-demo-1',
        shared_secret=secret,
        allowed_users={'1001'},
        admin_users=set(),
        allowed_groups=set(),
    )
    transport = httpx.ASGITransport(app=create_app(backend))
    timestamp = str(int(time.time()))
    authorize_body = json.dumps(
        {
            'platform': 'telegram',
            'sender_id': '1001',
            'chat_id': '1001',
            'chat_type': 'dm',
            'message_id': 'message-a',
        },
        separators=(',', ':'),
    ).encode()
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        authorize_response = await client.post(
            '/authorize',
            content=authorize_body,
            headers=signed_headers(
                secret,
                'hermes-demo-1',
                authorize_body,
                'nonce-authorize',
                timestamp=timestamp,
            ),
        )
        token = authorize_response.json()['context_token']
        consume_body = json.dumps(
            {'context_token': token, 'session_id': 'session-a', 'query': 'policy'},
            separators=(',', ':'),
        ).encode()
        consume_response = await client.post(
            '/consume',
            content=consume_body,
            headers=signed_headers(
                secret,
                'hermes-demo-1',
                consume_body,
                'nonce-consume',
                path='/consume',
                timestamp=timestamp,
            ),
        )

    assert consume_response.status_code == 200
    assert token not in consume_response.text
    assert set(consume_response.json()) == {'answer', 'citation_id'}


def test_group_requires_both_approved_user_and_group() -> None:
    backend = SpikeBackend(
        instance_id='hermes-demo-1',
        shared_secret='test-secret-that-is-at-least-32-bytes',
        allowed_users={'1001'},
        admin_users=set(),
        allowed_groups={'-1002001'},
    )
    payload = {
        'platform': 'telegram',
        'sender_id': '1001',
        'chat_id': '-1002001',
        'chat_type': 'group',
        'message_id': 'message-a',
    }
    assert backend.authorize(payload, now=100.0)
    with pytest.raises(PermissionError, match='group'):
        backend.authorize({**payload, 'chat_id': '-9999'}, now=100.0)


def test_backend_rejects_weak_service_secret() -> None:
    with pytest.raises(ValueError, match='at least 32 bytes'):
        SpikeBackend(
            instance_id='hermes-demo-1',
            shared_secret='too-short',
            allowed_users=set(),
            admin_users=set(),
            allowed_groups=set(),
        )


def test_backend_configuration_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    required = (
        'AITEGRATE_HERMES_SHARED_SECRET',
        'AITEGRATE_HERMES_INSTANCE_ID',
        'AITEGRATE_SPIKE_ALLOWED_USERS',
        'AITEGRATE_SPIKE_ADMIN_USERS',
        'AITEGRATE_SPIKE_ALLOWED_GROUPS',
    )
    for name in required:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv('AITEGRATE_HERMES_INSTANCE_ID', 'hermes-test-1')
    monkeypatch.setenv('AITEGRATE_SPIKE_ALLOWED_USERS', '1001')
    with pytest.raises(ValueError, match='secret'):
        backend_from_env()

    monkeypatch.setenv('AITEGRATE_HERMES_SHARED_SECRET', 'x' * 32)
    monkeypatch.setenv('AITEGRATE_HERMES_INSTANCE_ID', '')
    with pytest.raises(ValueError, match='instance ID'):
        backend_from_env()

    monkeypatch.setenv('AITEGRATE_HERMES_INSTANCE_ID', 'hermes-test-1')
    monkeypatch.setenv('AITEGRATE_SPIKE_ALLOWED_USERS', '')
    with pytest.raises(ValueError, match='allowed users'):
        backend_from_env()

    monkeypatch.setenv('AITEGRATE_SPIKE_ALLOWED_USERS', '1001')
    monkeypatch.setenv('AITEGRATE_SPIKE_ADMIN_USERS', '1002')
    with pytest.raises(ValueError, match='administrators'):
        backend_from_env()


def test_valid_configuration_creates_application(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('AITEGRATE_HERMES_INSTANCE_ID', 'hermes-test-1')
    monkeypatch.setenv('AITEGRATE_HERMES_SHARED_SECRET', 'x' * 32)
    monkeypatch.setenv('AITEGRATE_SPIKE_ALLOWED_USERS', '1001,1002')
    monkeypatch.setenv('AITEGRATE_SPIKE_ADMIN_USERS', '1002')
    monkeypatch.setenv('AITEGRATE_SPIKE_ALLOWED_GROUPS', '-1002001')
    backend = backend_from_env()
    app = create_app(backend)

    assert backend.admin_users == {'1002'}
    assert {route.path for route in app.routes} >= {
        '/health',
        '/authorize',
        '/consume',
        '/revoke',
    }


@pytest.mark.parametrize(
    ('payload', 'allowed'),
    [
        (
            {
                'platform': 'telegram',
                'sender_id': '1001',
                'chat_id': '1001',
                'chat_type': 'dm',
                'message_id': 'message-a',
            },
            True,
        ),
        (
            {
                'platform': 'telegram',
                'sender_id': '1001',
                'chat_id': '1002',
                'chat_type': 'dm',
                'message_id': 'message-a',
            },
            False,
        ),
        (
            {
                'platform': 'telegram',
                'sender_id': '1001',
                'chat_id': '-1002001',
                'chat_type': 'group',
                'message_id': 'message-a',
            },
            True,
        ),
        (
            {
                'platform': 'telegram',
                'sender_id': '1001',
                'chat_id': '-9999',
                'chat_type': 'group',
                'message_id': 'message-a',
            },
            False,
        ),
        (
            {
                'platform': 'telegram',
                'sender_id': '1001',
                'chat_id': '',
                'chat_type': 'group',
                'message_id': 'message-a',
            },
            False,
        ),
        (
            {
                'platform': 'telegram',
                'sender_id': '9999',
                'chat_id': '-1002001',
                'chat_type': 'group',
                'message_id': 'message-a',
            },
            False,
        ),
        (
            {
                'platform': 'telegram',
                'sender_id': '1001',
                'chat_id': '-1002001',
                'chat_type': 'channel',
                'message_id': 'message-a',
            },
            False,
        ),
        (
            {
                'platform': 'telegram',
                'sender_id': '1001',
                'chat_id': '-1002001',
                'chat_type': 'mystery',
                'message_id': 'message-a',
            },
            False,
        ),
        (
            {
                'platform': 'telegram',
                'sender_id': '1001',
                'chat_id': '1001',
                'chat_type': 'dm',
                'message_id': '',
            },
            False,
        ),
        (
            {
                'platform': 'discord',
                'sender_id': '1001',
                'chat_id': '1001',
                'chat_type': 'dm',
                'message_id': 'message-a',
            },
            False,
        ),
    ],
)
def test_backend_validates_telegram_identity(
    payload: dict[str, str],
    allowed: bool,
) -> None:
    backend = SpikeBackend(
        instance_id='hermes-demo-1',
        shared_secret='test-secret-that-is-at-least-32-bytes',
        allowed_users={'1001'},
        admin_users=set(),
        allowed_groups={'-1002001'},
    )
    if allowed:
        assert backend.authorize(payload, now=100.0)
    else:
        with pytest.raises(PermissionError):
            backend.authorize(payload, now=100.0)


def test_forum_is_allowed_because_pinned_hermes_normalizes_it() -> None:
    backend = SpikeBackend(
        instance_id='hermes-demo-1',
        shared_secret='test-secret-that-is-at-least-32-bytes',
        allowed_users={'1001'},
        admin_users=set(),
        allowed_groups={'-1002001'},
    )
    assert backend.authorize(
        {
            'platform': 'telegram',
            'sender_id': '1001',
            'chat_id': '-1002001',
            'chat_type': 'forum',
            'message_id': 'message-a',
        },
        now=100.0,
    )


def test_new_turn_after_end_hook_uses_new_capability() -> None:
    client = RecordingClient({'1001': 'token-a'})
    bridge._client_override = client
    bridge._pre_gateway_dispatch(event('1001', '1001', 'message-a'))
    bridge._handle_contract_lookup({'query': 'first'}, task_id='session-a')
    bridge._on_session_end(session_id='session-a')

    client.token_by_user['1001'] = 'token-b'
    bridge._pre_gateway_dispatch(event('1001', '1001', 'message-b'))
    bridge._handle_contract_lookup({'query': 'second'}, task_id='session-a')

    assert client.consumptions == [
        ('token-a', 'session-a', 'first'),
        ('token-b', 'session-a', 'second'),
    ]


def test_tool_without_hook_has_no_authorized_context() -> None:
    result = bridge._handle_contract_lookup({'query': 'question'}, task_id='session-a')
    assert json.loads(result) == {'error': 'missing authorized turn context'}


def test_revoke_failure_is_redacted_and_context_is_cleared(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = 'opaque-token-that-must-not-be-logged'
    bridge._client_override = BrokenClient()
    bridge._turn_context_token.set(token)

    with caplog.at_level(logging.WARNING):
        bridge._on_session_end(session_id='session-a')

    assert bridge._turn_context_token.get() is None
    assert token not in caplog.text


def test_interrupted_turn_without_end_hook_relies_on_ttl_and_use_limit() -> None:
    store = CapabilityStore()
    token = store.issue(
        instance_id='hermes-demo-1',
        user_id='1001',
        role='employee',
        scopes=('public', 'internal'),
        chat_id='1001',
        chat_type='dm',
        message_id='message-a',
        now=100.0,
    )

    assert store.consume(token, 'session-a', now=101.0)
    with pytest.raises(PermissionError, match='expired'):
        store.consume(token, 'session-a', now=221.0)


def test_hermes_setup_is_idempotent_and_restricts_telegram(tmp_path: Path) -> None:
    config_path = tmp_path / 'config.yaml'
    config_path.write_text(
        'model: fictional-provider/model\n'
        'plugins:\n'
        '  enabled:\n'
        '    - existing-plugin\n'
        'platform_toolsets:\n'
        '  telegram:\n'
        '    - terminal\n'
        '    - web\n',
        encoding='utf-8',
    )

    assert configure(config_path)
    config = load_config(config_path)
    assert config['model'] == 'fictional-provider/model'
    assert config['platform_toolsets']['telegram'] == ['aitegrate']
    assert config['plugins']['enabled'] == [
        'aitegrate-auth-bridge',
        'existing-plugin',
    ]
    assert config_path.with_suffix('.yaml.aitegrate-backup').exists()
    assert not configure(config_path)
    assert not configure(config_path, check_only=True)


def test_hermes_setup_rejects_duplicate_yaml_keys(tmp_path: Path) -> None:
    config_path = tmp_path / 'config.yaml'
    config_path.write_text(
        'platform_toolsets: {}\nplatform_toolsets: {}\n',
        encoding='utf-8',
    )
    with pytest.raises(ValueError, match='duplicate YAML key'):
        configure(config_path)
