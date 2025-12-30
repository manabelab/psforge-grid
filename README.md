# psforge-grid

Core data models and I/O for the psforge project.

## Overview

psforge-grid serves as the **Hub** of the psforge ecosystem, providing:

- Common data classes (`System`, `Bus`, `Branch`, `Generator`, `Load`, `Shunt`)
- PSS/E RAW file parser (v33/v34 partial support)
- Shared utilities for power system analysis

## LLM Affinity Design

> **"Pickaxe in the Gold Rush"** - psforge is designed for seamless LLM integration.

psforge-grid implements LLM-friendly data structures:

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
