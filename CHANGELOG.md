# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.10.0] - 2026-08-20

### Changed (BREAKING)

Every element is now identified by a unified string `id` (`^[A-Za-z0-9_]+$`,
unique across the whole system, all element types combined) and carries a
common identity layer: `id` / `order` (sort order, `float | None`) / `name` /
`tags` (`"key:value"` convention for region/voltage/facility grouping).
Identifier roles moved to `id`; the source-format keys remain as optional
round-trip data. Parsers generate ids deterministically: `B{number}` for
buses (file position where the format has no bus numbers) and type prefix +
1-based file position for everything else (`BR1`, `G1`, `LD1`, `SH1`,
`GC1`). Connection and source-key information deliberately stay out of the
id — an id that embeds `from`/`to` starts lying the moment the branch is
rewired — and `order` carries the same file position as a float.

| Element | Before | After |
|---------|--------|-------|
| Bus | `bus_id: int` | `id: str` + `number: int \| None` (source bus number) |
| Branch | `from_bus: int` / `to_bus: int` | `from_bus_id: str` / `to_bus_id: str` (Bus.id refs) |
| Branch | `circuit_id: str = "1"` | `circuit_id: str \| None = None` (source data) |
| Generator | `bus_id: int` / `gen_id: str = "1"` | `bus_id: str` / `machine_id: str \| None` |
| Load | `bus_id: int` / `load_id: str = "1"` | `bus_id: str` / `load_id: str \| None` |
| Shunt | `bus_id: int` / `shunt_id: str = "1"` | `bus_id: str` / `shunt_id: str \| None` |
| GeneratorCost | `gen_index: int` (list position) | `generator_id: str` (survives reordering) |
| DiagramData | `dict[int, ...]` / `dict[tuple, ...]` keys | keyed by element `id` strings |

- `System.get_bus()` / `get_bus_index()` / `get_bus_ids()` /
  `get_bus_generators()` and friends take/return string ids.
- psforge-grid JSON format version is now **2.0**. Version 1.x files are
  still read: elements are migrated to the identity schema on load
  (ids generated, `gen_index` resolved to `generator_id`), and writing the
  System back produces a 2.0 file.
- Writers that need integer bus numbers (RAW, MATPOWER, CPAT) use
  `Bus.number` and assign unused numbers in list order when it is absent.

### Added

- `System.id` / `System.order` / `System.tags`, and `System.case_time` —
  the point in time the network data represents, as ISO-8601 with partial
  precision (`"2026"`, `"2026-08"`, `"2026-08-20T15:00"`), so a monthly
  snapshot does not need a fabricated day.
- `System.get_element(id)` — cross-type lookup by unified id.
- `System.used_ids()` — every element id in the system.
- `System.assign_ids()` — opt-in regeneration of all ids by the standard
  rules, updating references and diagram keys consistently.
- `System.validate()` now checks id syntax, system-wide id uniqueness,
  GeneratorCost generator references and `case_time` format.
