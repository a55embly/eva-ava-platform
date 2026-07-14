'''Static contract checks against the pinned Hermes source checkout.'''

from __future__ import annotations

import ast
import asyncio
import concurrent.futures
import importlib.util
import os
import subprocess
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from hermes.plugins import aitegrate_auth_bridge as bridge

EXPECTED_COMMIT = '3c231eb3979ab9c57d5cd6d02f1d577a3b718b43'


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _gateway_executor_method(source_path: Path) -> Any:
    source = source_path.read_text(encoding='utf-8')
    tree = ast.parse(source, filename=str(source_path))
    runner = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'GatewayRunner'
    )
    method = next(
        node
        for node in runner.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == '_run_in_executor_with_context'
    )
    isolated = ast.Module(
        body=[
            ast.Import(names=[ast.alias(name='asyncio')]),
            ast.ImportFrom(
                module='contextvars',
                names=[ast.alias(name='copy_context')],
                level=0,
            ),
            method,
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(isolated)
    namespace: dict[str, Any] = {}
    exec(compile(isolated, str(source_path), 'exec'), namespace)
    return namespace['_run_in_executor_with_context']


class _RecordingClient:
    def __init__(self) -> None:
        self.consumed: list[tuple[str, str, str]] = []
        self.revoked: list[tuple[str, str]] = []

    def authorize(self, payload: dict[str, Any]) -> str:
        return 'capability-for-' + str(payload['sender_id'])

    def consume(self, token: str, session_id: str, query: str) -> dict[str, Any]:
        self.consumed.append((token, session_id, query))
        return {'answer': 'fictional evidence'}

    def revoke(self, token: str, session_id: str) -> None:
        self.revoked.append((token, session_id))


@pytest.fixture(scope='module')
def hermes_source() -> Path:
    configured = os.getenv('HERMES_SOURCE_ROOT')
    if not configured:
        pytest.skip('set HERMES_SOURCE_ROOT to run checks against pinned Hermes source')
    root = Path(configured)
    commit = subprocess.run(
        ['git', 'rev-parse', 'HEAD'],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert commit == EXPECTED_COMMIT
    return root


def test_gateway_hook_precedes_session_creation(hermes_source: Path) -> None:
    source = (hermes_source / 'gateway' / 'run.py').read_text(encoding='utf-8')
    handler = source[source.index('async def _handle_message') :]
    hook_position = handler.index('pre_gateway_dispatch')
    session_position = handler.index('session_store.get_or_create_session(source)')
    assert hook_position < session_position
    hook_slice = handler[hook_position : hook_position + 1000]
    assert 'event=event' in hook_slice
    assert 'gateway=self' in hook_slice
    assert 'session_store=self.session_store' in hook_slice


def test_gateway_task_id_matches_session_id(hermes_source: Path) -> None:
    source = (hermes_source / 'gateway' / 'run.py').read_text(encoding='utf-8')
    assert f'{chr(34)}task_id{chr(34)}: session_id' in source
    assert 'agent.run_conversation(_api_run_message, **_conversation_kwargs)' in source


def test_contextvar_reaches_real_upstream_registry_dispatch(
    hermes_source: Path,
) -> None:
    thread_context = _load_module(
        'pinned_hermes_thread_context',
        hermes_source / 'tools' / 'thread_context.py',
    )
    registry_module = _load_module(
        'pinned_hermes_registry',
        hermes_source / 'tools' / 'registry.py',
    )
    thread_context._callback_api = lambda: (
        lambda: None,
        lambda: None,
        lambda value: None,
        lambda value: None,
    )
    registry = registry_module.ToolRegistry()
    registry.register(
        name='aitegrate_contract_lookup',
        toolset='aitegrate',
        schema=bridge.CONTRACT_LOOKUP_SCHEMA,
        handler=bridge._handle_contract_lookup,
    )
    client = _RecordingClient()
    bridge._client_override = client
    bridge._turn_context_token.set(None)
    source = SimpleNamespace(
        platform=SimpleNamespace(value='telegram'),
        user_id='1001',
        chat_id='1001',
        chat_type='dm',
        thread_id=None,
        message_id='message-a',
    )
    event = SimpleNamespace(source=source, message_id='message-a')
    assert bridge._pre_gateway_dispatch(event) == {'action': 'allow'}
    def run_conversation_without_model() -> str:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                thread_context.propagate_context_to_thread(registry.dispatch),
                'aitegrate_contract_lookup',
                {'query': 'policy'},
                task_id='hermes-session-a',
            )
            result = future.result(timeout=5)
        bridge._on_session_end(
            session_id='hermes-session-a',
            task_id='hermes-session-a',
            turn_id='hermes-turn-a',
        )
        return result

    executor_method = _gateway_executor_method(hermes_source / 'gateway' / 'run.py')

    async def exercise_gateway_bridge() -> str:
        return await executor_method(object(), run_conversation_without_model)

    result = asyncio.run(exercise_gateway_bridge())
    parsed_result = __import__('json').loads(result)
    assert parsed_result == {'answer': 'fictional evidence'}
    expected_use = ('capability-for-1001', 'hermes-session-a', 'policy')
    expected_revoke = ('capability-for-1001', 'hermes-session-a')
    assert client.consumed == [expected_use]
    assert client.revoked == [expected_revoke]
    assert bridge._turn_context_token.get() == 'capability-for-1001'
    bridge._turn_context_token.set(None)


def test_tool_handler_receives_task_id_but_not_turn_id(hermes_source: Path) -> None:
    source = (hermes_source / 'model_tools.py').read_text(encoding='utf-8')
    dispatch = source[source.index('def handle_function_call') :]
    regular_dispatch = dispatch[dispatch.index('return registry.dispatch') :]
    regular_dispatch = regular_dispatch[:500]
    assert 'task_id=task_id' in regular_dispatch
    assert 'turn_id=turn_id' not in regular_dispatch
    assert 'session_id=session_id' not in regular_dispatch


def test_end_hook_can_revoke_the_current_turn(hermes_source: Path) -> None:
    source = (hermes_source / 'agent' / 'conversation_loop.py').read_text(encoding='utf-8')
    hook = source[source.index('# Plugin hook: on_session_end') :]
    hook = hook[:1000]
    assert 'session_id=agent.session_id' in hook
    assert 'task_id=effective_task_id' in hook
    assert 'turn_id=turn_id' in hook


def test_supported_session_lifecycle_surfaces_exist(hermes_source: Path) -> None:
    web = (hermes_source / 'hermes_cli' / 'web_server.py').read_text(encoding='utf-8')
    cli = (hermes_source / 'hermes_cli' / 'main.py').read_text(encoding='utf-8')
    assert '/api/sessions/{session_id}/export' in web
    assert '/api/sessions/{session_id}' in web
    assert 'sessions delete' in cli or 'sessions_delete' in cli
    assert 'sessions export' in cli or 'sessions_export' in cli
