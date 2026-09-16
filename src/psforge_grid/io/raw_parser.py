"""PSS/E RAW file parser.

This module provides functionality to parse PSS/E RAW format files (v33/v34)
and convert them to psforge System objects.

Supported Formats:
    - PSS/E v33: Bus data starts immediately after 3-line case ID header
    - PSS/E v34: Uses explicit "BEGIN XXX DATA" section markers

Architecture:
    The module provides two interfaces:
    - RawParser class: Implements IParser interface for factory pattern
    - parse_raw function: Convenience function for quick usage

    Both use the same parsing logic internally.

How this parser was derived:
    Neither the Siemens PSS/E Program Operation Manual nor a PSS/E licence was
    used to write it. Nothing here is transcribed from Siemens documentation.

    The v34 support was built by running the parser against published real
    files and correcting what it got wrong, rather than from a specification;
    the primary record of that work is the project note
    ``01_psforge_gridの設計方針/05_追加調査報告書_RAWパーサー動作確認.md``.
    Several record layouts are documented by the fixtures themselves: a v34
    file written by PSS/E carries ``@!`` header comments naming each field, and
    ``tests/fixtures/39bus.raw`` is the reference used here for the generator
    and branch records.

    The origin of the v33 field offsets is no longer recorded and is not
    guessed at here. Checking them against powsybl's public PSS/E
    documentation, and recording that comparison, is outstanding work.

Test Data Sources:
    Terms for every file are recorded in ``tests/fixtures/NOTICE.md``; the
    notices travel with the files.

    - New England 39-bus (v34): NatLabRockies/ParaEMT_public, BSD 3-Clause.
      Written by PSS/E 34.8 itself -- the reference for what a real v34 file
      looks like.
    - Synthetic 2000-bus (v33): Texas A&M Electric Grid Test Case Repository.
    - IEEE 14-bus and 118-bus (v33): written by this package's own RawWriter
      from the pglib-opf MATPOWER cases, which carry the University of
      Washington data under CC BY 4.0. Being psforge's own output, they cannot
      show that the parser reads what other tools produce -- that is what the
      two files above are for.

References:
    - pglib-opf: https://github.com/power-grid-lib/pglib-opf
    - Texas A&M Repository: https://electricgrids.engr.tamu.edu/electric-grid-test-cases/

IDE Navigation Tips:
    - Press F12 on RawParser to see this implementation
    - Press Ctrl+F12 (Mac: Cmd+F12) on IParser to see other implementations
"""

from __future__ import annotations

import contextlib
import math
from pathlib import Path

from psforge_grid.io.errors import FileFormatError, MalformedRecordError, UnsupportedVersionError
from psforge_grid.io.parse_report import ParseReportBuilder
from psforge_grid.io.protocols import IParser
from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt
from psforge_grid.models.system import System

#: RAW revisions this parser reads. A file declaring anything else is refused
#: rather than parsed partially: a newer revision moves fields, and reading the
#: records that happen to still line up drops the rest without a word.
SUPPORTED_REVISIONS = (32, 33, 34)


class _RecordError(Exception):
    """A single record could not be read. Carries the reason for the report."""


def _split_fields(line: str) -> list[str]:
    """Split one RAW record into fields.

    PSS/E separates fields by commas **or** blanks, and the two are mixed in
    practice -- ``0     100.00  33 , 0, 0, 60.00`` is a real case header. A
    comma always ends a field; a run of blanks ends a field too, but a blank run
    followed by a comma is one separator, not two. Consecutive commas do mark an
    omitted field, so they yield an empty string.

    Quoted text is kept intact, including the blanks and commas inside it.

    Args:
        line: One record from a RAW file, without its trailing newline.

    Returns:
        The fields, stripped of surrounding blanks and of the quotes that
        delimited them.

    Example:
        >>> _split_fields("1,'Bus 1  ', 138.0,3")
        ['1', 'Bus 1', '138.0', '3']
        >>> _split_fields("0     100.00  33 , 0, 0, 60.00")
        ['0', '100.00', '33', '0', '0', '60.00']
        >>> _split_fields("1, ,3")
        ['1', '', '3']
    """
    fields: list[str] = []
    current: list[str] = []
    quote: str | None = None
    pending_separator = False  # a blank run is held until we know what follows

    for char in line:
        if quote is not None:
            if char == quote:
                quote = None
            else:
                current.append(char)
            continue

        if char in "'\"":
            if pending_separator:
                fields.append("".join(current).strip())
                current = []
                pending_separator = False
            quote = char
            continue

        if char == ",":
            fields.append("".join(current).strip())
            current = []
            pending_separator = False
            continue

        if char.isspace():
            if current or quote is not None:
                pending_separator = True
            continue

        if pending_separator:
            fields.append("".join(current).strip())
            current = []
            pending_separator = False
        current.append(char)

    if current or pending_separator or quote is not None:
        fields.append("".join(current).strip())
    return fields


