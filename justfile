# Show available commands
default:
    @just --list

# Run all checks
check: check-format check-lint check-type

# Verify code formatting
check-format:
    uv run ruff format --check .
    npx prettier --check web/

# Run linting checks
check-lint:
    uv run ruff check .

# Run type checking
check-type:
    uv run ty check

# Auto-format and auto-fix all issues
fix: fix-format fix-lint

# Auto-format code
fix-format:
    uv run ruff format .
    npx prettier --write web/

# Auto-fix linting issues
fix-lint:
    uv run ruff check --fix .

# Run all tests with coverage
test:
    uv run pytest --cov=src/chitai --cov-report=term-missing

# Run only unit tests
test-unit:
    uv run pytest tests/unit/

# Run only integration tests
test-integration:
    uv run pytest tests/integration/

# Start dev environment (builds image if needed)
docker-up:
    docker compose -f docker/compose.yaml --profile dev up -d --build

# Stop containers
docker-down:
    docker compose -f docker/compose.yaml down

# View container logs
docker-logs:
    docker compose -f docker/compose.yaml logs -f

# Rebuild and restart dev environment
docker-restart:
    docker compose -f docker/compose.yaml --profile dev up -d --build --force-recreate
