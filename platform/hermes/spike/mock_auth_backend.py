'''In-memory authorization backend for the Hermes contract spike only.'''

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping

from fastapi import FastAPI, HTTPException, Request

TOKEN_TTL_SECONDS = 120
MAX_TOOL_USES = 3
SIGNATURE_CLOCK_SKEW_SECONDS = 30


@dataclass
class Capability:
    tenant_id: str
    instance_id: str
    user_id: str
    role: str
    scopes: tuple[str, ...]
    chat_id: str
    chat_type: str
    message_id: str
    expires_at: float
    remaining_uses: int
    session_id: str | None = None
    revoked: bool = False


class CapabilityStore:
    '''Thread-safe, token-hashing store used to prove capability semantics.'''

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}
        self._nonces: dict[str, float] = {}
        self._lock = threading.Lock()

    def issue(
        self,
        *,
        instance_id: str,
        user_id: str,
        role: str,
        scopes: tuple[str, ...],
        chat_id: str,
        chat_type: str,
        message_id: str,
        now: float,
    ) -> str:
        token = secrets.token_urlsafe(32)
        capability = Capability(
            tenant_id='fictional-demo',
            instance_id=instance_id,
            user_id=user_id,
            role=role,
            scopes=scopes,
            chat_id=chat_id,
            chat_type=chat_type,
            message_id=message_id,
            expires_at=now + TOKEN_TTL_SECONDS,
            remaining_uses=MAX_TOOL_USES,
        )
        with self._lock:
            self._capabilities[_token_digest(token)] = capability
        return token

    def consume(self, token: str, session_id: str, now: float) -> Capability:
        if not session_id:
            raise PermissionError('missing session identity')
        with self._lock:
            capability = self._capabilities.get(_token_digest(token))
            if capability is None:
                raise PermissionError('unknown capability')
            if capability.revoked:
                raise PermissionError('revoked capability')
            if capability.expires_at <= now:
                raise PermissionError('expired capability')
            if capability.remaining_uses <= 0:
                raise PermissionError('capability use limit exhausted')
            if capability.session_id is None:
                capability.session_id = session_id
            elif capability.session_id != session_id:
                raise PermissionError('capability belongs to another session')
            capability.remaining_uses -= 1
            return capability

    def revoke(self, token: str, session_id: str) -> None:
        if not session_id:
            raise PermissionError('missing session identity')
        with self._lock:
            capability = self._capabilities.get(_token_digest(token))
            if capability is None:
                raise PermissionError('unknown capability')
            if capability.session_id not in (None, session_id):
                raise PermissionError('capability belongs to another session')
            capability.revoked = True

    def accept_nonce(self, nonce: str, now: float) -> None:
        with self._lock:
            stale = [
                value
                for value, accepted_at in self._nonces.items()
                if accepted_at + SIGNATURE_CLOCK_SKEW_SECONDS < now
            ]
            for value in stale:
                self._nonces.pop(value, None)
            if nonce in self._nonces:
                raise PermissionError('replayed service request')
            self._nonces[nonce] = now


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _csv_env(name: str) -> set[str]:
    return {value.strip() for value in os.getenv(name, '').split(',') if value.strip()}