def _required(fields: list[str], index: int, name: str) -> str:
    """Return a field the record cannot be understood without.

    Args:
        fields: Fields of the record.
        index: 0-based position of the field.
        name: Field name as the format spells it, used in the skip reason.

    Returns:
        The field value.

    Raises:
        _RecordError: If the field is missing or empty. The record is then
            skipped and recorded rather than filled with a made-up default:
            a bus record truncated before ``IDE`` would otherwise turn a PV bus
            into a PQ bus without a word.
    """
    if index >= len(fields) or fields[index] == "":
        raise _RecordError(f"missing required field {name} (index {index}, got {len(fields)})")
    return fields[index]


def _required_int(fields: list[str], index: int, name: str) -> int:
    """Return a required field as an int, or raise :class:`_RecordError`."""
    value = _required(fields, index, name)
    try:
        return int(float(value))
    except ValueError as exc:
        raise _RecordError(f"{name}: could not read {value!r} as an integer") from exc


def _required_float(fields: list[str], index: int, name: str) -> float:
    """Return a required field as a float, or raise :class:`_RecordError`."""
    value = _required(fields, index, name)
    try:
        return float(value)
    except ValueError as exc:
        raise _RecordError(f"{name}: could not read {value!r} as a number") from exc


def _optional_float(fields: list[str], index: int, default: float | None) -> float | None:
    """Return an optional numeric field, falling back to ``default``.

    Used only for fields the format itself allows to be absent (limits, owner
    data). Never used for a field that changes what the element *is*.
    """
    if index >= len(fields) or fields[index] == "":
        return default
    try:
        return float(fields[index])
    except ValueError:
        return default


def _optional_number(fields: list[str], index: int, default: float) -> float:
    """Return an optional numeric field that always has a usable value.

    The ``float | None`` variant above is for fields that stay ``None`` when the
    source did not provide them; this one is for fields the model requires and
    the format lets the writer omit, such as the normal voltage limits.
    """
    value = _optional_float(fields, index, default)
    return default if value is None else value


def _optional_int(fields: list[str], index: int, default: int) -> int:
    """Return an optional integer field, falling back to ``default``."""
    if index >= len(fields) or fields[index] == "":
        return default
    try:
        return int(float(fields[index]))
    except ValueError:
        return default


def _is_terminator(line: str) -> bool:
    """Whether a line ends a data section rather than holding a record."""
    stripped = line.strip()
    return stripped.startswith("0 /") or stripped.startswith("Q") or stripped in ("0", "0/")


