"""What a parser could not read.

A parser that quietly drops records it does not recognise produces a ``System``
that looks complete and is not. :class:`ParseReport` carries the other half of
the answer: which records were skipped, from which line, and why.

Every parser attaches one to the ``System`` it returns
(:attr:`psforge_grid.models.system.System.parse_report`), so the information
survives as far as ``summarize()`` and ``to_llm_context()``.

Example:
    >>> report = ParseReport(
    ...     format="raw",
    ...     records_read=1284,
    ...     skipped=(
    ...         SkippedRecord(512, "BUS DATA", "expected >=10 fields, got 3", "  2,'Bus 2 ', 138.0"),
    ...     ),
    ... )
    >>> report.is_clean
    False
    >>> print(report.to_description())
    raw: 1284 records read, 1 skipped
      line 512    BUS DATA        expected >=10 fields, got 3
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Skipped source lines are stored truncated; a malformed record can be long.
MAX_RAW_LINE_CHARS = 200


@dataclass(frozen=True)
class SkippedRecord:
    """One record the parser could not read.

    Attributes:
        line_no: 1-based line number in the source file.
        section: Data block the record belongs to, e.g. ``"BUS DATA"``.
            ``"UNKNOWN"`` when the parser could not tell.
        reason: Why the record was skipped, specific enough to act on
            (``"expected >=10 fields, got 3"``, not ``"invalid"``).
        raw_line: The source line, truncated to :data:`MAX_RAW_LINE_CHARS`.
    """

    line_no: int
    section: str
    reason: str
    raw_line: str = ""

    def __post_init__(self) -> None:
        """Truncate an over-long source line in place."""
        if len(self.raw_line) > MAX_RAW_LINE_CHARS:
            object.__setattr__(self, "raw_line", self.raw_line[:MAX_RAW_LINE_CHARS] + "...")

    def to_description(self) -> str:
        """Return a one-line, LLM-readable description of this skip."""
        return f"line {self.line_no:<6} {self.section:<15} {self.reason}"


@dataclass(frozen=True)
class ParseReport:
    """Summary of what one parse run read and could not read.

    Attributes:
        format: Format name the parser was reading, e.g. ``"raw"``.
        records_read: Number of records successfully turned into elements.
        skipped: Records the parser could not read.
        warnings: Notes that are not failures -- an inferred delimiter, a
            version guess, a section the parser ignores by design.
    """

    format: str
    records_read: int = 0
    skipped: tuple[SkippedRecord, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def is_clean(self) -> bool:
        """Whether every record was read and nothing needed a warning."""
        return not self.skipped and not self.warnings

    @property
    def skipped_count(self) -> int:
        """Number of records the parser could not read."""
        return len(self.skipped)

    def to_description(self) -> str:
        """Return an LLM-readable description of the parse.

        The first line always states the totals, so a reader who sees only the
        headline still learns that records were lost.
        """
        lines = [f"{self.format}: {self.records_read} records read, {len(self.skipped)} skipped"]
        lines.extend(f"  {record.to_description()}" for record in self.skipped)
        lines.extend(f"  warning: {warning}" for warning in self.warnings)
        return "\n".join(lines)


@dataclass
class ParseReportBuilder:
    """Mutable accumulator that parsers fill while reading a file.

    Parsers collect skips as they go and call :meth:`build` once at the end.

    Example:
        >>> builder = ParseReportBuilder(format="raw")
        >>> builder.record_read()
        >>> builder.skip(7, "BUS DATA", "expected >=10 fields, got 2", " 2,'Bus 2'")
        >>> builder.build().skipped_count
        1
    """

    format: str
    records_read: int = 0
    _skipped: list[SkippedRecord] = field(default_factory=list)
    _warnings: list[str] = field(default_factory=list)

    def record_read(self, count: int = 1) -> None:
        """Count records that were read successfully.

        Args:
            count: How many records to add to the tally.
        """
        self.records_read += count

    def skip(self, line_no: int, section: str, reason: str, raw_line: str = "") -> None:
        """Record a record that could not be read.

        Args:
            line_no: 1-based line number in the source file.
            section: Data block the record belongs to.
            reason: Why it was skipped, specific enough to act on.
            raw_line: The source line.
        """
        self._skipped.append(SkippedRecord(line_no, section, reason, raw_line))

    def warn(self, message: str) -> None:
        """Record a note that is not a failure.

        Args:
            message: What the parser inferred or ignored.
        """
        self._warnings.append(message)

    def build(self) -> ParseReport:
        """Return the immutable report for this parse run."""
        return ParseReport(
            format=self.format,
            records_read=self.records_read,
            skipped=tuple(self._skipped),
            warnings=tuple(self._warnings),
        )
