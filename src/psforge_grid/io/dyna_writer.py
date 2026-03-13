"""Writer for CPAT dyna card format files.

This module provides functionality to export System objects to CPAT
Fortran fixed-column card format (.dyna). Symmetric counterpart of DynaParser.

The .dyna format uses 80-character lines with sections:
    DATA → T (transmission lines) → TEND → X (transformers) → XEND
    → N (nodes) → NEND → G1-G5 (generators) → GEND → STOP

Example:
    >>> from psforge_grid.io.dyna_writer import write_dyna
    >>> write_dyna(system, "output.dyna")
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from psforge_grid.io.protocols import IWriter

if TYPE_CHECKING:
    from psforge_grid.models.branch import Branch
    from psforge_grid.models.generator import Generator
    from psforge_grid.models.system import System


def _fmt_float(value: float, width: int) -> str:
    """Format a float to fit within a fixed column width.

    Uses up to 6 decimal places, truncating as needed to fit the width.

    Args:
        value: Float value to format.
        width: Target field width in characters.

    Returns:
        Right-justified formatted string of exactly `width` characters.
    """
    for decimals in range(6, -1, -1):
        s = f"{value:.{decimals}f}"
        if len(s) <= width:
            return s.rjust(width)
    # Fallback: scientific notation
    s = f"{value:.2e}"
    return s.rjust(width)


def _fmt_int(value: int, width: int) -> str:
    """Format an integer to fit within a fixed column width.

    Args:
        value: Integer value.
        width: Target field width.

    Returns:
        Right-justified formatted string.
    """
    return str(value).rjust(width)


def _pad(s: str, width: int) -> str:
    """Left-justify a string within a fixed column width.

    Args:
        s: String to pad.
        width: Target width.

    Returns:
        Left-justified string of exactly `width` characters.
    """
    return s[:width].ljust(width)


class DynaWriter(IWriter):
    """Writer for CPAT dyna card format (.dyna).

    Exports a System object to CPAT Fortran fixed-column card format.
    Performs the inverse of DynaParser.

    Note:
        - All P/Q values are written in p.u. on system base MVA
        - Generator machine parameters are written on machine base (mbase)
        - Y1C (charging susceptance) is written as-is from Branch.b_pu

    See Also:
        - DynaParser: The symmetric read implementation
        - WriterFactory: Factory for creating writer instances
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return ["dyna"]

    @property
    def format_name(self) -> str:
        """Return human-readable format name."""
        return "CPAT Dyna"

    def write(self, system: System, filepath: str | Path) -> None:
        """Write a System to a CPAT .dyna file.

        Args:
            system: System object to export
            filepath: Output file path
        """
        lines: list[str] = []

        # DATA card
        lines.append("DATA")
        name = (system.name or "PSFORGE")[:8]
        header = (system.name or "")[8:][:40]
        data_line = (
            "  "
            + _pad(name, 8)
            + _fmt_float(system.base_mva, 10)
            + _fmt_float(60.0, 10)
            + " " * 10
            + _pad(header, 40)
        )
        lines.append(data_line)

        # T cards (transmission lines)
        tlines = [br for br in system.branches if not br.is_transformer]
        for br in tlines:
            lines.append(_write_t_card(br))
            if br.has_zero_sequence_data:
                lines.append(_write_t_zero_seq(br))
        lines.append("TEND")

        # X cards (transformers)
        xfmrs = [br for br in system.branches if br.is_transformer]
        for br in xfmrs:
            lines.append(_write_x_card(br))
        lines.append("XEND")

        # N cards (nodes)
        # Build generator bus lookup for P_gen
        gen_bus_data: dict[int, tuple[float, float]] = {}
        for gen in system.generators:
            if gen.status == 1:
                bus_id = gen.bus_id
                p, v = gen_bus_data.get(bus_id, (0.0, gen.v_setpoint))
                gen_bus_data[bus_id] = (p + gen.p_gen, v)

        # Build load bus lookup
        load_bus_data: dict[int, tuple[float, float]] = {}
        for load in system.loads:
            if load.status == 1:
                bus_id = load.bus_id
                p, q = load_bus_data.get(bus_id, (0.0, 0.0))
                load_bus_data[bus_id] = (p + load.p_load, q + load.q_load)

        # Build shunt bus lookup
        shunt_bus_data: dict[int, float] = {}
        for shunt in system.shunts:
            if shunt.status == 1:
                shunt_bus_data[shunt.bus_id] = shunt_bus_data.get(shunt.bus_id, 0.0) + shunt.b_pu

        for bus in system.buses:
            p_gen, v_set = gen_bus_data.get(bus.bus_id, (0.0, 0.0))
            p_load, q_load = load_bus_data.get(bus.bus_id, (0.0, 0.0))
            shunt_b = shunt_bus_data.get(bus.bus_id, 0.0)

            # N card line (1-based columns)
            # Col 1: N, Col 2: zone flag (blank)
            # Col 4-10: NO, Col 11-20: VO, Col 21-30: PGO, Col 31-40: QGO
            # Col 41-50: PLO, Col 51-60: QLO, Col 61-68: YCO
            # Col 69-80: NNAME or VRT
            # Col 1: N, Col 2: zone (blank), Col 3: blank
            # Col 4-10: NO, Col 11-20: VO, Col 21-30: PGO, Col 31-40: QGO
            # Col 41-50: PLO, Col 51-60: QLO, Col 61-68: YCO
            # Col 69-80: NNAME
            line = (
                "N  "
                + _fmt_int(bus.bus_id, 7)
                + _fmt_float(bus.v_magnitude, 10)
                + _fmt_float(p_gen, 10)
                + _fmt_float(0.0, 10)  # QGO
                + _fmt_float(p_load, 10)
                + _fmt_float(q_load, 10)
                + _fmt_float(shunt_b, 8)
                + _pad(bus.name or "", 12)
            )
            lines.append(line)
        lines.append("NEND")

        # G cards (generators)
        for gen in system.generators:
            lines.extend(_write_g_cards(gen, system.base_mva))
        lines.append("GEND")

        lines.append("STOP")

        path = Path(filepath)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_t_card(br: Branch) -> str:
    """Write T card primary line for a transmission line.

    Args:
        br: Branch object (non-transformer).

    Returns:
        Formatted T card string.
    """
    z_flag = "Z" if br.has_zero_sequence_data else " "
    circuit_id = int(br.circuit_id) if br.circuit_id.isdigit() else 1
    # Col 1: T, Col 4-10: NO, Col 12: Z, Col 14-20: NFO
    # Col 24-30: NTO, Col 33: L, Col 36-45: Z1R, Col 46-55: Z1X
    # Col 56-65: Y1C, Col 69-80: TNAME
    line = (
        "T  "
        + _fmt_int(circuit_id, 7)
        + " "
        + z_flag
        + " "
        + _fmt_int(br.from_bus, 7)
        + "   "
        + _fmt_int(br.to_bus, 7)
        + "  1"
        + "  "
        + _fmt_float(br.r_pu, 10)
        + _fmt_float(br.x_pu, 10)
        + _fmt_float(br.b_pu, 10)
        + "   "
        + _pad(br.name or "", 12)
    )
    return line


