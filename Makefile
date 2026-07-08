INIT_SQL ?= backend/sql/init.sql
DB_NAME ?= video_workflow
DB_USER ?= app

.PHONY: up down migrate init-db dev-backend dev-worker dev-frontend

up:
	docker-compose up -d

down:
	docker-compose down

migrate:
	docker-compose run --rm backend sh -c "uv sync --frozen && uv run alembic upgrade head"

init-db: up
	docker-compose exec -T postgres psql -U $(DB_USER) -d $(DB_NAME) -v ON_ERROR_STOP=1 < $(INIT_SQL)

dev-backend:
	docker-compose up backend

dev-worker:
	docker-compose up worker

dev-frontend:
	docker-compose up frontend
