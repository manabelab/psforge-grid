"""Tests for CPAT dyna card format parser.

Tests parsing of CPAT Fortran fixed-column card format files
using the model system from CPAT manual p.26.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from psforge_grid.io.dyna.card_parsers import (
    DynaGenerator,
    parse_data_card,
    parse_g1_card,
    parse_g3_card,
    parse_n_card,
    parse_t_card_primary,
    parse_x_card_primary,
)
from psforge_grid.io.dyna.format_utils import is_comment, read_float, read_int, read_str
from psforge_grid.io.dyna_parser import DynaParser, parse_dyna
from psforge_grid.io.factories import ParserFactory
from psforge_grid.models.system import System

FIXTURE_DIR = Path(__file__).parent / "fixtures"
DYNA_FILE = FIXTURE_DIR / "cpat_model11.dyna"


# =============================================================================
# Format utility tests
# =============================================================================


class TestFormatUtils:
    """Tests for Fortran fixed-column reading utilities."""

    def test_read_int_basic(self) -> None:
        line = "T   500050 Z    1040"
        assert read_int(line, 4, 10) == 500050

    def test_read_int_blank(self) -> None:
        line = "T         Z"
        assert read_int(line, 4, 10) == 0

    def test_read_int_default(self) -> None:
        line = "T"
        assert read_int(line, 4, 10, default=99) == 99

    def test_read_float_basic(self) -> None:
        # Use actual column-aligned line from fixture (T card primary)
        line = "T   500050 Z    1040      1050        0.00351   0.06686   0.02994   500KV 1-A"
        assert read_float(line, 36, 45) == pytest.approx(0.00351)
        assert read_float(line, 46, 55) == pytest.approx(0.06686)
        assert read_float(line, 56, 65) == pytest.approx(0.02994)

    def test_read_str_basic(self) -> None:
        line = "T   500050 Z    1040      1050"
        assert read_str(line, 12, 12) == "Z"

    def test_read_str_short_line(self) -> None:
        line = "T"
        assert read_str(line, 69, 80) == ""

    def test_is_comment(self) -> None:
        assert is_comment("* This is a comment")
        assert not is_comment("T  500050 Z    1040")
        assert not is_comment("")


# =============================================================================
# Card parser tests
# =============================================================================


class TestCardParsers:
    """Tests for individual card type parsers."""

    def test_parse_data_card(self) -> None:
        line = "  MANUAL-X    1000.0      60.0"
        ctrl = parse_data_card(line)
        assert ctrl.base_mva == pytest.approx(1000.0)
        assert ctrl.frequency_hz == pytest.approx(60.0)
        assert "MANUAL-X" in ctrl.system_name

    def test_parse_t_card_primary(self) -> None:
        line = "T   500050 Z    1040      1050        0.00351   0.06686   0.02994   500KV 1-A"
        tl = parse_t_card_primary(line)
        assert tl.branch_no == 500050
        assert tl.has_zero_seq is True
        assert tl.from_node == 1040
        assert tl.to_node == 1050
        assert tl.z1r == pytest.approx(0.00351)
        assert tl.z1x == pytest.approx(0.06686)
        assert tl.y1c == pytest.approx(0.02994)
        assert "500KV 1-A" in tl.name

    def test_parse_x_card_primary(self) -> None:
        line = "X   800010 Z    1010      1040        0.02320      1.07             22/500 TR"
        xfmr = parse_x_card_primary(line)
        assert xfmr.branch_no == 800010
        assert xfmr.from_node == 1010
        assert xfmr.to_node == 1040
        assert xfmr.z1x == pytest.approx(0.02320)
        assert xfmr.tap_ratio == pytest.approx(1.07)
        assert "22/500 TR" in xfmr.name

    def test_parse_n_card_generator(self) -> None:
        line = "N     1010                 5.0      1.25                            G-1"
        node = parse_n_card(line)
        assert node.node_no == 1010
        assert node.p_gen == pytest.approx(5.0)
        assert node.q_gen == pytest.approx(1.25)
        assert node.p_load == pytest.approx(0.0)
        assert node.name == "G-1"

    def test_parse_n_card_load(self) -> None:
        line = "N     1090      1.00                           6.0                  LOAD-9"
        node = parse_n_card(line)
        assert node.node_no == 1090
        assert node.v0 == pytest.approx(1.0)
        assert node.p_load == pytest.approx(6.0)
        assert node.name == "LOAD-9"

    def test_parse_n_card_swing(self) -> None:
        line = "N     1100      1.00       1.0                 4.0      -0.5        SWING"
        node = parse_n_card(line)
        assert node.node_no == 1100
        assert node.v0 == pytest.approx(1.0)
        assert node.p_gen == pytest.approx(1.0)
        assert node.q_gen == pytest.approx(0.0)  # QGO is col 31-40, blank here
        assert node.p_load == pytest.approx(4.0)
        assert node.q_load == pytest.approx(-0.5)
        assert "SWING" in node.name

    def test_parse_g1_card(self) -> None:
        line = "G1    1010    4    2    5000.0    4500.0  7.0               G-1"
        gen = parse_g1_card(line)
        assert gen.node_no == 1010
        assert gen.lgt == 4
        assert gen.ngt == 2
        assert gen.gmva == pytest.approx(5000.0)
        assert gen.gmw == pytest.approx(4500.0)
        assert gen.mg == pytest.approx(7.0)
        assert "G-1" in gen.name

    def test_parse_g3_card(self) -> None:
        line = "G3              1.70      0.35      0.25      1.00      0.03"
        gen = DynaGenerator()
        parse_g3_card(line, gen)
        assert gen.xd == pytest.approx(1.70)
        assert gen.xdd == pytest.approx(0.35)
        assert gen.xddd == pytest.approx(0.25)
        assert gen.tdd == pytest.approx(1.00)
        assert gen.tddd == pytest.approx(0.03)


# =============================================================================
# Integration tests
# =============================================================================


class TestDynaParserIntegration:
    """Integration tests using the CPAT model system fixture."""

    @pytest.fixture()
    def system(self) -> System:
        """Parse the test fixture file."""
        return parse_dyna(DYNA_FILE)

    def test_file_exists(self) -> None:
        assert DYNA_FILE.exists(), f"Test fixture not found: {DYNA_FILE}"

    def test_parse_returns_system(self, system: System) -> None:
        assert isinstance(system, System)

    def test_base_mva(self, system: System) -> None:
        assert system.base_mva == pytest.approx(1000.0)

    def test_system_name(self, system: System) -> None:
        assert "MANUAL" in system.name.upper()

    def test_bus_count(self, system: System) -> None:
        """Model system has 10 nodes (1010-1100)."""
        assert system.num_buses == 10

    def test_branch_count(self, system: System) -> None:
        """9 transmission lines + 5 transformers = 14 branches."""
        assert system.num_branches == 14

    def test_generator_count(self, system: System) -> None:
        """4 generators: G-1 (1010), G-2 (1020), G-3 (1030), SWING (1100)."""
        assert system.num_generators == 4

    def test_load_count(self, system: System) -> None:
        """Buses with nonzero load: 1090 (P=6.0) and 1100 (Q=-0.5, P=4.0)."""
        assert system.num_loads >= 1

    def test_slack_bus(self, system: System) -> None:
        """Swing node is 1100."""
        slack_buses = system.get_slack_buses()
        assert len(slack_buses) == 1
        assert slack_buses[0].bus_id == 1100

    def test_pv_buses(self, system: System) -> None:
        """Generator buses 1010, 1020, 1030 should be PV."""
        pv_buses = system.get_pv_buses()
        pv_ids = {b.bus_id for b in pv_buses}
        assert 1010 in pv_ids
        assert 1020 in pv_ids
        assert 1030 in pv_ids

    def test_transmission_line_impedance(self, system: System) -> None:
        """Check 500KV 1-A line (1040→1050): Z1R=0.00351, Z1X=0.06686."""
        branches = [b for b in system.branches if b.from_bus == 1040 and b.to_bus == 1050]
        assert len(branches) >= 1
        b = branches[0]
        assert b.r_pu == pytest.approx(0.00351, abs=1e-5)
        assert b.x_pu == pytest.approx(0.06686, abs=1e-5)
        assert b.b_pu == pytest.approx(0.02994, abs=1e-5)

    def test_transformer_tap(self, system: System) -> None:
        """Check 22/500 TR (1010→1040): Z1X=0.0232, tap=1.07."""
        branches = [b for b in system.branches if b.from_bus == 1010 and b.to_bus == 1040]
        assert len(branches) == 1
        b = branches[0]
        assert b.x_pu == pytest.approx(0.02320, abs=1e-5)
        assert b.tap_ratio == pytest.approx(1.07, abs=1e-3)

    def test_generator_machine_data(self, system: System) -> None:
        """Check G-1 (1010) machine parameters."""
        gens = system.get_bus_generators(1010)
        assert len(gens) == 1
        g = gens[0]
        assert g.mbase == pytest.approx(5000.0)
        assert g.xd_pu == pytest.approx(1.70)
        assert g.xdp_pu == pytest.approx(0.35)
        assert g.xdpp_pu == pytest.approx(0.25)

    def test_generator_sequence_reactance(self, system: System) -> None:
        """Check G-1 (1010) sequence reactances from G5 card."""
        gens = system.get_bus_generators(1010)
        assert len(gens) == 1
        g = gens[0]
        assert g.x0_pu == pytest.approx(0.25)
        assert g.x2_pu == pytest.approx(0.25)

    def test_system_validates(self, system: System) -> None:
        """System should pass validation (no missing bus refs, etc.)."""
        errors = system.validate()
        assert errors == [], f"Validation errors: {errors}"


# =============================================================================
# Factory and convenience tests
# =============================================================================


class TestDynaFactoryIntegration:
    """Tests for factory registration and convenience methods."""

    def test_parser_factory_create(self) -> None:
        parser = ParserFactory.create("dyna")
        assert isinstance(parser, DynaParser)

    def test_parser_factory_from_extension(self) -> None:
        parser = ParserFactory.from_extension("dyna")
        assert isinstance(parser, DynaParser)

    def test_system_from_dyna(self) -> None:
        system = System.from_dyna(DYNA_FILE)
        assert system.num_buses == 10

    def test_system_from_file(self) -> None:
        system = System.from_file(DYNA_FILE)
        assert system.num_buses == 10

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            parse_dyna("/nonexistent/file.dyna")

    def test_available_formats_includes_dyna(self) -> None:
        assert "dyna" in ParserFactory.available_formats()

    def test_supported_extensions_includes_dyna(self) -> None:
        assert "dyna" in ParserFactory.supported_extensions()