- Docstring examples run in CI (`pytest --doctest-modules src/`, #15) with a
  root `conftest.py` injecting a small `system` into the doctest namespace.

### Migration notes

- Spokes: psforge-flow pins `<0.10.0` and is unaffected until it migrates;
  psforge-fault must cap its pin below 0.10 before this release reaches
  PyPI.
- Renames are deliberately loud: code using `branch.from_bus` or
  `Bus(bus_id=1, ...)` fails with `AttributeError`/`TypeError` instead of
  silently comparing an int to a string.

## [0.9.1] - 2026-07-16

### Fixed

- `__version__` is read from installed package metadata instead of being
  hardcoded, so `pyproject.toml` is the single source of truth and the two
  cannot drift apart. The literal is why 0.7.0 shipped reporting `"0.6.0"`:
  the bump touched `pyproject.toml` and nothing cross-checked the other copy.
  0.9.0's value was correct only because it was corrected by hand.

  Verified against a built wheel rather than an editable install, since
  `importlib.metadata` reads install-time metadata: `psforge_grid-0.9.1` reports
  `0.9.1`.

## [0.9.0] - 2026-07-16

### Added

- `System.check_data_completeness()` reports inputs that downstream analyses
  need but the source file lacks (#9). RAW and MATPOWER data routinely arrives
  without branch ratings or machine reactances, and nothing rejected it: a
  thermal screening simply had no limit to compare against, and a fault study
  silently treated a reactance-less generator as absent, **understating** fault
  current rather than failing. IEEE 300 has `rate_a` missing on 411/411
  branches and reactances missing on 69/69 generators, and said nothing.

  The warnings are also surfaced by `validate_detailed()` and by
  `to_llm_context()`, which grows a `### Missing Data` section.

- `System.assign_default_ratings()` and `System.assign_default_reactances()`
  apply documented defaults for the two gaps above (#9). Both are **opt-in**:
  the package's stated position is that unspecified limits yield
  `NOT_CLASSIFIED` rather than an arbitrary default, so inventing data stays a
  decision the caller makes. Neither overwrites real data unless asked.

- `System.assumptions` records those invented-data decisions, and
  `to_llm_context()` / `to_description()` declare them. An LLM interpreting the
  results is told which numbers rest on assumptions instead of reporting them
  as measured. Not persisted by the writers: writing the system to a file bakes
  the invented values in and drops the note with them.

### Fixed

- `psforge validate -f json` reported `FAILED` for a system whose only issues
  were warnings, while `-f summary` reported `PASSED` for the very same system.
  The JSON branch keyed off all issues rather than errors alone.
- `psforge validate -f json` emitted unparseable JSON when a message was long
  enough for rich to line-wrap it, inserting newlines mid-string.

## [0.8.0] - 2026-07-16

### Changed

- **BREAKING**: `System` count accessors are now properties instead of methods (#8).
  `num_buses`, `num_branches`, `num_generators`, `num_loads`, `num_shunts` and
  `num_generator_costs` must be accessed without parentheses:

  ```python
  system.num_buses()   # before
  system.num_buses     # after
  ```

  This aligns `System` with every other model in the package (`Bus.is_pq`,
  `Branch.is_transformer`, `ScenarioSet.num_scenarios`, ...), which already
  expose derived scalars as properties. `System` was the sole outlier, and the
  inconsistency forced callers to guess which form applied.

- `System.__repr__` now returns a one-line summary instead of the
  dataclass-generated dump of every component (#8). The old repr expanded every
  bus, branch, generator, load and shunt recursively, reaching ~1.4 MB on
  IEEE 300; it is now 94 characters. Use `to_description()` or
  `to_llm_context()` for detailed output.

  ```text
  <System 'case300.raw' buses=300 branches=411 generators=69 loads=201 shunts=29 base_mva=100.0>
  ```

### Added

- Runnable usage examples in the docstrings of all six `System` count
  properties and `__repr__` (#10).

### Fixed

- `__version__` reported `0.6.0` while `pyproject.toml` declared `0.7.0`, so the
  released 0.7.0 package identified itself as 0.6.0 at runtime. Both now report
  `0.8.0`.
- The package docstring example called `system.to_summary()`, which does not
  exist. It now calls `to_description()` (#10).

## [0.7.0] - 2026-05-06

Released 2026-05-06 but never recorded here; reconstructed from the history.

### Added

- `DiagramData` model for GUI layout support, with schematic and geographic
  coordinate data on `System` (`diagram_schematic`, `diagram_geographic`).

### Known issues

- The package reports `__version__ == "0.6.0"` at runtime; `pyproject.toml`
  declares `0.7.0`. Fixed in 0.8.0.

## [0.6.0] - 2026-03-15

### Added

- `Modification`, `ScenarioDefinition`, `ScenarioSet` typed dataclasses (`models/scenario.py`)
  - Replaces dict-based `load_scenarios()` / `write_scenario()` functions
  - Type-safe scenario definitions with validation at construction time
  - `ScenarioSet.from_json()` / `to_json()` for file I/O
  - `ScenarioSet.resolve()` produces independent System objects per scenario
  - `to_description()` methods for LLM-friendly output on all 3 classes
- `psforge scenario list` CLI subcommand with `--format table|json|summary` output

### Changed

- `psforge_grid.io.scenario_loader` now re-exports `ScenarioSet` only (backward-compatible import path)

### Removed

- `load_scenarios()` and `write_scenario()` functions (use `ScenarioSet.from_json()` / `to_json()`)

## [0.5.0] - 2026-03-15

### Added

- `Branch.is_xfmr` field: Explicit transformer flag set by source format parsers
  - `True` when parsed from PSS/E TRANSFORMER DATA section
  - `None` (default) when the source format does not distinguish transformers
  - `is_transformer` property checks `is_xfmr` first, then falls back to tap_ratio/shift_angle heuristics
  - Fixes IEEE 9-bus DSSWriter misclassification (step-up transformers with tap_ratio=1.0 were exported as Lines)
- `IWriter` abstract interface (`io/protocols.py`) — symmetric counterpart of `IParser`
- `WriterFactory` (`io/factories.py`) with `create()`, `from_extension()`, `from_path()`, `available_formats()`, `supported_extensions()`
- `RawWriter` — exports System to PSS/E RAW v33 format
- `MatpowerWriter` — exports System to MATPOWER .m format (including gencost)
- `PopWriter` — exports System to CPAT .pop format (ZIP archive with 3 XML files)
- `DynaWriter` — exports System to CPAT dyna card format (80-char fixed-column)
- `DSSWriter` — exports System to OpenDSS .dss script format (per-unit → physical unit conversion)
- `DSSParser` — imports OpenDSS .dss files via `opendssdirect.py` API (compile-then-extract approach)
- `DSSWriter.write_fault_study()` — fault study mode with Y-circuit transformer model
  - Converts Yg-Yg transformers to Y-circuit equivalent (near-ideal transformer + series reactor + Yg-Delta grounding)
  - Outputs generator Vsource with Z1 (gen reactance) and Z0 (zero-sequence impedance)
  - Outputs line Z0 with configurable estimation factor when explicit zero-sequence data is unavailable
  - Z2 defaults to Z1 in OpenDSS (not explicitly output) for better 1LG/2LG accuracy
- `System.to_raw()`, `to_matpower()`, `to_pop()`, `to_dyna()`, `to_dss()` facade methods
- `System.from_dss()` facade method for OpenDSS import
- `System.to_file()` — auto-detect format by file extension
- `write_raw()`, `write_matpower()`, `write_pop()`, `write_dyna()`, `write_dss()` convenience functions
- Cross-format model fields: `Branch.winding_connection`, `nomv_from`, `nomv_to`, `sbase_mva`, `mag_g`, `mag_b`; `Generator.kv`, `connection`, `model_type`, `rneut`, `xneut`; `Load.kv`, `connection`, `model_type`; `Shunt.kv`, `connection`, `num_steps`; `System.frequency_hz`
- `Branch.reg_control_mode`, `reg_target_voltage_pu`, `tap_max`, `tap_min` — voltage regulation fields from CPAT .pop
- `opendssdirect.py` as core dependency for OpenDSS interoperability
- `JsonWriter` — exports System to psforge-grid JSON format (`.psfg.json`)
  - Human/LLM-friendly format with metadata (`"format": "psforge-grid"`, `"version": "1.0"`)
  - `None` fields omitted by default for compact output (`omit_none=True`)
  - Snake_case field names with unit suffixes (`_pu`, `_mw`, `_kv`)
- `JsonParser` — imports `.psfg.json` files with format validation (rejects pglib-uc and other JSON)
- `System.from_json()` and `System.to_json()` facade methods
- `load_scenarios()` — load base case + differential modifications for N-1 / parametric studies
- `write_scenario()` — write scenario definition files (`"format": "psforge-grid-scenario"`)
- Compound extension support in `ParserFactory.from_path()` and `WriterFactory.from_path()` for `.psfg.json`
- JSON fixture files: `ieee14.psfg.json`, `ieee9.psfg.json`, `WEST10peak.psfg.json`, `ieee14_contingencies.psfg.json`
- 41 JSON I/O tests (writer, parser, factory, fixture validation, scenario loading)
- `docs/development.md` — development setup guide (moved from README)
- 28 DSS writer/parser tests (factory, output, compilation, round-trip with bus/gen count verification)
- 25 writer tests including round-trip verification for all 4 formats
- CLI: Multi-format support — all commands (`info`, `show`, `validate`) accept any supported format via auto-detection (`from_file()`)
- CLI: `convert` command — format conversion between any supported formats (e.g., `.raw` → `.psfg.json`)
- CLI: `describe` command — natural language system description with detail levels (`brief`/`normal`/`full`)
- CLI: `diff` command — element-level comparison of two power system files (bus/branch/load changes)
- CLI: `show --where` filter — field expression filtering (e.g., `v_magnitude<0.95`)
- CLI: `show` element_id filtering — display specific element by ID (e.g., `show buses 1`)
- `System.validate_detailed()` — structured validation method (moved from CLI internal)
- `tests/conftest.py` — shared test fixtures (`fixtures_dir`, `ieee14_system`, `ieee9_system`)
- 32 new CLI tests (multi-format: 7, convert: 8, describe: 6, where: 6, diff: 5)

### Changed

- CLI: Renamed `raw_file` argument to `input_file` to reflect multi-format support
- `IFormatter`: Added `format_loads()` to the interface and all 4 implementations
- Refactored `_compute_diff()` into `_diff_buses()`, `_diff_branches()`, `_diff_loads()` helpers

### Fixed

- `VoltageStatus` duplicate definition removed from `formatters.py` (now imported from `models.enums`)
- Hardcoded π values replaced with `math.pi`/`math.degrees()` in `bus.py` and `generator.py`
- Version mismatch in `__init__.py` corrected (`0.3.0` → `0.4.0`)
- `show` element_id filter used shallow copy instead of `deepcopy` (could mutate original data)
- PopParser: Handle parallel circuit count (NL) correctly for multi-circuit branches
- PopParser: Read correct generator X0/X2 fields and transformer Z0 from .pop XML
- PopParser: Detect CPAT placeholder X0_Saturation (== Xd_Saturation) and treat as undefined to avoid using Xd as X0
- PopParser: Add X2_Saturation fallback when X2 field is empty
- PopParser: Fix Y1C convention — convert from CPAT half-charging (Y/2) to PSS/E total B convention (b_pu = Y1C * 2.0)
- PopWriter: Reverse Y1C conversion (Y1C = b_pu / 2.0)
- DSSWriter: Include R component in Y-circuit series reactor (previously X-only)
- DSSParser: Internal buses created by OpenDSS transformer modeling are now filtered out
- DSSParser: Swing bus generator (Circuit Vsource) is now recovered as a Generator with bus_type=3
- DSSParser: Bus types (swing/PV/PQ) are correctly assigned based on connected elements
- DSSWriter: Bus naming is now consistent across all element types (Circuit, Line, Transformer, Generator, Load, Shunt)

## [0.4.0] - 2026-03-12

### Added

- CPAT `.pop` format parser (`PopParser`) for CPAT-GUI project files (ZIP/XML)
  - Reads `data.pnsd` XML inside the ZIP archive
  - Parses nodes, branches (transmission lines and transformers), generators (G1-G5 machine data), and loads
  - Supports IEEJ standard model systems (e.g., `WEST10peak.pop`)
- CPAT dyna card format parser (`DynaParser`) for Fortran fixed-column (80-char) card format
  - Supports DATA, T (transmission line), X (transformer), N (node), and G1-G5 (generator) cards
  - Reads both positive-sequence and zero-sequence impedance data
- `System.from_pop()` and `System.from_dyna()` factory methods
- `ParserFactory` registration for `"pop"` and `"dyna"` format types
- Zero-sequence impedance fields on `Branch`: `r0_pu`, `x0_pu`, `b0_pu`
- Fault analysis fields on `Generator`: `xd_pu`, `xdp_pu`, `xdpp_pu`, `xqpp_pu`, `x2_pu`, `x0_pu`, `ra_pu`, `ta_s`
  - `get_fault_reactance()` method for selecting reactance by mode (xdqpp, xdpp, xdp, xd)
  - `get_armature_resistance()` method for computing Ra from Xd'' and Ta
- `NOT_CLASSIFIED` status to `VoltageStatus` and `LoadingStatus` enums
  - Indicates that no threshold judgment has been made
  - Used when `limits` parameter is not specified
- `is_classified` property to `VoltageStatus` and `LoadingStatus`
  - Returns `True` if status is classified (not `NOT_CLASSIFIED`)
- Test fixtures: `WEST10peak.pop` (IEEJ WEST 10-machine model), `cpat_model11.dyna` (CPAT Manual model system)

### Changed

- `VoltageStatus.is_violation` returns `False` for `NOT_CLASSIFIED`
- `LoadingStatus.is_heavy_or_overload` returns `False` for `NOT_CLASSIFIED`
- `severity` property returns `Severity.INFO` for `NOT_CLASSIFIED`

## [0.1.0] - 2025-12-31

### Added

- Initial release
- Core data models: `System`, `Bus`, `Branch`, `Generator`, `Load`, `Shunt`
- PSS/E RAW file parser (v33/v34 partial support)
- `VoltageStatus` and `LoadingStatus` enums with semantic classification
- `LimitsConfig` for configurable threshold values
- CLI tools for system information display
