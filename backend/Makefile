.PHONY: help install build run migrate clean test lint format dev docker-build docker-run docker-stop docker-clean deploy prod-up prod-down logs backup restore

# Default target
help:
	@echo "Available commands:"
	@echo "Development:"
	@echo "  install     - Create venv and install dependencies"
	@echo "  build       - Build the application (install + migrate)"
	@echo "  run         - Run the application"
	@echo "  dev         - Run in development mode with auto-reload"
	@echo "  migrate     - Run database migrations"
	@echo "  test        - Run tests"
	@echo "  lint        - Run code linting"
	@echo "  format      - Format code with black"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"
	@echo "  docker-stop  - Stop Docker containers"
	@echo "  docker-clean - Clean Docker images and containers"
	@echo ""
	@echo "Production:"
	@echo "  deploy      - Deploy to production"
	@echo "  prod-up     - Start production environment"
	@echo "  prod-down   - Stop production environment"
	@echo "  logs        - View production logs"
	@echo "  backup      - Backup production data"
	@echo "  restore     - Restore from backup"
	@echo ""
	@echo "  clean       - Clean up build artifacts"

# Create virtual environment
create_venv:
	python -m venv .venv

# install dependencies
install: create_venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

# Build the application
build: install migrate
	@echo "Backend build complete"

# Run database migrations
migrate:
	.venv/bin/alembic upgrade head

# Run the application
run:
	.venv/bin/uvicorn main:app --port 8000 --reload
# 	uv run python main.py

# Run in development mode
dev:
	.venv/bin/uvicorn main:app --port 8000 --reload

# Run tests
test:
	.venv/bin/pytest

# Run linting
lint:
	.venv/bin/python -m py_compile main.py

# Format code
format:
	.venv/bin/black .

# Clean up
clean:
	rm -rf .venv
	rm -rf __pycache__
	rm -rf *.pyc
	rm -rf .pytest_cache
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/

# Docker commands
docker-build:
	docker build -t keycloak-backend:latest .

docker-run:
	docker run -d --name keycloak-backend -p 8000:8000 keycloak-backend:latest

docker-stop:
	docker compose down

docker-clean:
	docker compose down -v --rmi all
	docker system prune -f

# Production deployment
deploy: docker-build
	@echo "Deploying to production..."
	docker compose -f docker-compose.yml up -d --build
	@echo "Waiting for services to be healthy..."
	@timeout 300 sh -c 'until docker compose ps | grep -q "healthy"; do sleep 5; done'
	@echo "Production deployment complete!"

prod-up:
	@echo "Starting production environment..."
	docker compose up -d
	@echo "Services starting..."

prod-down:
	@echo "Stopping production environment..."
	docker compose down

# Production monitoring
logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-keycloak:
	docker compose logs -f keycloak

logs-db:
	docker compose logs -f db

# Backup and restore
backup:
	@echo "Creating backup..."
	mkdir -p backups
	docker compose exec db pg_dump -U ${POSTGRES_USER:-keycloak} ${POSTGRES_DB:-keycloak} > backups/db_backup_$(shell date +%Y%m%d_%H%M%S).sql
	docker compose exec redis redis-cli --rdb backups/redis_backup_$(shell date +%Y%m%d_%H%M%S).rdb
	@echo "Backup completed"

restore:
	@echo "Restoring from backup..."
	@echo "Please specify backup file: make restore BACKUP_FILE=backups/db_backup_YYYYMMDD_HHMMSS.sql"
ifdef BACKUP_FILE
	docker compose exec -T db psql -U ${POSTGRES_USER:-keycloak} -d ${POSTGRES_DB:-keycloak} < $(BACKUP_FILE)
	@echo "Restore completed"
else
	@echo "Error: BACKUP_FILE not specified"
endif

# Health checks
health:
	@echo "Checking service health..."
	curl -f http://localhost:8000/health || echo "Backend: UNHEALTHY"
	curl -f http://localhost:8080/health/ready || echo "Keycloak: UNHEALTHY"

# Security scan
security-scan:
	docker run --rm -v $(PWD):/app -w /app securecodewarrior/docker-security-scanning

# Performance monitoring
stats:
	docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
