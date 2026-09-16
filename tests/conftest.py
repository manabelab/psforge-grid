"""Shared test fixtures for psforge-grid.

Provides common fixtures used across multiple test modules:
- ``fixtures_dir``: Path to the ``tests/fixtures/`` directory
- ``ieee14_system``: IEEE 14-bus system parsed from RAW (module-scoped)
- ``newengland39_system``: New England 39-bus system parsed from RAW (module-scoped)
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
def newengland39_system() -> System:
    """Load the New England 39-bus system from RAW file (module-scoped).

    This is the v34 fixture, and the only one written by PSS/E itself, so it
    is what the v34 tests read. Reused across tests within the same module for
    efficiency. Do not mutate the returned System in tests; create a copy if
    needed.
    """
    return System.from_raw(FIXTURES_DIR / "39bus.raw")
