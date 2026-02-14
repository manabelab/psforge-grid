"""Input/Output utilities for power system data.

This module provides parsers and writers for various power system data formats.

Architecture:
    The package uses a Factory pattern with pluggable parser backends:

    - IParser: Abstract interface for file parsers (protocols.py)
    - ParserFactory: Factory for creating parser instances (factories.py)
    - RawParser: PSS/E RAW format implementation (raw_parser.py)

Main Components:
    - parse_raw: Convenience function for parsing PSS/E RAW files
    - RawParser: Class implementing IParser for PSS/E format
    - ParserFactory: Factory for creating parsers by format/extension

Example:
    >>> from psforge_grid.io import parse_raw
    >>> system = parse_raw("ieee14.raw")

Advanced Usage:
    >>> from psforge_grid.io import ParserFactory
    >>> parser = ParserFactory.create("raw")
    >>> system = parser.parse("ieee14.raw")

    >>> # Auto-detect format from file extension
    >>> parser = ParserFactory.from_path("ieee14.raw")
"""

from psforge_grid.io.factories import ParserFactory
from psforge_grid.io.matpower_parser import MatpowerParser, parse_matpower
from psforge_grid.io.protocols import IParser
from psforge_grid.io.raw_parser import RawParser, parse_raw

__all__ = [
    # Main functions
    "parse_raw",
    "parse_matpower",
    # Interface and factory
    "IParser",
    "ParserFactory",
    # Implementations
    "RawParser",
    "MatpowerParser",
]
