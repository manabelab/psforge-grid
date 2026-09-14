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
