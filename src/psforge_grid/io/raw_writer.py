"""Writer for PSS/E RAW format files.

This module provides functionality to export System objects to PSS/E RAW
format (v33). Symmetric counterpart of RawParser.

The PSS/E RAW format consists of:
    - 3-line case identification header
    - Data sections (Bus, Load, Shunt, Generator, Branch) separated by
      "0 /" terminators
    - Final "Q" terminator

Example:
    >>> from psforge_grid.io.raw_writer import write_raw
    >>> write_raw(system, tmp_path / "output.raw")
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

from psforge_grid.io.numbering import bus_number_map
from psforge_grid.io.protocols import IWriter

if TYPE_CHECKING:
    from psforge_grid.models.system import System


class RawWriter(IWriter):
    """Writer for PSS/E RAW format (v33).

    Exports a System object to PSS/E RAW format. Performs the inverse
    of RawParser: converts per-unit values back to physical units and
    radians back to degrees.

    RAW identifies buses by integer number, so buses are written with
    :func:`~psforge_grid.io.numbering.bus_number_map`: source-provided
    ``Bus.number`` values are kept, and buses without one get the lowest
    unused positive integers in list order. The unified string ``id`` is
    not written (RAW has no field for it); round-trip identity relies on
    ``number``, ``circuit_id``, ``machine_id``, ``load_id`` and
    ``shunt_id`` instead.

    See Also:
        - RawParser: The symmetric read implementation
        - WriterFactory: Factory for creating writer instances
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return ["raw", "RAW"]

    @property
    def format_name(self) -> str:
        """Return human-readable format name."""
        return "PSS/E RAW"

    def write(self, system: System, filepath: str | Path) -> None:
        """Write a System to a PSS/E RAW file (v33 format).

        Args:
            system: System object to export
            filepath: Output file path
        """
        lines: list[str] = []
        base_mva = system.base_mva

        # RAW needs integer bus numbers; keep source numbers, assign the rest
        num_map = bus_number_map(system)

        # Case identification (3 lines)
        lines.append(f" 0, {base_mva:.1f},  33, 0, 0, 60.00 / PSS/E-33.0")
        name = system.name if system.name else "psforge export"
        lines.append(name)
        lines.append("")

        # Bus data
        for bus in system.buses:
            v_angle_deg = math.degrees(bus.v_angle)
            name_field = f"'{bus.name}'" if bus.name else "''"
            lines.append(
                f" {num_map[bus.id]},{name_field},{bus.base_kv:.1f},"
                f"{bus.bus_type},{bus.area},{bus.zone},1,"
                f"{bus.v_magnitude:.6f},{v_angle_deg:.6f},"
                f"{bus.v_max:.4f},{bus.v_min:.4f}"
            )
        lines.append("0 / END OF BUS DATA, BEGIN LOAD DATA")

        # Load data
        for load in system.loads:
            p_mw = load.p_load * base_mva
            q_mvar = load.q_load * base_mva
            load_id = f"'{load.load_id or '1'}'"
            lines.append(
                f" {num_map[load.bus_id]},{load_id},{load.status},1,1,"
                f"{p_mw:.6f},{q_mvar:.6f},"
                f"0.0,0.0,0.0,0.0,1,1,0"
            )
        lines.append("0 / END OF LOAD DATA, BEGIN FIXED SHUNT DATA")

        # Fixed shunt data
        for shunt in system.shunts:
            g_mw = shunt.g_pu * base_mva
            b_mvar = shunt.b_pu * base_mva
            shunt_id = f"'{shunt.shunt_id or '1'}'"
            lines.append(
                f" {num_map[shunt.bus_id]},{shunt_id},{shunt.status},{g_mw:.6f},{b_mvar:.6f}"
            )
        lines.append("0 / END OF FIXED SHUNT DATA, BEGIN GENERATOR DATA")

        # Generator data
        for gen in system.generators:
            p_mw = gen.p_gen * base_mva
            q_mvar = gen.q_gen * base_mva
            q_max_mvar = (gen.q_max * base_mva) if gen.q_max is not None else 9999.0
            q_min_mvar = (gen.q_min * base_mva) if gen.q_min is not None else -9999.0
            p_max_mw = (gen.p_max * base_mva) if gen.p_max is not None else 9999.0
            p_min_mw = (gen.p_min * base_mva) if gen.p_min is not None else 0.0
            machine_id = f"'{gen.machine_id or '1'}'"
            lines.append(
                f" {num_map[gen.bus_id]},{machine_id},{p_mw:.6f},{q_mvar:.6f},"
                f"{q_max_mvar:.6f},{q_min_mvar:.6f},"
                f"{gen.v_setpoint:.6f},0,{gen.mbase:.1f},"
                f"0.0,1.0,0.0,0.0,1.0,{gen.status},"
                f"{p_max_mw:.6f},{p_min_mw:.6f}"
            )
        lines.append("0 / END OF GENERATOR DATA, BEGIN BRANCH DATA")

        # Branch data (non-transformer lines only)
        # Transformer data (separate section in v33)
        non_transformer_branches = []
        transformer_branches = []
        for br in system.branches:
            if br.is_transformer:
                transformer_branches.append(br)
            else:
                non_transformer_branches.append(br)

        for br in non_transformer_branches:
            rate_a = br.rate_a if br.rate_a is not None else 0.0
            rate_b = br.rate_b if br.rate_b is not None else 0.0
            rate_c = br.rate_c if br.rate_c is not None else 0.0
            ckt = f"'{br.circuit_id or '1'}'"
            lines.append(
                f" {num_map[br.from_bus_id]},{num_map[br.to_bus_id]},{ckt},"
                f"{br.r_pu:.6f},{br.x_pu:.6f},{br.b_pu:.6f},"
                f"{rate_a:.2f},{rate_b:.2f},{rate_c:.2f},"
                f"0.0,0.0,0.0,0.0,{br.status},0,0.0"
            )
        lines.append("0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA")

        # Transformer data
        for br in transformer_branches:
            rate_a = br.rate_a if br.rate_a is not None else 0.0
            shift_deg = math.degrees(br.shift_angle)
            ckt = f"'{br.circuit_id or '1'}'"
            # Line 1: header
            lines.append(
                f" {num_map[br.from_bus_id]},{num_map[br.to_bus_id]},0,{ckt},1,1,1,"
                f"0.0,0.0,2,'',{br.status},1,1.0,0,1.0,0,0.0,0.0"
            )
            # Line 2: impedance
            lines.append(f" {br.r_pu:.6f},{br.x_pu:.6f},{base_mva:.1f}")
            # Line 3: winding 1
            lines.append(
                f" {br.tap_ratio:.6f},0.0,{shift_deg:.6f},"
                f"{rate_a:.2f},0.00,0.00,"
                f"0,0,1.1,0.9,1.1,0.9,0,0,0.0"
            )
            # Line 4: winding 2
            lines.append(" 1.000000,0.0")
        lines.append("0 / END OF TRANSFORMER DATA")
        lines.append("Q")

        path = Path(filepath)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_raw(system: System, filepath: str | Path) -> None:
    """Write a System to a PSS/E RAW file (convenience function).

    Args:
        system: System object to export
        filepath: Output file path

    Example:
        >>> from psforge_grid.io.raw_writer import write_raw
        >>> write_raw(system, tmp_path / "output.raw")
        >>> (tmp_path / "output.raw").exists()
        True
    """
    writer = RawWriter()
    writer.write(system, filepath)
