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
    from psforge_grid.models.generator import Generator
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
                f"basefreq={freq:.1f} "
                f"Mvasc3=1e10 Mvasc1=1e10"
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
                gen_model = gen.model_type if gen.model_type is not None else 1
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

    @staticmethod
    def _normalize_conn(conn: str) -> str:
        """Normalize winding connection string to OpenDSS format.

        OpenDSS only accepts "wye" or "delta" for transformer connections.
        Maps variants like "wye-grounded", "wye grounded", "Yg" to "wye".
        """
        c = conn.strip().lower()
        if "delta" in c or c.startswith("d"):
            return "delta"
        return "wye"

    def _branch_name(self, br: Branch) -> str:
        """Generate a unique OpenDSS element name for a branch.

        Always includes circuit_id suffix to avoid duplicate names
        when parallel circuits share the same branch name.
        """
        base = br.name or f"Br{br.from_bus}_{br.to_bus}"
        return self._sanitize_name(f"{base}_{br.circuit_id}")

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

        br_name = self._branch_name(br)
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

        # Winding connection — normalize to OpenDSS format ("wye" or "delta")
        if br.winding_connection is not None:
            conn = br.winding_connection
        elif abs(br.shift_angle) > 0.1:
            conn = "delta-wye" if br.shift_angle > 0 else "wye-delta"
        else:
            conn = "wye-wye"

        # Handle formats like "wye-grounded/wye-grounded", "delta/wye", etc.
        conn_parts = conn.split("/") if "/" in conn else conn.split("-", 1)
        conn_from = self._normalize_conn(conn_parts[0] if len(conn_parts) > 0 else "wye")
        conn_to = self._normalize_conn(conn_parts[1] if len(conn_parts) > 1 else "wye")

        # Impedance: convert from system p.u. to transformer-base percent
        # %Z = Z_pu * (rated_mva / base_mva) * 100
        xhl = br.x_pu * (rated_mva / base_mva) * 100.0
        pct_r = br.r_pu * (rated_mva / base_mva) * 100.0

        br_name = self._branch_name(br)
        from_name = bus_id_to_name.get(br.from_bus, f"Bus{br.from_bus}")
        to_name = bus_id_to_name.get(br.to_bus, f"Bus{br.to_bus}")

        lines.append(
            f"New Transformer.{br_name} "
            f"phases=3 windings=2 "
            f"buses=({from_name}, {to_name}) "
            f'conns="{conn_from} {conn_to}" '
            f'kvs="{kv_from:.4f} {kv_to:.4f}" '
            f'kvas="{rated_kva:.2f} {rated_kva:.2f}" '
            f"XHL={xhl:.6f} %loadloss={pct_r:.6f} %noloadloss=0"
        )

        # Tap setting
        if br.tap_ratio != 1.0:
            lines.append(f"~ Taps=({br.tap_ratio:.6f}, 1.0)")

        return lines

    def to_fault_study_string(
        self,
        system: System,
        *,
        gen_reactance: str = "xdp",
        gen_x0_fallback: str = "xd",
        zero_seq_line_factor: float = 2.0,
    ) -> str:
        """Convert System to OpenDSS script for fault study (T-method equivalent).

        Generates a DSS script optimized for short-circuit analysis:
        - Generators modeled as Vsource (voltage behind impedance)
        - Zero-sequence parameters (R0, X0, B0) included on lines
        - No loads (no-load voltage condition)
        - Transformers with proper winding connections for zero-sequence

        This mirrors CPAT's T-method setup:
        - Z1: gen_reactance (default Xd') for positive-sequence
        - Z2: X2 or Xd'' for negative-sequence
        - Z0: X0 with fallback for zero-sequence
        - Line Z0 = factor * Z1 when explicit Z0 data unavailable

        Args:
            system: Power system data to export
            gen_reactance: Generator reactance type for Z1.
                "xdp" (default, CPAT compatible): Xd' (transient)
                "xdpp": Xd'' (sub-transient)
                "xd": Xd (synchronous)
            gen_x0_fallback: Fallback when generator X0 is None.
                "xd" (default, CPAT compatible): use Xd as X0
                "xdp": use Xd', "xdpp": use Xd''
            zero_seq_line_factor: Z0/Z1 ratio for lines without Z0 data.
                Default 2.0 matches CPAT manual p.86 (Zo=2*Z1).

        Returns:
            OpenDSS script string for fault study
        """
        lines: list[str] = []
        base_mva = system.base_mva
        freq = system.frequency_hz if system.frequency_hz is not None else 60.0

        bus_kv = {bus.bus_id: bus.base_kv for bus in system.buses}
        bus_id_to_name: dict[int, str] = {}
        for bus in system.buses:
            if bus.name:
                bus_id_to_name[bus.bus_id] = self._sanitize_name(bus.name)
            else:
                bus_id_to_name[bus.bus_id] = f"Bus{bus.bus_id}"

        # Find swing bus
        swing_buses = [b for b in system.buses if b.bus_type == 3]
        swing_bus = swing_buses[0] if swing_buses else (system.buses[0] if system.buses else None)

        if swing_bus is None:
            return ""

        swing_name = bus_id_to_name.get(swing_bus.bus_id, f"Bus{swing_bus.bus_id}")
        swing_kv = swing_bus.base_kv
        sys_name = self._sanitize_name(system.name or "System")

        # Group generators by bus
        gen_by_bus: dict[int, list[Generator]] = {}
        for g in system.generators:
            if g.status == 1:
                gen_by_bus.setdefault(g.bus_id, []).append(g)

        # --- Circuit source (swing bus generator with impedance) ---
        swing_gens = gen_by_bus.get(swing_bus.bus_id, [])
        lines.append("! psforge-grid OpenDSS export (Fault Study mode)")
        lines.append(f"! Base MVA: {base_mva}")
        lines.append(f"! gen_reactance={gen_reactance}, gen_x0_fallback={gen_x0_fallback}")
        lines.append(f"! zero_seq_line_factor={zero_seq_line_factor}")
        lines.append("Clear")
        lines.append("")

        if swing_gens:
            gen = swing_gens[0]
            r1, x1, r0, x0, r2, x2 = self._gen_impedance_ohm(
                gen, swing_kv, gen_reactance, gen_x0_fallback
            )
            lines.append(
                f"New Circuit.{sys_name} "
                f"basekv={swing_kv:.4f} pu=1.0 "
                f"phases=3 bus1={swing_name} "
                f"basefreq={freq:.1f} "
                f"R1={r1:.6f} X1={x1:.6f} R0={r0:.6f} X0={x0:.6f}"
            )
            # Additional generators at swing bus
            for g in swing_gens[1:]:
                gname = self._sanitize_name(g.name or f"G{g.gen_id}_Bus{g.bus_id}")
                r1, x1, r0, x0, r2, x2 = self._gen_impedance_ohm(
                    g, swing_kv, gen_reactance, gen_x0_fallback
                )
                lines.append(
                    f"New Vsource.{gname} "
                    f"bus1={swing_name} basekv={swing_kv:.4f} pu=1.0 "
                    f"R1={r1:.6f} X1={x1:.6f} R0={r0:.6f} X0={x0:.6f}"
                )
        else:
            lines.append(
                f"New Circuit.{sys_name} "
                f"basekv={swing_kv:.4f} pu=1.0 "
                f"phases=3 bus1={swing_name} "
                f"basefreq={freq:.1f} "
                f"Mvasc3=1e10 Mvasc1=1e10"
            )
        lines.append(f"Set DefaultBaseFreq={freq:.1f}")
        lines.append("")

        # --- Non-swing generators as Vsource ---
        non_swing_gens = [
            g for g in system.generators if g.status == 1 and g.bus_id != swing_bus.bus_id
        ]
        if non_swing_gens:
            lines.append("! === Generators (Vsource for fault study) ===")
            for gen in non_swing_gens:
                gen_kv = gen.kv if gen.kv is not None else bus_kv.get(gen.bus_id, 1.0)
                gname = self._sanitize_name(gen.name or f"G{gen.gen_id}_Bus{gen.bus_id}")
                bus_name = bus_id_to_name.get(gen.bus_id, f"Bus{gen.bus_id}")
                r1, x1, r0, x0, r2, x2 = self._gen_impedance_ohm(
                    gen, gen_kv, gen_reactance, gen_x0_fallback
                )
                lines.append(
                    f"New Vsource.{gname} "
                    f"bus1={bus_name} basekv={gen_kv:.4f} pu=1.0 "
                    f"R1={r1:.6f} X1={x1:.6f} R0={r0:.6f} X0={x0:.6f}"
                )
            lines.append("")

        # --- Lines with zero-sequence parameters ---
        tx_lines = [b for b in system.branches if not b.is_transformer and b.status == 1]
        if tx_lines:
            lines.append("! === Transmission Lines ===")
            for br in tx_lines:
                lines.append(
                    self._branch_to_line_fault(
                        br, bus_id_to_name, bus_kv, base_mva, zero_seq_line_factor
                    )
                )
            lines.append("")

        # --- Transformers (Y-circuit model for Yg-Yg, standard for others) ---
        xfmrs = [b for b in system.branches if b.is_transformer and b.status == 1]
        # Track buses that need Yg-Delta grounding transformers
        # Key: bus_id, Value: list of (xhl_pct, rated_kva, kv)
        gnd_xfmr_data: dict[int, list[tuple[float, float, float]]] = {}
        if xfmrs:
            lines.append("! === Transformers ===")
            for br in xfmrs:
                if self._is_yg_yg(br):
                    lines.extend(
                        self._branch_to_ycircuit_fault(
                            br, bus_id_to_name, bus_kv, base_mva, gnd_xfmr_data
                        )
                    )
                else:
                    lines.extend(self._branch_to_transformer(br, bus_id_to_name, bus_kv, base_mva))
            lines.append("")

        # --- Yg-Delta grounding transformers ---
        if gnd_xfmr_data:
            lines.append("! === Grounding Transformers (Yg-Delta) ===")
            for bus_id, entries in gnd_xfmr_data.items():
                bus_name = bus_id_to_name.get(bus_id, f"Bus{bus_id}")
                kv = bus_kv.get(bus_id, 1.0)
                for idx, (xhl_pct, rated_kva, _kv) in enumerate(entries):
                    delta_bus = f"{bus_name}_gnd{idx}"
                    lines.append(
                        f"New Transformer.Gnd_{bus_name}_{idx} "
                        f"phases=3 windings=2 "
                        f"buses=({bus_name}, {delta_bus}) "
                        f'conns="wye delta" '
                        f'kvs="{kv:.4f} {kv:.4f}" '
                        f'kvas="{rated_kva:.2f} {rated_kva:.2f}" '
                        f"XHL={xhl_pct:.6f} %loadloss=0 %noloadloss=0"
                    )
            lines.append("")

        # --- No loads (fault study uses no-load condition) ---
        lines.append("! Loads omitted for no-load fault study condition")
        lines.append("")

        # --- Shunts (affect network impedance) ---
        active_shunts = [s for s in system.shunts if s.status == 1]
        if active_shunts:
            lines.append("! === Shunts ===")
            for sh in active_shunts:
                sh_kv = sh.kv if sh.kv is not None else bus_kv.get(sh.bus_id, 1.0)
                sh_conn = sh.connection or "wye"
                bus_name = bus_id_to_name.get(sh.bus_id, f"Bus{sh.bus_id}")
                q_kvar = sh.b_pu * base_mva * 1000.0
                sh_name = self._sanitize_name(sh.name or f"Sh{sh.shunt_id}_Bus{sh.bus_id}")
                if sh.b_pu > 0:
                    lines.append(
                        f"New Capacitor.{sh_name} "
                        f"bus1={bus_name} phases=3 "
                        f"kv={sh_kv:.4f} kvar={q_kvar:.2f} conn={sh_conn}"
                    )
                elif sh.b_pu < 0:
                    lines.append(
                        f"New Reactor.{sh_name} "
                        f"bus1={bus_name} phases=3 "
                        f"kv={sh_kv:.4f} kvar={abs(q_kvar):.2f} conn={sh_conn}"
                    )
            lines.append("")

        # --- Bus voltage bases ---
        unique_kvs = sorted({bus.base_kv for bus in system.buses})
        kv_str = str(unique_kvs).replace("'", "")
        lines.append(f"Set VoltageBases={kv_str}")
        lines.append("CalcVoltageBases")
        lines.append("")

        return "\n".join(lines) + "\n"

    def write_fault_study(
        self,
        system: System,
        filepath: str | Path,
        **kwargs: object,
    ) -> None:
        """Write System to an OpenDSS .dss file for fault study.

        Args:
            system: Power system data to export
            filepath: Output file path
            **kwargs: Passed to to_fault_study_string()
        """
        content = self.to_fault_study_string(system, **kwargs)  # type: ignore[arg-type]
        Path(filepath).write_text(content, encoding="utf-8")

    @staticmethod
    def _is_yg_yg(br: Branch) -> bool:
        """Check if a transformer has Yg-Yg (wye-grounded/wye-grounded) connection.

        Args:
            br: Transformer branch

        Returns:
            True if both windings are wye-grounded
        """
        conn = br.winding_connection
        if conn is None:
            return False
        # PopParser format: "wye-grounded/wye-grounded"
        if "/" in conn:
            parts = conn.split("/")
        else:
            return False
        return all("wye-grounded" in p.lower() for p in parts)

    def _branch_to_ycircuit_fault(
        self,
        br: Branch,
        bus_id_to_name: dict[int, str],
        bus_kv: dict[int, float],
        base_mva: float,
        gnd_xfmr_data: dict[int, list[tuple[float, float, float]]],
    ) -> list[str]:
        """Convert a Yg-Yg transformer to Y-circuit model for fault study.

        The Y-circuit model replaces a single Yg-Yg transformer with:
        1. A near-ideal transformer (XHL~0) connecting from_bus_m to to_bus
        2. A series reactor between from_bus and from_bus_m with the
           original transformer impedance
        3. Yg-Delta grounding transformers at each terminal bus (registered
           in gnd_xfmr_data for later generation)

        This decomposition correctly models zero-sequence current paths
        through Yg-Yg transformers, which standard OpenDSS 2-winding
        transformer models cannot represent accurately.

        Args:
            br: Transformer branch (must be Yg-Yg)
            bus_id_to_name: Bus ID to OpenDSS name mapping
            bus_kv: Bus ID to base kV mapping
            base_mva: System base MVA
            gnd_xfmr_data: Accumulator for grounding transformer data.
                Mutated to register buses needing Yg-Delta transformers.

        Returns:
            List of OpenDSS command strings
        """
        result_lines: list[str] = []

        kv_from = br.nomv_from if br.nomv_from is not None else bus_kv.get(br.from_bus, 1.0)
        kv_to = br.nomv_to if br.nomv_to is not None else bus_kv.get(br.to_bus, 1.0)
        rated_mva = br.sbase_mva if br.sbase_mva is not None else base_mva
        rated_kva = rated_mva * 1000.0

        # Impedance: convert from system p.u. to transformer-base percent
        xhl_pct = br.x_pu * (rated_mva / base_mva) * 100.0

        # Convert x_pu to ohms on from-bus base for the series reactor
        z_base = kv_from**2 / base_mva
        x_ohm = br.x_pu * z_base

        br_name = self._branch_name(br)
        from_name = bus_id_to_name.get(br.from_bus, f"Bus{br.from_bus}")
        to_name = bus_id_to_name.get(br.to_bus, f"Bus{br.to_bus}")
        from_mid = f"{from_name}_m"

        # 1a. Near-ideal transformer: from_mid → to_bus
        result_lines.append(
            f"New Transformer.{br_name} "
            f"phases=3 windings=2 "
            f"buses=({from_mid}, {to_name}) "
            f'conns="wye wye" '
            f'kvs="{kv_from:.4f} {kv_to:.4f}" '
            f'kvas="{rated_kva:.2f} {rated_kva:.2f}" '
            f"XHL=0.000100 %loadloss=0 %noloadloss=0"
        )

        # 1b. Series reactor: from_bus → from_mid (carries original impedance)
        result_lines.append(
            f"New Reactor.Rser_{br_name} "
            f"bus1={from_name} bus2={from_mid} phases=3 "
            f"Z1=[0, {x_ohm:.6f}] Z0=[0, 0.000001]"
        )

        # 2. Register grounding transformers at both terminal buses
        for bus_id in (br.from_bus, br.to_bus):
            kv = bus_kv.get(bus_id, 1.0)
            gnd_xfmr_data.setdefault(bus_id, []).append((xhl_pct, rated_kva, kv))

        return result_lines

    def _gen_impedance_ohm(
        self,
        gen: Generator,
        bus_kv: float,
        gen_reactance: str,
        gen_x0_fallback: str,
    ) -> tuple[float, float, float, float, float, float]:
        """Convert generator reactances to (R1, X1, R0, X0, R2, X2) in ohms.

        Uses machine base MVA for impedance conversion:
            Z_ohm = Z_pu_mbase * kV^2 / mbase

        Args:
            gen: Generator data
            bus_kv: Bus voltage [kV] for ohm conversion
            gen_reactance: Reactance type for Z1 ("xdp", "xdpp", "xd")
            gen_x0_fallback: Fallback for X0 ("xd", "xdp", "xdpp")

        Returns:
            (R1, X1, R0, X0, R2, X2) in ohms
        """
        z_base = bus_kv**2 / gen.mbase  # ohm per p.u. on machine base

        # Z1: positive-sequence (Xd' for CPAT)
        x1_pu = gen.get_fault_reactance(gen_reactance) or 0.01
        ra = gen.get_armature_resistance()
        r1_pu = ra if ra is not None else 0.0

        # Z0: zero-sequence (X0 with fallback)
        x0_pu = gen.x0_pu
        if x0_pu is None:
            x0_pu = gen.get_fault_reactance(gen_x0_fallback) or x1_pu
        r0_pu = 0.0

        # Z2: negative-sequence (X2, or Xd'' as approximation)
        x2_pu = gen.x2_pu
        if x2_pu is None:
            x2_pu = gen.xdpp_pu or x1_pu
        r2_pu = r1_pu

        return (
            r1_pu * z_base,
            x1_pu * z_base,
            r0_pu * z_base,
            x0_pu * z_base,
            r2_pu * z_base,
            x2_pu * z_base,
        )

    def _branch_to_line_fault(
        self,
        br: Branch,
        bus_id_to_name: dict[int, str],
        bus_kv: dict[int, float],
        base_mva: float,
        zero_seq_line_factor: float,
    ) -> str:
        """Convert a transmission line to OpenDSS Line with zero-sequence parameters.

        When explicit Z0 data (r0_pu, x0_pu) is available, uses it directly.
        Otherwise, estimates Z0 = factor * Z1 (CPAT default: factor=2.0).
        """
        from_kv = bus_kv.get(br.from_bus, 1.0)
        z_base = from_kv**2 / base_mva

        # Positive-sequence
        r1_ohm = br.r_pu * z_base
        x1_ohm = br.x_pu * z_base
        b1_us = br.b_pu / z_base * 1e6 if z_base > 0 else 0.0

        # Zero-sequence
        if br.has_zero_sequence_data:
            r0_ohm = (br.r0_pu or 0.0) * z_base
            x0_ohm = (br.x0_pu or 0.0) * z_base
            b0_us = (br.b0_pu or 0.0) / z_base * 1e6 if z_base > 0 else 0.0
        else:
            r0_ohm = r1_ohm * zero_seq_line_factor
            x0_ohm = x1_ohm * zero_seq_line_factor
            b0_us = b1_us / zero_seq_line_factor if zero_seq_line_factor != 0 else 0.0

        br_name = self._branch_name(br)
        from_name = bus_id_to_name.get(br.from_bus, f"Bus{br.from_bus}")
        to_name = bus_id_to_name.get(br.to_bus, f"Bus{br.to_bus}")

        line = (
            f"New Line.{br_name} "
            f"bus1={from_name} bus2={to_name} phases=3 "
            f"r1={r1_ohm:.6f} x1={x1_ohm:.6f} b1={b1_us:.6f} "
            f"r0={r0_ohm:.6f} x0={x0_ohm:.6f} b0={b0_us:.6f} "
            f"length=1 units=none"
        )

        if br.rate_a is not None:
            normamps = br.rate_a / (math.sqrt(3) * from_kv) * 1000.0
            line += f" normamps={normamps:.2f}"

        return line


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
