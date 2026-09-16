"""Factory for creating power system file parsers and writers.

This module provides factory pattern implementations for
instantiating the appropriate parser or writer based on file format.

The factory pattern enables:
    - Runtime format selection (PSS/E, MATPOWER, OpenDSS, etc.)
    - Automatic format detection from file extension
    - Formats supplied by other distributions, not only by this package

Example:
    These need a file on disk, so they are shown without a ``>>>`` prompt
    rather than as doctests that cannot run::

        from psforge_grid.io.factories import ParserFactory, WriterFactory

        parser = ParserFactory.create("raw")          # PSS/E format
        system = parser.parse("ieee14.raw")
        writer = WriterFactory.create("matpower")
        writer.write(system, "output.m")

Adding a format:
    A format does not have to live in this package. Register one directly::

        ParserFactory.register("myfmt", "mypkg.my_parser.MyParser", ["myfmt"])
        WriterFactory.register("myfmt", "mypkg.my_writer.MyWriter", ["myfmt"])

    or advertise it from an installed distribution through the
    ``psforge_grid.formats`` entry-point group, in which case it is registered
    the first time anything asks the factory a question. Either way
    :meth:`ParserFactory.available_formats` and ``System.from_file`` see it.
    See :mod:`psforge_grid.io._registry` for the contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from psforge_grid.io._registry import PARSERS, WRITERS, PluginError

if TYPE_CHECKING:
    from psforge_grid.io.protocols import IParser, IWriter


class ParserFactory:
    """Factory for creating power system file parsers.

    Selects between the built-in formats and any registered by another
    distribution. Implementations are imported only when first used, so an
    unused format costs nothing and an optional dependency is not required
    until something asks for the format that needs it.

    Built-in Formats:
        - "raw": PSS/E RAW format (v32/v33/v34, default)
        - "matpower": MATPOWER format (.m files)
        - "dss": OpenDSS script format (.dss)
        - "json": psforge-grid JSON format (.psfg.json)

    Example:
        >>> # Explicit format selection
        >>> parser = ParserFactory.create("raw")
        >>>
        >>> # Auto-detect from extension
        >>> parser = ParserFactory.from_extension(".raw")
        >>>
        >>> # Check what is available, including registered plugins
        >>> formats = ParserFactory.available_formats()
    """

    @staticmethod
    def register(
        name: str,
        target: str | type,
        extensions: tuple[str, ...] | list[str] = (),
    ) -> None:
        """Register a parser, replacing any format of the same name.

        Args:
            name: Format name, as passed to :meth:`create`. Case-insensitive.
            target: The parser class, or its dotted path
                (``"mypkg.my_parser.MyParser"``). A dotted path is imported
                only when the format is first used.
            extensions: Extensions this format claims, without the leading
                dot. Matching is case-insensitive.

        Example:
            Shown without a ``>>>`` prompt on purpose: registering mutates a
            process-wide registry, so running it as a doctest would leave the
            format behind for everything that ran afterwards.

            .. code-block:: python

                ParserFactory.register("myfmt", "mypkg.my_parser.MyParser", ["myfmt"])
                assert "myfmt" in ParserFactory.available_formats()
        """
        PARSERS.register(name, target, extensions)

    @staticmethod
    def create(format_type: str = "raw") -> IParser:
        """Create a parser instance.

        Args:
            format_type: Parser format name. Case-insensitive. See
                :meth:`available_formats` for what is registered.

        Returns:
            IParser implementation ready for use

        Raises:
            ValueError: If no format is registered under that name

        Example:
            >>> parser = ParserFactory.create("raw")
            >>> parser.format_name
            'PSS/E RAW'
        """
        parser: IParser = PARSERS.create(format_type)
        return parser

    @staticmethod
    def from_extension(extension: str) -> IParser:
        """Create a parser based on file extension.

        Args:
            extension: File extension, with or without leading dot, in any
                case. Examples: ``".raw"``, ``"raw"``, ``".RAW"``, ``"m"``

        Returns:
            IParser implementation for the detected format

        Raises:
            ValueError: If no registered format claims that extension

        Example:
            >>> parser = ParserFactory.from_extension(".raw")
            >>> parser = ParserFactory.from_extension("raw")
        """
        return ParserFactory.create(PARSERS.name_for_extension(extension))

    @staticmethod
    def from_path(filepath: str | Path) -> IParser:
        """Create a parser based on file path.

        Extracts the extension from the file path and creates
        the appropriate parser. Supports compound extensions
        like ``.psfg.json``.

        Args:
            filepath: Path to the data file

        Returns:
            IParser implementation for the detected format

        Raises:
            ValueError: If no registered format claims the file's extension

        Example:
            >>> parser = ParserFactory.from_path("path/to/ieee14.raw")
            >>> parser = ParserFactory.from_path("data.psfg.json")
        """
        path = Path(filepath)
        # Check compound extension first (e.g., .psfg.json)
        compound_ext = "".join(path.suffixes).lstrip(".")
        if PARSERS.knows_extension(compound_ext):
            return ParserFactory.from_extension(compound_ext)
        extension = path.suffix
        if not extension:
            raise ValueError(f"Cannot determine format: file has no extension: {path}")
        return ParserFactory.from_extension(extension)

    @staticmethod
    def available_formats() -> list[str]:
        """Get list of available parser formats.

        Includes formats registered by other distributions, so the answer
        depends on what is installed.

        Returns:
            List of format names that can be passed to create()

        Example:
            >>> formats = ParserFactory.available_formats()
            >>> "raw" in formats
            True
        """
        return PARSERS.names()

    @staticmethod
    def supported_extensions() -> list[str]:
        """Get list of all supported file extensions.

        Returns:
            Extensions (lowercase, without the dot) that are recognised.
            Matching is case-insensitive, so ``.RAW`` resolves through the
            ``raw`` entry rather than appearing separately.

        Example:
            >>> extensions = ParserFactory.supported_extensions()
            >>> "raw" in extensions
            True
        """
        return PARSERS.extensions()

    @staticmethod
    def plugin_errors() -> list[PluginError]:
        """Report entry points that advertised a format but failed to load.

        A broken plugin does not stop psforge from working, and this is how
        to find out that it is the reason a format is missing.

        Returns:
            One entry per failed entry point; empty when all loaded.
        """
        return PARSERS.errors()


class WriterFactory:
    """Factory for creating power system file writers.

    Symmetric counterpart of ParserFactory, with its own registry: a format
    may be readable without being writable.

    Built-in Formats:
        - "raw": PSS/E RAW format (v33)
        - "matpower": MATPOWER format (.m files)
        - "dss": OpenDSS script format (.dss)
        - "json": psforge-grid JSON format (.psfg.json)

    Example:
        Writing needs a System and a destination, so this is shown without a
        ``>>>`` prompt::

            writer = WriterFactory.create("raw")
            writer.write(system, "output.raw")

            # Auto-detect from extension
            writer = WriterFactory.from_extension(".m")
            writer.write(system, "output.m")
    """

    @staticmethod
    def register(
        name: str,
        target: str | type,
        extensions: tuple[str, ...] | list[str] = (),
    ) -> None:
        """Register a writer, replacing any format of the same name.

        Args:
            name: Format name, as passed to :meth:`create`. Case-insensitive.
            target: The writer class, or its dotted path. A dotted path is
                imported only when the format is first used.
            extensions: Extensions this format claims, without the leading
                dot. Matching is case-insensitive.
        """
        WRITERS.register(name, target, extensions)

    @staticmethod
    def create(format_type: str = "raw") -> IWriter:
        """Create a writer instance.

        Args:
            format_type: Writer format name. Case-insensitive. See
                :meth:`available_formats` for what is registered.

        Returns:
            IWriter implementation ready for use

        Raises:
            ValueError: If no format is registered under that name

        Example:
            >>> writer = WriterFactory.create("raw")
            >>> writer.format_name
            'PSS/E RAW'
        """
        writer: IWriter = WRITERS.create(format_type)
        return writer

    @staticmethod
    def from_extension(extension: str) -> IWriter:
        """Create a writer based on file extension.

        Args:
            extension: File extension, with or without leading dot, in any
                case.

        Returns:
            IWriter implementation for the detected format

        Raises:
            ValueError: If no registered format claims that extension
        """
        return WriterFactory.create(WRITERS.name_for_extension(extension))

    @staticmethod
    def from_path(filepath: str | Path) -> IWriter:
        """Create a writer based on file path.

        Args:
            filepath: Path to the output file

        Returns:
            IWriter implementation for the detected format

        Raises:
            ValueError: If no registered format claims the file's extension
        """
        path = Path(filepath)
        compound_ext = "".join(path.suffixes).lstrip(".")
        if WRITERS.knows_extension(compound_ext):
            return WriterFactory.from_extension(compound_ext)
        extension = path.suffix
        if not extension:
            raise ValueError(f"Cannot determine format: file has no extension: {path}")
        return WriterFactory.from_extension(extension)

    @staticmethod
    def available_formats() -> list[str]:
        """Get list of available writer formats.

        Includes formats registered by other distributions.

        Returns:
            List of format names that can be passed to create()
        """
        return WRITERS.names()

    @staticmethod
    def supported_extensions() -> list[str]:
        """Get list of all supported file extensions.

        Returns:
            Extensions (lowercase, without the dot) that are recognised.
        """
        return WRITERS.extensions()

    @staticmethod
    def plugin_errors() -> list[PluginError]:
        """Report entry points that advertised a format but failed to load.

        Returns:
            One entry per failed entry point; empty when all loaded.
        """
        return WRITERS.errors()
