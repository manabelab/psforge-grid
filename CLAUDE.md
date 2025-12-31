# psforge-grid - Claude AI Development Guidelines

## Repository Role

**psforge-grid** is the **Hub** of the psforge ecosystem, serving as the "dictionary" of power system data structures.

### Responsibilities

- Common data classes (`System`, `Bus`, `Branch`, `Generator`, `Load`, `Shunt`)
- PSS/E RAW file parser (v33/v34)
- Shared utilities for power system analysis
- **Foundation for LLM-friendly output structures**

---

## Interface & Factory Architecture

> **This repository implements the Interface-Factory pattern** for pluggable file format parsers.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    User Code                                │
│         system = System.from_raw("ieee14.raw")              │
│         # or: system = parse_raw("ieee14.raw")              │
├─────────────────────────────────────────────────────────────┤
│                    Factory Methods: System (models/system.py)│
│         - System.from_raw(): Create from PSS/E file         │
│         - System.from_file(): Auto-detect format            │
├─────────────────────────────────────────────────────────────┤
│                    Factory: ParserFactory (io/factories.py) │
│         - ParserFactory.create("raw") → RawParser           │
│         - ParserFactory.from_path(...) → auto-detect        │
├─────────────────────────────────────────────────────────────┤
│                    Interface: IParser (io/protocols.py)     │
│         - Abstract base class (ABC)                         │
│         - parse(filepath) → System                          │
├─────────────────────────────────────────────────────────────┤
│                    Implementations: io/                     │
│         - RawParser: PSS/E RAW format (v33/v34)             │
│         - [MatpowerParser]: MATPOWER format [planned]       │
└─────────────────────────────────────────────────────────────┘
```

### Module Structure

```
psforge_grid/
├── __init__.py          # Public API exports
├── models/              # Dataclass definitions
│   ├── __init__.py
│   ├── system.py        # System (with factory methods)
│   ├── bus.py
│   ├── branch.py
│   ├── generator.py
│   ├── load.py
│   └── shunt.py
└── io/                  # File I/O (Interface-Factory pattern)
    ├── __init__.py      # Public exports
    ├── protocols.py     # IParser interface
    ├── factories.py     # ParserFactory
    └── raw_parser.py    # RawParser implementation
```

### VSCode Navigation

- **F12 on System.from_raw()**: Goes to factory method
- **Ctrl+F12 on IParser.parse()**: Lists all implementations (RawParser, etc.)
- Docstrings include "See Also" cross-references

---

## LLM Affinity Design Principles

> **This repository is critical for LLM affinity** - all data models defined here must support LLM-friendly output.

### Core Principles for psforge-grid

| Principle | Application in psforge-grid |
|-----------|----------------------------|
| **Explicit over Implicit** | Data classes must include unit information (e.g., `voltage_pu`, `power_mw`) |
| **Semantic Annotation** | Status enums (`BusStatus.NORMAL`, `BusStatus.LOW_VOLTAGE`) for all entities |
| **Self-Documenting** | Rich docstrings explaining physical meaning, not just data types |

### Required Patterns

#### 1. Explicit Units in Field Names

```python
# GOOD: Unit is explicit
@dataclass
class BusResult:
    voltage_magnitude_pu: float
    voltage_magnitude_kv: float
    voltage_angle_deg: float

# BAD: Unit is ambiguous
@dataclass
class BusResult:
    v: float  # pu? kV? Which one?
    theta: float  # degrees? radians?
```

#### 2. Semantic Status Fields

```python
from enum import Enum

class VoltageStatus(Enum):
    NORMAL = "NORMAL"
    LOW = "LOW"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class BusResult:
    voltage_magnitude_pu: float
    voltage_status: VoltageStatus  # LLM can immediately understand state
```

#### 3. to_description() Methods

All data classes should have a `to_description()` method for LLM-readable output:

```python
@dataclass
class Bus:
    bus_id: int
    name: str
    base_kv: float

    def to_description(self) -> str:
        """Human/LLM-readable description of this bus."""
        return f"Bus {self.bus_id} ({self.name}): {self.base_kv} kV"
```

---

## Instructions for AI Agents

### When Modifying Data Classes

1. **Always include unit suffix** in field names (`_pu`, `_mw`, `_mvar`, `_kv`, `_deg`, `_rad`)
2. **Add status enums** for values that can be evaluated (voltage, loading, etc.)
3. **Write educational docstrings** explaining physical meaning
4. **Implement `to_description()`** for all public data classes
5. **Consider both education and business use cases**

### Type Hints

All public APIs must have complete type hints:

```python
def parse_raw(filepath: str | Path) -> System:
    """Parse a PSS/E RAW file and return a System object.

    Args:
        filepath: Path to the RAW file

    Returns:
        System object containing all parsed data

    Raises:
        FileNotFoundError: If the file does not exist
        ParseError: If the file format is invalid
    """
```

### Educational Value

Remember that psforge serves both education and professional markets. Code should be:

- **Readable**: Prioritize clarity over cleverness
- **Well-documented**: Explain the "why" not just the "what"
- **Progressive**: Support learners from beginner to expert
