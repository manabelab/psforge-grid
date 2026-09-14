"""Tests for what the parsers do with input they cannot read.

A parser that quietly returns an empty or partial ``System`` is worse than one
that fails: the caller -- an LLM above all -- analyses the result as if it were
the real grid. These tests pin the behaviour that replaced it.

The RAW files here are written inline rather than committed as fixtures: each
one is a few lines long and exists to exercise one specific defect.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from psforge_grid.io.errors import (
    FileFormatError,
    MalformedRecordError,
    ParseError,
    UnsupportedVersionError,
)
from psforge_grid.io.parse_report import ParseReport, SkippedRecord
from psforge_grid.io.raw_parser import _split_fields
from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.load import Load
from psforge_grid.models.system import System

FIXTURES = Path(__file__).parent / "fixtures"

# A minimal but complete v33 case: two buses, one load, one generator, one line.
# Fields are separated by blanks, which PSS/E permits and which used to make the
# parser return an empty System without raising.
BLANK_DELIMITED_RAW = """\
0    100.00 33      0      0        60.000000000 / BLANK DELIMITED CASE
Title line one
Title line two
     1 'Bus 1'      230.00      3      1      1      1         1.06000000  0.0  1.1  0.9
     2 'Bus 2'      230.00      1      1      1      1         1.00000000  0.0  1.1  0.9
0 / END OF BUS DATA
     2 '1'      1      1      1        21.700000000        12.700000000
0 / END OF LOAD DATA
0 / END OF FIXED SHUNT DATA
     1 '1'    40.000    10.000   50.0  -50.0  1.06000  0  100.0 0 0 0 0 1.0 1
0 / END OF GENERATOR DATA
     1      2 '1'   0.01938   0.05917   0.05280  100.0  0.0  0.0  0.0 0.0 0.0 0.0 1
