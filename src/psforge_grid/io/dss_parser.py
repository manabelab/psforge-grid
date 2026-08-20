"""Parser for OpenDSS script format files (.dss).

This module provides functionality to parse OpenDSS .dss files into System
objects using the opendssdirect.py API. Instead of text parsing, the .dss
file is compiled by the OpenDSS engine, and element data is extracted via API.

This approach handles all OpenDSS scripting features (variables, redirects,
master scripts) transparently.

Identifier generation:
    Unified ids are a type prefix plus the 1-based appearance order within
    that element type (matching the integer part of ``order``):

    - Bus: ``B{n}`` (appearance order after internal-bus filtering)
    - Branch: ``BR{n}`` (Lines first, then Transformers)
    - Generator: ``G{n}`` (the Vsource swing generator is first),
      Load: ``LD{n}``, Shunt: ``SH{n}`` (Capacitors first, then Reactors)

    Every candidate still passes through
    :func:`~psforge_grid.models.identity.make_unique` against a single
    ``used`` set shared by all element types, as a safety net.
    ``Bus.number`` stays ``None`` because OpenDSS does not provide bus
    numbers ("Optional + None = Source Not Provided"); the original DSS
    name is kept in ``name``.

Example:
    >>> from psforge_grid.io.dss_parser import parse_dss
    >>> system = parse_dss("network.dss")  # doctest: +SKIP
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING

import opendssdirect as dss

from psforge_grid.io.protocols import IParser
from psforge_grid.models.branch import Branch
from psforge_grid.models.bus import Bus
from psforge_grid.models.generator import Generator
from psforge_grid.models.identity import make_unique
from psforge_grid.models.load import Load
from psforge_grid.models.shunt import Shunt
from psforge_grid.models.system import System

if TYPE_CHECKING:
    from collections.abc import Sequence


def _assign_order(elements: Sequence[Bus | Branch | Generator | Load | Shunt]) -> None:
    """Assign sort order 1.0, 2.0, ... in appearance order (one element type)."""
    for seq, element in enumerate(elements, start=1):
        element.order = float(seq)


class DSSParser(IParser):
    """Parser for OpenDSS script format (.dss).

    Uses opendssdirect.py to compile .dss files and extract circuit
    element data via the OpenDSS API.

    See Also:
        - DSSWriter: Writes System objects to .dss files
        - ParserFactory.create("dss"): Factory creation
        - System.from_dss(): Facade method
    """

    @property
    def supported_extensions(self) -> list[str]:
        """Supported file extensions for OpenDSS format."""
        return ["dss", "DSS"]

    @property
    def format_name(self) -> str:
        """Human-readable format name."""
        return "OpenDSS Script"

    def parse(self, filepath: str | Path) -> System:
        """Parse an OpenDSS .dss file into a System object.

        Handles two OpenDSS-specific issues:
        1. Internal bus filtering: OpenDSS creates internal buses for
           transformer modeling. Only buses referenced by user-defined
           elements are included in the output.
        2. Swing bus generator recovery: The Circuit source (Vsource) is
           extracted as a swing generator, since OpenDSS does not include
           it in the Generators iterator.

        Args:
            filepath: Path to the .dss file

        Returns:
            System object containing parsed power system data

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file cannot be compiled by OpenDSS
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Reset OpenDSS and compile the file
        dss.Basic.ClearAll()
        result = dss.run_command(f'Compile "{filepath.resolve()}"')
        if result and "error" in result.lower():
            raise ValueError(f"OpenDSS compilation error: {result}")

        # Solve to initialize the circuit (snapshot mode)
        dss.run_command("Solve Mode=Snapshot")

        # Extract system info
        sys_name = dss.Circuit.Name()
        base_freq = dss.Solution.Frequency()

        # OpenDSS doesn't have a single "base MVA" concept like PSS/E
        base_mva = 100.0

        # Extract ALL buses (including OpenDSS internal buses) with
        # provisional ids; final ids are assigned after internal-bus
        # filtering so numbering reflects the final appearance order.
        all_buses = self._extract_buses()
        bus_name_to_id = {bus.name: bus.id for bus in all_buses if bus.name}
        bus_kv = {bus.id: bus.base_kv for bus in all_buses}

        # Extract elements
        branches = self._extract_lines(bus_name_to_id, bus_kv, base_mva)
        xfmr_branches = self._extract_transformers(bus_name_to_id, base_mva)
        branches.extend(xfmr_branches)

        generators = self._extract_generators(bus_name_to_id, base_mva)
        loads = self._extract_loads(bus_name_to_id, base_mva)
        shunts = self._extract_shunts(bus_name_to_id, base_mva)

        # Issue 2: Extract Circuit source (Vsource) as swing generator
        swing_gen, swing_bus_id = self._extract_vsource_generator(bus_name_to_id, base_mva)
        if swing_gen is not None:
            generators.insert(0, swing_gen)

        # Issue 1: Filter internal buses (keep only those referenced by elements)
        referenced_ids: set[str] = set()
        for br in branches:
            referenced_ids.add(br.from_bus_id)
            referenced_ids.add(br.to_bus_id)
        for g in generators:
            referenced_ids.add(g.bus_id)
        for lo in loads:
            referenced_ids.add(lo.bus_id)
        for sh in shunts:
            referenced_ids.add(sh.bus_id)

        buses = [b for b in all_buses if b.id in referenced_ids]

        # Set bus types: swing (3), PV (2), PQ (1)
        gen_bus_ids = {g.bus_id for g in generators}
        for bus in buses:
            if bus.id == swing_bus_id:
                bus.bus_type = 3
            elif bus.id in gen_bus_ids:
                bus.bus_type = 2
            else:
                bus.bus_type = 1

        # Assign final unified ids: type prefix + 1-based appearance order
        # within the type (B{n}, BR{n}, G{n}, LD{n}, SH{n}). One `used` set
        # per parse; make_unique is kept as a safety net.
        used: set[str] = set()

        def finalize(candidate: str) -> str:
            new_id = make_unique(candidate, used)
            used.add(new_id)
            return new_id

        bus_id_map: dict[str, str] = {}
        for n, bus in enumerate(buses, start=1):
            new_id = finalize(f"B{n}")
            bus_id_map[bus.id] = new_id
            bus.id = new_id
        for n, br in enumerate(branches, start=1):
            br.id = finalize(f"BR{n}")
            br.from_bus_id = bus_id_map[br.from_bus_id]
            br.to_bus_id = bus_id_map[br.to_bus_id]
        for n, g in enumerate(generators, start=1):
            g.id = finalize(f"G{n}")
            g.bus_id = bus_id_map[g.bus_id]
        for n, lo in enumerate(loads, start=1):
            lo.id = finalize(f"LD{n}")
            lo.bus_id = bus_id_map[lo.bus_id]
        for n, sh in enumerate(shunts, start=1):
            sh.id = finalize(f"SH{n}")
            sh.bus_id = bus_id_map[sh.bus_id]

        # Assign sort order per element type: 1.0, 2.0, ... in appearance order
        _assign_order(buses)
        _assign_order(branches)
        _assign_order(generators)
        _assign_order(loads)
        _assign_order(shunts)

        return System(
            buses=buses,
            branches=branches,
            generators=generators,
            loads=loads,
            shunts=shunts,
            base_mva=base_mva,
            frequency_hz=base_freq,
            name=sys_name,
        )

    def _extract_buses(self) -> list[Bus]:
        """Extract bus data from the compiled OpenDSS circuit.

        Buses receive provisional ids; the final ``B{n}`` ids are assigned
        in :meth:`parse` after internal-bus filtering. ``Bus.number`` is
        left ``None``: OpenDSS has no bus number concept, and inventing one
        from the iteration index would violate the "Optional + None =
        Source Not Provided" principle.
        """
        buses: list[Bus] = []
        bus_names = dss.Circuit.AllBusNames()

        for i, name in enumerate(bus_names, start=1):
            dss.Circuit.SetActiveBus(name)
            kv_base = dss.Bus.kVBase()
            # Voltage magnitude in per-unit (use phase A for balanced)
            v_mag_pu_list = dss.Bus.puVmagAngle()

            v_mag = 1.0
            v_ang = 0.0
            if len(v_mag_pu_list) >= 2:
                v_mag = v_mag_pu_list[0]
                v_ang = v_mag_pu_list[1] * math.pi / 180.0  # deg -> rad

            # Bus type: determine from connected elements later
            # Default to PQ (1), will be updated based on generators
            bus_type = 1

            buses.append(
                Bus(
                    f"TMPB{i}",  # provisional; finalized in parse()
                    bus_type=bus_type,
                    v_magnitude=v_mag,
                    v_angle=v_ang,
                    base_kv=kv_base * math.sqrt(3),  # OpenDSS kVBase is line-to-neutral
                    name=name,
                )
            )

        return buses

    def _get_bus_id(self, bus_name: str, bus_name_to_id: dict[str, str]) -> str | None:
        """Resolve OpenDSS bus name to unified Bus.id.

        OpenDSS bus names may include node suffixes like 'bus1.1.2.3'.
        Strip the node part to match.
        """
        # Strip node suffix (e.g., "bus1.1.2.3" -> "bus1")
        base_name = bus_name.split(".")[0].lower()
        for name, bid in bus_name_to_id.items():
            if name.lower() == base_name:
                return bid
        return None

    def _extract_lines(
        self,
        bus_name_to_id: dict[str, str],
        bus_kv: dict[str, float],
        base_mva: float,
    ) -> list[Branch]:
        """Extract Line elements as Branch objects (provisional ids)."""
        branches: list[Branch] = []

        flag = dss.Lines.First()
        while flag > 0:
            name = dss.Lines.Name()
            bus1 = dss.Lines.Bus1()
            bus2 = dss.Lines.Bus2()

            from_id = self._get_bus_id(bus1, bus_name_to_id)
            to_id = self._get_bus_id(bus2, bus_name_to_id)

            if from_id is not None and to_id is not None:
                r1_ohm = dss.Lines.R1()
                x1_ohm = dss.Lines.X1()
                c1_nf = dss.Lines.C1()  # nanofarads per unit length
                length = dss.Lines.Length()

                from_kv = bus_kv.get(from_id, 1.0)
                z_base = from_kv**2 / base_mva if base_mva > 0 else 1.0

                # Convert physical to per-unit
                r_pu = (r1_ohm * length) / z_base if z_base > 0 else 0.0
                x_pu = (x1_ohm * length) / z_base if z_base > 0 else 0.0
                # C1 is in nF/unit_length. B = 2*pi*f*C
                # But OpenDSS also stores B directly when set via b1 parameter
                # For lines set with b1 (microsiemens), C1 = b1 / (2*pi*f) * 1e3
                # Convert back: b_us = C1_nf * 2 * pi * f * length / 1e3
                freq = dss.Solution.Frequency()
                b_us = c1_nf * 2 * math.pi * freq * length / 1e3
                b_pu = b_us * z_base * 1e-6 if z_base > 0 else 0.0

                # Ratings
                normamps = dss.Lines.NormAmps()
                rate_a = None
                if normamps > 0 and from_kv > 0:
                    rate_a = normamps * math.sqrt(3) * from_kv / 1000.0

                branches.append(
                    Branch(
                        f"TMPLN{len(branches) + 1}",  # provisional; finalized in parse()
                        from_bus_id=from_id,
                        to_bus_id=to_id,
                        r_pu=r_pu,
                        x_pu=x_pu,
                        b_pu=b_pu,
                        rate_a=rate_a,
                        name=name,
                    )
                )

            flag = dss.Lines.Next()

        return branches

    def _extract_transformers(
        self,
        bus_name_to_id: dict[str, str],
        base_mva: float,
    ) -> list[Branch]:
        """Extract Transformer elements as Branch objects (provisional ids)."""
        branches: list[Branch] = []

        flag = dss.Transformers.First()
        while flag > 0:
            name = dss.Transformers.Name()
            num_windings = dss.Transformers.NumWindings()

            if num_windings >= 2:
                # Get winding 1 info
                dss.Transformers.Wdg(1)
                bus1 = dss.CktElement.BusNames()[0] if dss.CktElement.BusNames() else ""
                kv1 = dss.Transformers.kV()
                kva1 = dss.Transformers.kVA()
                tap1 = dss.Transformers.Tap()

                # Get winding 2 info
                dss.Transformers.Wdg(2)
                bus2 = dss.CktElement.BusNames()[1] if len(dss.CktElement.BusNames()) > 1 else ""
                kv2 = dss.Transformers.kV()
                tap2 = dss.Transformers.Tap()

                from_id = self._get_bus_id(bus1, bus_name_to_id)
                to_id = self._get_bus_id(bus2, bus_name_to_id)

                if from_id is not None and to_id is not None:
                    # XHL and %R
                    xhl = dss.Transformers.Xhl()
                    pct_r = dss.Transformers.R()  # %R for current winding

                    rated_mva = kva1 / 1000.0

                    # Convert from transformer-base percent to system-base p.u.
                    # Z_pu = %Z / 100 * (base_mva / rated_mva)
                    x_pu = (xhl / 100.0) * (base_mva / rated_mva) if rated_mva > 0 else 0.0
                    r_pu = (pct_r / 100.0) * (base_mva / rated_mva) if rated_mva > 0 else 0.0

                    # Tap ratio
                    tap_ratio = tap1 / tap2 if tap2 != 0 else tap1

                    # Connection types
                    # OpenDSS: IsDelta() for current winding
                    dss.Transformers.Wdg(1)
                    is_delta1 = dss.Transformers.IsDelta()
                    dss.Transformers.Wdg(2)
                    is_delta2 = dss.Transformers.IsDelta()

                    conn1 = "delta" if is_delta1 else "wye"
                    conn2 = "delta" if is_delta2 else "wye"
                    winding_connection = f"{conn1}-{conn2}"

                    # Shift angle from connection type
                    shift_angle = 0.0
                    if is_delta1 and not is_delta2:
                        shift_angle = math.pi / 6.0  # +30 degrees
                    elif not is_delta1 and is_delta2:
                        shift_angle = -math.pi / 6.0  # -30 degrees

                    branches.append(
                        Branch(
                            f"TMPXF{len(branches) + 1}",  # provisional; finalized in parse()
                            from_bus_id=from_id,
                            to_bus_id=to_id,
                            r_pu=r_pu,
                            x_pu=x_pu,
                            b_pu=0.0,
                            tap_ratio=tap_ratio,
                            shift_angle=shift_angle,
                            winding_connection=winding_connection,
                            nomv_from=kv1,
                            nomv_to=kv2,
                            sbase_mva=rated_mva,
                            name=name,
                        )
                    )

            flag = dss.Transformers.Next()

        return branches

    def _extract_generators(
        self, bus_name_to_id: dict[str, str], base_mva: float
    ) -> list[Generator]:
        """Extract Generator elements (provisional ids)."""
        generators: list[Generator] = []

        flag = dss.Generators.First()
        while flag > 0:
            name = dss.Generators.Name()

            # Get bus from CktElement
            bus_names = dss.CktElement.BusNames()
            bus1 = bus_names[0] if bus_names else ""
            bus_id = self._get_bus_id(bus1, bus_name_to_id)

            if bus_id is not None:
                kw = dss.Generators.kW()
                kvar = dss.Generators.kvar()
                kv = dss.Generators.kV()
                model = dss.Generators.Model()
                is_delta = dss.Generators.IsDelta()

                p_pu = kw / (base_mva * 1000.0) if base_mva > 0 else 0.0
                q_pu = kvar / (base_mva * 1000.0) if base_mva > 0 else 0.0

                generators.append(
                    Generator(
                        f"TMPG{len(generators) + 1}",  # provisional; finalized in parse()
                        bus_id=bus_id,
                        p_gen=p_pu,
                        q_gen=q_pu,
                        kv=kv,
                        connection="delta" if is_delta else "wye",
                        model_type=model,
                        name=name,
                    )
                )

            flag = dss.Generators.Next()

        return generators

    def _extract_loads(self, bus_name_to_id: dict[str, str], base_mva: float) -> list[Load]:
        """Extract Load elements (provisional ids)."""
        loads: list[Load] = []

        flag = dss.Loads.First()
        while flag > 0:
            name = dss.Loads.Name()

            bus_names = dss.CktElement.BusNames()
            bus1 = bus_names[0] if bus_names else ""
            bus_id = self._get_bus_id(bus1, bus_name_to_id)

            if bus_id is not None:
                kw = dss.Loads.kW()
                kvar = dss.Loads.kvar()
                kv = dss.Loads.kV()
                model = dss.Loads.Model()
                is_delta = dss.Loads.IsDelta()

                p_pu = kw / (base_mva * 1000.0) if base_mva > 0 else 0.0
                q_pu = kvar / (base_mva * 1000.0) if base_mva > 0 else 0.0

                loads.append(
                    Load(
                        f"TMPLD{len(loads) + 1}",  # provisional; finalized in parse()
                        bus_id=bus_id,
                        p_load=p_pu,
                        q_load=q_pu,
                        kv=kv,
                        connection="delta" if is_delta else "wye",
                        model_type=model,
                        name=name,
                    )
                )

            flag = dss.Loads.Next()

        return loads

    def _extract_shunts(self, bus_name_to_id: dict[str, str], base_mva: float) -> list[Shunt]:
        """Extract Capacitor and Reactor elements as Shunt objects (provisional ids)."""
        shunts: list[Shunt] = []

        # Capacitors
        flag = dss.Capacitors.First()
        while flag > 0:
            name = dss.Capacitors.Name()
            bus_names = dss.CktElement.BusNames()
            bus1 = bus_names[0] if bus_names else ""
            bus_id = self._get_bus_id(bus1, bus_name_to_id)

            if bus_id is not None:
                kvar = dss.Capacitors.kvar()
                kv = dss.Capacitors.kV()
                is_delta = dss.Capacitors.IsDelta()
                num_steps = dss.Capacitors.NumSteps()

                b_pu = kvar / (base_mva * 1000.0) if base_mva > 0 else 0.0

                shunts.append(
                    Shunt(
                        f"TMPSH{len(shunts) + 1}",  # provisional; finalized in parse()
                        bus_id=bus_id,
                        g_pu=0.0,
                        b_pu=b_pu,
                        kv=kv,
                        connection="delta" if is_delta else "wye",
                        num_steps=num_steps if num_steps > 1 else None,
                        name=name,
                    )
                )

            flag = dss.Capacitors.Next()

        # Reactors
        flag = dss.Reactors.First()
        while flag > 0:
            name = dss.Reactors.Name()
            bus_names = dss.CktElement.BusNames()
            bus1 = bus_names[0] if bus_names else ""
            bus_id = self._get_bus_id(bus1, bus_name_to_id)

            if bus_id is not None:
                kvar = dss.Reactors.kvar()
                kv = dss.Reactors.kV()
                is_delta = dss.Reactors.IsDelta()

                b_pu = -kvar / (base_mva * 1000.0) if base_mva > 0 else 0.0

                shunts.append(
                    Shunt(
                        f"TMPSH{len(shunts) + 1}",  # provisional; finalized in parse()
                        bus_id=bus_id,
                        g_pu=0.0,
                        b_pu=b_pu,
                        kv=kv,
                        connection="delta" if is_delta else "wye",
                        name=name,
                    )
                )

            flag = dss.Reactors.Next()

        return shunts

    def _extract_vsource_generator(
        self, bus_name_to_id: dict[str, str], base_mva: float
    ) -> tuple[Generator | None, str | None]:
        """Extract the Circuit source (Vsource) as a swing Generator.

        OpenDSS represents the Circuit source as a Vsource element, which
        is not included in the Generators iterator. This method recovers
        the swing bus generator from the first Vsource.

        Returns:
            Tuple of (Generator or None, swing Bus.id or None)
        """
        flag = dss.Vsources.First()
        if flag == 0:
            return None, None

        name = dss.Vsources.Name()
        bus_names = dss.CktElement.BusNames()
        bus1 = bus_names[0] if bus_names else ""
        bus_id = self._get_bus_id(bus1, bus_name_to_id)

        if bus_id is None:
            return None, None

        v_pu = dss.Vsources.PU()

        # Get solved power output from CktElement.Powers()
        # Returns [P1, Q1, P2, Q2, ...] per phase, power INTO the element.
        # For a source delivering power, negate to get generated power.
        powers = dss.CktElement.Powers()
        p_kw = 0.0
        q_kvar = 0.0
        if len(powers) >= 6:
            # 3-phase: sum phases 1-3 (indices 0,2,4 for P; 1,3,5 for Q)
            p_kw = -(powers[0] + powers[2] + powers[4])
            q_kvar = -(powers[1] + powers[3] + powers[5])

        p_pu = p_kw / (base_mva * 1000.0) if base_mva > 0 else 0.0
        q_pu = q_kvar / (base_mva * 1000.0) if base_mva > 0 else 0.0

        gen = Generator(
            "TMPVS1",  # provisional; finalized in parse()
            bus_id=bus_id,
            p_gen=p_pu,
            q_gen=q_pu,
            v_setpoint=v_pu,
            name=name,
        )
        return gen, bus_id


def parse_dss(filepath: str | Path) -> System:
    """Parse an OpenDSS .dss file into a System object.

    Convenience function that creates a DSSParser and parses.

    Args:
        filepath: Path to the .dss file

    Returns:
        System object containing parsed power system data

    Example:
        >>> from psforge_grid.io.dss_parser import parse_dss
        >>> system = parse_dss("network.dss")  # doctest: +SKIP
    """
    return DSSParser().parse(filepath)
