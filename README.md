# Chitai

Reading practice tool

## Quick Start

### Development

```bash
# Run with Docker (dev profile with hot-reload)
cd docker
docker compose --profile dev up --build

# Or run locally
uv run main.py
```

Access the interfaces:
- Controller: http://localhost:8000/web/controller/
- Display: http://localhost:8000/web/display/
- Admin: http://localhost:8000/web/admin/

### Production

```bash
cd docker
docker compose --profile prod up --build -d
```

## Development

### Requirements

- Python 3.14+
- uv
- Docker (optional)

### Setup

```bash
# Install dependencies
uv sync

# Run linter
uv run ruff check

# Run type checker
uv run ty

# Run tests
uv run pytest
```
