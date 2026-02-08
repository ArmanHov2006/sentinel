# Sentinel LLM Gateway — Development Commands
#
# Usage:
#   make up        Start all services in background
#   make down      Stop all services
#   make build     Rebuild containers from scratch
#   make logs      Follow sentinel container logs
#   make test      Run tests inside container
#   make lint      Run linter inside container
#   make redis-cli Open Redis CLI
#   make clean     Stop services and remove volumes
#   make dev       Start with dev tools (Redis Commander)
#   make restart   Restart all services
#   make status    Show container status
#   make shell     Open bash shell in sentinel container

.PHONY: up down build logs test lint redis-cli clean dev restart status shell

up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build --no-cache

logs:
	docker-compose logs -f sentinel

test:
	docker-compose exec sentinel pytest -v

lint:
	docker-compose exec sentinel ruff check .

redis-cli:
	docker-compose exec redis redis-cli

clean:
	docker-compose down -v --remove-orphans

dev:
	docker-compose --profile dev up -d

restart: down up

status:
	docker-compose ps

shell:
	docker-compose exec sentinel /bin/bash