def _write_t_zero_seq(br: Branch) -> str:
    """Write T card zero-sequence continuation line.

    Args:
        br: Branch with zero-sequence data.

    Returns:
        Formatted zero-sequence line.
    """
    r0 = br.r0_pu if br.r0_pu is not None else 0.0
    x0 = br.x0_pu if br.x0_pu is not None else 0.0
    b0 = br.b0_pu if br.b0_pu is not None else 0.0
    # Col 4-10: NMO (0), Col 16-25: ZOR, Col 26-35: ZOX, Col 56-65: YOC
    line = (
        "T  "
        + _fmt_int(0, 7)
        + "     "
        + _fmt_float(r0, 10)
        + _fmt_float(x0, 10)
        + " " * 20
        + _fmt_float(b0, 10)
    )
    return line


def _write_x_card(br: Branch) -> str:
    """Write X card primary line for a transformer.

    Args:
        br: Branch object (transformer).

    Returns:
        Formatted X card string.
    """
    circuit_id = int(br.circuit_id) if br.circuit_id.isdigit() else 1
    # Col 1: X, Col 2: R (blank), Col 4-10: NO, Col 12: Z (blank)
    # Col 14-20: NFO, Col 24-30: NTO, Col 33: L (1)
    # Col 36-45: Z1X, Col 46-55: TAPR, Col 56-65: TAPI
    # Col 69-80: XNAME
    line = (
        "X  "
        + _fmt_int(circuit_id, 7)
        + "  "
        + _fmt_int(br.from_bus, 7)
        + "   "
        + _fmt_int(br.to_bus, 7)
        + "  1"
        + "  "
        + _fmt_float(br.x_pu, 10)
        + _fmt_float(br.tap_ratio, 10)
        + _fmt_float(br.shift_angle, 10)
        + "   "
        + _pad(br.name or "", 12)
    )
    return line


