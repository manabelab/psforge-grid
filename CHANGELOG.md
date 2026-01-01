# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `NOT_CLASSIFIED` status to `VoltageStatus` and `LoadingStatus` enums
  - Indicates that no threshold judgment has been made
  - Used when `limits` parameter is not specified
- `is_classified` property to `VoltageStatus` and `LoadingStatus`
  - Returns `True` if status is classified (not `NOT_CLASSIFIED`)

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