class SpikeBackend:
    '''Verify the Hermes instance, authorize demo identities, and issue capabilities.'''

    def __init__(
        self,
        *,
        instance_id: str,
        shared_secret: str,
        allowed_users: set[str],
        admin_users: set[str],
        allowed_groups: set[str],
        store: CapabilityStore | None = None,
    ) -> None:
        if not instance_id.strip():
            raise ValueError('Hermes instance ID must not be empty')
        if len(shared_secret.encode()) < 32:
            raise ValueError('Hermes shared secret must contain at least 32 bytes')
        if not allowed_users:
            raise ValueError('Telegram allowed users must not be empty')
        if not admin_users <= allowed_users:
            raise ValueError('Telegram administrators must be allowed users')
        self.instance_id = instance_id.strip()
        self.shared_secret = shared_secret
        self.allowed_users = allowed_users
        self.admin_users = admin_users
        self.allowed_groups = allowed_groups
        self.store = store or CapabilityStore()

    def verify_service_request(
        self,
        headers: Mapping[str, str],
        body: bytes,
        *,
        method: str,
        path: str,
        now: float,
    ) -> None:
        instance_id = headers.get('x-aitegrate-hermes-instance', '')
        timestamp = headers.get('x-aitegrate-timestamp', '')
        nonce = headers.get('x-aitegrate-nonce', '')
        signature = headers.get('x-aitegrate-signature', '')
        if instance_id != self.instance_id or not nonce or not signature:
            raise PermissionError('untrusted Hermes instance')
        try:
            request_time = int(timestamp)
        except ValueError as exc:
            raise PermissionError('invalid request timestamp') from exc
        if abs(now - request_time) > SIGNATURE_CLOCK_SKEW_SECONDS:
            raise PermissionError('stale service request')
        digest = hashlib.sha256(body).hexdigest()
        signing_input = (
            f'{method.upper()}\n{path}\n{instance_id}\n{timestamp}\n{nonce}\n{digest}'
        ).encode()
        expected = hmac.new(
            self.shared_secret.encode(),
            signing_input,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise PermissionError('invalid service signature')
        self.store.accept_nonce(nonce, now)

    def authorize(self, payload: Mapping[str, Any], *, now: float) -> str:
        if payload.get('platform') != 'telegram':
            raise PermissionError('unsupported platform')
        user_id = str(payload.get('sender_id') or '')
        chat_id = str(payload.get('chat_id') or '')
        chat_type = str(payload.get('chat_type') or '')
        message_id = str(payload.get('message_id') or '')
        if not message_id:
            raise PermissionError('missing Telegram message identity')
        if chat_type not in {'dm', 'group', 'forum'}:
            raise PermissionError('unsupported Telegram chat type')
        if user_id not in self.allowed_users:
            raise PermissionError('unapproved Telegram identity')
        if chat_type == 'dm' and chat_id != user_id:
            raise PermissionError('invalid Telegram direct message identity')
        if chat_type in {'group', 'forum'} and (
            not chat_id or chat_id not in self.allowed_groups
        ):
            raise PermissionError('unapproved Telegram group')
        role = 'admin' if user_id in self.admin_users else 'employee'
        scopes = ('public', 'internal', 'admin') if role == 'admin' else ('public', 'internal')
        return self.store.issue(
            instance_id=self.instance_id,
            user_id=user_id,
            role=role,
            scopes=scopes,
            chat_id=chat_id,
            chat_type=chat_type,
            message_id=message_id,
            now=now,
        )


def backend_from_env() -> SpikeBackend:
    return SpikeBackend(
        instance_id=os.getenv('AITEGRATE_HERMES_INSTANCE_ID', ''),
        shared_secret=os.getenv('AITEGRATE_HERMES_SHARED_SECRET', ''),
        allowed_users=_csv_env('AITEGRATE_SPIKE_ALLOWED_USERS'),
        admin_users=_csv_env('AITEGRATE_SPIKE_ADMIN_USERS'),
        allowed_groups=_csv_env('AITEGRATE_SPIKE_ALLOWED_GROUPS'),
    )


def create_app(backend: SpikeBackend) -> FastAPI:
    '''Create an application around explicitly supplied, validated settings.'''
    app = FastAPI(title='Aitegrate Hermes Contract Spike')

    async def trusted_payload(request: Request) -> dict[str, Any]:
        body = await request.body()
        try:
            backend.verify_service_request(
                request.headers,
                body,
                method=request.method,
                path=request.url.path,
                now=time.time(),
            )
            payload = json.loads(body)
        except (PermissionError, ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=401, detail='unauthorized service request') from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail='JSON object required')
        return payload

    @app.get('/health')
    async def health() -> dict[str, str]:
        return {'status': 'ok'}

    @app.post('/authorize')
    async def authorize(request: Request) -> dict[str, Any]:
        payload = await trusted_payload(request)
        try:
            token = backend.authorize(payload, now=time.time())
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail='Telegram identity denied') from exc
        return {'context_token': token, 'expires_in': TOKEN_TTL_SECONDS}

    @app.post('/consume')
    async def consume(request: Request) -> dict[str, Any]:
        payload = await trusted_payload(request)
        try:
            backend.store.consume(
                str(payload.get('context_token') or ''),
                str(payload.get('session_id') or ''),
                time.time(),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail='turn context denied') from exc
        return {
            'answer': 'To jest fikcyjny dowod autoryzowanego przeplywu.',
            'citation_id': 'contract-spike-1',
        }

    @app.post('/revoke')
    async def revoke(request: Request) -> dict[str, bool]:
        payload = await trusted_payload(request)
        try:
            backend.store.revoke(
                str(payload.get('context_token') or ''),
                str(payload.get('session_id') or ''),
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail='turn context denied') from exc
        return {'revoked': True}

    return app


def create_app_from_env() -> FastAPI:
    '''Uvicorn factory that fails startup when required settings are absent.'''
    return create_app(backend_from_env())
