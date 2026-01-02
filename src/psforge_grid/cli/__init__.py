"""CLI module for psforge-grid.

This module provides command-line interface tools for power system data
inspection and validation. It is designed with LLM affinity in mind,
providing structured outputs that are easy for both humans and LLMs to parse.

Commands:
    info: Display summary information about a power system
    show: Display detailed information about specific elements
    validate: Validate system data for consistency

Example:
    $ psforge-grid info ieee14.raw
    $ psforge-grid show ieee14.raw bus 1
    $ psforge-grid validate ieee14.raw --strict

Note:
    This module requires optional CLI dependencies. Install with:
    pip install psforge-grid[cli]
"""

from __future__ import annotations


def main() -> None:
    """Entry point for psforge-grid CLI.

    This function is the main entry point registered in pyproject.toml.
    It provides graceful degradation when CLI dependencies are not installed.
    """
    try:
        from psforge_grid.cli.app import app

        app()
    except ImportError as e:
        import sys

        print(
            "CLI dependencies not installed.\n"
            "Please install with: pip install psforge-grid[cli]\n"
            f"\nError details: {e}"
        )
        sys.exit(1)


__all__ = ["main"]
