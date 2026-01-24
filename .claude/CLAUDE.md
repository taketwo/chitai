# Chitai — Project Guidelines

## Collaboration Guidelines

### Change Management

**NEVER commit changes without explicit instruction from the user.**

1. **Commits** - Wait for the user to explicitly ask you to commit
2. **Feature branches** - If asked to commit but not on a feature branch, STOP and ask:
   - Permission to create a new branch
   - What to name the branch
3. **Pull requests** - Only create PRs when the user explicitly asks
4. **Review first** - Always give the user time to review changes before any git operations
5. **Staging files** - NEVER use `git add -A` or `git add .`. If uncertain which files to stage, ask the user to stage them or explicitly list the files you intend to stage for confirmation

## Conventional Commits

### Commit Types

Use these conventional commit types:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only changes
- `refactor` - Code change that neither fixes a bug nor adds a feature
- `test` - Adding or updating tests
- `chore` - Tooling, dependencies, configuration

### Commit Scopes

Scopes are optional but recommended. Use these scopes:

**Core Application Layers:**
- `server` - FastAPI app, WebSocket handling, routing
- `db` - SQLAlchemy models, migrations, database operations
- `language` - Text processing, syllabification, language adapters
- `illustrations` - Image search, storage handling
- `settings` - Configuration management

**Client:**
- `ui` - All user interfaces (controller, display, admin)

**Infrastructure:**
- `docker` - Dockerfile, compose configuration
- `ci` - GitHub Actions workflows
- `deps` - Dependency updates
- `tests` - Test infrastructure changes

### Format

```
<type>[optional scope]: <description>

[optional body]
```

**Do NOT include attribution footers** (no "Generated with Claude Code" or "Co-Authored-By").

### Usage Examples
```
feat(language): add rusyll integration for Russian
feat(server): implement session state management
feat(ui): add word advance button to controller
fix(ui): resolve tablet layout on iPad
test(db): add integration tests for session persistence
chore(deps): update fastapi to 0.129.0
docs: update README with deployment instructions
chore: add justfile recipe for database migrations
```

## Python Dependencies

### Dependency Categories

- **Core runtime**: fastapi, pydantic-settings, uvicorn, websockets
- **Syllabification**: rusyll (Russian), pyphen (German/English, v1.0+)
- **Database** (v0.2+): sqlalchemy, alembic
- **Dev tools**: pytest, pytest-asyncio, pytest-cov, ruff, ty

### Adding Dependencies

Use `uv add <package>` for runtime dependencies, `uv add --dev <package>` for dev dependencies.

## Framework & Library Standards

### Pydantic v2

- Use `model_config = ConfigDict(from_attributes=True)` not `class Config`

### FastAPI

- Use `Annotated[Session, Depends(get_session)]` for dependencies
- Runtime type imports (`Session`, `Generator`) need `# noqa: TC002/TC003`

### SQLAlchemy

Use **SQLAlchemy 2.0 query style exclusively**:

- `session.scalars(select(Model).where(...))` for queries, **NOT** `session.query()`
- `session.get(Model, id)` for primary key lookups
- `.where()` instead of `.filter_by()`
- `.is_(None)` for NULL checks

### WebSockets

Starlette WebSocket operations raise:

- `WebSocketDisconnect` - connection closed or network error
- `RuntimeError` - WebSocket not connected/accepted yet
- `ValueError` - invalid JSON in receive_json()

Catch these exceptions when calling send/receive methods.

## Code Quality & Linting

### Ruff Configuration

This project uses Ruff with **ALL diagnostics enabled** (with a few exceptions defined in `pyproject.toml`).

Handling Ruff diagnostics:
1. **Try to fix diagnostics first** - most diagnostics point to real issues or better patterns
2. **Don't go crazy** - if a diagnostic seems unreasonable for this project, consider ignoring it
3. **Ignore hierarchy** (in order of preference):
   - Line-level ignore: `# noqa: <code>` for one-off cases
   - File-level ignore: `# ruff: noqa: <code>` at top of file for single files
   - Pattern-based ignore: Add to `lint.per-file-ignores` in `pyproject.toml` for file patterns (e.g., `tests/**/*.py`)
   - Project-level ignore: Add to `lint.ignore` in `pyproject.toml`
4. **ALL ignores require explicit user permission** - NEVER add any ignore without asking the user first and getting EXPLICIT permission

## Development Workflow

### Git Workflow

This project uses a **PR-based workflow** with branch protection:

1. **Never commit directly to main** - main branch is protected on GitHub
2. **Create feature branches** - use descriptive names: `feat/syllabification`, `fix/websocket-disconnect`
3. **Open PR when ready** - CI must pass (format, lint, type check, tests, docker build)
4. **Merge triggers deploy** - successful merge to main automatically deploys via GitHub Actions + Watchtower

**Typical workflow:**
```bash
git checkout -b feat/add-syllabification
# ... make changes ...
just fix          # Auto-format and fix issues
just check        # Verify all checks pass
just test         # Run tests
git add .
git commit -m "feat(syllables): add rusyll integration"
git push -u origin feat/add-syllabification
# ... open PR on GitHub ...
```

### Just Recipes

This project uses `just` for common development tasks. Always prefer using these recipes over running commands directly.

**Available recipes:**

- `just` - Show all available commands
- `just check` - Run all checks (format, lint, type)
- `just fix` - Auto-format and auto-fix all issues
- `just test` - Run all tests with coverage
- `just test-unit` - Run only unit tests
- `just test-integration` - Run only integration tests
- `just docker-build` - Build Docker image
- `just docker-up` - Start dev environment
- `just docker-down` - Stop containers
- `just docker-logs` - View container logs
- `just docker-restart` - Restart dev environment

**When working on code:**
1. Use `just fix` before committing to auto-format and fix linting issues
2. Use `just check` to verify all checks pass (mimics CI)
3. Use `just test` to run tests with coverage

**If a recipe is missing for a common task, add it to the justfile** rather than documenting manual commands.
