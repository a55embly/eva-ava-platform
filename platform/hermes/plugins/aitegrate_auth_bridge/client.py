'''Authenticated HTTP client used by the Hermes contract-spike plugin.'''

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BridgeClientError(RuntimeError):
    '''Raised when the backend cannot safely authorize a Hermes turn.'''


@dataclass(frozen=True)
class BridgeSettings:
    '''Non-model-visible connection settings for one Hermes instance.'''

    backend_url: str
    instance_id: str
    shared_secret: str
    timeout_seconds: float = 2.0


class AuthBackendClient:
    '''Call the spike backend using signed, replay-resistant requests.'''

    def __init__(self, settings: BridgeSettings) -> None:
        self._settings = settings

    def authorize(self, payload: dict[str, Any]) -> str:
        response = self._request('/authorize', payload)
        token = response.get('context_token')
        if not isinstance(token, str) or not token:
            raise BridgeClientError('authorization response did not contain a context token')
        return token

    def consume(self, token: str, session_id: str, query: str) -> dict[str, Any]:
        return self._request(
            '/consume',
            {'context_token': token, 'session_id': session_id, 'query': query},
        )

    def revoke(self, token: str, session_id: str) -> None:
        self._request(
            '/revoke',
            {'context_token': token, 'session_id': session_id},
        )

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        method = 'POST'
        body = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(18)
        body_digest = hashlib.sha256(body).hexdigest()
        signing_input = (
            f'{method}\n{path}\n{self._settings.instance_id}\n'
            f'{timestamp}\n{nonce}\n{body_digest}'
        ).encode()
        signature = hmac.new(
            self._settings.shared_secret.encode(),
            signing_input,
            hashlib.sha256,
        ).hexdigest()
        request = Request(
            self._settings.backend_url.rstrip('/') + path,
            data=body,
            method=method,
            headers={
                'Content-Type': 'application/json',
                'X-Aitegrate-Hermes-Instance': self._settings.instance_id,
                'X-Aitegrate-Timestamp': timestamp,
                'X-Aitegrate-Nonce': nonce,
                'X-Aitegrate-Signature': signature,
            },
        )
        try:
            with urlopen(request, timeout=self._settings.timeout_seconds) as response:
                result = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            raise BridgeClientError(f'backend rejected request with status {exc.code}') from exc
        except (OSError, URLError, ValueError, json.JSONDecodeError) as exc:
            raise BridgeClientError('backend authorization request failed') from exc
        if not isinstance(result, dict):
            raise BridgeClientError('backend returned an invalid response')
        return result
