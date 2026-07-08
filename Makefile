INIT_SQL ?= backend/sql/init.sql
DB_NAME ?= video_workflow
DB_USER ?= app

.PHONY: up down migrate init-db dev-backend dev-worker dev-frontend

up:
	docker-compose up -d

down:
	docker-compose down

migrate:
	cd backend && uv run alembic upgrade head

init-db: up
	docker-compose exec -T postgres psql -U $(DB_USER) -d $(DB_NAME) -v ON_ERROR_STOP=1 < $(INIT_SQL)

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-worker:
	cd backend && uv run python -m app.workers.combined_worker

dev-frontend:
	cd frontend && pnpm dev
