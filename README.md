# psforge-grid

Core data models and I/O for the psforge project.

## Overview

psforge-grid serves as the **Hub** of the psforge ecosystem, providing:

- Common data classes (`System`, `Bus`, `Branch`, `Generator`, etc.)
- PSS/E `.raw` file parser
- Shared utilities for power system analysis

## Installation

```bash
# Install the package
pip install psforge-grid

# Or install from source
pip install -e .
```

## Development Setup

### Prerequisites

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Install Development Dependencies

```bash
# Using uv (recommended)
uv pip install -e ".[dev]"

# Or using pip
pip install -e ".[dev]"
```

### Setup Pre-commit Hooks

Pre-commit hooks automatically run ruff and mypy checks before each commit.

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks manually on all files
pre-commit run --all-files
```

### Manual Code Quality Checks

```bash
# Lint with ruff
ruff check src/ tests/

# Format with ruff
ruff format src/ tests/

# Type check with mypy
mypy src/
```

### Run Tests

```bash
pytest tests/ -v
```

### Editor Setup (VSCode/Cursor)

This project includes `.vscode/` configuration for seamless development:

- **Format on Save**: Automatically formats code with ruff
- **Organize Imports**: Automatically sorts imports
- **Type Checking**: Mypy extension provides real-time type checking

**Recommended Extensions:**
- `charliermarsh.ruff` - Ruff linter and formatter
- `ms-python.mypy-type-checker` - Mypy type checker
- `ms-python.python` - Python language support

## License

MIT