0 / END OF BRANCH DATA
"""


def _write(tmp_path: Path, name: str, content: str) -> Path:
    """Write ``content`` to ``tmp_path/name`` and return the path."""
    path = tmp_path / name
    path.write_text(content)
    return path


class TestFieldSplitting:
    """PSS/E separates fields by commas, blanks, or a mix of the two."""

    def test_comma_delimited(self) -> None:
        assert _split_fields("1,'Bus 1  ', 138.0,3") == ["1", "Bus 1", "138.0", "3"]

    def test_blank_delimited(self) -> None:
        assert _split_fields("  1 'Bus 1'  230.00  3") == ["1", "Bus 1", "230.00", "3"]

    def test_mixed_delimiters(self) -> None:
        """The case header of a real file: blanks and commas in one record."""
        assert _split_fields("0     100.00  33 , 0, 0, 60.00") == [
            "0",
            "100.00",
            "33",
            "0",
            "0",
            "60.00",
        ]

    def test_consecutive_commas_mark_an_omitted_field(self) -> None:
        assert _split_fields("1,,3") == ["1", "", "3"]

    def test_quoted_text_keeps_its_commas_and_blanks(self) -> None:
        assert _split_fields("1,'Bus, two  ',3") == ["1", "Bus, two", "3"]


class TestRefusedFiles:
    """Files that cannot be read at all raise instead of returning an empty System."""

    def test_empty_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileFormatError):
            System.from_raw(_write(tmp_path, "empty.raw", ""))

    def test_content_of_another_format(self, tmp_path: Path) -> None:
        with pytest.raises(FileFormatError):
            System.from_raw(_write(tmp_path, "alien.raw", "function mpc = case14\nmpc.bus = [\n"))

    def test_change_case_is_refused_by_name(self, tmp_path: Path) -> None:
        """IC=1 means 'apply to an existing case', not 'here is a base case'."""
        content = BLANK_DELIMITED_RAW.replace("0    100.00 33", "1    100.00 33", 1)
        with pytest.raises(FileFormatError, match="IC=1"):
            System.from_raw(_write(tmp_path, "change.raw", content))

    def test_unsupported_revision_is_refused_rather_than_half_read(self, tmp_path: Path) -> None:
        content = BLANK_DELIMITED_RAW.replace("0    100.00 33", "0    100.00 35", 1)
        with pytest.raises(UnsupportedVersionError, match="35"):
            System.from_raw(_write(tmp_path, "rev35.raw", content))

    def test_zero_base_mva_is_refused(self, tmp_path: Path) -> None:
        """A zero system base used to surface as ZeroDivisionError from inside."""
        content = BLANK_DELIMITED_RAW.replace("0    100.00 33", "0      0.00 33", 1)
        with pytest.raises(FileFormatError, match="SBASE"):
            System.from_raw(_write(tmp_path, "zerobase.raw", content))

    def test_every_refusal_is_a_parse_error(self, tmp_path: Path) -> None:
        """Callers can catch one family regardless of what was wrong."""
        with pytest.raises(ParseError):
            System.from_raw(_write(tmp_path, "empty.raw", ""))


class TestBlankDelimitedFiles:
    """Blank-separated records used to yield an empty System with no exception."""

    def test_all_blocks_are_read(self, tmp_path: Path) -> None:
        system = System.from_raw(_write(tmp_path, "blank.raw", BLANK_DELIMITED_RAW))
        assert len(system.buses) == 2
        assert len(system.loads) == 1
        assert len(system.generators) == 1
        assert len(system.branches) == 1

    def test_values_survive_blank_delimiting(self, tmp_path: Path) -> None:
        system = System.from_raw(_write(tmp_path, "blank.raw", BLANK_DELIMITED_RAW))
        slack = next(bus for bus in system.buses if bus.bus_id == 1)
        assert slack.bus_type == 3
        assert slack.base_kv == pytest.approx(230.0)
        assert slack.v_magnitude == pytest.approx(1.06)
        assert system.loads[0].p_load == pytest.approx(21.7 / 100.0)

    def test_report_is_clean(self, tmp_path: Path) -> None:
        system = System.from_raw(_write(tmp_path, "blank.raw", BLANK_DELIMITED_RAW))
        assert system.parse_report is not None
        assert system.parse_report.is_clean
        assert system.parse_report.records_read == 5


class TestTruncatedRecords:
    """A record missing the fields that define the element is not invented."""

    @staticmethod
    def _ieee14_with_truncated_bus2(tmp_path: Path) -> Path:
        lines = (FIXTURES / "ieee14.raw").read_text().splitlines()
        index = next(i for i, line in enumerate(lines) if line.strip().startswith("2,'Bus 2"))
        lines[index] = ",".join(lines[index].split(",")[:3])
        return _write(tmp_path, "truncated.raw", "\n".join(lines) + "\n")

    def test_truncated_bus_is_not_fabricated(self, tmp_path: Path) -> None:
        """Bus 2 of ieee14 is a PV bus at 1.045 pu.

        Truncating its record before IDE used to produce a PQ bus at 1.0 pu --
        a different element, created without a word. It must be skipped instead.
        """
        system = System.from_raw(self._ieee14_with_truncated_bus2(tmp_path))
        assert not any(bus.bus_id == 2 for bus in system.buses)
        assert len(system.buses) == 13

    def test_truncated_bus_is_reported_with_line_and_reason(self, tmp_path: Path) -> None:
        system = System.from_raw(self._ieee14_with_truncated_bus2(tmp_path))
        assert system.parse_report is not None
        assert system.parse_report.skipped_count == 1
        skipped = system.parse_report.skipped[0]
        assert skipped.section == "BUS DATA"
        assert "IDE" in skipped.reason
        assert skipped.line_no == 5

    def test_strict_mode_raises_on_the_same_file(self, tmp_path: Path) -> None:
        path = self._ieee14_with_truncated_bus2(tmp_path)
        with pytest.raises(MalformedRecordError, match="IDE"):
            System.from_raw(path, strict=True)


class TestReportOnGoodFiles:
    """A file that reads cleanly still carries a report."""

    def test_ieee14_reports_no_skips(self) -> None:
        system = System.from_raw(FIXTURES / "ieee14.raw")
        assert system.parse_report is not None
        assert system.parse_report.is_clean
        assert (
            system.parse_report.records_read == 51
        )  # 14 buses + 11 loads + 1 shunt + 5 gens + 20 branches

    def test_system_built_in_memory_has_no_report(self) -> None:
        assert System().parse_report is None


class TestParseReport:
    """The report renders for a reader who sees only its headline."""

    def test_totals_come_first(self) -> None:
        report = ParseReport(
            format="raw",
            records_read=10,
            skipped=(SkippedRecord(7, "BUS DATA", "missing required field IDE", "2,'Bus 2'"),),
        )
        assert report.to_description().splitlines()[0] == "raw: 10 records read, 1 skipped"
        assert not report.is_clean

    def test_long_source_lines_are_truncated(self) -> None:
        record = SkippedRecord(1, "BUS DATA", "reason", "x" * 500)
        assert len(record.raw_line) == 203
        assert record.raw_line.endswith("...")


# A minimal MATPOWER case, used to corrupt one row at a time.
MATPOWER_CASE = """\
function mpc = tiny
mpc.version = '2';
mpc.baseMVA = 100.0;
mpc.bus = [
\t1\t3\t0.0\t0.0\t0.0\t0.0\t1\t1.0\t0.0\t230.0\t1\t1.1\t0.9;
\t2\t1\t21.7\t12.7\t0.0\t0.0\t1\t1.0\t0.0\t230.0\t1\t1.1\t0.9;
];
mpc.gen = [
\t1\t40.0\t10.0\t50.0\t-50.0\t1.0\t100.0\t1\t100.0\t0.0;
];
mpc.branch = [
\t1\t2\t0.01938\t0.05917\t0.0528\t100.0\t0.0\t0.0\t0.0\t0.0\t1\t-360.0\t360.0;
];
"""

PSFG_JSON = """\
{
  "metadata": {"format": "psforge-grid", "version": "1.0"},
  "system": {"name": "tiny", "base_mva": 100.0},
  "buses": [
    {"bus_id": 1, "bus_type": 3, "base_kv": 230.0},
    {"bus_id": 2, "bus_type": 1, "base_kv": 230.0, "no_such_field": 1}
  ]
}
"""


class TestOtherFormatsRefuseBadFiles:
    """Every format reports failure the same way, whatever the format."""

    @pytest.mark.parametrize(
        ("suffix", "loader"),
        [
            (".raw", System.from_raw),
            (".m", System.from_matpower),
            (".psfg.json", System.from_json),
        ],
    )
    def test_empty_file(self, tmp_path: Path, suffix: str, loader) -> None:  # noqa: ANN001
        with pytest.raises(ParseError):
            loader(_write(tmp_path, f"empty{suffix}", ""))

    @pytest.mark.parametrize(
        ("suffix", "loader"),
        [
            (".raw", System.from_raw),
            (".m", System.from_matpower),
            (".psfg.json", System.from_json),
        ],
    )
    def test_content_of_another_format(self, tmp_path: Path, suffix: str, loader) -> None:  # noqa: ANN001
        content = (FIXTURES / "ieee14.raw").read_text() if suffix != ".raw" else MATPOWER_CASE
        with pytest.raises(ParseError):
            loader(_write(tmp_path, f"alien{suffix}", content))


class TestMatpowerRowsAreReported:
    """A short MATPOWER row used to disappear between two element counts."""

    def test_short_row_is_skipped_and_reported(self, tmp_path: Path) -> None:
        broken = MATPOWER_CASE.replace(
            "\t2\t1\t21.7\t12.7\t0.0\t0.0\t1\t1.0\t0.0\t230.0\t1\t1.1\t0.9;", "\t2\t1\t21.7;"
        )
        system = System.from_matpower(_write(tmp_path, "broken.m", broken))
        assert len(system.buses) == 1
        assert system.parse_report is not None
        assert system.parse_report.skipped_count == 1
        assert system.parse_report.skipped[0].section == "bus"
        assert "13 columns" in system.parse_report.skipped[0].reason

    def test_non_numeric_column_is_skipped_and_reported(self, tmp_path: Path) -> None:
        broken = MATPOWER_CASE.replace("\t2\t1\t21.7\t", "\t2\tBROKEN\t21.7\t")
        system = System.from_matpower(_write(tmp_path, "broken.m", broken))
        assert len(system.buses) == 1
        assert "not a number" in system.parse_report.skipped[0].reason

    def test_clean_case_reports_clean(self, tmp_path: Path) -> None:
        system = System.from_matpower(_write(tmp_path, "tiny.m", MATPOWER_CASE))
        assert system.parse_report is not None
        assert system.parse_report.is_clean
        assert system.parse_report.records_read == 4  # 2 buses + 1 gen + 1 branch

    def test_strict_raises(self, tmp_path: Path) -> None:
        broken = MATPOWER_CASE.replace("\t2\t1\t21.7\t", "\t2\tBROKEN\t21.7\t")
        with pytest.raises(MalformedRecordError):
            System.from_matpower(_write(tmp_path, "broken.m", broken), strict=True)


class TestJsonElementsAreReported:
    """A JSON element whose fields do not match the model is named, not dropped."""

    def test_unknown_field_is_reported_by_position(self, tmp_path: Path) -> None:
        system = System.from_json(_write(tmp_path, "tiny.psfg.json", PSFG_JSON))
        assert len(system.buses) == 1
        assert system.parse_report is not None
        assert system.parse_report.skipped[0].section == "buses[1]"

    def test_invalid_json_names_the_line(self, tmp_path: Path) -> None:
        with pytest.raises(FileFormatError, match="not valid JSON"):
            System.from_json(_write(tmp_path, "bad.psfg.json", "{\n  'not': json,\n}"))


class TestOpenDssLeavesTheWorkingDirectoryAlone:
    """OpenDSS's Compile changes the process working directory; the parser restores it."""

    def test_working_directory_is_preserved(self, tmp_path: Path) -> None:
        import os

        dss_path = tmp_path / "ieee14.dss"
        System.from_raw(FIXTURES / "ieee14.raw").to_dss(dss_path)

        before = os.getcwd()
        System.from_dss(dss_path)
        assert os.getcwd() == before


