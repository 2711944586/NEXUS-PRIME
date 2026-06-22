.PHONY: dev up down logs build migrate worker beat test-backend test-frontend clean

dev:
	docker compose up -d

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

migrate:
	docker compose exec backend flask db upgrade

worker:
	docker compose exec worker celery -A app.platform.jobs.celery_app worker -l info -Q events,reports,ai,celery

beat:
	docker compose exec beat celery -A app.platform.jobs.celery_app beat -l info --schedule /app/backend/.runtime/celerybeat-schedule

test-backend:
	docker compose exec backend pytest

test-frontend:
	docker compose exec frontend npm test -- --watch=false

clean:
	docker compose down -v
