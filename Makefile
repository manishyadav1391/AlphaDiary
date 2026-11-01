# TJ developer commands. Everything runs inside the dev containers, so the
# Python version, the dependencies and DATABASE_URL are the same for everyone.

COMPOSE := docker compose -f docker-compose.dev.yml
API := $(COMPOSE) exec -T api

.PHONY: dev down logs shell migrate migrate-check revision test lint fmt seed instruments holidays worker-logs create-user kite-credentials

## Build and start Postgres and the API.
dev:
	$(COMPOSE) up -d --build
	@echo "API health: http://localhost:8000/api/v1/health"
	@echo "Web: run 'npm run dev' in apps/web"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api

shell:
	$(COMPOSE) exec api bash

## Apply every migration to head. Safe to re-run.
migrate:
	$(API) alembic upgrade head

## Fail if the models and the migrations have drifted apart.
migrate-check:
	$(API) alembic check

## make revision m="add thing"
revision:
	$(API) alembic revision --autogenerate -m "$(m)"

test:
	$(API) pytest

lint:
	$(API) ruff check .
	$(API) ruff format --check .
	$(API) mypy
	cd apps/web && npm run lint

fmt:
	$(API) ruff format .
	$(API) ruff check --fix .

## Load seed/charge_rates.json into the database (FR-CHG-07).
seed:
	$(API) python -m app.cli seed

## Download and store the Kite instruments master (FR-IMP-05).
instruments:
	$(API) python -m app.cli instruments

## Refresh the NSE trading-holiday calendar (FR-REM-01).
holidays:
	$(API) python -m app.cli holidays

## Follow the worker's log.
worker-logs:
	$(COMPOSE) logs -f worker

## Create the single owner account (FR-AUTH-01). Prompts for email and password.
create-user:
	$(COMPOSE) exec api python -m app.cli create-user

## Store the Kite API key and secret, encrypted (FR-KITE-01).
kite-credentials:
	$(COMPOSE) exec api python -m app.cli set-kite-credentials