class RawParser(IParser):
    """PSS/E RAW format parser.

    Parses PSS/E RAW files (v33/v34) and constructs System objects.
    This class implements the IParser interface for use with ParserFactory.

    Supported Versions:
        - v33: Traditional format with fixed section order
        - v34: Modern format with explicit "BEGIN XXX DATA" markers

    See IParser.parse() for full documentation of the parse method.

    Example:
        >>> from psforge_grid.io.raw_parser import RawParser
        >>> parser = RawParser()
        >>> system = parser.parse("ieee14.raw")
        >>>
        >>> # Or use the convenience function:
        >>> from psforge_grid.io import parse_raw
        >>> system = parse_raw("ieee14.raw")
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return ["raw", "RAW"]

    @property
    def format_name(self) -> str:
        """Return human-readable format name."""
        return "PSS/E RAW"

    def parse(self, filepath: str | Path, *, strict: bool = False) -> System:
        """Parse PSS/E RAW file and return a System object.

        See IParser.parse() for full documentation.
        """
        return _parse_raw_impl(filepath, strict=strict)


def parse_raw(filepath: str | Path, *, strict: bool = False) -> System:
    """Parse PSS/E RAW file and return a System object.

    Convenience function for parsing PSS/E RAW files. For factory pattern
    usage, see RawParser class or ParserFactory.

    Reads a PSS/E RAW format file (v33 or v34) and constructs a complete
    System object with buses, branches, generators, loads, and shunts.

    Args:
        filepath: Path to .raw file

    Returns:
        System object containing parsed power system data

    Raises:
        FileNotFoundError: If the specified file does not exist
        ValueError: If the file format is invalid or cannot be parsed

    Note:
        - Supports both v33 and v34 PSS/E RAW formats
        - v33: Bus data starts immediately after 3-line case ID
        - v34: Uses explicit "BEGIN XXX DATA" section markers
        - Comments (lines starting with '@') are ignored
        - Empty lines and whitespace are handled automatically
        - Section markers ('0 /' or 'Q') denote end of data sections
        - Power values (MW, MVAr) are converted to per-unit on system base MVA

    See Also:
        - RawParser: Class implementing IParser interface
        - ParserFactory: Factory for creating parsers
        - System.from_raw(): Alternative factory method
    """
    return _parse_raw_impl(filepath, strict=strict)


def _parse_raw_impl(filepath: str | Path, *, strict: bool = False) -> System:
    """Internal implementation of RAW file parsing.

    This is the shared implementation used by both parse_raw()
    and RawParser.parse().
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    system = System()

    # Set system name from filename
    system.name = filepath.name

    builder = ParseReportBuilder(format="raw")

    try:
        raw_text = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise FileFormatError(f"could not read the file: {e}", filepath=str(filepath)) from e
    if "�" in raw_text:
        # Previously these bytes were dropped with errors="ignore", which could
        # silently change a bus name or a numeric field.
        builder.warn("file is not valid UTF-8; undecodable bytes were replaced")
    lines = list(enumerate(raw_text.splitlines(), start=1))

    # Split file into sections
    sections = _split_sections(lines)

    # Parse CASE IDENTIFICATION section for base MVA and case title
    base_mva, case_title = _parse_case_id(sections.get("CASE_ID", []), builder, str(filepath))
    system.base_mva = base_mva
    if case_title:
        system.description = case_title

    # Parse BUS DATA section
    if "BUS_DATA" in sections:
        system.buses = _parse_bus_data(sections["BUS_DATA"], builder)

    # Parse LOAD DATA section
    if "LOAD_DATA" in sections:
        system.loads = _parse_load_data(sections["LOAD_DATA"], system.base_mva, builder)

    # Parse FIXED SHUNT DATA section
    if "FIXED_SHUNT_DATA" in sections:
        system.shunts = _parse_fixed_shunt_data(
            sections["FIXED_SHUNT_DATA"], system.base_mva, builder
        )

    # Parse GENERATOR DATA section
    if "GENERATOR_DATA" in sections:
        system.generators = _parse_generator_data(
            sections["GENERATOR_DATA"], system.base_mva, builder
        )

    # Parse BRANCH DATA section
    if "BRANCH_DATA" in sections:
        system.branches = _parse_branch_data(sections["BRANCH_DATA"], builder)

    # Parse TRANSFORMER DATA section (v34 format)
    if "TRANSFORMER_DATA" in sections:
        transformer_branches = _parse_transformer_data(sections["TRANSFORMER_DATA"], builder)
        system.branches.extend(transformer_branches)

    report = builder.build()
    system.parse_report = report

    if not system.buses:
        # An empty System is indistinguishable from a genuinely empty grid, and
        # whatever reads it next -- an LLM above all -- will analyse it as real.
        raise FileFormatError(
            f"no bus records could be read; the file does not look like a PSS/E RAW case "
            f"({report.records_read} records read, {report.skipped_count} skipped)",
            filepath=str(filepath),
        )

    if strict and report.skipped:
        first = report.skipped[0]
        raise MalformedRecordError(
            f"{report.skipped_count} record(s) could not be read; first: {first.reason}",
            filepath=str(filepath),
            line_no=first.line_no,
        )

    return system


#: Placeholder for the block after the header, whose identity is only known
#: once a terminator names it.
_PROVISIONAL = "__AFTER_HEADER__"

