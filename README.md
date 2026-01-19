# Chitai

Reading practice tool

## Deployment

### Requirements

- Docker with compose plugin
- Git

#### Installing requirements on Ubuntu 24.04

```bash
# Install Docker
sudo apt install -y docker.io docker-compose-v2
# Enable Docker to start on boot
sudo systemctl enable docker
sudo systemctl start docker
# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER
```

### First-time setup

Clone and start the application:

```bash
git clone https://github.com/taketwo/chitai.git
cd chitai
docker compose -f docker/compose.yaml --profile prod up -d
```

This will:
- Pull the latest image from GitHub Container Registry
- Start the application on port 8000
- Start Watchtower to monitor for updates
- Configure automatic restart on server reboot

### Automatic updates

The deployment automatically stays up-to-date:
- Push to `main` branch triggers CI
- On successful tests, new Docker image is pushed to GitHub Container Registry
- Watchtower checks for updates every 5 minutes
- When a new image is found, Watchtower automatically pulls and restarts the application

### Stopping deployment

To stop and remove the application:

```bash
cd chitai
docker compose -f docker/compose.yaml --profile prod down
```

This stops all containers and prevents them from restarting on reboot.

## Development

### Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [just](https://github.com/casey/just) (command runner)
- Docker with compose plugin

### Setup

```bash
# Install dependencies
uv sync

# Set up database
just db-upgrade

# Run all checks (format, lint, type)
just check

# Run tests with coverage
just test

# Auto-fix formatting and linting issues
just fix
```

### Database

The application uses SQLite with Alembic for schema migrations:

```bash
# Apply pending migrations
just db-upgrade

# Reset database (delete and recreate from migrations)
just db-reset

# Create a new migration after model changes
just db-create-migration "description"
```

Database file is stored at `data/chitai.db`. Migrations run automatically on server startup in production.

### Docker development workflow

The dev environment uses Docker Compose with hot-reload enabled:

```bash
# Start dev environment (builds image if needed)
just docker-up

# View logs
just docker-logs

# Stop containers
just docker-down

# Rebuild and restart (needed after dependency or Docker config changes)
just docker-restart
```

The dev container:
- Mounts your local codebase at `/app` for live editing
- Runs with `CHITAI_RELOAD=true` for automatic code reloading
- Exposes the app on `http://localhost:8000`

**When to rebuild:**
- Dependency changes (`pyproject.toml`, `uv.lock`)
- Dockerfile or docker-compose changes

**No rebuild needed:**
- Python code changes (auto-reloaded)
- Static file changes (served from mounted volume)
