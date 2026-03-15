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

# Load from any supported format
system = System.from_raw("ieee14.raw")              # PSS/E RAW
system = System.from_matpower("case14.m")            # MATPOWER
system = System.from_pop("WEST10peak.pop")           # CPAT .pop
system = System.from_dyna("model.dyna")              # CPAT .dyna
system = System.from_dss("network.dss")              # OpenDSS
system = System.from_json("ieee14.psfg.json")        # psforge JSON
system = System.from_file("case14.m")                # Auto-detect

# Export to any format
system.to_raw("output.raw")
system.to_matpower("output.m")
system.to_json("output.psfg.json")                   # Human/LLM-friendly
system.to_file("output.m")                           # Auto-detect

# Explore the system
print(f"Buses: {len(system.buses)}, Branches: {len(system.branches)}")
print(system.to_summary())
```

```bash
# Or use the CLI
psforge-grid info ieee14.raw
psforge-grid show case14.m buses -f json
```

## Why psforge-grid?

| Feature | psforge-grid | Others |
|---------|--------------|--------|
| **LLM-friendly output** | Built-in JSON/summary formats | Manual formatting |
| **Educational design** | Rich docstrings, clear naming | Varies |
| **Type hints** | Complete type annotations | Often missing |
| **CLI included** | Yes, with multiple output formats | Usually separate |
| **Multi-format I/O** | 7 formats: RAW, MATPOWER, CPAT, OpenDSS, JSON | Usually single format |

## Overview

psforge-grid serves as the **Hub** of the psforge ecosystem, providing:

- Common data classes (`System`, `Bus`, `Branch`, `Generator`, `GeneratorCost`, `Load`, `Shunt`)
- **Parsers & Writers** for 7 formats (see [Supported Formats](#supported-formats))
- **Factory pattern**: `ParserFactory` / `WriterFactory` for format-agnostic I/O
- **Scenario loading**: Base case + differential modifications for N-1 / parametric studies
- OPF data support (`GeneratorCost` with polynomial and piecewise-linear cost models)
- Zero-sequence impedance and generator machine parameters for fault/stability analysis

## Supported Formats

| Format | Parse | Write | Extension | Round-trip |
|--------|-------|-------|-----------|------------|
| PSS/E RAW (v33/v34) | Yes | Yes (v33) | `.raw` | Yes |
| MATPOWER | Yes | Yes | `.m` | Yes |
| CPAT .pop (ZIP/XML) | Yes | Yes | `.pop` | Yes |
| CPAT .dyna (cards) | Yes | Yes | `.dyna` | Yes |
| OpenDSS | Yes | Yes | `.dss` | Yes |
| **psforge JSON** | Yes | Yes | `.psfg.json` | Yes |
| psforge Scenario | Yes | Yes | `.psfg.json` | - |

<details>
<summary>PSS/E RAW format details</summary>

### PSS/E RAW

The parser supports **core power flow data** for AC power flow analysis:

| Section | v33 | v34 | Notes |
|---------|-----|-----|-------|
| Case Identification | Yes | Yes | Base MVA, system info |
| Bus Data | Yes | Yes | All bus types (PQ, PV, Slack, Isolated) |
| Load Data | Yes | Yes | Constant power loads |
| Fixed Shunt Data | Yes | Yes | Capacitors and reactors |
| Generator Data | Yes | Yes | P, Q, voltage setpoint, Q limits |
| Branch Data | Yes | Yes | Transmission lines |
| Transformer Data | Yes | Yes | Two-winding, magnetizing admittance, `is_xfmr` flag |

**Not yet supported:** Area/Zone/Owner Data, DC lines, FACTS, Switched Shunts, Three-winding Transformers.

**Test data sources:**
- IEEE 9-bus (v34): [GitHub - todstewart1001](https://github.com/todstewart1001/PSSE-24-Hour-Load-Dispatch-IEEE-9-Bus-System-)
- IEEE 14-bus (v33): [GitHub - ITI/models](https://github.com/ITI/models/blob/master/electric-grid/physical/reference/ieee-14bus/)
- IEEE 118-bus (v33): [GitHub - powsybl](https://github.com/powsybl/powsybl-distribution/blob/main/resources/PSSE/IEEE_118_bus.raw)

</details>

<details>
<summary>MATPOWER format details</summary>

### MATPOWER

Supports [MATPOWER](https://matpower.app/) `.m` files, including [pglib-opf](https://github.com/power-grid-lib/pglib-opf) benchmark cases.

| Section | Notes |
|---------|-------|
| Bus Data (13 columns) | All bus types, Vmin/Vmax for OPF |
| Generator Data (10 columns) | Pmin/Pmax, Qmin/Qmax |
| Branch Data (13 columns) | Including angmin/angmax for OPF |
| Generator Cost Data | Polynomial (model=2) and piecewise-linear (model=1) |

```python
system = System.from_matpower("pglib_opf_case14_ieee.m")
for cost in system.generator_costs:
    print(cost.to_description())
    # "Generator Cost (polynomial, degree 2): 0.0430 * P^2 + 20.00 * P + 0.00"
