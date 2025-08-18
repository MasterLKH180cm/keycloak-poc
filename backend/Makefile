.PHONY: help install build run migrate clean test lint format dev

# Default target
help:
	@echo "Available commands:"
	@echo "  install     - Create venv and install dependencies"
	@echo "  build       - Build the application (install + migrate)"
	@echo "  run         - Run the application"
	@echo "  dev         - Run in development mode with auto-reload"
	@echo "  migrate     - Run database migrations"
	@echo "  clean       - Clean up build artifacts"
	@echo "  test        - Run tests"
	@echo "  lint        - Run code linting"
	@echo "  format      - Format code with black"

# Create virtual environment
create_venv:
	uv venv

# install dependencies
install:
	uv add -r requirements.txt

# Build the application
build: install migrate
	@echo "Backend build complete"

# Run database migrations
migrate:
	uv run alembic upgrade head

# Run the application
run:
	uv run python main.py

# Run in development mode
dev:
	uv run uvicorn main:app --reload

# Run tests
test:
	uv run pytest

# Run linting
lint:
	uv run python -m py_compile main.py

# Format code
format:
	uv run black .

# Clean up
clean:
	rm -rf .venv
	rm -rf __pycache__
	rm -rf *.pyc
	rm -rf .pytest_cache
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
