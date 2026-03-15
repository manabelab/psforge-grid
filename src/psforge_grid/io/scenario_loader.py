"""Scenario loader for base case + modifications pattern.

This module is maintained for backward compatibility but delegates
all functionality to the ScenarioSet dataclass in
``psforge_grid.models.scenario``.

The canonical API is now ``ScenarioSet.from_json()`` and
``ScenarioSet.to_json()``. See :mod:`psforge_grid.models.scenario`
for details.
"""

from __future__ import annotations

from psforge_grid.models.scenario import ScenarioSet

__all__ = ["ScenarioSet"]

# Re-export ScenarioSet as the public API from the io package.
# The old load_scenarios / write_scenario functions have been removed.
# Use ScenarioSet.from_json() and ScenarioSet.to_json() instead.
