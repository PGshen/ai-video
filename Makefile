.PHONY: up down migrate dev-backend dev-worker dev-frontend

up:
	docker-compose up -d

down:
	docker-compose down

migrate:
	cd backend && uv run alembic upgrade head

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-worker:
	cd backend && uv run python -m app.workers.combined_worker

dev-frontend:
	cd frontend && pnpm dev