class TestSkippedRecordsReachTheLlmContext:
    """What the parser could not read must survive into the LLM-facing output."""

    def test_context_names_the_missing_records(self, tmp_path: Path) -> None:
        lines = (FIXTURES / "ieee14.raw").read_text().splitlines()
        index = next(i for i, line in enumerate(lines) if line.strip().startswith("2,'Bus 2"))
        lines[index] = ",".join(lines[index].split(",")[:3])
        system = System.from_raw(_write(tmp_path, "t.raw", "\n".join(lines) + "\n"))

        context = system.to_llm_context()
        assert "Records Not Read:" in context
        assert "1 record(s)" in context
        assert "BUS DATA" in context

    def test_clean_file_adds_no_section(self) -> None:
        context = System.from_raw(FIXTURES / "ieee14.raw").to_llm_context()
        assert "Records Not Read" not in context


def _tiny_system() -> System:
    """Build a two-bus system in memory.

    Used to generate CPAT-format test decks with psforge's own writers, so that
    the CPAT parsers can be exercised without shipping CPAT-derived data. This
    checks the robustness contract -- what happens to a damaged record -- not
    fidelity to CPAT's dialect, which needs real CPAT files and lives in the
    round-trip tests.
    """
    return System(
        buses=[
            Bus(1, bus_type=3, base_kv=230.0, v_magnitude=1.0),
            Bus(2, bus_type=1, base_kv=230.0, v_magnitude=1.0),
        ],
        branches=[Branch(1, 2, r_pu=0.01, x_pu=0.1, b_pu=0.02)],
        generators=[Generator(bus_id=1, p_gen=0.5, q_gen=0.1, v_setpoint=1.0)],
        loads=[Load(bus_id=2, p_load=0.4, q_load=0.1)],
        base_mva=100.0,
        name="TINY",
    )


