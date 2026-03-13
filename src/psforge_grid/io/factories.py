"""Factory for creating power system file parsers and writers.

This module provides factory pattern implementations for
instantiating the appropriate parser or writer based on file format.

The factory pattern enables:
    - Runtime format selection (PSS/E, MATPOWER, CPAT, etc.)
    - Automatic format detection from file extension
    - Future extensibility for new formats

Example:
    >>> from psforge_grid.io.factories import ParserFactory, WriterFactory
    >>> parser = ParserFactory.create("raw")  # PSS/E format
    >>> system = parser.parse("ieee14.raw")
    >>> writer = WriterFactory.create("matpower")
    >>> writer.write(system, "output.m")
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psforge_grid.io.protocols import IParser, IWriter


class ParserFactory:
    """Factory for creating power system file parsers.

    Supports format selection between PSS/E RAW, MATPOWER, and
    future formats. Uses lazy imports to avoid circular dependencies.

    Available Formats:
        - "raw": PSS/E RAW format (v33/v34, default)
        - "matpower": MATPOWER format (.m files)
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
        "matpower": "psforge_grid.io.matpower_parser.MatpowerParser",
        "pop": "psforge_grid.io.pop_parser.PopParser",
        "dyna": "psforge_grid.io.dyna_parser.DynaParser",
        # "cim": "psforge_grid.io.cim_parser.CimParser",  # planned
    }

    # Extension to format mapping
    _EXTENSION_MAP = {
        "raw": "raw",
        "RAW": "raw",
        "m": "matpower",
        "pop": "pop",
        "dyna": "dyna",
        # "xml": "cim",  # planned
    }

    @staticmethod
    def create(format_type: str = "raw") -> IParser:
        """Create a parser instance.

        Args:
            format_type: Parser format type. Available options:
                - "raw": PSS/E RAW format (v33/v34, default)
                - "matpower": MATPOWER format (.m files)
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
        elif format_type == "matpower":
            from psforge_grid.io.matpower_parser import MatpowerParser

            return MatpowerParser()
        elif format_type == "pop":
            from psforge_grid.io.pop_parser import PopParser

            return PopParser()
        elif format_type == "dyna":
            from psforge_grid.io.dyna_parser import DynaParser

            return DynaParser()
        elif format_type == "cim":
            raise NotImplementedError(
                "CIM parser is planned for future release. "
                "Currently 'raw' and 'matpower' formats are available."
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
        return ["raw", "matpower", "pop", "dyna"]

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


class WriterFactory:
    """Factory for creating power system file writers.

    Supports format selection between PSS/E RAW, MATPOWER, CPAT Pop,
    and CPAT Dyna formats. Symmetric counterpart of ParserFactory.

    Available Formats:
        - "raw": PSS/E RAW format (v33)
        - "matpower": MATPOWER format (.m files)
        - "pop": CPAT Pop format (.pop, ZIP+XML)
        - "dyna": CPAT Dyna format (.dyna, fixed-column cards)

    Example:
        >>> writer = WriterFactory.create("raw")
        >>> writer.write(system, "output.raw")
        >>>
        >>> # Auto-detect from extension
        >>> writer = WriterFactory.from_extension(".m")
        >>> writer.write(system, "output.m")
    """

    # Extension to format mapping (same as ParserFactory)
    _EXTENSION_MAP = {
        "raw": "raw",
        "RAW": "raw",
        "m": "matpower",
        "pop": "pop",
        "dyna": "dyna",
    }

    @staticmethod
    def create(format_type: str = "raw") -> IWriter:
        """Create a writer instance.

        Args:
            format_type: Writer format type. Available options:
                - "raw": PSS/E RAW format (v33, default)
                - "matpower": MATPOWER format (.m files)
                - "pop": CPAT Pop format (.pop, ZIP+XML)
                - "dyna": CPAT Dyna format (.dyna, fixed-column cards)

        Returns:
            IWriter implementation ready for use

        Raises:
            ValueError: If unknown format specified

        Example:
            >>> writer = WriterFactory.create("raw")
            >>> writer.write(system, "output.raw")
        """
        if format_type == "raw":
            from psforge_grid.io.raw_writer import RawWriter

            return RawWriter()
        elif format_type == "matpower":
            from psforge_grid.io.matpower_writer import MatpowerWriter

            return MatpowerWriter()
        elif format_type == "pop":
            from psforge_grid.io.pop_writer import PopWriter

            return PopWriter()
        elif format_type == "dyna":
            from psforge_grid.io.dyna_writer import DynaWriter

            return DynaWriter()
        else:
            available = WriterFactory.available_formats()
            raise ValueError(f"Unknown format: '{format_type}'. Available formats: {available}")

    @staticmethod
    def from_extension(extension: str) -> IWriter:
        """Create a writer based on file extension.

        Args:
            extension: File extension (with or without leading dot)

        Returns:
            IWriter implementation for the detected format

        Raises:
            ValueError: If extension is not recognized

        Example:
            >>> writer = WriterFactory.from_extension(".raw")
        """
        ext = extension.lstrip(".")

        if ext in WriterFactory._EXTENSION_MAP:
            format_type = WriterFactory._EXTENSION_MAP[ext]
            return WriterFactory.create(format_type)
        else:
            supported = list(WriterFactory._EXTENSION_MAP.keys())
            raise ValueError(f"Unknown extension: '{extension}'. Supported extensions: {supported}")

    @staticmethod
    def from_path(filepath: str | Path) -> IWriter:
        """Create a writer based on file path.

        Args:
            filepath: Path to the output file

        Returns:
            IWriter implementation for the detected format

        Raises:
            ValueError: If file extension is not recognized

        Example:
            >>> writer = WriterFactory.from_path("output.raw")
        """
        path = Path(filepath)
        extension = path.suffix
        if not extension:
            raise ValueError(f"Cannot determine format: file has no extension: {path}")
        return WriterFactory.from_extension(extension)

    @staticmethod
    def available_formats() -> list[str]:
        """Get list of available writer formats.

        Returns:
            List of format names that can be passed to create()
        """
        return ["raw", "matpower", "pop", "dyna"]

    @staticmethod
    def supported_extensions() -> list[str]:
        """Get list of all supported file extensions for writing.

        Returns:
            List of file extensions (without dot) that are recognized
        """
        return list(WriterFactory._EXTENSION_MAP.keys())
