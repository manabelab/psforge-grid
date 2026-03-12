"""XML parsing utilities for .pop format.

Helper functions to safely extract typed values from XML elements,
handling missing tags and type conversion errors gracefully.
"""

from __future__ import annotations

from xml.etree.ElementTree import Element


def get_float(elem: Element, tag: str, default: float = 0.0) -> float:
    """Extract a float value from a child element.

    Args:
        elem: Parent XML element.
        tag: Child element tag name.
        default: Value to return if tag is missing or empty.

    Returns:
        Parsed float value, or default.
    """
    child = elem.find(tag)
    if child is not None and child.text and child.text.strip():
        try:
            return float(child.text.strip())
        except ValueError:
            return default
    return default


def get_int(elem: Element, tag: str, default: int = 0) -> int:
    """Extract an integer value from a child element.

    Args:
        elem: Parent XML element.
        tag: Child element tag name.
        default: Value to return if tag is missing or empty.

    Returns:
        Parsed integer value, or default.
    """
    child = elem.find(tag)
    if child is not None and child.text and child.text.strip():
        try:
            return int(child.text.strip())
        except ValueError:
            return default
    return default


def get_str(elem: Element, tag: str, default: str = "") -> str:
    """Extract a string value from a child element.

    Args:
        elem: Parent XML element.
        tag: Child element tag name.
        default: Value to return if tag is missing or empty.

    Returns:
        Text content, or default.
    """
    child = elem.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def get_bool(elem: Element, tag: str, default: bool = False) -> bool:
    """Extract a boolean value from a child element.

    CPAT XML uses lowercase "true"/"false" strings.

    Args:
        elem: Parent XML element.
        tag: Child element tag name.
        default: Value to return if tag is missing or empty.

    Returns:
        Parsed boolean value, or default.
    """
    child = elem.find(tag)
    if child is not None and child.text and child.text.strip():
        return child.text.strip().lower() == "true"
    return default
