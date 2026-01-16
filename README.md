# Chitai

Reading practice tool

## Quick Start

### Development

```bash
# Start dev environment with Docker (hot-reload enabled)
just docker-up
```

Access the interfaces:
- Controller: http://localhost:8000/web/controller/
- Display: http://localhost:8000/web/display/
- Admin: http://localhost:8000/web/admin/

### Production

```bash
docker build -f docker/Dockerfile -t chitai:latest .
docker compose -f docker/compose.yaml --profile prod up -d
```

## Development

### Requirements

- Python 3.14+
- uv
- just
- Docker

### Setup

```bash
# Install dependencies
uv sync

# Run all checks (format, lint, type)
just check

# Run tests with coverage
just test

# Auto-fix formatting and linting issues
just fix

# Build Docker image
just docker-build

# Start dev environment
just docker-up

# View all available commands
just --list
```
