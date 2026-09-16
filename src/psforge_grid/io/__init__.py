"""Input/Output utilities for power system data.

This module provides parsers and writers for various power system data formats.

Architecture:
    The package uses a Factory pattern with pluggable parser/writer backends:

    - IParser / IWriter: Abstract interfaces (protocols.py)
    - ParserFactory / WriterFactory: Factories for creating instances (factories.py)
    - Parsers: RawParser, MatpowerParser, DSSParser, JsonParser
    - Writers: RawWriter, MatpowerWriter, DSSWriter, JsonWriter

Main Components:
    - parse_raw / write_raw: PSS/E RAW format
    - parse_matpower / write_matpower: MATPOWER .m format
    - ParserFactory / WriterFactory: Format-agnostic creation

Example:
    >>> from psforge_grid.io import parse_raw, write_matpower
    >>> system = parse_raw("ieee14.raw")
    >>> write_matpower(system, "ieee14.m")

Advanced Usage:
    >>> from psforge_grid.io import ParserFactory, WriterFactory
    >>> parser = ParserFactory.create("raw")
    >>> system = parser.parse("ieee14.raw")
    >>> writer = WriterFactory.create("matpower")
    >>> writer.write(system, "ieee14.m")
"""

from psforge_grid.io.dss_parser import DSSParser, parse_dss
from psforge_grid.io.dss_writer import DSSWriter, write_dss
from psforge_grid.io.factories import ParserFactory, WriterFactory
from psforge_grid.io.json_parser import JsonParser, parse_json
from psforge_grid.io.json_writer import JsonWriter, write_json
from psforge_grid.io.matpower_parser import MatpowerParser, parse_matpower
from psforge_grid.io.matpower_writer import MatpowerWriter, write_matpower
from psforge_grid.io.protocols import IParser, IWriter
from psforge_grid.io.raw_parser import RawParser, parse_raw
from psforge_grid.io.raw_writer import RawWriter, write_raw
from psforge_grid.io.scenario_loader import ScenarioSet

__all__ = [
    # Parse functions
    "parse_raw",
    "parse_matpower",
    "parse_dss",
    "parse_json",
    # Write functions
    "write_raw",
    "write_matpower",
    "write_dss",
    "write_json",
    # Scenario
    "ScenarioSet",
    # Interfaces
    "IParser",
    "IWriter",
    # Factories
    "ParserFactory",
    "WriterFactory",
    # Parser implementations
    "RawParser",
    "MatpowerParser",
    "DSSParser",
    "JsonParser",
    # Writer implementations
    "RawWriter",
    "MatpowerWriter",
    "DSSWriter",
    "JsonWriter",
]
