"""Tests for large-scale PSS/E RAW parsing.

Exercises the RAW parser and writer on ``ACTIVSg2000.raw``, a 2000-bus synthetic
model of the Texas grid. The small IEEE fixtures cannot catch problems that only
appear at scale: multiple areas and voltage levels, several thousand branches,
and a mix of in-service and out-of-service generators.

The case is synthetic and does not represent any actual grid. See
``tests/fixtures/README.md`` for its provenance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from psforge_grid.models.system import System

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ACTIVSG2000 = FIXTURES_DIR / "ACTIVSg2000.raw"

# Nameplate figures of the published case, converted from per-unit at 100 MVA base.
BASE_MVA = 100.0
TOTAL_P_LOAD_MW = 67109.0
TOTAL_Q_LOAD_MVAR = 19014.0
TOTAL_P_GEN_MW = 68728.0


@pytest.fixture(scope="module")
def activsg2000_system() -> System:
    """Load the 2000-bus case (module-scoped; parsing costs ~0.2 s).

    Do not mutate the returned System in tests; create a copy if needed.
    """
    return System.from_raw(ACTIVSG2000)


class TestLargeCaseParsing:
    """Parsing a 2000-bus PSS/E v33 case."""

    def test_element_counts(self, activsg2000_system: System) -> None:
        """All element tables are read completely."""
        assert len(activsg2000_system.buses) == 2000
        assert len(activsg2000_system.generators) == 544
        assert len(activsg2000_system.loads) == 1350
        assert len(activsg2000_system.branches) == 3206
        assert len(activsg2000_system.shunts) == 4

    def test_base_mva(self, activsg2000_system: System) -> None:
        """System base is read from the case header."""
        assert activsg2000_system.base_mva == BASE_MVA

    def test_bus_type_distribution(self, activsg2000_system: System) -> None:
        """Exactly one slack bus, the rest split between PV and PQ."""
        assert len(activsg2000_system.get_slack_buses()) == 1
        assert len(activsg2000_system.get_pv_buses()) == 484
        assert len(activsg2000_system.get_pq_buses()) == 1515
        assert activsg2000_system.get_slack_buses()[0].bus_id == 7098

    def test_voltage_levels(self, activsg2000_system: System) -> None:
        """Transmission and generator-terminal voltage levels are preserved.

        Small fixtures carry one or two levels; this case carries ten, so a
        base_kv that silently defaulted would show up here.
        """
        levels = sorted({bus.base_kv for bus in activsg2000_system.buses})
        assert levels == [13.2, 13.8, 18.0, 20.0, 22.0, 24.0, 115.0, 161.0, 230.0, 500.0]

    def test_areas(self, activsg2000_system: System) -> None:
        """Bus area assignments survive parsing (the IEEE fixtures are single-area)."""
        assert sorted({bus.area for bus in activsg2000_system.buses}) == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_bus_id_range(self, activsg2000_system: System) -> None:
        """Bus numbers are four-digit and non-contiguous, unlike the IEEE fixtures."""
        bus_ids = [bus.bus_id for bus in activsg2000_system.buses]
        assert min(bus_ids) == 1001
        assert max(bus_ids) == 8160
        assert len(set(bus_ids)) == 2000

    def test_transformer_and_line_split(self, activsg2000_system: System) -> None:
        """Transformer branches are distinguished from transmission lines."""
        transformers = [br for br in activsg2000_system.branches if br.is_transformer]
        assert len(transformers) == 861
        assert len(activsg2000_system.branches) - len(transformers) == 2345

    def test_generator_status_mix(self, activsg2000_system: System) -> None:
        """Out-of-service generators are kept, not dropped."""
        in_service = [gen for gen in activsg2000_system.generators if gen.status == 1]
        assert len(in_service) == 432
        assert len(activsg2000_system.generators) - len(in_service) == 112

    def test_nothing_is_skipped(self, activsg2000_system: System) -> None:
        """All 7104 records read at this scale, with nothing dropped or warned about.

        The parser skips records it cannot read rather than inventing values for
        them, so on a file this size a silent regression would show up here as a
        non-empty skip list long before anyone noticed a missing element.
        """
        report = activsg2000_system.parse_report
        assert report is not None
        assert report.is_clean, report.to_description()
        assert report.records_read == 7104

    def test_shunt_buses(self, activsg2000_system: System) -> None:
        """Fixed shunts are attached to the right buses."""
        assert [shunt.bus_id for shunt in activsg2000_system.shunts] == [2017, 2096, 3051, 8005]


class TestLargeCaseTotals:
    """Aggregate quantities, as a check that magnitudes are not mis-scaled."""

    def test_total_load(self, activsg2000_system: System) -> None:
        """Total load matches the ~67 GW scale of the published case."""
        p_mw = sum(load.p_load for load in activsg2000_system.loads) * BASE_MVA
        q_mvar = sum(load.q_load for load in activsg2000_system.loads) * BASE_MVA
        assert p_mw == pytest.approx(TOTAL_P_LOAD_MW, rel=1e-4)
        assert q_mvar == pytest.approx(TOTAL_Q_LOAD_MVAR, rel=1e-4)

    def test_total_generation(self, activsg2000_system: System) -> None:
        """Dispatched generation covers the load plus losses."""
        p_mw = sum(gen.p_gen for gen in activsg2000_system.generators) * BASE_MVA
        assert p_mw == pytest.approx(TOTAL_P_GEN_MW, rel=1e-4)
        assert p_mw > TOTAL_P_LOAD_MW


class TestLargeCaseRoundTrip:
    """RAW writer at scale."""

    def test_raw_round_trip_preserves_counts(
        self, activsg2000_system: System, tmp_path: Path
    ) -> None:
        """Writing 2000 buses and reading them back loses no elements."""
        output = tmp_path / "activsg2000_out.raw"
        activsg2000_system.to_raw(output)
        reparsed = System.from_raw(output)

        assert len(reparsed.buses) == len(activsg2000_system.buses)
        assert len(reparsed.generators) == len(activsg2000_system.generators)
        assert len(reparsed.loads) == len(activsg2000_system.loads)
        assert len(reparsed.branches) == len(activsg2000_system.branches)
        assert len(reparsed.shunts) == len(activsg2000_system.shunts)

    def test_raw_round_trip_preserves_bus_data(
        self, activsg2000_system: System, tmp_path: Path
    ) -> None:
        """Bus identity and voltage survive a write/read cycle at scale."""
        output = tmp_path / "activsg2000_out.raw"
        activsg2000_system.to_raw(output)
        reparsed = System.from_raw(output)

        for original, written in zip(activsg2000_system.buses, reparsed.buses, strict=True):
            assert written.bus_id == original.bus_id
            assert written.base_kv == pytest.approx(original.base_kv)
            assert written.v_magnitude == pytest.approx(original.v_magnitude, abs=1e-5)
