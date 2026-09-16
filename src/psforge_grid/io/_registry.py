"""The registry that decides which class reads or writes a given format.

Formats used to be a chain of ``if format_type == "raw": ...`` inside each
factory, with the list of names repeated in three places that could disagree.
They are now entries in a registry, which has one consequence worth stating
plainly: **a format no longer has to live in this package**. A separate
distribution can add one, and code that calls ``System.from_file(path)`` picks
it up without knowing it exists.

Third-party formats arrive one of two ways:

- explicitly, by calling :meth:`ParserFactory.register`;
- automatically, from the ``psforge_grid.formats`` entry-point group of any
  installed distribution. The entry point must name a callable taking no
  arguments; it is called once and is expected to register what it provides.

A plugin that fails to load does not stop psforge from working, but it is not
swallowed either: the failure is kept, reported through
:meth:`ParserFactory.plugin_errors`, and raised as a warning the first time
anything touches the registry. A format that silently is not there is exactly
the kind of quiet gap the parsers themselves stopped tolerating in 0.10.0.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from dataclasses import dataclass, field
from importlib import import_module
from importlib import metadata as _metadata
from typing import Any

#: Entry-point group that installed distributions use to add formats.
ENTRY_POINT_GROUP = "psforge_grid.formats"


class FormatPluginWarning(UserWarning):
    """A distribution advertised a format plugin that could not be loaded."""


@dataclass(frozen=True)
class PluginError:
    """One entry point that did not load.

    Attributes:
        entry_point: Name of the entry point as the distribution declared it.
        distribution: Distribution that declared it, or ``"unknown"``.
        reason: The exception, rendered as text.
    """

    entry_point: str
    distribution: str
    reason: str

    def to_description(self) -> str:
        """Return a one-line, LLM-readable description of this failure."""
        return f"{self.entry_point} (from {self.distribution}): {self.reason}"


@dataclass
class _FormatRegistry:
    """Format name to implementation, for one side of the read/write pair.

    Args:
        kind: ``"parser"`` or ``"writer"``. Used only in messages, so that a
            missing writer does not report itself as a missing parser.
    """

    kind: str
    _targets: dict[str, str | type] = field(default_factory=dict)
    _extensions: dict[str, str] = field(default_factory=dict)
    _errors: list[PluginError] = field(default_factory=list)
    _entry_points_loaded: bool = False

    def register(
        self,
        name: str,
        target: str | type,
        extensions: tuple[str, ...] | list[str] = (),
    ) -> None:
        """Add or replace a format.

        Args:
            name: Format name, as passed to ``create()``. Case-insensitive.
            target: The class, or its dotted path (``"pkg.mod.Class"``).
                A dotted path is imported only when the format is first used,
                so registering costs nothing and cannot fail on a missing
                optional dependency.
            extensions: File extensions this format claims, without the
                leading dot. Matching is case-insensitive, and a compound
                extension such as ``"psfg.json"`` is allowed.

        Raises:
            ValueError: If ``name`` is empty.
        """
        key = name.strip().lower()
        if not key:
            raise ValueError("A format name cannot be empty")
        self._targets[key] = target
        for extension in extensions:
            self._extensions[extension.strip().lstrip(".").lower()] = key

    def create(self, name: str) -> Any:
        """Instantiate the implementation registered under ``name``.

        Args:
            name: Format name. Case-insensitive.

        Returns:
            A new instance of the registered class.

        Raises:
            ValueError: If no format is registered under that name.
        """
        self._load_entry_points()
        key = name.strip().lower()
        target = self._targets.get(key)
        if target is None:
            raise ValueError(f"Unknown format: '{name}'. Available formats: {self.names()}")
        return self._resolve(target)()

    def name_for_extension(self, extension: str) -> str:
        """Return the format name that claims ``extension``.

        Args:
            extension: File extension, with or without the leading dot.

        Returns:
            The registered format name.

        Raises:
            ValueError: If no format claims that extension.
        """
        self._load_entry_points()
        key = extension.strip().lstrip(".").lower()
        name = self._extensions.get(key)
        if name is None:
            raise ValueError(
                f"Unknown extension: '{extension}'. Supported extensions: {self.extensions()}"
            )
        return name

    def knows_extension(self, extension: str) -> bool:
        """Whether some format claims ``extension``."""
        self._load_entry_points()
        return extension.strip().lstrip(".").lower() in self._extensions

    def names(self) -> list[str]:
        """Return every registered format name, in registration order."""
        self._load_entry_points()
        return list(self._targets)

    def extensions(self) -> list[str]:
        """Return every claimed extension, lowercased and without the dot.

        Matching is case-insensitive, so ``.RAW`` resolves through the ``raw``
        entry rather than needing one of its own.
        """
        self._load_entry_points()
        return list(self._extensions)

    def errors(self) -> list[PluginError]:
        """Return the entry points that failed to load, if any."""
        self._load_entry_points()
        return list(self._errors)

    @staticmethod
    def _resolve(target: str | type) -> type:
        """Turn a dotted path into the class it names, or pass a class through."""
        if not isinstance(target, str):
            return target
        module_name, _, attribute = target.rpartition(".")
        if not module_name:
            raise ValueError(f"Not a dotted path to a class: '{target}'")
        resolved = getattr(import_module(module_name), attribute)
        if not isinstance(resolved, type):
            raise TypeError(f"'{target}' is not a class")
        return resolved

    def _load_entry_points(self) -> None:
        """Register formats advertised by installed distributions, once.

        Runs on first use rather than at import, so that importing
        ``psforge_grid`` does not pay for scanning installed distributions,
        and so a plugin cannot deadlock the import of the package it extends.
        """
        if self._entry_points_loaded:
            return
        self._entry_points_loaded = True

        entry_points: Iterable[Any]
        try:
            entry_points = _metadata.entry_points(group=ENTRY_POINT_GROUP)
        except Exception as exc:  # pragma: no cover - depends on the environment
            self._errors.append(PluginError(ENTRY_POINT_GROUP, "unknown", repr(exc)))
            entry_points = ()

        for entry_point in entry_points:
            distribution = getattr(getattr(entry_point, "dist", None), "name", None)
            try:
                hook = entry_point.load()
                hook()
            except Exception as exc:
                self._errors.append(
                    PluginError(entry_point.name, distribution or "unknown", repr(exc))
                )

        for error in self._errors:
            warnings.warn(
                f"A format plugin did not load, so the formats it provides are "
                f"unavailable: {error.to_description()}",
                FormatPluginWarning,
                stacklevel=2,
            )


#: Built-in and third-party parsers. Shared by every ParserFactory call.
PARSERS = _FormatRegistry("parser")

#: Built-in and third-party writers. Shared by every WriterFactory call.
WRITERS = _FormatRegistry("writer")

PARSERS.register("raw", "psforge_grid.io.raw_parser.RawParser", ["raw"])
PARSERS.register("matpower", "psforge_grid.io.matpower_parser.MatpowerParser", ["m"])
PARSERS.register("dss", "psforge_grid.io.dss_parser.DSSParser", ["dss"])
PARSERS.register("json", "psforge_grid.io.json_parser.JsonParser", ["psfg.json"])

WRITERS.register("raw", "psforge_grid.io.raw_writer.RawWriter", ["raw"])
WRITERS.register("matpower", "psforge_grid.io.matpower_writer.MatpowerWriter", ["m"])
WRITERS.register("dss", "psforge_grid.io.dss_writer.DSSWriter", ["dss"])
WRITERS.register("json", "psforge_grid.io.json_writer.JsonWriter", ["psfg.json"])
