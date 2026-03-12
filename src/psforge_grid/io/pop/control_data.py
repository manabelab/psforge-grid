"""ControlData and VolDataSet parser for .pop format.

Extracts system-wide parameters from data.pnsd:
    - ControlData: base MVA (Swva), frequency (F), system name (Header)
    - VolDataSet: voltage class table mapping index → kV rating
"""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from psforge_grid.io.pop.xml_utils import get_float, get_str


@dataclass
class PopControlData:
    """System-wide control parameters from a .pop file.

    Attributes:
        base_mva: System base MVA (Swva tag). Used for per-unit conversion.
        frequency_hz: System frequency in Hz (F tag).
        header: System name / description (Header tag).
        voltage_classes: Mapping of voltage class index to rated kV.
            Index corresponds to NumVol in DataNodeValue.
    """

    base_mva: float = 100.0
    frequency_hz: float = 60.0
    header: str = ""
    voltage_classes: dict[int, float] = field(default_factory=dict)


def parse_control_data(pnsd_root: Element) -> PopControlData:
    """Parse ControlData and VolDataSet from data.pnsd XML root.

    Args:
        pnsd_root: Root element of data.pnsd XML.

    Returns:
        PopControlData with base MVA, frequency, header, and voltage classes.
    """
    result = PopControlData()

    cd = pnsd_root.find("ControlData")
    if cd is not None:
        result.base_mva = get_float(cd, "Swva", 100.0)
        result.frequency_hz = get_float(cd, "F", 60.0)
        result.header = get_str(cd, "Header")

    # VolDataSet: index → kV mapping
    vds = pnsd_root.find("VolDataSet")
    if vds is not None:
        data = vds.find("Data")
        if data is not None:
            for i, vol_data in enumerate(data):
                kv = get_float(vol_data, "Vol", 0.0)
                result.voltage_classes[i] = kv

    return result
