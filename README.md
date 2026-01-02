# psforge-grid

[![PyPI version](https://badge.fury.io/py/psforge-grid.svg)](https://badge.fury.io/py/psforge-grid)
[![Python versions](https://img.shields.io/pypi/pyversions/psforge-grid.svg)](https://pypi.org/project/psforge-grid/)
[![Tests](https://github.com/manabelab/psforge-grid/actions/workflows/test.yml/badge.svg)](https://github.com/manabelab/psforge-grid/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Hub data model for the psforge power system analysis ecosystem**

Core data models and I/O for power system analysis with LLM-friendly design.

## Quick Start

```bash
pip install psforge-grid
```

```python
from psforge_grid import System

# Load a PSS/E RAW file
system = System.from_raw("ieee14.raw")

# Explore the system
print(f"Buses: {len(system.buses)}, Branches: {len(system.branches)}")

# Get LLM-friendly summary
print(system.to_summary())
```

```bash
# Or use the CLI
psforge-grid info ieee14.raw
psforge-grid show ieee14.raw buses -f json
```

## Why psforge-grid?

| Feature | psforge-grid | Others |
|---------|--------------|--------|
| **LLM-friendly output** | Built-in JSON/summary formats | Manual formatting |
| **Educational design** | Rich docstrings, clear naming | Varies |
| **Type hints** | Complete type annotations | Often missing |
| **CLI included** | Yes, with multiple output formats | Usually separate |
| **PSS/E RAW support** | v33/v34 core sections | Varies |

## Overview

psforge-grid serves as the **Hub** of the psforge ecosystem, providing:

- Common data classes (`System`, `Bus`, `Branch`, `Generator`, `Load`, `Shunt`)
- PSS/E RAW file parser (v33/v34 partial support)
- Shared utilities for power system analysis

## LLM Affinity Design

> **"Pickaxe in the Gold Rush"** - psforge is designed for seamless LLM integration.

psforge-grid implements LLM-friendly data structures and CLI:

| Feature | Description |
|---------|-------------|
| **Explicit Units** | Field names include units (`voltage_pu`, `power_mw`) |
| **Semantic Status** | Enum-based status annotations (`VoltageStatus.LOW`) |
| **Self-Documenting** | Rich docstrings explaining physical meaning |
| **to_description()** | Human/LLM-readable output methods |

```python
# Example: LLM-friendly bus description
bus = system.get_bus(14)
print(bus.to_description())
# Output: "Bus 14 (LOAD_BUS): 13.8 kV, PQ type"
```

### CLI for LLM Integration

psforge-grid includes a CLI designed for LLM-friendly output:

```bash
# System summary in different formats
psforge-grid info ieee14.raw              # Table format
psforge-grid info ieee14.raw -f json      # JSON for API/LLM
psforge-grid info ieee14.raw -f summary   # Compact for tokens

# Display element details
psforge-grid show ieee14.raw buses
psforge-grid show ieee14.raw branches -f json

# Validate system data
psforge-grid validate ieee14.raw
psforge-grid validate ieee14.raw --strict
```

**Output Formats:**
- `table`: Human-readable tables (default)
- `json`: Structured JSON for LLM/API processing
- `summary`: Compact text for token-efficient LLM usage
- `csv`: Comma-separated values for data analysis

See [CLAUDE.md](CLAUDE.md) for detailed AI development guidelines.

## PSS/E RAW Format Support

### Current Status

The parser supports **core power flow data** required for basic AC power flow analysis:

| Section | v33 | v34 | Notes |
|---------|-----|-----|-------|
| Case Identification | Yes | Yes | Base MVA, system info |
| Bus Data | Yes | Yes | All bus types (PQ, PV, Slack, Isolated) |
| Load Data | Yes | Yes | Constant power loads |
| Fixed Shunt Data | Yes | Yes | Capacitors and reactors |
| Generator Data | Yes | Yes | P, Q, voltage setpoint, Q limits |
| Branch Data | Yes | Yes | Transmission lines |
| Transformer Data | Yes | Yes | Two-winding transformers only |

### Not Yet Supported

The following sections are parsed but ignored (data is skipped):

- Area Data, Zone Data, Owner Data
- Two-Terminal DC Data, Multi-Terminal DC Data
- VSC DC Line Data, FACTS Device Data
- Switched Shunt Data (use Fixed Shunt instead)
- Multi-Section Line Data, Impedance Correction Data
- GNE Data, Induction Machine Data, Substation Data
- Three-winding Transformers

### Test Data Sources

Parser has been validated with IEEE test cases from multiple sources:

- IEEE 9-bus (v34): [GitHub - todstewart1001](https://github.com/todstewart1001/PSSE-24-Hour-Load-Dispatch-IEEE-9-Bus-System-)
- IEEE 14-bus (v33): [GitHub - ITI/models](https://github.com/ITI/models/blob/master/electric-grid/physical/reference/ieee-14bus/)
- IEEE 118-bus (v33): [GitHub - powsybl](https://github.com/powsybl/powsybl-distribution/blob/main/resources/PSSE/IEEE_118_bus.raw)

### Future Plans

1. **Phase 2**: Three-winding transformer support
2. **Phase 3**: Switched shunt data support
3. **Future**: HVDC, FACTS device support (as needed)

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

#### Option 1: Global Install with pipx (Recommended)

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

#### Option 2: Local Install in Virtual Environment

```bash
# Install pre-commit in your virtual environment
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually on all files
pre-commit run --all-files
```

> **Note:** CI runs ruff and mypy checks via GitHub Actions (`.github/workflows/test.yml`), so code quality is enforced on push/PR even if local hooks are skipped.

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

## Related Projects

psforge is a modular power system analysis ecosystem:

| Package | Description | Status |
|---------|-------------|--------|
| **psforge-grid** (this) | Core data models and I/O (Hub) | Active |
| [psforge-flow](https://github.com/manabelab/psforge-flow) | AC power flow calculation | Active |
| psforge-stability | Transient stability analysis | Planned |
| psforge-schedule | Unit commitment optimization | Planned |

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest tests/`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

See [CLAUDE.md](CLAUDE.md) for AI development guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Developed by [Manabe Lab LLC](https://github.com/manabelab)**
