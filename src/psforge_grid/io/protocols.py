"""Protocols for power system data file I/O.

This module defines abstract interfaces for file parsers and writers,
enabling support for multiple data formats (PSS/E, MATPOWER, CPAT, etc.).

The design enables:
    - Transparent format switching via ParserFactory / WriterFactory
    - Extensibility for new file formats
    - Testing with mock parsers / writers

IDE Navigation Tips:
    - Press F12 on IParser/IWriter to see interface definitions
    - Press Ctrl+F12 (Mac: Cmd+F12) to jump to implementations
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psforge_grid.models.system import System


class IParser(ABC):
    """Abstract base class for power system file parsers.

    All file format parsers must implement this interface to ensure
    consistent API across different data formats.

    Implementations:
        - :class:`~psforge_grid.io.raw_parser.RawParser`:
          PSS/E RAW format (v33/v34)
        - :class:`~psforge_grid.io.matpower_parser.MatpowerParser`:
          MATPOWER format [future]
        - :class:`~psforge_grid.io.cim_parser.CimParser`:
          CIM/XML format [future]

    See Also:
        - RawParser: io/raw_parser.py
        - ParserFactory: io/factories.py

    Example:
        >>> from psforge_grid.io.factories import ParserFactory
        >>> parser = ParserFactory.create("raw")
        >>> system = parser.parse("ieee14.raw")  # doctest: +SKIP
    """

    @abstractmethod
    def parse(self, filepath: str | Path) -> System:
        """Parse a power system data file.

        Reads a power system file and constructs a complete
        System object with all components (buses, branches, generators, etc.).

        Args:
            filepath: Path to the data file.
                The file must exist and be in the format supported by
                the specific parser implementation.

        Returns:
            System object containing:
                - buses: List of Bus objects representing network nodes
                - branches: List of Branch objects (lines and transformers)
                - generators: List of Generator objects
                - loads: List of Load objects
                - shunts: List of Shunt objects
                - base_mva: System base MVA value

        Raises:
            FileNotFoundError: If the specified file does not exist
            ValueError: If the file format is invalid or cannot be parsed
            PermissionError: If the file cannot be read due to permissions

        Note:
            - All power values are converted to per-unit on system base MVA
            - Voltage angles are in radians (not degrees)
            - Component status (in-service/out-of-service) is preserved

        See Also:
            - RawParser.parse(): PSS/E RAW format specifics
            - System: Container class for parsed data
        """
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions.

        Returns:
            List of file extensions (without dot) that this parser supports.
            For example: ["raw", "RAW"] for PSS/E format.
        """
        pass

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Return human-readable format name.

        Returns:
            Format name for display purposes.
            For example: "PSS/E RAW" or "MATPOWER".
        """
        pass


class IWriter(ABC):
    """Abstract base class for power system file writers.

    All file format writers must implement this interface to ensure
    consistent API across different data formats. Symmetric counterpart
    of IParser.

    Implementations:
        - :class:`~psforge_grid.io.raw_writer.RawWriter`:
          PSS/E RAW format (v33)
        - :class:`~psforge_grid.io.matpower_writer.MatpowerWriter`:
          MATPOWER format (.m files)
        - :class:`~psforge_grid.io.pop_writer.PopWriter`:
          CPAT Pop format (.pop, ZIP+XML)
        - :class:`~psforge_grid.io.dyna_writer.DynaWriter`:
          CPAT Dyna format (.dyna, fixed-column cards)

    See Also:
        - WriterFactory: io/factories.py
        - IParser: The symmetric read interface

    Example:
        >>> from psforge_grid.io.factories import WriterFactory
        >>> writer = WriterFactory.create("raw")
        >>> writer.write(system, tmp_path / "output.raw")
    """

    @abstractmethod
    def write(self, system: System, filepath: str | Path) -> None:
        """Write a power system to a data file.

        Serializes a System object to the file format supported by
        this writer implementation.

        Args:
            system: System object containing all power system components.
            filepath: Path to the output file. Parent directory must exist.

        Raises:
            ValueError: If the system data cannot be represented in this format
            PermissionError: If the file cannot be written due to permissions
            OSError: If there is an I/O error during writing

        Note:
            - Per-unit values are converted back to physical units as required
              by the specific file format
            - Voltage angles are converted from radians to degrees where needed
            - Fields not supported by the target format are silently ignored

        See Also:
            - IParser.parse(): The symmetric read operation
            - System: Container class for power system data
        """
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions for writing.

        Returns:
            List of file extensions (without dot) that this writer supports.
            For example: ["raw", "RAW"] for PSS/E format.
        """
        pass

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Return human-readable format name.

        Returns:
            Format name for display purposes.
            For example: "PSS/E RAW" or "MATPOWER".
        """
        pass
