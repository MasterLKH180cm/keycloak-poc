# keycloak-poc
test the aggregation of backend auth services and keycloak

## Prerequisites

- Python 3.12+ (as specified in .python-version)
- [uv](https://github.com/astral-sh/uv) package manager

## Quick Start

### 1. Install uv (if not already installed)
```bash
pip install uv
```

### 2. Build the application
```bash
make build
```

### 3. Run the application
```bash
make run
```

## Development Setup

### Install dependencies
```bash
make install
```

### Run in development mode (with auto-reload)
```bash
make dev
```

## Database Management

### Sync database schema
```bash
make migrate
# or manually:
uv run alembic upgrade head
```

## Available Make Commands

- `make install` - Create venv and install dependencies  
- `make build` - Build application (install + migrate)
- `make run` - Run the application
- `make dev` - Run with auto-reload for development
- `make migrate` - Run database migrations
- `make test` - Run pytest tests
- `make lint` - Run code linting
- `make format` - Format code with black
- `make clean` - Clean build artifacts
- `make help` - Show available commands

## Manual Commands

### Activate virtual environment
```bash
# Windows
.venv\Scripts\activate

# Linux/macOS  
source .venv/bin/activate
```

### Install dependencies manually
```bash
uv venv
uv pip install -e .
```

### Run application manually and check [localhost link](http://0.0.0.0:8000)
```bash
uv run python main.py
```