class TestDynaCardsAreReported:
    """CPAT dyna decks generated here; no CPAT-derived data is needed."""

    @staticmethod
    def _deck(tmp_path: Path) -> Path:
        path = tmp_path / "tiny.dyna"
        _tiny_system().to_dyna(path)
        return path

    def test_generated_deck_reads_back_cleanly(self, tmp_path: Path) -> None:
        system = System.from_dyna(self._deck(tmp_path))
        assert len(system.buses) == 2
        assert system.parse_report is not None
        assert system.parse_report.is_clean

    def test_truncated_node_card_is_reported(self, tmp_path: Path) -> None:
        """An N card cut short loses its node number and used to vanish."""
        path = self._deck(tmp_path)
        lines = path.read_text().splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith("N        2"))
        lines[index] = "N   "
        path.write_text("\n".join(lines) + "\n")

        system = System.from_dyna(path)
        assert len(system.buses) == 1
        assert system.parse_report is not None
        assert system.parse_report.skipped_count == 1
        assert system.parse_report.skipped[0].section == "N"
        assert "node number" in system.parse_report.skipped[0].reason

    def test_unrecognised_card_is_reported(self, tmp_path: Path) -> None:
        path = self._deck(tmp_path)
        lines = path.read_text().splitlines()
        lines.insert(7, "ZZ  this card belongs to no section")
        path.write_text("\n".join(lines) + "\n")

        system = System.from_dyna(path)
        assert len(system.buses) == 2
        assert system.parse_report is not None
        assert any("unrecognised card" in record.reason for record in system.parse_report.skipped)

    def test_strict_raises_on_a_damaged_card(self, tmp_path: Path) -> None:
        path = self._deck(tmp_path)
        lines = path.read_text().splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith("N        2"))
        lines[index] = "N   "
        path.write_text("\n".join(lines) + "\n")

        with pytest.raises(MalformedRecordError):
            System.from_dyna(path, strict=True)

    def test_empty_deck_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(FileFormatError):
            System.from_dyna(_write(tmp_path, "empty.dyna", ""))


class TestPopArchivesAreReported:
    """CPAT .pop archives generated here; no CPAT-derived data is needed."""

    @staticmethod
    def _archive(tmp_path: Path) -> Path:
        path = tmp_path / "tiny.pop"
        _tiny_system().to_pop(path)
        return path

    def test_generated_archive_reads_back_cleanly(self, tmp_path: Path) -> None:
        system = System.from_pop(self._archive(tmp_path))
        assert len(system.buses) == 2
        assert system.parse_report is not None
        assert system.parse_report.is_clean

    def test_truncated_archive_is_refused(self, tmp_path: Path) -> None:
        """A damaged ZIP used to escape as BadZipFile from inside the parser."""
        path = self._archive(tmp_path)
        path.write_bytes(path.read_bytes()[: len(path.read_bytes()) // 2])
        with pytest.raises(FileFormatError):
            System.from_pop(path)

    def test_file_that_is_not_an_archive_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(FileFormatError):
            System.from_pop(_write(tmp_path, "notzip.pop", "this is not a ZIP archive"))
