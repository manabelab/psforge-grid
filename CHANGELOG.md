# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Fixed

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
