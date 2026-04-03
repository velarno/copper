# CLAUDE.md — Copper CLI

Copper is a Python CLI tool for interacting with the [Copernicus Climate Data Store (CDS)](https://cds.climate.copernicus.eu/). It provides dataset discovery, template-based request management, cost estimation/optimization, and data download using the STAC (SpatioTemporal Asset Catalog) API.

---

## Repository Structure

```
copper/
├── api/
│   ├── stac/                  # Core STAC API module
│   │   ├── __init__.py        # Module exports
│   │   ├── client.py          # httpx-based STAC API client with rate limiting
│   │   ├── commands.py        # Typer CLI commands (stac subgroup)
│   │   ├── config.py          # Pydantic settings, enums, logging setup
│   │   ├── crud.py            # High-level DB operations (CollectionBrowser, TemplateUpdater)
│   │   ├── database.py        # SQLite engine/table initialization
│   │   ├── exceptions.py      # Custom exception hierarchy
│   │   ├── models.py          # SQLModel ORM models
│   │   ├── optimizer.py       # TemplateOptimizer: budget-based request splitting
│   │   └── utils.py           # HTTP helpers, model-to-JSON/table converters
│   └── templates/
│       └── commands.py        # Typer CLI commands (template subgroup)
├── tests/
│   ├── conftest.py            # Pytest fixtures; session-scoped catalog loader
│   ├── test_optimizer.py
│   ├── test_template.py
│   └── test_utils.py
├── docs/
│   ├── TESTING.md             # Testing guide
│   └── badges.md
├── specs/
│   └── costings-module.md     # Design spec for cost estimation
├── scripts/
│   └── setup-pre-commit.sh    # Install/configure pre-commit hooks
├── main.py                    # CLI entry point (wires stac + template subcommands)
├── pyproject.toml             # Package metadata, dependencies, scripts
├── pytest.ini                 # Pytest options and coverage config
├── .pre-commit-config.yaml    # Ruff lint/format + basic checks
└── .python-version            # 3.12
```

---

## Development Setup

**Package manager**: `uv` (required — do not use pip directly)

```bash
uv sync --group dev     # Install all dependencies including dev group
./scripts/setup-pre-commit.sh  # Install pre-commit hooks (run once)
```

**Python version**: 3.12 (pinned in `.python-version`)

**CLI entry points** (both are the same):
```bash
uv run copper <command>
uv run cdsfetch <command>
```

---

## Running Tests

```bash
uv run pytest                    # Run all tests with coverage
uv run pytest -m critical        # Run only critical tests
uv run pytest -m unit            # Run only unit tests
uv run pytest -m "not slow"      # Skip slow tests
uv run pytest tests/test_optimizer.py  # Run a specific file
uv run coverage report           # Print coverage summary
```

Test markers defined in `pytest.ini`: `unit`, `integration`, `slow`, `critical`

Coverage configuration:
- Source: `api/` only
- Minimum threshold: 50%
- Reports: terminal-missing, HTML (`htmlcov/`), XML (`coverage.xml`)

Fixtures in `conftest.py` include a session-scoped fixture that calls `init_all_collections()` to populate the SQLite DB before any tests run. Tests that require a loaded catalog depend on this.

---

## Linting and Formatting

**Tool**: Ruff (via pre-commit)

```bash
pre-commit run              # Run all hooks on staged files
pre-commit run --all-files  # Run on entire codebase
uv run ruff check --fix .   # Auto-fix linting issues
uv run ruff format .        # Format code
```

Line length: **88** characters (Ruff default).

Pre-commit also enforces: trailing whitespace, end-of-file newlines, YAML validity, no large files, no merge conflict markers, no debug statements.

---

## Architecture Overview

### CLI Layer (`main.py`, `api/stac/commands.py`, `api/templates/commands.py`)

- Built with **Typer**; hierarchical subcommands: `copper stac ...` and `copper template ...`
- `copper tpl` is a hidden alias for `copper template`
- Many template subcommands have short aliases (e.g., `+` for `add`, `-` for `remove`)
- Output format is controlled by `--json` flag (Rich table vs. raw JSON)

### Data Models (`api/stac/models.py`)

All models use **SQLModel** (Pydantic + SQLAlchemy hybrid). Key model groups:
- **Catalog/Collection**: `CatalogLink`, `Collection`, `Keyword`, `CollectionLink`
- **Schemas**: `InputSchema`, `InputParameter`, `SchemaConstraints`
- **Templates**: `Template`, `TemplateParameter`, `TemplateHistory`
- **Cost**: `CostEstimate`
- **Variable types**: `SingleEnumVariable`, `SingleArrayVariable`, `NumberArrayVariable`

### Database (`api/stac/database.py`, `api/stac/crud.py`)

- **SQLite** (`database.db`) via SQLModel engine
- `database.py`: engine creation, table initialization with `SQLModel.metadata.create_all()`
- `crud.py`: `CollectionBrowser` (read/search collections) and `TemplateUpdater` (template CRUD)
- Session lifecycle: use `with Session(engine) as session` pattern

### STAC API Client (`api/stac/client.py`)

- `StacClient` extends `httpx.Client`
- Rate limit: 10 requests/minute (configurable)
- `init_all_collections()` fetches all collections from CDS and populates the local DB
- Custom exceptions from `exceptions.py` are raised for auth/rate-limit/API errors

### Cost Optimizer (`api/stac/optimizer.py`)

- `TemplateOptimizer.ensure_budget()`: splits a template into multiple smaller ones so each fits within a cost budget
- Splitting strategy: BFS, always splits the highest-cardinality parameter first
- `param_cardinalities()` computes the size of each parameter dimension
- `param_factors()` returns prime factorizations used to determine split points

### Configuration (`api/stac/config.py`)

- `STACConfig` is a Pydantic `BaseSettings` class
- Environment variables: `CDS_API_KEY`, `LOG_LEVEL`
- Enums: `CostMethod` (`local` | `api`), `OutputFormat` (`json` | `table`)
- `setup_logging()` configures the root logger

---

## Key Conventions

### Naming
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants/enums: `UPPER_SNAKE_CASE`
- Private helpers: `_leading_underscore`

### Error Handling
- Raise typed exceptions from `api/stac/exceptions.py` (never bare `Exception`)
- Exception hierarchy: `STACError` → `STACValidationError`, `STACDatabaseError`, `STACAPIError`, `STACAuthenticationError`, `STACRateLimitError`, `STACOptimizationError`, `STACConfigurationError`
- In CLI commands, catch exceptions and call `typer.Exit(1)` with a Rich error message

### Type Hints
- All functions must have full type annotations
- Use `Optional[X]` / `X | None` (Python 3.10+ union syntax acceptable)
- Use `TypedDict` for complex dict shapes

### Database Sessions
- Always use context manager: `with Session(engine) as session:`
- Add then `session.commit()` and `session.refresh(obj)` after writes
- Avoid keeping sessions open across async boundaries

### Adding New CLI Commands
1. Add the Typer command in the relevant `commands.py`
2. Use `typer.Option` / `typer.Argument` with help strings
3. Add aliases via `@app.command(name="...", aliases=[...])`
4. Output: default to Rich table; add `--json` flag for JSON output using `models_to_json()` / `models_to_table()` from `utils.py`

---

## CI/CD

**GitHub Actions**: `.github/workflows/test.yml`

- Triggers: push/PR to `main` or `develop`
- Matrix: Python 3.10, 3.11, 3.12 on Ubuntu latest
- Steps: checkout → setup Python → install uv → cache deps → `uv sync --group dev` → pytest with coverage → upload to Codecov → enforce 50% threshold

---

## Environment Variables

| Variable      | Description                         | Required |
|---------------|-------------------------------------|----------|
| `CDS_API_KEY` | Copernicus CDS API key              | Yes (for API calls) |
| `LOG_LEVEL`   | Logging level (`INFO`, `DEBUG`, …)  | No (default: `INFO`) |

CDS credentials can also be placed in `~/.cdsapirc` (standard cdsapi config file).

---

## Important Files to Know

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point — wires subcommands together |
| `api/stac/models.py` | All ORM models — source of truth for data shapes |
| `api/stac/crud.py` | All DB read/write logic |
| `api/stac/client.py` | CDS API interaction |
| `api/stac/optimizer.py` | Template cost splitting logic |
| `tests/conftest.py` | Shared fixtures; catalog initialization |
| `pyproject.toml` | Dependencies and package config |
| `todo.md` | Remaining known issues and planned work |
