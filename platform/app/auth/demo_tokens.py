"""Fail-closed demo authentication for the single-tenant MVP."""

import hmac
from dataclasses import dataclass

from app.rag.models import AccessLevel

_MINIMUM_TOKEN_LENGTH = 32


@dataclass(frozen=True)
class Principal:
    """Authenticated demo identity passed to application services."""

    subject: str
    access_level: AccessLevel


class DemoTokenAuthorizer:
    """Map opaque environment-backed bearer tokens to demo principals."""

    def __init__(self, employee_token: str = "", admin_token: str = "") -> None:
        self._employee_token = self._valid_token(employee_token)
        self._admin_token = self._valid_token(admin_token)

    def authorize(self, token: str) -> Principal | None:
        if self._employee_token and hmac.compare_digest(token, self._employee_token):
            return Principal("demo-employee", AccessLevel.EMPLOYEE)
        if self._admin_token and hmac.compare_digest(token, self._admin_token):
            return Principal("demo-admin", AccessLevel.ADMIN)
        return None

    @staticmethod
    def _valid_token(token: str) -> str:
        return token if len(token) >= _MINIMUM_TOKEN_LENGTH else ""
