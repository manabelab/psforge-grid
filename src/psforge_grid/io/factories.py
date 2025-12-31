"""Factory for creating power system file parsers.

This module provides a factory pattern implementation for
instantiating the appropriate parser based on file format.

The factory pattern enables:
    - Runtime format selection (PSS/E, MATPOWER, etc.)
    - Automatic format detection from file extension
    - Future extensibility for new formats

Example:
    >>> from psforge_grid.io.factories import ParserFactory
    >>> parser = ParserFactory.create("raw")  # PSS/E format
    >>> system = parser.parse("ieee14.raw")
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psforge_grid.io.protocols import IParser


class ParserFactory:
    """Factory for creating power system file parsers.

    Supports format selection between PSS/E RAW, MATPOWER, and
    future formats. Uses lazy imports to avoid circular dependencies.

    Available Formats:
        - "raw": PSS/E RAW format (v33/v34, default)
        - "matpower": MATPOWER format [planned]
        - "cim": CIM/XML format [planned]

    Example:
        >>> # Explicit format selection
        >>> parser = ParserFactory.create("raw")
        >>>
        >>> # Auto-detect from extension
        >>> parser = ParserFactory.from_extension(".raw")
        >>>
        >>> # Check available formats
        >>> formats = ParserFactory.available_formats()
    """

    # Registry of available formats
    _FORMATS = {
        "raw": "psforge_grid.io.raw_parser.RawParser",
        # "matpower": "psforge_grid.io.matpower_parser.MatpowerParser",  # planned
        # "cim": "psforge_grid.io.cim_parser.CimParser",  # planned
    }

    # Extension to format mapping
    _EXTENSION_MAP = {
        "raw": "raw",
        "RAW": "raw",
        # "m": "matpower",  # planned
        # "xml": "cim",  # planned
    }

    @staticmethod
    def create(format_type: str = "raw") -> IParser:
        """Create a parser instance.

        Args:
            format_type: Parser format type. Available options:
                - "raw": PSS/E RAW format (v33/v34, default)
                - "matpower": MATPOWER format [planned]
                - "cim": CIM/XML format [planned]

        Returns:
            IParser implementation ready for use

        Raises:
            ValueError: If unknown format specified
            NotImplementedError: If format is planned but not yet implemented

        Example:
            >>> parser = ParserFactory.create("raw")
            >>> system = parser.parse("ieee14.raw")
        """
        if format_type == "raw":
            # Lazy import to avoid circular dependency
            from psforge_grid.io.raw_parser import RawParser

            return RawParser()
        elif format_type in ("matpower", "cim"):
            raise NotImplementedError(
                f"{format_type.upper()} parser is planned for future release. "
                "Currently only 'raw' format is available."
            )
        else:
            available = ParserFactory.available_formats()
            raise ValueError(f"Unknown format: '{format_type}'. Available formats: {available}")

    @staticmethod
    def from_extension(extension: str) -> IParser:
        """Create a parser based on file extension.

        Automatically selects the appropriate parser based on
        the file extension.

        Args:
            extension: File extension (with or without leading dot)
                Examples: ".raw", "raw", ".RAW", "m"

        Returns:
            IParser implementation for the detected format

        Raises:
            ValueError: If extension is not recognized

        Example:
            >>> parser = ParserFactory.from_extension(".raw")
            >>> parser = ParserFactory.from_extension("raw")
        """
        # Remove leading dot if present
        ext = extension.lstrip(".")

        if ext in ParserFactory._EXTENSION_MAP:
            format_type = ParserFactory._EXTENSION_MAP[ext]
            return ParserFactory.create(format_type)
        else:
            supported = list(ParserFactory._EXTENSION_MAP.keys())
            raise ValueError(f"Unknown extension: '{extension}'. Supported extensions: {supported}")

    @staticmethod
    def from_path(filepath: str | Path) -> IParser:
        """Create a parser based on file path.

        Extracts the extension from the file path and creates
        the appropriate parser.

        Args:
            filepath: Path to the data file

        Returns:
            IParser implementation for the detected format

        Raises:
            ValueError: If file extension is not recognized

        Example:
            >>> parser = ParserFactory.from_path("path/to/ieee14.raw")
        """
        path = Path(filepath)
        extension = path.suffix
        if not extension:
            raise ValueError(f"Cannot determine format: file has no extension: {path}")
        return ParserFactory.from_extension(extension)

    @staticmethod
    def available_formats() -> list[str]:
        """Get list of available parser formats.

        Returns:
            List of format names that can be passed to create()

        Example:
            >>> formats = ParserFactory.available_formats()
            >>> print(formats)  # ['raw']
        """
        # Currently only raw is fully implemented
        return ["raw"]

    @staticmethod
    def supported_extensions() -> list[str]:
        """Get list of all supported file extensions.

        Returns:
            List of file extensions (without dot) that are recognized

        Example:
            >>> extensions = ParserFactory.supported_extensions()
            >>> print(extensions)  # ['raw', 'RAW']
        """
        return list(ParserFactory._EXTENSION_MAP.keys())
