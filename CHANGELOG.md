# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
