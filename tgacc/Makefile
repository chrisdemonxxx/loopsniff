.PHONY: dev build deploy migrate logs clean stop restart

# Development — start all services with live output
dev:
	docker compose up --build

# Build all Docker images without starting
build:
	docker compose build

# Production deploy — detached with forced rebuild
deploy:
	docker compose up -d --build --remove-orphans

# Run Alembic database migrations inside the API container
migrate:
	docker compose exec api alembic upgrade head

# Tail logs for all services
logs:
	docker compose logs -f --tail=100

# Stop all services and remove containers, networks, and volumes
clean:
	docker compose down -v --remove-orphans

# Stop all services
stop:
	docker compose down

# Restart all services
restart:
	docker compose down
	docker compose up -d --build
