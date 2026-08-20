"""Shared pytest configuration.

Supplies the names that docstring examples use so they can actually run under
``pytest --doctest-modules``. An example that says

    >>> print(system.to_description())

is asking the reader to bring their own ``system``; without one it cannot
execute, and an example that never executes is free to rot (psforge-grid
shipped 68 non-running examples before this existed). Injecting a small
system here lets every such example run and be checked on each CI run, while
keeping the docstrings short enough to read. Examples that genuinely need a
real data file (``System.from_raw("ieee14.raw")``) stay illustrative and are
marked ``# doctest: +SKIP``.
"""

from __future__ import annotations

import pytest

from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.load import Load
from psforge_grid.models.system import System


def _doctest_system() -> System:
    """A 2-bus system small enough to keep doctest output stable."""
    return System(
        name="Doctest",
        base_mva=100.0,
        buses=[
            Bus("B1", bus_type=3, base_kv=66.0, number=1, name="Gen"),
            Bus("B2", bus_type=1, base_kv=66.0, number=2, name="Load"),
        ],
        branches=[Branch("BR1", "B1", "B2", r_pu=0.01, x_pu=0.1, circuit_id="1")],
        generators=[Generator("G1", bus_id="B1", p_gen=1.0, machine_id="1", name="G1")],
        loads=[Load("LD1", bus_id="B2", p_load=0.8, q_load=0.2, load_id="1")],
    )


@pytest.fixture(autouse=True)
def _inject_doctest_names(doctest_namespace: dict, tmp_path: object) -> None:
    """Make ``system`` (and a writable ``tmp_path``) available to examples."""
    doctest_namespace["system"] = _doctest_system()
    doctest_namespace["tmp_path"] = tmp_path
