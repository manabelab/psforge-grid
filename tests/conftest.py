"""Shared test fixtures for psforge-grid.

Provides common fixtures used across multiple test modules:
- ``fixtures_dir``: Path to the ``tests/fixtures/`` directory
- ``ieee14_system``: IEEE 14-bus system parsed from RAW (module-scoped)
- ``ieee9_system``: IEEE 9-bus system parsed from RAW (module-scoped)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from psforge_grid.models.system import System

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture(scope="module")
def ieee14_system() -> System:
    """Load IEEE 14-bus system from RAW file (module-scoped).

    Reused across tests within the same module for efficiency.
    Do not mutate the returned System in tests; create a copy if needed.
    """
    return System.from_raw(FIXTURES_DIR / "ieee14.raw")


@pytest.fixture(scope="module")
def ieee9_system() -> System:
    """Load IEEE 9-bus system from RAW file (module-scoped).

    Reused across tests within the same module for efficiency.
    Do not mutate the returned System in tests; create a copy if needed.
    """
    return System.from_raw(FIXTURES_DIR / "ieee9.raw")
