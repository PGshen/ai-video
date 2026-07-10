INIT_SQL ?= backend/sql/init.sql
DB_NAME ?= video_workflow
DB_USER ?= app

UV ?= uv
PNPM ?= pnpm

.PHONY: up up-infra down migrate init-db dev-backend dev-worker dev-frontend run-backend run-worker run-frontend

up:
	docker-compose up -d

up-infra:
	docker-compose up -d postgres temporal temporal-ui minio

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

# 直接在宿主机源码启动（需要宿主机已装 uv / pnpm，glibc 较新时可用，见 CLAUDE.md）
run-backend:
	cd backend && $(UV) sync --frozen && $(UV) run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	cd backend && $(UV) sync --frozen && $(UV) run python -m app.workers.combined_worker

run-frontend:
	cd frontend && $(PNPM) install && $(PNPM) exec vite --host 0.0.0.0