#: Data blocks in the order PSS/E writes them. Only the first six are turned
#: into elements; the rest are listed so that a terminator naming one of them
#: moves the reader to the right place instead of losing everything after it.
_BLOCK_LABELS: tuple[tuple[str, str], ...] = (
    ("SYSTEM-WIDE DATA", "SYSTEM_WIDE_DATA"),
    ("BUS DATA", "BUS_DATA"),
    ("LOAD DATA", "LOAD_DATA"),
    ("FIXED SHUNT DATA", "FIXED_SHUNT_DATA"),
    ("GENERATOR DATA", "GENERATOR_DATA"),
    ("BRANCH DATA", "BRANCH_DATA"),
    ("TRANSFORMER DATA", "TRANSFORMER_DATA"),
    ("AREA DATA", "AREA_DATA"),
    ("TWO-TERMINAL DC DATA", "TWO_TERMINAL_DC_DATA"),
    ("VSC DC LINE DATA", "VSC_DC_DATA"),
    ("IMPEDANCE CORRECTION DATA", "IMPEDANCE_CORRECTION_DATA"),
    ("MULTI-TERMINAL DC DATA", "MULTI_TERMINAL_DC_DATA"),
    ("MULTI-SECTION LINE DATA", "MULTI_SECTION_LINE_DATA"),
    ("ZONE DATA", "ZONE_DATA"),
    ("INTER-AREA TRANSFER DATA", "INTER_AREA_TRANSFER_DATA"),
    ("OWNER DATA", "OWNER_DATA"),
    ("FACTS DEVICE DATA", "FACTS_DATA"),
    ("SWITCHED SHUNT DATA", "SWITCHED_SHUNT_DATA"),
    ("GNE DEVICE DATA", "GNE_DATA"),
    ("INDUCTION MACHINE DATA", "INDUCTION_MACHINE_DATA"),
)


def _next_block(ended: str | None) -> str | None:
    """Return the block that follows ``ended``, or ``None`` at the end.

    Files written without the "BEGIN ... DATA" half of the terminator comment
    rely on block order alone. Without this, everything after the first
    terminator is dropped -- and dropped silently, because no record is ever
    even attempted.

    Args:
        ended: Name of the block that just ended, or ``None`` if unknown.

    Returns:
        Name of the next block, or ``None`` if the order is exhausted or the
        block that ended is unknown.
    """
    if ended is None:
        return None
    names = [name for _, name in _BLOCK_LABELS]
    try:
        index = names.index(ended)
    except ValueError:
        return None
    return names[index + 1] if index + 1 < len(names) else None


def _split_sections(lines: list[tuple[int, str]]) -> dict[str, list[tuple[int, str]]]:
    """Split a RAW file into its data blocks, keeping source line numbers.

    Line numbers are carried through so that a record which cannot be read can
    be reported against its place in the original file.

    Args:
        lines: ``(1-based line number, line text)`` for every line of the file.

    Returns:
        Mapping of block name to the numbered lines it contains. The case
        identification header is returned under ``"CASE_ID"``.
    """
    markers = tuple((f"BEGIN {label}", name) for label, name in _BLOCK_LABELS)
    end_markers = tuple((f"END OF {label}", name) for label, name in _BLOCK_LABELS)

    sections: dict[str, list[tuple[int, str]]] = {}
    current_section: str | None = None
    current_lines: list[tuple[int, str]] = []
    case_id_lines: list[tuple[int, str]] = []
    header_count = 0

    for line_no, raw in lines:
        line = raw.strip()

        # Skip comments
        if line.startswith("@"):
            continue

        # Case identification header (first three non-comment lines)
        if header_count < 3 and current_section is None:
            case_id_lines.append((line_no, line))
            header_count += 1
            if header_count == 3:
                sections["CASE_ID"] = case_id_lines
                # What follows the header depends on the revision: bus data in
                # v33, system-wide parameters in v34. Rather than guess, hold
                # the lines until a terminator says which block just ended.
                current_section = _PROVISIONAL
            continue

        line_upper = line.upper()

        if _is_terminator(line):
            if current_section:
                sections.setdefault(current_section, []).extend(current_lines)
                current_lines = []
                if current_section == _PROVISIONAL:
                    pass  # renamed just below, once the terminator is read
            ended = current_section
            current_section = None
            # A terminator may name the next block ("BEGIN LOAD DATA"), name the
            # block that just ended ("END OF BUS DATA"), or name nothing at all.
            for marker, name in end_markers:
                if marker in line_upper:
                    ended = name
                    break
            if ended is None or ended == _PROVISIONAL:
                # Nothing named the block that just ended, so fall back to the
                # v33 convention that bus data comes first.
                ended = "BUS_DATA"
            if _PROVISIONAL in sections:
                sections[ended] = sections.pop(_PROVISIONAL) + sections.get(ended, [])
            if not any(marker in line_upper for marker, _ in markers):
                current_section = _next_block(ended)

        started = False
        for marker, name in markers:
            if marker in line_upper:
                current_section = name
                started = True
                break
        if started or _is_terminator(line):
            continue

        if current_section and line:
            current_lines.append((line_no, line))

    if current_section and current_lines:
        sections.setdefault(current_section, []).extend(current_lines)

    if "CASE_ID" not in sections and case_id_lines:
        # Fewer than three lines before the data began. Keep what there is so
        # the header check can report what is actually wrong with the file.
        sections["CASE_ID"] = case_id_lines

    return sections


