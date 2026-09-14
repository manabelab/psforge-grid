"""Exceptions raised while reading power system data files.

Every parser in :mod:`psforge_grid.io` reports failures through this hierarchy.
Internal exceptions raised by the standard library (``ValueError``,
``ZeroDivisionError``, ``json.JSONDecodeError``, ...) are wrapped in a
:class:`ParseError` so that callers can catch one family of exceptions
regardless of the file format they are reading.

``FileNotFoundError`` is deliberately *not* wrapped: a missing file means the
same thing in every Python program, and callers already handle it.

Example:
    >>> from psforge_grid.io.errors import ParseError
    >>> try:
    ...     system = System.from_raw("broken.raw")  # doctest: +SKIP
    ... except ParseError as exc:  # doctest: +SKIP
    ...     print(exc)
"""

from __future__ import annotations


class ParseError(Exception):
    """Base class for every failure to read a power system data file.

    Attributes:
        filepath: The file being read, when the parser knew it.
        line_no: 1-based line number the failure is attributed to, when known.
    """

    def __init__(
        self,
        message: str,
        *,
        filepath: str | None = None,
        line_no: int | None = None,
    ) -> None:
        """Initialise the error.

        Args:
            message: What went wrong, in terms the caller can act on.
            filepath: Path of the file being read, if known.
            line_no: 1-based line number, if the failure is tied to one line.
        """
        self.filepath = filepath
        self.line_no = line_no
        location = ""
        if filepath is not None:
            location = f" [{filepath}"
            location += f":{line_no}]" if line_no is not None else "]"
        super().__init__(f"{message}{location}")


class FileFormatError(ParseError):
    """The file cannot be read as the requested format at all.

    Raised when the file is empty, holds a different format, declares a case
    flag the parser does not handle, or yields no elements whatsoever. A parser
    must raise this rather than return an empty ``System``: an empty system is
    indistinguishable from a genuinely empty grid, and downstream tools -- an
    LLM above all -- will analyse it as if it were real.
    """


class UnsupportedVersionError(ParseError):
    """The file declares a format version this parser does not support.

    Raised instead of parsing the parts that happen to be readable. A partial
    read of an unsupported version silently drops whatever the newer version
    changed, which is worse than refusing the file.
    """


class MalformedRecordError(ParseError):
    """A record does not match the layout its format requires.

    Raised only when parsing in strict mode. In the default (non-strict) mode
    the record is skipped and recorded in
    :class:`~psforge_grid.io.parse_report.ParseReport` instead.
    """
