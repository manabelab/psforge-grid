"""ZIP archive extraction for .pop files.

A .pop file is a ZIP archive containing XML files:
    - data.pnsd: Electrical parameters
    - *.pnsw: Topology / single-line diagram
    - *.pnsj: Operating point / case data
    - *.pnsy: Stability scenarios (not used for power flow)
    - pop.ini: GUI settings (not used)
    - gckcnv.xml: Check parameters (not used)
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, fromstring


class PopArchive:
    """Extracts and provides access to XML data within a .pop file.

    The .pop format uses ZIP compression with XML contents. File names
    inside the archive may use CP932 (Shift-JIS) encoding for Japanese
    characters.

    Attributes:
        pnsd_root: Parsed XML root of data.pnsd (electrical parameters).
        pnsw_root: Parsed XML root of the .pnsw file (topology).
        pnsj_root: Parsed XML root of the .pnsj file (operating point).
    """

    pnsd_root: Element
    pnsw_root: Element
    pnsj_root: Element

    def __init__(self, filepath: str | Path) -> None:
        """Open a .pop file and parse its XML contents.

        Args:
            filepath: Path to the .pop file.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not a valid ZIP or missing required XML.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            zf = zipfile.ZipFile(path, "r")
        except zipfile.BadZipFile as e:
            raise ValueError(f"Not a valid .pop (ZIP) file: {path}") from e

        with zf:
            self.pnsd_root = self._read_xml(zf, "data.pnsd")
            self.pnsw_root = self._find_and_read(zf, ".pnsw")
            self.pnsj_root = self._find_and_read(zf, ".pnsj")

    @staticmethod
    def _read_xml(zf: zipfile.ZipFile, name: str) -> Element:
        """Read and parse a specific file from the ZIP archive.

        Args:
            zf: Open ZipFile object.
            name: Exact filename inside the archive.

        Returns:
            Parsed XML Element tree root.

        Raises:
            ValueError: If the file is not found in the archive.
        """
        try:
            data = zf.read(name)
        except KeyError as e:
            raise ValueError(f"Required file '{name}' not found in .pop archive") from e
        return fromstring(data.decode("utf-8"))

    @staticmethod
    def _find_and_read(zf: zipfile.ZipFile, suffix: str) -> Element:
        """Find a file by extension suffix and parse it.

        File names in .pop archives may be encoded in CP932 (Shift-JIS),
        so we match by suffix rather than exact name.

        Args:
            zf: Open ZipFile object.
            suffix: File extension to search for (e.g., ".pnsw").

        Returns:
            Parsed XML Element tree root.

        Raises:
            ValueError: If no file with the given suffix is found.
        """
        for info in zf.infolist():
            # Try both raw filename and CP932-decoded filename
            name = info.filename
            if name.endswith(suffix):
                data = zf.read(info.filename)
                return fromstring(data.decode("utf-8"))

        # Try with CP932 encoding for Japanese filenames
        for info in zf.infolist():
            try:
                decoded = info.filename.encode("cp437").decode("cp932")
            except (UnicodeDecodeError, UnicodeEncodeError):
                decoded = info.filename
            if decoded.endswith(suffix):
                data = zf.read(info.filename)
                return fromstring(data.decode("utf-8"))

        raise ValueError(f"No '*{suffix}' file found in .pop archive")