def _parse_case_id(
    lines: list[tuple[int, str]],
    builder: ParseReportBuilder,
    filepath: str,
) -> tuple[float, str]:
    """Read the case identification header and check the file is one we can read.

    PSS/E RAW header (v33)::

        Line 1: IC, SBASE, REV, XFRRAT, NXFRAT, BASFRQ / comment
        Line 2: Case title line 1
        Line 3: Case title line 2

    Args:
        lines: Numbered lines of the CASE_ID block.
        builder: Report being filled for this parse run.
        filepath: Path of the file, used in error messages.

    Returns:
        ``(base_mva, case_title)``.

    Raises:
        FileFormatError: If the header is unreadable, if IC is not 0 (the file
            is a change case to be applied to an existing one, not a base case),
            or if SBASE is not a positive number.
        UnsupportedVersionError: If REV names a revision outside
            :data:`SUPPORTED_REVISIONS`.
    """
    base_mva = 100.0
    case_title = ""

    if not lines:
        raise FileFormatError("the file has no case identification header", filepath=filepath)

    line_no, first_line = lines[0]
    # Everything after the first "/" is a comment, and may contain commas.
    fields = _split_fields(first_line.split("/", 1)[0])

    try:
        ic = int(float(_required(fields, 0, "IC")))
    except (_RecordError, ValueError) as exc:
        raise FileFormatError(
            f"the first line is not a PSS/E case identification record: {first_line[:60]!r}",
            filepath=filepath,
            line_no=line_no,
        ) from exc

    if ic != 0:
        raise FileFormatError(
            f"IC={ic}: this file changes an existing case rather than defining a base case; "
            "only IC=0 files can be read on their own",
            filepath=filepath,
            line_no=line_no,
        )

    try:
        base_mva = float(_required(fields, 1, "SBASE"))
    except (_RecordError, ValueError) as exc:
        raise FileFormatError(
            "SBASE (system base MVA) could not be read from the header",
            filepath=filepath,
            line_no=line_no,
        ) from exc
    if base_mva <= 0:
        raise FileFormatError(
            f"SBASE={base_mva}: the system base MVA must be positive",
            filepath=filepath,
            line_no=line_no,
        )

    if len(fields) > 2 and fields[2] != "":
        try:
            revision = int(float(fields[2]))
        except ValueError:
            builder.warn(f"REV field {fields[2]!r} is not a number; revision not checked")
        else:
            if revision not in SUPPORTED_REVISIONS:
                raise UnsupportedVersionError(
                    f"RAW revision {revision} is not supported "
                    f"(this parser reads {', '.join(str(r) for r in SUPPORTED_REVISIONS)}); "
                    "reading it partially would drop whatever the revision moved",
                    filepath=filepath,
                    line_no=line_no,
                )
    else:
        builder.warn("header does not declare a REV; assuming a supported revision")

    # Lines 2-3 hold the case title
    title_parts = []
    for _, text in lines[1:3]:
        stripped = text.strip()
        if stripped and not stripped.startswith("BEGIN ") and not stripped.startswith("GENERAL,"):
            title_parts.append(stripped)
    case_title = " ".join(title_parts).strip()

    return base_mva, case_title


def _parse_bus_data(lines: list[tuple[int, str]], builder: ParseReportBuilder) -> list[Bus]:
    """Parse the BUS DATA block.

    Record layout (v33)::

        I, 'NAME', BASKV, IDE, AREA, ZONE, OWNER, VM, VA, NVHI, NVLO, EVHI, EVLO

    ``IDE`` (bus type) and ``VM``/``VA`` are required rather than defaulted: a
    record truncated before ``IDE`` would otherwise be read as a PQ bus at
    1.0 pu, turning a PV bus into a different element without a word.

    Args:
        lines: Numbered lines of the block.
        builder: Report being filled for this parse run.

    Returns:
        The buses that could be read. Records that could not are recorded in
        the report.
    """
    buses = []

    for line_no, line in lines:
        if not line or _is_terminator(line):
            continue

        try:
            fields = _split_fields(line)
            bus_id = _required_int(fields, 0, "I")
            base_kv = _required_float(fields, 2, "BASKV")
            bus_type = _required_int(fields, 3, "IDE")
            v_magnitude = _required_float(fields, 7, "VM")
            v_angle_deg = _required_float(fields, 8, "VA")
        except _RecordError as exc:
            builder.skip(line_no, "BUS DATA", str(exc), line)
            continue

        name = fields[1] if len(fields) > 1 and fields[1] != "" else None
        bus = Bus(
            bus_id=bus_id,
            bus_type=bus_type,
            base_kv=base_kv,
            v_magnitude=v_magnitude,
            v_angle=v_angle_deg * math.pi / 180.0,
            area=_optional_int(fields, 4, 1),
            zone=_optional_int(fields, 5, 1),
            v_max=_optional_number(fields, 9, 1.1),
            v_min=_optional_number(fields, 10, 0.9),
            name=name,
        )
        buses.append(bus)
        builder.record_read()

    return buses


