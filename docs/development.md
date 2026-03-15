# Development Setup

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

## Install Development Dependencies

```bash
# Using uv (recommended)
uv pip install -e ".[dev]"

# Or using pip
pip install -e ".[dev]"
```

## Setup Pre-commit Hooks

Pre-commit hooks automatically run ruff and mypy checks before each commit.

### Option 1: Global Install with pipx (Recommended)

Using [pipx](https://github.com/pypa/pipx) for global installation is recommended, especially when using **git worktree** for parallel development. This ensures `pre-commit` is available across all worktrees without additional setup.

```bash
# Install pipx if not already installed
brew install pipx  # macOS
# or: pip install --user pipx

# Install pre-commit globally
pipx install pre-commit

# Install hooks (only needed once per repository)
pre-commit install

# Run hooks manually on all files
pre-commit run --all-files
```

**Why pipx?**
- Works across all git worktrees without per-worktree setup
- Isolated environment prevents dependency conflicts
- Single installation, works everywhere

### Option 2: Local Install in Virtual Environment

```bash
# Install pre-commit in your virtual environment
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually on all files
pre-commit run --all-files
```

> **Note:** CI runs ruff and mypy checks via GitHub Actions (`.github/workflows/test.yml`), so code quality is enforced on push/PR even if local hooks are skipped.

## Manual Code Quality Checks

```bash
# Lint with ruff
ruff check src/ tests/

# Format with ruff
ruff format src/ tests/

# Type check with mypy
mypy src/
```

## Run Tests

```bash
pytest tests/ -v
```

## Editor Setup (VSCode/Cursor)

This project includes `.vscode/` configuration for seamless development:

- **Format on Save**: Automatically formats code with ruff
- **Organize Imports**: Automatically sorts imports
- **Type Checking**: Mypy extension provides real-time type checking

**Recommended Extensions:**
- `charliermarsh.ruff` - Ruff linter and formatter
- `ms-python.mypy-type-checker` - Mypy type checker
- `ms-python.python` - Python language support
