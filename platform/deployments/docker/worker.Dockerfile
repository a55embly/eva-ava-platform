FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY worker ./worker
COPY knowledge ./knowledge
COPY migrations ./migrations
RUN pip install --no-cache-dir .

RUN useradd --create-home appuser
USER appuser

CMD ["python", "-m", "worker.main"]
