"""Parser protocols for power system data files.

This module defines abstract interfaces for file parsers,
enabling support for multiple data formats (PSS/E, MATPOWER, etc.).

The design enables:
    - Transparent format switching via ParserFactory
    - Extensibility for new file formats
    - Testing with mock parsers

IDE Navigation Tips:
    - Press F12 on IParser to see this interface definition
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
        >>> system = parser.parse("ieee14.raw")
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