def _parse_load_data(
    lines: list[tuple[int, str]], base_mva: float, builder: ParseReportBuilder
) -> list[Load]:
    """Parse the LOAD DATA block.

    Record layout (v33)::

        I, ID, STATUS, AREA, ZONE, PL, QL, IP, IQ, YP, YQ, OWNER, SCALE, INTRPT

    Args:
        lines: Numbered lines of the block.
        base_mva: System base MVA, for the conversion to per-unit.
        builder: Report being filled for this parse run.

    Returns:
        The loads that could be read.
    """
    loads = []

    for line_no, line in lines:
        if not line or _is_terminator(line):
            continue

        try:
            fields = _split_fields(line)
            bus_id = _required_int(fields, 0, "I")
            p_load_mw = _required_float(fields, 5, "PL")
            q_load_mvar = _required_float(fields, 6, "QL")
        except _RecordError as exc:
            builder.skip(line_no, "LOAD DATA", str(exc), line)
            continue

        loads.append(
            Load(
                bus_id=bus_id,
                p_load=p_load_mw / base_mva,
                q_load=q_load_mvar / base_mva,
                status=_optional_int(fields, 2, 1),
                load_id=fields[1] if len(fields) > 1 and fields[1] != "" else "1",
            )
        )
        builder.record_read()

    return loads


def _parse_fixed_shunt_data(
    lines: list[tuple[int, str]], base_mva: float, builder: ParseReportBuilder
) -> list[Shunt]:
    """Parse the FIXED SHUNT DATA block.

    Record layout (v33)::

        I, ID, STATUS, GL, BL

    Args:
        lines: Numbered lines of the block.
        base_mva: System base MVA, for the conversion to per-unit.
        builder: Report being filled for this parse run.

    Returns:
        The shunts that could be read.
    """
    shunts = []

    for line_no, line in lines:
        if not line or _is_terminator(line):
            continue

        try:
            fields = _split_fields(line)
            bus_id = _required_int(fields, 0, "I")
            g_mw = _required_float(fields, 3, "GL")
            b_mvar = _required_float(fields, 4, "BL")
        except _RecordError as exc:
            builder.skip(line_no, "FIXED SHUNT DATA", str(exc), line)
            continue

        shunts.append(
            Shunt(
                bus_id=bus_id,
                g_pu=g_mw / base_mva,
                b_pu=b_mvar / base_mva,
                status=_optional_int(fields, 2, 1),
                shunt_id=fields[1] if len(fields) > 1 and fields[1] != "" else "1",
            )
        )
        builder.record_read()

    return shunts


def _parse_generator_data(
    lines: list[tuple[int, str]], base_mva: float, builder: ParseReportBuilder
) -> list[Generator]:
    """Parse the GENERATOR DATA block.

    Record layout (v33)::

        I, ID, PG, QG, QT, QB, VS, IREG, MBASE, ZR, ZX, RT, XT, GTAP, STAT, ...

    ``QT``/``QB`` stay optional and become ``None`` when absent, following the
    "Optional + None = source not provided" rule; ``VS`` is required because a
    generator with an invented voltage setpoint is a different machine.

    Args:
        lines: Numbered lines of the block.
        base_mva: System base MVA, for the conversion to per-unit.
        builder: Report being filled for this parse run.

    Returns:
        The generators that could be read.
    """
    generators = []

    for line_no, line in lines:
        if not line or _is_terminator(line):
            continue

        try:
            fields = _split_fields(line)
            bus_id = _required_int(fields, 0, "I")
            p_gen_mw = _required_float(fields, 2, "PG")
            q_gen_mvar = _required_float(fields, 3, "QG")
            v_setpoint = _required_float(fields, 6, "VS")
        except _RecordError as exc:
            builder.skip(line_no, "GENERATOR DATA", str(exc), line)
            continue

        q_max_mvar = _optional_float(fields, 4, None)
        q_min_mvar = _optional_float(fields, 5, None)
        mbase = _optional_number(fields, 8, base_mva)

        generators.append(
            Generator(
                bus_id=bus_id,
                p_gen=p_gen_mw / base_mva,
                q_gen=q_gen_mvar / base_mva,
                v_setpoint=v_setpoint,
                q_max=q_max_mvar / base_mva if q_max_mvar is not None else None,
                q_min=q_min_mvar / base_mva if q_min_mvar is not None else None,
                mbase=mbase,
                status=_optional_int(fields, 14, 1),
                gen_id=fields[1] if len(fields) > 1 and fields[1] != "" else "1",
            )
        )
        builder.record_read()

    return generators


