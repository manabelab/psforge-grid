"""Writer for OpenDSS script format files (.dss).

This module provides functionality to export System objects to OpenDSS
script format. Uses physical units (kV, kW, kvar, ohm) as required by
OpenDSS, converting from psforge-grid's per-unit system.

Unit conversion from per-unit to physical:
    Z [ohm] = Z_pu * V_base^2 / S_base
    P [kW]  = P_pu * S_base * 1000
    Q [kvar] = Q_pu * S_base * 1000
    V [kV]  = V_pu * V_base

Example:
    >>> from psforge_grid.io.dss_writer import write_dss
    >>> write_dss(system, "output.dss")
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

from psforge_grid.io.protocols import IWriter

if TYPE_CHECKING:
    from psforge_grid.models.branch import Branch
    from psforge_grid.models.system import System


class DSSWriter(IWriter):
    """Writer for OpenDSS script format (.dss).

    Converts psforge-grid System objects to OpenDSS-compatible scripts.
    Handles per-unit to physical unit conversion and positive-sequence
    to three-phase balanced model transformation.

    See Also:
        - DSSParser: Reads .dss files back to System objects
        - WriterFactory.create("dss"): Factory creation
        - System.to_dss(): Facade method
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Supported file extensions for OpenDSS format."""
        return ["dss", "DSS"]

    @property
    def format_name(self) -> str:
        """Human-readable format name."""
        return "OpenDSS Script"

    def write(self, system: System, filepath: str | Path) -> None:
        """Write System to an OpenDSS .dss file.

        Args:
            system: Power system data to export
            filepath: Output file path
        """
        content = self.to_string(system)
        Path(filepath).write_text(content, encoding="utf-8")

    def to_string(self, system: System) -> str:
        """Convert System to OpenDSS script string.

        Args:
            system: Power system data to export

        Returns:
            OpenDSS script as a string
        """
        lines: list[str] = []
        base_mva = system.base_mva
        freq = system.frequency_hz if system.frequency_hz is not None else 60.0

        # Build bus_id -> base_kv lookup
        bus_kv = {bus.bus_id: bus.base_kv for bus in system.buses}

        # Pre-compute consistent bus_id -> OpenDSS name mapping
        bus_id_to_name: dict[int, str] = {}
        for bus in system.buses:
            if bus.name:
                bus_id_to_name[bus.bus_id] = self._sanitize_name(bus.name)
            else:
                bus_id_to_name[bus.bus_id] = f"Bus{bus.bus_id}"

        # Find swing bus for Circuit definition
        swing_buses = [b for b in system.buses if b.bus_type == 3]
        if not swing_buses:
            swing_bus = system.buses[0] if system.buses else None
        else:
            swing_bus = swing_buses[0]

        # --- Circuit definition ---
        if swing_bus is not None:
            swing_kv = swing_bus.base_kv
            swing_pu = swing_bus.v_magnitude
            swing_name = bus_id_to_name.get(swing_bus.bus_id, f"Bus{swing_bus.bus_id}")
            sys_name = self._sanitize_name(system.name or "System")

            lines.append("! psforge-grid OpenDSS export")
            lines.append(f"! Base MVA: {base_mva}")
            lines.append("Clear")
            lines.append("")
            lines.append(
                f"New Circuit.{sys_name} "
                f"basekv={swing_kv:.4f} pu={swing_pu:.6f} "
                f"phases=3 bus1={swing_name} "
                f"basefreq={freq:.1f}"
            )
            lines.append(f"Set DefaultBaseFreq={freq:.1f}")
            lines.append("")

        # --- Lines (transmission lines, non-transformer branches) ---
        tx_lines = [b for b in system.branches if not b.is_transformer and b.status == 1]
        if tx_lines:
            lines.append("! === Transmission Lines ===")
            for br in tx_lines:
                lines.append(self._branch_to_line(br, bus_id_to_name, bus_kv, base_mva))
            lines.append("")

        # --- Transformers ---
        xfmrs = [b for b in system.branches if b.is_transformer and b.status == 1]
        if xfmrs:
            lines.append("! === Transformers ===")
            for br in xfmrs:
                lines.extend(self._branch_to_transformer(br, bus_id_to_name, bus_kv, base_mva))
            lines.append("")

        # --- Generators (non-swing) ---
        non_swing_gens = [
            g
            for g in system.generators
            if g.status == 1 and (swing_bus is None or g.bus_id != swing_bus.bus_id)
        ]
        if non_swing_gens:
            lines.append("! === Generators ===")
            for gen in non_swing_gens:
                gen_kv = gen.kv if gen.kv is not None else bus_kv.get(gen.bus_id, 1.0)
                gen_conn = gen.connection or "wye"
                gen_model = gen.model_type if gen.model_type is not None else 3
                p_kw = gen.p_gen * base_mva * 1000.0
                q_kvar = gen.q_gen * base_mva * 1000.0
                gen_name = self._sanitize_name(gen.name or f"G{gen.gen_id}_Bus{gen.bus_id}")
                bus_name = bus_id_to_name.get(gen.bus_id, f"Bus{gen.bus_id}")

                line = (
                    f"New Generator.{gen_name} "
                    f"bus1={bus_name} phases=3 "
                    f"kv={gen_kv:.4f} kw={p_kw:.2f} kvar={q_kvar:.2f} "
                    f"model={gen_model} conn={gen_conn}"
                )
                lines.append(line)
            lines.append("")

        # --- Loads ---
        active_loads = [lo for lo in system.loads if lo.status == 1]
        if active_loads:
            lines.append("! === Loads ===")
            for lo in active_loads:
                lo_kv = lo.kv if lo.kv is not None else bus_kv.get(lo.bus_id, 1.0)
                lo_conn = lo.connection or "wye"
                lo_model = lo.model_type if lo.model_type is not None else 1
                p_kw = lo.p_load * base_mva * 1000.0
                q_kvar = lo.q_load * base_mva * 1000.0
                lo_name = self._sanitize_name(lo.name or f"L{lo.load_id}_Bus{lo.bus_id}")
                bus_name = bus_id_to_name.get(lo.bus_id, f"Bus{lo.bus_id}")

                line = (
                    f"New Load.{lo_name} "
                    f"bus1={bus_name} phases=3 "
                    f"kv={lo_kv:.4f} kw={p_kw:.2f} kvar={q_kvar:.2f} "
                    f"model={lo_model} conn={lo_conn}"
                )
                lines.append(line)
            lines.append("")

        # --- Shunts ---
        active_shunts = [s for s in system.shunts if s.status == 1]
        if active_shunts:
            lines.append("! === Shunts ===")
            for sh in active_shunts:
                sh_kv = sh.kv if sh.kv is not None else bus_kv.get(sh.bus_id, 1.0)
                sh_conn = sh.connection or "wye"
                bus_name = bus_id_to_name.get(sh.bus_id, f"Bus{sh.bus_id}")

                # Convert susceptance from p.u. to kvar at rated voltage
                # Q_kvar = B_pu * S_base * 1000
                q_kvar = sh.b_pu * base_mva * 1000.0
                sh_name = self._sanitize_name(sh.name or f"Sh{sh.shunt_id}_Bus{sh.bus_id}")

                if sh.b_pu > 0:
                    # Capacitor
                    line = (
                        f"New Capacitor.{sh_name} "
                        f"bus1={bus_name} phases=3 "
                        f"kv={sh_kv:.4f} kvar={q_kvar:.2f} "
                        f"conn={sh_conn}"
                    )
                elif sh.b_pu < 0:
                    # Reactor (kvar is positive for reactor rating)
                    line = (
                        f"New Reactor.{sh_name} "
                        f"bus1={bus_name} phases=3 "
                        f"kv={sh_kv:.4f} kvar={abs(q_kvar):.2f} "
                        f"conn={sh_conn}"
                    )
                else:
                    continue
                lines.append(line)
            lines.append("")

        # --- Bus voltage bases ---
        unique_kvs = sorted({bus.base_kv for bus in system.buses})
        kv_str = str(unique_kvs).replace("'", "")
        lines.append(f"Set VoltageBases={kv_str}")
        lines.append("CalcVoltageBases")
        lines.append("")

        return "\n".join(lines) + "\n"

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use as an OpenDSS identifier.

        Removes or replaces characters that are invalid in OpenDSS names.
        """
        import re

        # Replace spaces, dots, hyphens with underscores
        sanitized = re.sub(r"[\s.\-/\\]+", "_", name)
        # Remove any remaining non-alphanumeric characters (except underscores)
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "", sanitized)
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = f"N{sanitized}"
        return sanitized or "unnamed"

    def _branch_to_line(
        self,
        br: Branch,
        bus_id_to_name: dict[int, str],
        bus_kv: dict[int, float],
        base_mva: float,
    ) -> str:
        """Convert a transmission line Branch to OpenDSS Line element."""
        from_kv = bus_kv.get(br.from_bus, 1.0)
        z_base = from_kv**2 / base_mva  # ohm

        r_ohm = br.r_pu * z_base
        x_ohm = br.x_pu * z_base

        # B in per-unit to microsiemens: B_uS = B_pu / z_base * 1e6
        # But OpenDSS Line uses C (nanofarads) or B (microsiemens per unit length)
        # For simplicity, use LineCode or direct R1/X1/C1 with length=1
        b_us = br.b_pu / z_base * 1e6 if z_base > 0 else 0.0

        br_name = self._sanitize_name(br.name or f"Br{br.from_bus}_{br.to_bus}_{br.circuit_id}")
        from_name = bus_id_to_name.get(br.from_bus, f"Bus{br.from_bus}")
        to_name = bus_id_to_name.get(br.to_bus, f"Bus{br.to_bus}")

        line = (
            f"New Line.{br_name} "
            f"bus1={from_name} bus2={to_name} phases=3 "
            f"r1={r_ohm:.6f} x1={x_ohm:.6f} b1={b_us:.6f} "
            f"length=1 units=none"
        )

        # Add ratings if available
        if br.rate_a is not None:
            # OpenDSS normamps = MVA / (sqrt(3) * kV) * 1000
            normamps = br.rate_a / (math.sqrt(3) * from_kv) * 1000.0
            line += f" normamps={normamps:.2f}"

        return line

    def _branch_to_transformer(
        self,
        br: Branch,
        bus_id_to_name: dict[int, str],
        bus_kv: dict[int, float],
        base_mva: float,
    ) -> list[str]:
        """Convert a transformer Branch to OpenDSS Transformer element."""
        lines: list[str] = []

        # Winding voltages
        kv_from = br.nomv_from if br.nomv_from is not None else bus_kv.get(br.from_bus, 1.0)
        kv_to = br.nomv_to if br.nomv_to is not None else bus_kv.get(br.to_bus, 1.0)

        # Rated capacity
        rated_mva = br.sbase_mva if br.sbase_mva is not None else base_mva
        rated_kva = rated_mva * 1000.0

        # Winding connection
        if br.winding_connection is not None:
            conn = br.winding_connection
        elif abs(br.shift_angle) > 0.1:
            conn = "delta-wye" if br.shift_angle > 0 else "wye-delta"
        else:
            conn = "wye-wye"

        conn_parts = conn.split("-")
        conn_from = conn_parts[0] if len(conn_parts) > 0 else "wye"
        conn_to = conn_parts[1] if len(conn_parts) > 1 else "wye"

        # Impedance: convert from system p.u. to transformer-base percent
        # %Z = Z_pu * (rated_mva / base_mva) * 100
        xhl = br.x_pu * (rated_mva / base_mva) * 100.0
        pct_r = br.r_pu * (rated_mva / base_mva) * 100.0

        br_name = self._sanitize_name(br.name or f"Xfmr{br.from_bus}_{br.to_bus}_{br.circuit_id}")
        from_name = bus_id_to_name.get(br.from_bus, f"Bus{br.from_bus}")
        to_name = bus_id_to_name.get(br.to_bus, f"Bus{br.to_bus}")

        lines.append(
            f"New Transformer.{br_name} "
            f"phases=3 windings=2 "
            f"buses=({from_name}, {to_name}) "
            f'conns="{conn_from} {conn_to}" '
            f'kvs="{kv_from:.4f} {kv_to:.4f}" '
            f'kvas="{rated_kva:.2f} {rated_kva:.2f}" '
            f"XHL={xhl:.6f} %R={pct_r:.6f}"
        )

        # Tap setting
        if br.tap_ratio != 1.0:
            lines.append(f"~ Taps=({br.tap_ratio:.6f}, 1.0)")

        return lines


def write_dss(system: System, filepath: str | Path) -> None:
    """Write System to an OpenDSS .dss file.

    Convenience function that creates a DSSWriter and writes.

    Args:
        system: Power system data to export
        filepath: Output file path

    Example:
        >>> from psforge_grid.io.dss_writer import write_dss
        >>> write_dss(system, "output.dss")
    """
    DSSWriter().write(system, filepath)