```

</details>

<details>
<summary>CPAT format details (.pop / .dyna)</summary>

### CPAT

Supports two [CPAT](https://www.jpower.co.jp/bs/cpat/) formats for IEEJ standard model systems.

**`.pop` format** (recommended): CPAT-GUI native project file (ZIP archive + XML).

| Feature | Status | Notes |
|---------|--------|-------|
| System data (pnsd) | Yes | Nodes, branches, generators, loads |
| Generator machine data | Yes | G1-G5 card fields (Xd, Xd', Xd'', etc.) |
| Zero-sequence data | Yes | Branch and generator zero-sequence impedances |

**`.dyna` card format**: Legacy Fortran fixed-column (80-character) cards.

| Card Type | Description |
|-----------|-------------|
| DATA | System name, base MVA, frequency |
| T / X / N | Transmission lines / Transformers / Nodes |
| G1-G5 | Generator machine parameters |

</details>

<details>
<summary>OpenDSS format details</summary>

### OpenDSS

Supports [OpenDSS](https://opendss.epri.com/) `.dss` script files via [opendssdirect.py](https://pypi.org/project/opendssdirect.py/).

**DSSWriter** converts per-unit → physical units:

| System Element | OpenDSS Element |
|---------------|-----------------|
| Swing bus | `New Circuit` (Vsource) |
| Branch (line) | `New Line` |
| Branch (transformer) | `New Transformer` |
| Generator | `New Generator` |
| Load / Shunt | `New Load` / `New Capacitor` / `New Reactor` |

**Fault study mode** (`write_fault_study()`): Y-circuit transformer model with Yg-Delta grounding for zero-sequence analysis.

**DSSParser** compiles `.dss` files with OpenDSS and extracts data via API.

</details>

<details>
<summary>psforge JSON format details (.psfg.json)</summary>

### psforge JSON

Human/LLM-friendly native format with explicit metadata, distinct from pglib-uc JSON.

- **Extension**: `.psfg.json`
- **Metadata**: `"format": "psforge-grid"`, `"version": "1.0"`
- **Field names**: snake_case with unit suffixes (`_pu`, `_mw`, `_kv`)
- **Compact output**: `None` fields omitted by default

```python
# Export / Import
system.to_json("ieee14.psfg.json")
system = System.from_json("ieee14.psfg.json")

# Include all fields (with null values)
system.to_json("full.psfg.json", omit_none=False)
```

#### Scenario loading (base case + modifications)

Define N-1 contingencies or parametric studies with minimal data:

```python
from psforge_grid.io import load_scenarios, write_scenario

# Define scenarios
write_scenario(
    "contingencies.psfg.json",
    base_case="ieee14.psfg.json",
    scenarios=[
        {
            "name": "N-1_Line_1-5",
            "modifications": [
                {"target": "branches", "match": {"from_bus": 1, "to_bus": 5},
                 "set": {"status": 0}}
            ]
        },
    ],
)

# Load: returns {"base": System, "N-1_Line_1-5": System, ...}
scenarios = load_scenarios("contingencies.psfg.json")
```

</details>

## LLM Affinity Design

> **"Pickaxe in the Gold Rush"** - psforge is designed for seamless LLM integration.

| Feature | Description |
|---------|-------------|
| **Explicit Units** | Field names include units (`voltage_pu`, `power_mw`) |
| **Semantic Status** | Enum-based status annotations (`VoltageStatus.LOW`) |
| **Self-Documenting** | Rich docstrings explaining physical meaning |
| **to_description()** | Human/LLM-readable output methods |

```python
bus = system.get_bus(14)
print(bus.to_description())
# Output: "Bus 14 (LOAD_BUS): 13.8 kV, PQ type"
```

### CLI for LLM Integration

```bash
psforge-grid info ieee14.raw              # Table format
psforge-grid info ieee14.raw -f json      # JSON for API/LLM
psforge-grid info ieee14.raw -f summary   # Compact for tokens
psforge-grid show ieee14.raw buses -f json
psforge-grid validate ieee14.raw --strict
```

**Output Formats:** `table` (default), `json`, `summary`, `csv`

See [CLAUDE.md](CLAUDE.md) for detailed AI development guidelines.

## Installation

```bash
pip install psforge-grid

# Or install from source
pip install -e .
```

## Development

See [docs/development.md](docs/development.md) for full setup instructions (pre-commit hooks, editor config, etc.).

```bash
pip install -e ".[dev]"     # Install dev dependencies
pytest tests/ -v            # Run tests
ruff check src/ tests/      # Lint
mypy src/                   # Type check
```

## psforge Ecosystem (Hub & Spoke Architecture)

```
                    ┌──────────────────────┐
                    │    psforge-grid      │
                    │   (Hub: Data & I/O)  │
                    └──────────┬───────────┘
                               │
     ┌─────────────┬───────────┼───────────┬─────────────┐
     │             │           │           │             │
┌────▼────┐  ┌────▼────┐ ┌────▼─────┐ ┌───▼────┐  ┌────▼────┐
│ psforge │  │ psforge │ │ psforge- │ │psforge-│  │ psforge │
│  -flow  │  │ -fault  │ │stability │ │schedule│  │ -turbo  │
│ (Power  │  │ (Fault  │ │(Transient│ │ (Unit  │  │  (C++   │
│  Flow)  │  │Analysis)│ │Stability)│ │Commit.)│  │ Engine) │
└─────────┘  └─────────┘ └──────────┘ └────────┘  └─────────┘
```

| Package | Description | Status |
|---------|-------------|--------|
| **psforge-grid** (this) | Core data models, parsers, and CLI | Active |
| **psforge-flow** | AC power flow (Newton-Raphson) | Active |
| **psforge-fault** | Short-circuit fault analysis | Active |
| **psforge-stability** | Transient stability analysis | Planned |
| **psforge-schedule** | Unit commitment optimization | Planned |
| **psforge-turbo** | High-performance C++ engine (Phase 2) | Frozen |

All packages are developed and maintained by [Manabe Lab LLC](https://github.com/manabelab).

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