def _parse_branch_data(lines: list[tuple[int, str]], builder: ParseReportBuilder) -> list[Branch]:
    """Parse the BRANCH DATA block (v33 and v34 layouts).

    The two layouts differ by one field::

        v33: I, J, CKT, R, X, B, RATEA, RATEB, RATEC, GI, BI, GJ, BJ, ST, ...
        v34: I, J, CKT, R, X, B, NAME, RATE1..RATE12, GI, BI, GJ, BJ, STAT, ...

    v34 inserts ``NAME`` at index 6, so the layout is told apart by whether that
    field reads as a number.

    Args:
        lines: Numbered lines of the block.
        builder: Report being filled for this parse run.

    Returns:
        The branches that could be read.
    """
    branches = []

    for line_no, line in lines:
        if not line or _is_terminator(line):
            continue

        try:
            fields = _split_fields(line)
            from_bus = _required_int(fields, 0, "I")
            to_bus = _required_int(fields, 1, "J")
            r_pu = _required_float(fields, 3, "R")
            x_pu = _required_float(fields, 4, "X")
        except _RecordError as exc:
            builder.skip(line_no, "BRANCH DATA", str(exc), line)
            continue

        b_pu = _optional_number(fields, 5, 0.0)

        # v34 puts NAME where v33 puts RATEA; a non-numeric field 6 means v34.
        is_v34 = False
        if len(fields) > 6 and fields[6] != "":
            try:
                float(fields[6])
            except ValueError:
                is_v34 = True

        rate_base, status_index = (7, 23) if is_v34 else (6, 13)
        rates: list[float | None] = []
        for offset in range(3):
            rate = _optional_float(fields, rate_base + offset, None)
            rates.append(rate if rate is not None and rate > 0 else None)

        branches.append(
            Branch(
                from_bus=from_bus,
                to_bus=to_bus,
                r_pu=r_pu,
                x_pu=x_pu,
                b_pu=b_pu,
                rate_a=rates[0],
                rate_b=rates[1],
                rate_c=rates[2],
                status=_optional_int(fields, status_index, 1),
                circuit_id=fields[2] if len(fields) > 2 and fields[2] != "" else "1",
            )
        )
        builder.record_read()

    return branches


