"""Fortran fixed-column format reading utilities.

CPAT card format uses 80-character lines with fields at fixed column positions.
Column indices in this module are 1-based (matching CPAT manual convention).

Example:
    >>> line = "T  500050 Z    1040      1050"
    >>> read_int(line, 4, 10)  # columns 4-10
    500050
    >>> read_str(line, 12, 12)  # column 12
    'Z'
"""

from __future__ import annotations


def read_int(line: str, col_start: int, col_end: int, default: int = 0) -> int:
    """Read an integer from fixed columns (1-based, inclusive).

    Args:
        line: Input line (may be shorter than col_end).
        col_start: Start column (1-based).
        col_end: End column (1-based, inclusive).
        default: Value to return if field is blank.

    Returns:
        Parsed integer, or default if blank/missing.
    """
    field = _extract_field(line, col_start, col_end)
    if not field:
        return default
    return int(field)


def read_float(line: str, col_start: int, col_end: int, default: float = 0.0) -> float:
    """Read a float from fixed columns (1-based, inclusive).

    Args:
        line: Input line (may be shorter than col_end).
        col_start: Start column (1-based).
        col_end: End column (1-based, inclusive).
        default: Value to return if field is blank.

    Returns:
        Parsed float, or default if blank/missing.
    """
    field = _extract_field(line, col_start, col_end)
    if not field:
        return default
    return float(field)


def read_str(line: str, col_start: int, col_end: int, default: str = "") -> str:
    """Read a string from fixed columns (1-based, inclusive).

    Args:
        line: Input line (may be shorter than col_end).
        col_start: Start column (1-based).
        col_end: End column (1-based, inclusive).
        default: Value to return if field is blank.

    Returns:
        Stripped string, or default if blank/missing.
    """
    field = _extract_field(line, col_start, col_end)
    if not field:
        return default
    return field


def _extract_field(line: str, col_start: int, col_end: int) -> str:
    """Extract and strip a field from fixed columns.

    Converts 1-based column indices to 0-based Python slice.
    Handles lines shorter than col_end gracefully.

    Args:
        line: Input line.
        col_start: Start column (1-based).
        col_end: End column (1-based, inclusive).

    Returns:
        Stripped field string (empty if blank or out of range).
    """
    # Convert 1-based inclusive to 0-based Python slice
    start = col_start - 1
    end = col_end
    if start >= len(line):
        return ""
    return line[start:end].strip()


def is_comment(line: str) -> bool:
    """Check if a line is a comment (first character is '*').

    Args:
        line: Input line.

    Returns:
        True if the line is a comment.
    """
    return len(line) > 0 and line[0] == "*"


def is_blank(line: str) -> bool:
    """Check if a line is blank.

    Args:
        line: Input line.

    Returns:
        True if the line is blank or whitespace only.
    """
    return line.strip() == ""
