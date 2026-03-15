"""Writer for MATPOWER .m format files.

This module provides functionality to export System objects to MATPOWER
format (.m files). Symmetric counterpart of MatpowerParser.

The MATPOWER format consists of a MATLAB function returning an mpc struct
with baseMVA, bus, gen, branch, and optionally gencost matrices.

Example:
    >>> from psforge_grid.io.matpower_writer import write_matpower
    >>> write_matpower(system, "output.m")
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

from psforge_grid.io.protocols import IWriter

if TYPE_CHECKING:
    from psforge_grid.models.system import System


class MatpowerWriter(IWriter):
    """Writer for MATPOWER format (.m files).

    Exports a System object to MATPOWER format. Performs the inverse
    of MatpowerParser: converts per-unit power values back to MW/MVAr
    and radians back to degrees.

    Note:
        - Loads and shunts from the bus data are embedded in the bus matrix
          (MATPOWER convention), not in separate sections
        - Generator costs are written to the gencost section if present
        - Fields not supported by MATPOWER (e.g., zero-sequence data) are
          silently ignored

    See Also:
        - MatpowerParser: The symmetric read implementation
        - WriterFactory: Factory for creating writer instances
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return ["m"]

    @property
    def format_name(self) -> str:
        """Return human-readable format name."""
        return "MATPOWER"

    def write(self, system: System, filepath: str | Path) -> None:
        """Write a System to a MATPOWER .m file.

        Args:
            system: System object to export
            filepath: Output file path
        """
        path = Path(filepath)
        case_name = path.stem
        base_mva = system.base_mva

        lines: list[str] = []
        lines.append(f"function mpc = {case_name}")
        lines.append("")
        lines.append("%% MATPOWER Case Format : Version 2")
        lines.append("mpc.version = '2';")
        lines.append("")
        lines.append("%%-----  Power Flow Data  -----%%")
        lines.append("%% system MVA base")
        lines.append(f"mpc.baseMVA = {base_mva};")
        lines.append("")

        # Aggregate loads and shunts per bus for MATPOWER bus matrix
        bus_loads: dict[int, tuple[float, float]] = {}
        for load in system.loads:
            if load.status == 1:
                key = load.bus_id
                p, q = bus_loads.get(key, (0.0, 0.0))
                bus_loads[key] = (p + load.p_load * base_mva, q + load.q_load * base_mva)

        bus_shunts: dict[int, tuple[float, float]] = {}
        for shunt in system.shunts:
            if shunt.status == 1:
                key = shunt.bus_id
                g, b = bus_shunts.get(key, (0.0, 0.0))
                bus_shunts[key] = (g + shunt.g_pu * base_mva, b + shunt.b_pu * base_mva)

        # Bus data
        lines.append("%% bus data")
        lines.append("%\tbus_i\ttype\tPd\tQd\tGs\tBs\tarea\tVm\tVa\tbaseKV\tzone\tVmax\tVmin")
        lines.append("mpc.bus = [")
        for bus in system.buses:
            pd, qd = bus_loads.get(bus.bus_id, (0.0, 0.0))
            gs, bs = bus_shunts.get(bus.bus_id, (0.0, 0.0))
            va_deg = math.degrees(bus.v_angle)
            lines.append(
                f"\t{bus.bus_id}\t{bus.bus_type}\t{pd:.6f}\t{qd:.6f}\t"
                f"{gs:.6f}\t{bs:.6f}\t{bus.area}\t{bus.v_magnitude:.6f}\t"
                f"{va_deg:.6f}\t{bus.base_kv:.1f}\t{bus.zone}\t"
                f"{bus.v_max:.4f}\t{bus.v_min:.4f};"
            )
        lines.append("];")
        lines.append("")

        # Generator data
        lines.append("%% generator data")
        lines.append("%\tbus\tPg\tQg\tQmax\tQmin\tVg\tmBase\tstatus\tPmax\tPmin")
        lines.append("mpc.gen = [")
        for gen in system.generators:
            pg = gen.p_gen * base_mva
            qg = gen.q_gen * base_mva
            qmax = (gen.q_max * base_mva) if gen.q_max is not None else 9999.0
            qmin = (gen.q_min * base_mva) if gen.q_min is not None else -9999.0
            pmax = (gen.p_max * base_mva) if gen.p_max is not None else 9999.0
            pmin = (gen.p_min * base_mva) if gen.p_min is not None else 0.0
            lines.append(
                f"\t{gen.bus_id}\t{pg:.6f}\t{qg:.6f}\t{qmax:.6f}\t{qmin:.6f}\t"
                f"{gen.v_setpoint:.6f}\t{gen.mbase:.1f}\t{gen.status}\t"
                f"{pmax:.6f}\t{pmin:.6f};"
            )
        lines.append("];")
        lines.append("")

        # Branch data
        lines.append("%% branch data")
        lines.append(
            "%\tfbus\ttbus\tr\tx\tb\trateA\trateB\trateC\tratio\tangle\tstatus\tangmin\tangmax"
        )
        lines.append("mpc.branch = [")
        for br in system.branches:
            rate_a = br.rate_a if br.rate_a is not None else 0.0
            rate_b = br.rate_b if br.rate_b is not None else 0.0
            rate_c = br.rate_c if br.rate_c is not None else 0.0
            # MATPOWER convention: ratio=0 means transmission line (no transformer)
            ratio = br.tap_ratio if br.is_transformer else 0.0
            angle_deg = math.degrees(br.shift_angle)
            angmin_deg = math.degrees(br.angmin) if br.angmin is not None else -360.0
            angmax_deg = math.degrees(br.angmax) if br.angmax is not None else 360.0
            lines.append(
                f"\t{br.from_bus}\t{br.to_bus}\t{br.r_pu:.6f}\t{br.x_pu:.6f}\t"
                f"{br.b_pu:.6f}\t{rate_a:.2f}\t{rate_b:.2f}\t{rate_c:.2f}\t"
                f"{ratio:.6f}\t{angle_deg:.6f}\t{br.status}\t"
                f"{angmin_deg:.6f}\t{angmax_deg:.6f};"
            )
        lines.append("];")

        # Generator cost data (if present)
        if system.generator_costs:
            lines.append("")
            lines.append("%%-----  OPF Data  -----%%")
            lines.append("%% generator cost data")
            lines.append("%\tmodel\tstartup\tshutdown\tncost\tcost...")
            lines.append("mpc.gencost = [")
            for gc in system.generator_costs:
                ncost = gc.n_coefficients
                cost_str = "\t".join(f"{c:.6f}" for c in gc.coefficients)
                lines.append(
                    f"\t{gc.model}\t{gc.startup:.6f}\t{gc.shutdown:.6f}\t{ncost}\t{cost_str};"
                )
            lines.append("];")

        lines.append("")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_matpower(system: System, filepath: str | Path) -> None:
    """Write a System to a MATPOWER .m file (convenience function).

    Args:
        system: System object to export
        filepath: Output file path

    Example:
        >>> from psforge_grid.io.matpower_writer import write_matpower
        >>> write_matpower(system, "output.m")
    """
    writer = MatpowerWriter()
    writer.write(system, filepath)
