# Chitai

Reading practice tool

## Quick start

### Development

```bash
# Start dev environment with Docker (hot-reload enabled)
just docker-up
```

Access the interfaces:
- Controller: http://localhost:8000/web/controller/
- Display: http://localhost:8000/web/display/
- Admin: http://localhost:8000/web/admin/

### Production deployment

1. **First-time setup on server:**
   ```bash
   git clone https://github.com/taketwo/chitai.git
   cd chitai
   docker compose -f docker/compose.yaml --profile prod up -d
   ```

2. **Updates:**
   - Push to `main` branch triggers CI
   - On successful tests, Docker image is pushed to GitHub Container Registry
   - On server, pull and restart:
   ```bash
   docker compose -f docker/compose.yaml --profile prod pull
   docker compose -f docker/compose.yaml --profile prod up -d
   ```

The application will automatically restart on server reboot.

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
