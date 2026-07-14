FROM python:3.12-slim

WORKDIR /app
COPY requirements-hermes-spike.lock ./
RUN python -m pip install --no-cache-dir --upgrade pip==26.1.2 \
    && python -m pip install --no-cache-dir --requirement requirements-hermes-spike.lock

COPY hermes ./hermes

RUN useradd --create-home appuser
USER appuser

CMD ["uvicorn", "hermes.spike.mock_auth_backend:create_app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8010"]