def _write_g_cards(gen: Generator, base_mva: float) -> list[str]:
    """Write G1-G5 card set for a generator.

    Args:
        gen: Generator object.
        base_mva: System base MVA for P_max conversion.

    Returns:
        List of G card lines (G1, optionally G3, G4, G5).
    """
    cards: list[str] = []

    gmva = gen.mbase
    gmw = (gen.p_max * base_mva) if gen.p_max is not None else 0.0

    # G1 card (1-based columns)
    # Col 1-2: G1, Col 3: blank, Col 4-10: NFG
    # Col 11-12: blank, Col 13-15: LGT, Col 16-17: blank, Col 18-20: NGT
    # Col 21-30: GMVA, Col 31-40: GMW
    # Col 41-45: MG, Col 46-50: PLM, Col 51-55: DG, Col 56-60: QKGT
    # Col 61-72: GNAME
    g1 = (
        "G1 "  # col 1-3
        + _fmt_int(gen.bus_id, 7)  # col 4-10
        + "  "  # col 11-12
        + _fmt_int(2, 3)  # col 13-15 (LGT)
        + "  "  # col 16-17
        + _fmt_int(1, 3)  # col 18-20 (NGT)
        + _fmt_float(gmva, 10)  # col 21-30
        + _fmt_float(gmw, 10)  # col 31-40
        + _fmt_float(0.0, 5)  # col 41-45 (MG)
        + _fmt_float(0.0, 5)  # col 46-50 (PLM)
        + _fmt_float(0.0, 5)  # col 51-55 (DG)
        + _fmt_float(0.0, 5)  # col 56-60 (QKGT)
        + _pad(gen.name or "", 12)  # col 61-72
    )
    cards.append(g1)

    # G3 card (D-axis) - only if machine parameters exist
    has_d_axis = any(v is not None for v in [gen.xd_pu, gen.xdp_pu, gen.xdpp_pu])
    if has_d_axis:
        g3 = (
            "G3 "
            + " " * 7
            + _fmt_float(gen.xd_pu or 0.0, 10)
            + _fmt_float(gen.xdp_pu or 0.0, 10)
            + _fmt_float(gen.xdpp_pu or 0.0, 10)
            + _fmt_float(0.0, 10)
            + _fmt_float(0.0, 10)
            + _fmt_float(0.0, 10)
            + _fmt_float(0.0, 10)
        )
        cards.append(g3)

    # G4 card (Q-axis) - only if Xq'' exists
    if gen.xqpp_pu is not None:
        g4 = (
            "G4 "
            + " " * 7
            + _fmt_float(0.0, 10)
            + _fmt_float(0.0, 10)
            + _fmt_float(gen.xqpp_pu, 10)
            + _fmt_float(0.0, 10)
            + _fmt_float(0.0, 10)
            + _fmt_float(0.0, 10)
            + _fmt_float(0.0, 10)
        )
        cards.append(g4)

    # G5 card (leakage, armature, sequence) - if sequence data exists
    has_seq = any(v is not None for v in [gen.x0_pu, gen.x2_pu, gen.ra_pu, gen.ta_s])
    if has_seq:
        ra_type = "R" if gen.ra_pu is not None else "'"
        ta_val = gen.ra_pu if gen.ra_pu is not None else (gen.ta_s or 0.0)
        g5 = (
            "G5"
            + ra_type
            + " " * 7
            + _fmt_float(0.0, 10)
            + _fmt_float(ta_val, 10)
            + _fmt_float(gen.x0_pu or 0.0, 10)
            + _fmt_float(gen.x2_pu or 0.0, 10)
        )
        cards.append(g5)

    return cards


def write_dyna(system: System, filepath: str | Path) -> None:
    """Write a System to a CPAT .dyna file (convenience function).

    Args:
        system: System object to export
        filepath: Output file path

    Example:
        >>> from psforge_grid.io.dyna_writer import write_dyna
        >>> write_dyna(system, "output.dyna")
    """
    writer = DynaWriter()
    writer.write(system, filepath)
