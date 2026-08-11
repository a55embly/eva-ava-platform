"""Tests for the basic process health endpoint."""

import logging

from fastapi.testclient import TestClient

from app.main import app, create_app


def test_health() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness_and_readiness_are_separate() -> None:
    ready_client = TestClient(create_app(readiness_check=lambda: True))
    unavailable_client = TestClient(create_app(readiness_check=lambda: False))

    assert ready_client.get("/health/live").json() == {"status": "ok"}
    assert ready_client.get("/health/ready").status_code == 200
    assert unavailable_client.get("/health/live").status_code == 200
    assert unavailable_client.get("/health/ready").status_code == 503
    assert unavailable_client.get("/health/ready").json() == {
        "detail": "database unavailable"
    }


def test_request_id_is_returned_and_sensitive_headers_are_not_logged(
    caplog: object,
) -> None:
    client = TestClient(create_app(readiness_check=lambda: True))

    with caplog.at_level(logging.INFO, logger="app.requests"):  # type: ignore[attr-defined]
        response = client.get(
            "/health/live",
            headers={
                "X-Request-ID": "interview-demo-42",
                "Authorization": "Bearer never-log-this-token",
            },
        )

    assert response.headers["X-Request-ID"] == "interview-demo-42"
    assert "request_id=interview-demo-42" in caplog.text  # type: ignore[attr-defined]
    assert "never-log-this-token" not in caplog.text  # type: ignore[attr-defined]
