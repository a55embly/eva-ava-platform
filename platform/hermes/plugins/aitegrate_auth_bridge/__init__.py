'''Hermes hook-to-tool authorization contract spike.

The opaque context token lives only in a task-local ContextVar. It is not
part of a tool schema, tool arguments, the user message, or a tool result.
'''

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from typing import Any, Protocol

from .client import AuthBackendClient, BridgeSettings

logger = logging.getLogger(__name__)


class BridgeClient(Protocol):
    def authorize(self, payload: dict[str, Any]) -> str: ...

    def consume(self, token: str, session_id: str, query: str) -> dict[str, Any]: ...

    def revoke(self, token: str, session_id: str) -> None: ...


_turn_context_token: ContextVar[str | None] = ContextVar(
    'aitegrate_turn_context_token',
    default=None,
)
_client_override: BridgeClient | None = None

CONTRACT_LOOKUP_SCHEMA: dict[str, Any] = {
    'name': 'aitegrate_contract_lookup',
    'description': 'Return fictional authorized evidence for the current Telegram turn.',
    'parameters': {
        'type': 'object',
        'properties': {
            'query': {
                'type': 'string',
                'description': 'Question to look up in the fictional contract backend.',
            }
        },
        'required': ['query'],
        'additionalProperties': False,
    },
}


def _client() -> BridgeClient:
    if _client_override is not None:
        return _client_override
    return AuthBackendClient(
        BridgeSettings(
            backend_url=os.environ['AITEGRATE_BACKEND_URL'],
            instance_id=os.environ['AITEGRATE_HERMES_INSTANCE_ID'],
            shared_secret=os.environ['AITEGRATE_HERMES_SHARED_SECRET'],
        )
    )


def _source_value(source: Any, name: str, default: str = '') -> str:
    value = getattr(source, name, default)
    enum_value = getattr(value, 'value', value)
    return str(enum_value) if enum_value is not None else default


def _pre_gateway_dispatch(event: Any, **_: Any) -> dict[str, str]:
    '''Authorize platform-provided identifiers and fail closed on every error.'''
    _turn_context_token.set(None)
    try:
        source = getattr(event, 'source', None)
        if source is None:
            return {'action': 'skip', 'reason': 'missing-source'}
        payload = {
            'platform': _source_value(source, 'platform'),
            'sender_id': _source_value(source, 'user_id'),
            'chat_id': _source_value(source, 'chat_id'),
            'chat_type': _source_value(source, 'chat_type', 'dm'),
            'thread_id': _source_value(source, 'thread_id'),
            'message_id': str(
                getattr(event, 'message_id', None)
                or getattr(source, 'message_id', None)
                or getattr(event, 'platform_update_id', None)
                or ''
            ),
        }
        token = _client().authorize(payload)
    except Exception:
        logger.warning(
            'Aitegrate authorization denied or unavailable; failing closed',
        )
        _turn_context_token.set(None)
        return {'action': 'skip', 'reason': 'aitegrate-authorization-failed'}

    _turn_context_token.set(token)
    return {'action': 'allow'}


def _handle_contract_lookup(args: dict[str, Any], **kwargs: Any) -> str:
    '''Consume the hidden context without accepting identity from the model.'''
    token = _turn_context_token.get()
    session_id = str(kwargs.get('task_id') or '')
    query = args.get('query')
    if not token or not session_id:
        return json.dumps({'error': 'missing authorized turn context'})
    if not isinstance(query, str) or not query.strip():
        return json.dumps({'error': 'query is required'})
    try:
        result = _client().consume(token, session_id, query.strip())
    except Exception:
        return json.dumps({'error': 'authorized lookup failed'})
    return json.dumps(result, ensure_ascii=False)


def _on_session_end(session_id: str = '', task_id: str = '', **_: Any) -> None:
    '''Revoke the capability at the end of every Hermes conversation turn.'''
    token = _turn_context_token.get()
    effective_session_id = session_id or task_id
    try:
        if token and effective_session_id:
            _client().revoke(token, effective_session_id)
    except Exception:
        logger.warning(
            'Aitegrate turn context revocation failed for session=%s',
            effective_session_id,
        )
    finally:
        _turn_context_token.set(None)


def register(ctx: Any) -> None:
    '''Register the smallest public Hermes surface needed by the spike.'''
    ctx.register_hook('pre_gateway_dispatch', _pre_gateway_dispatch)
    ctx.register_hook('on_session_end', _on_session_end)
    ctx.register_tool(
        name='aitegrate_contract_lookup',
        toolset='aitegrate',
        schema=CONTRACT_LOOKUP_SCHEMA,
        handler=_handle_contract_lookup,
        description='Look up fictional Aitegrate evidence for an authorized turn.',
    )