def _parse_transformer_data(
    lines: list[tuple[int, str]], builder: ParseReportBuilder
) -> list[Branch]:
    """Parse TRANSFORMER DATA section (v34 format).

    In v34, transformer data spans multiple lines per transformer:
    - Line 1: I, J, K, CKT, CW, CZ, CM, MAG1, MAG2, NMETR, NAME, STAT, ...
    - Line 2: R1-2, X1-2, SBASE1-2, ... (impedance data)
    - Line 3: WINDV1, NOMV1, ANG1, RATE1-1, ... (winding 1 data)
    - Line 4: WINDV2, NOMV2, ... (winding 2 data for 2-winding)
    - (Optional Line 5: WINDV3, ... for 3-winding transformers)

    A transformer that runs off the end of the block, or whose records cannot be
    read, is recorded in the report rather than dropped silently.

    Args:
        lines: Numbered lines of the block.
        builder: Report being filled for this parse run.

    Returns:
        The transformers that could be read, as branches.
    """
    branches = []
    i = 0

    while i < len(lines):
        record_line_no, line = lines[i]
        line = line.strip()
        if not line or line.startswith("@"):
            i += 1
            continue

        try:
            # Line 1: Header with I, J, K, CKT, ...
            fields1 = _split_fields(line)

            from_bus = _required_int(fields1, 0, "I")
            to_bus = _required_int(fields1, 1, "J")
            k_bus = _required_int(fields1, 2, "K")  # 0 = two-winding
            circuit_id = fields1[3] if len(fields1) > 3 and fields1[3] != "" else "1"

            # MAG1 (magnetizing G) at position 7, MAG2 (magnetizing B) at position 8
            mag_g = None
            mag_b = None
            if len(fields1) > 7:
                with contextlib.suppress(ValueError):
                    val = float(fields1[7])
                    if val != 0.0:
                        mag_g = val
            if len(fields1) > 8:
                with contextlib.suppress(ValueError):
                    val = float(fields1[8])
                    if val != 0.0:
                        mag_b = val

            # STAT is typically at position 11 in v34
            status = 1
            if len(fields1) > 11:
                with contextlib.suppress(ValueError):
                    status = int(fields1[11])

            # Determine number of windings
            is_three_winding = k_bus != 0
            num_data_lines = 5 if is_three_winding else 4

            # Check if we have enough lines
            if i + num_data_lines - 1 >= len(lines):
                builder.skip(
                    record_line_no,
                    "TRANSFORMER DATA",
                    f"record needs {num_data_lines} lines but the block ends first",
                    line,
                )
                break

            # Line 2: Impedance data (R1-2, X1-2, SBASE1-2, ...)
            i += 1
            line2 = lines[i][1].strip()
            if line2.startswith("@"):
                i += 1
                if i >= len(lines):
                    break
                line2 = lines[i][1].strip()

            fields2 = _split_fields(line2)
            r_pu = float(fields2[0]) if len(fields2) > 0 else 0.0
            x_pu = float(fields2[1]) if len(fields2) > 1 else 0.0

            # SBASE1-2 (transformer rated MVA) at position 2
            sbase_mva = None
            if len(fields2) > 2:
                with contextlib.suppress(ValueError):
                    val = float(fields2[2])
                    if val > 0:
                        sbase_mva = val

            # Line 3: Winding 1 data (WINDV1, NOMV1, ANG1, RATE1-1, ...)
            i += 1
            line3 = lines[i][1].strip()
            if line3.startswith("@"):
                i += 1
                if i >= len(lines):
                    break
                line3 = lines[i][1].strip()

            fields3 = _split_fields(line3)
            windv1 = float(fields3[0]) if len(fields3) > 0 else 1.0
            nomv1 = None
            if len(fields3) > 1:
                with contextlib.suppress(ValueError):
                    val = float(fields3[1])
                    if val > 0:
                        nomv1 = val
            ang1_deg = float(fields3[2]) if len(fields3) > 2 else 0.0
            ang1_rad = ang1_deg * math.pi / 180.0

            # Rate from winding 1 data
            rate_a = None
            if len(fields3) > 3:
                rate_val = float(fields3[3])
                if rate_val > 0:
                    rate_a = rate_val

            # Line 4: Winding 2 data (WINDV2, NOMV2, ...)
            i += 1
            line4 = lines[i][1].strip()
            if line4.startswith("@"):
                i += 1
                if i >= len(lines):
                    break
                line4 = lines[i][1].strip()

            fields4 = _split_fields(line4)
            windv2 = float(fields4[0]) if len(fields4) > 0 else 1.0
            nomv2 = None
            if len(fields4) > 1:
                with contextlib.suppress(ValueError):
                    val = float(fields4[1])
                    if val > 0:
                        nomv2 = val

            # Calculate effective tap ratio
            tap_ratio = windv1 / windv2 if windv2 != 0 else windv1

            # Infer winding connection from shift angle
            winding_connection = None
            if abs(ang1_rad) > 0.1:  # ~5.7 degrees threshold
                winding_connection = "delta-wye" if ang1_rad > 0 else "wye-delta"
            # Note: wye-wye vs delta-delta cannot be distinguished from angle alone

            # Skip winding 3 line for 3-winding transformers
            if is_three_winding:
                i += 1
                line5 = lines[i][1].strip()
                if line5.startswith("@"):
                    i += 1

            branch = Branch(
                from_bus=from_bus,
                to_bus=to_bus,
                r_pu=r_pu,
                x_pu=x_pu,
                b_pu=0.0,  # Transformers have no line charging
                tap_ratio=tap_ratio,
                shift_angle=ang1_rad,
                rate_a=rate_a,
                status=status,
                circuit_id=circuit_id,
                winding_connection=winding_connection,
                nomv_from=nomv1,
                nomv_to=nomv2,
                sbase_mva=sbase_mva,
                mag_g=mag_g,
                mag_b=mag_b,
                is_xfmr=True,
            )
            branches.append(branch)
            builder.record_read()

            i += 1

        except (_RecordError, IndexError, ValueError) as exc:
            builder.skip(record_line_no, "TRANSFORMER DATA", str(exc) or type(exc).__name__, line)
            i += 1
            continue

    return branches
