# Deployment & infrastructure

## Environment variables

All settings are driven by environment variables with the `CHITAI_` prefix (Pydantic settings in `src/chitai/settings.py`).

| Variable                          | Default                  | Effect                                    |
|-----------------------------------|--------------------------|-------------------------------------------|
| `CHITAI_RELOAD`                   | `false`                  | Uvicorn hot-reload (dev only)             |
| `CHITAI_DATABASE_URL`             | `sqlite:///data/chitai.db` | SQLAlchemy connection string            |
| `CHITAI_GRACE_PERIOD_SECONDS`     | `3600`                   | Idle session auto-end timeout             |
| `CHITAI_WS_PING_TIMEOUT_SECONDS`  | `300`                    | Uvicorn WebSocket ping timeout            |
| `CHITAI_CERT_DIR`                 | `data/certs`             | Directory for TLS cert and key            |

## TLS

All connections use TLS. On first container start, `docker/entrypoint.sh` checks for `cert.pem` and `key.pem` in the cert directory. If they are missing it runs `generate-cert.sh` to create a self-signed certificate. The cert persists in the `data/` volume across container restarts and rebuilds.

Clients connect via `wss://`. Browsers will show a certificate warning on first visit; this is expected for a local-network tool.

## Docker Compose profiles

`docker/compose.yaml` defines two profiles:

- **`dev`** (`chitai-dev` service): source tree is bind-mounted into the container, `CHITAI_RELOAD=true` enables hot-reload. Start with `just docker-up`.
- **`prod`** (`chitai` service): pulls a pre-built image from the container registry, `restart: unless-stopped`, data volume is the only mount. A `watchtower` sidecar checks for new images every 5 minutes and auto-updates.

## CI/CD

Two GitHub Actions workflows in `.github/workflows/`:

**`ci.yaml`** — runs on every PR and on push to main.
- Code quality: `just check` (ruff format, prettier, ruff lint, ty type check)
- Tests: `just test` (pytest with coverage)
- Container smoke test: build the prod image, start it, wait for healthy, stop it.

Main branch is protected; CI must pass before merge.

**`deploy.yaml`** — runs after CI succeeds on main.
- Builds the Docker image and pushes it to `ghcr.io/taketwo/chitai:latest`.

## Local development workflow

```bash
just docker-up          # start dev container (builds if needed)
just docker-logs -f     # follow logs (frontend logs appear here too)
just docker-restart     # force rebuild + restart
just docker-down        # stop
```

The `just` recipes are the intended entry point for all common tasks. See `justfile` for the full list.
