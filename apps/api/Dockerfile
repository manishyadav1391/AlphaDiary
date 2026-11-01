# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Kolkata

WORKDIR /srv/api

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./

# Development image: test and lint tooling included so `make test` and
# `make lint` run inside the same container the app runs in.
FROM base AS dev
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production image: runtime dependencies only, non-root.
FROM base AS prod
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --system --uid 10001 tj && chown -R tj:tj /srv/api
USER tj
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
