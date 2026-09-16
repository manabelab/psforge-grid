"""A format can come from another distribution, and says so when it cannot.

These tests exist because the registry is the seam psforge offers to code it
does not ship. If registration silently did nothing, or a broken plugin took
the package down with it, the failure would surface as "the file type is not
supported" with nothing pointing at the cause.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from psforge_grid.io import _registry
from psforge_grid.io._registry import (
    ENTRY_POINT_GROUP,
    FormatPluginWarning,
    PluginError,
    _FormatRegistry,
)
from psforge_grid.io.factories import ParserFactory, WriterFactory
from psforge_grid.models.system import System

FIXTURES = Path(__file__).parent / "fixtures"


class _FakeParser:
    """Minimal stand-in: enough to prove the registry returned *this* class."""

    @property
    def supported_extensions(self) -> list[str]:
        return ["fake"]

    @property
    def format_name(self) -> str:
        return "fake"

    def parse(self, filepath: str | Path) -> System:
        return System(name=f"parsed by the fake parser: {Path(filepath).name}")


class _FakeWriter:
    @property
    def supported_extensions(self) -> list[str]:
        return ["fake"]

    @property
    def format_name(self) -> str:
        return "fake"

    def write(self, system: System, filepath: str | Path) -> None:
        Path(filepath).write_text(f"written by the fake writer: {system.name}\n")


@pytest.fixture
def clean_registry() -> _FormatRegistry:
    """A registry of its own, so a test cannot leak a format into the others."""
    registry = _FormatRegistry("parser")
    registry.register("raw", "psforge_grid.io.raw_parser.RawParser", ["raw"])
    return registry


class TestBuiltInFormatsStillResolve:
    """The built-ins moved into the registry; they must behave as before."""

    def test_every_built_in_parser_is_registered(self) -> None:
        assert set(ParserFactory.available_formats()) >= {"raw", "matpower", "dss", "json"}

    def test_every_built_in_writer_is_registered(self) -> None:
        assert set(WriterFactory.available_formats()) >= {"raw", "matpower", "dss", "json"}

    def test_extension_matching_ignores_case(self) -> None:
        """`.RAW` used to need its own entry; now one entry covers both."""
        from psforge_grid.io.raw_parser import RawParser

        assert isinstance(ParserFactory.from_extension(".RAW"), RawParser)
        assert isinstance(ParserFactory.from_extension("raw"), RawParser)
        assert isinstance(ParserFactory.from_path("a.RAW"), RawParser)

    def test_format_name_ignores_case(self) -> None:
        from psforge_grid.io.raw_parser import RawParser

        assert isinstance(ParserFactory.create("RAW"), RawParser)

    def test_compound_extension_still_wins_over_the_last_suffix(self) -> None:
        """`.psfg.json` must not be read as plain `.json`."""
        from psforge_grid.io.json_parser import JsonParser

        assert isinstance(ParserFactory.from_path("case.psfg.json"), JsonParser)

    def test_unknown_format_names_what_is_available(self) -> None:
        with pytest.raises(ValueError, match="Available formats"):
            ParserFactory.create("no-such-format")

    def test_unknown_extension_names_what_is_supported(self) -> None:
        with pytest.raises(ValueError, match="Supported extensions"):
            ParserFactory.from_extension(".nope")

    def test_a_file_without_an_extension_says_so(self) -> None:
        with pytest.raises(ValueError, match="no extension"):
            ParserFactory.from_path("case")


class TestRegisteringAFormat:
    """The seam itself: a class this package does not own becomes usable."""

    def test_a_registered_class_is_what_create_returns(
        self, clean_registry: _FormatRegistry
    ) -> None:
        clean_registry.register("fake", _FakeParser, ["fake"])
        assert isinstance(clean_registry.create("fake"), _FakeParser)

    def test_a_registered_format_appears_in_the_listing(
        self, clean_registry: _FormatRegistry
    ) -> None:
        clean_registry.register("fake", _FakeParser, ["fake"])
        assert "fake" in clean_registry.names()
        assert "fake" in clean_registry.extensions()

    def test_a_registered_extension_resolves_to_its_format(
        self, clean_registry: _FormatRegistry
    ) -> None:
        clean_registry.register("fake", _FakeParser, ["fake"])
        assert clean_registry.name_for_extension(".FAKE") == "fake"

    def test_a_dotted_path_is_imported_only_when_used(
        self, clean_registry: _FormatRegistry
    ) -> None:
        """Registering a format whose module does not exist must not raise.

        This is what lets a plugin declare a format that needs an optional
        dependency without forcing the import at registration time.
        """
        clean_registry.register("ghost", "no_such_module.NoSuchParser", ["ghost"])
        assert "ghost" in clean_registry.names()

        with pytest.raises(ModuleNotFoundError):
            clean_registry.create("ghost")

    def test_registering_over_a_name_replaces_it(self, clean_registry: _FormatRegistry) -> None:
        clean_registry.register("raw", _FakeParser, ["raw"])
        assert isinstance(clean_registry.create("raw"), _FakeParser)

    def test_an_empty_name_is_refused(self, clean_registry: _FormatRegistry) -> None:
        with pytest.raises(ValueError, match="cannot be empty"):
            clean_registry.register("   ", _FakeParser)

    def test_a_target_that_is_not_a_class_is_refused(self, clean_registry: _FormatRegistry) -> None:
        clean_registry.register("notaclass", "psforge_grid.io._registry.PARSERS")
        with pytest.raises(TypeError, match="not a class"):
            clean_registry.create("notaclass")


class TestEntryPointDiscovery:
    """An installed distribution can add a format without anyone calling it."""

    @staticmethod
    def _entry_point(monkeypatch: pytest.MonkeyPatch, hook: object, name: str = "fake"):
        class _EP:
            def __init__(self) -> None:
                self.name = name
                self.dist = type("D", (), {"name": "fake-dist"})()

            def load(self) -> object:
                return hook

        def fake_entry_points(*, group: str) -> tuple[object, ...]:
            assert group == ENTRY_POINT_GROUP
            return (_EP(),)

        monkeypatch.setattr(_registry._metadata, "entry_points", fake_entry_points)

    def test_an_advertised_format_is_registered_on_first_use(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = _FormatRegistry("parser")

        def hook() -> None:
            registry.register("fake", _FakeParser, ["fake"])

        self._entry_point(monkeypatch, hook)

        # Nothing has touched the registry yet, so the hook has not run.
        assert registry._entry_points_loaded is False
        assert "fake" in registry.names()
        assert isinstance(registry.create("fake"), _FakeParser)

    def test_discovery_runs_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        registry = _FormatRegistry("parser")
        calls: list[int] = []

        def hook() -> None:
            calls.append(1)

        self._entry_point(monkeypatch, hook)
        registry.names()
        registry.names()
        registry.extensions()
        assert calls == [1]

    def test_a_broken_plugin_does_not_break_the_registry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = _FormatRegistry("parser")
        registry.register("raw", "psforge_grid.io.raw_parser.RawParser", ["raw"])

        def hook() -> None:
            raise RuntimeError("the plugin exploded")

        self._entry_point(monkeypatch, hook)

        with pytest.warns(FormatPluginWarning, match="the plugin exploded"):
            names = registry.names()

        # The built-in format is still usable.
        assert "raw" in names
        from psforge_grid.io.raw_parser import RawParser

        assert isinstance(registry.create("raw"), RawParser)

    def test_a_broken_plugin_is_reported_not_swallowed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registry = _FormatRegistry("parser")

        def hook() -> None:
            raise RuntimeError("the plugin exploded")

        self._entry_point(monkeypatch, hook)

        with pytest.warns(FormatPluginWarning):
            errors = registry.errors()

        assert len(errors) == 1
        assert errors[0].entry_point == "fake"
        assert errors[0].distribution == "fake-dist"
        assert "the plugin exploded" in errors[0].reason
        assert "fake-dist" in errors[0].to_description()

    def test_plugin_errors_is_reachable_from_the_public_factory(self) -> None:
        """With nothing broken installed, the list is empty rather than absent."""
        assert ParserFactory.plugin_errors() == []
        assert WriterFactory.plugin_errors() == []


class TestSystemFacadeSeesRegisteredFormats:
    """`System.from_file` is the path a user actually takes."""

    def test_from_file_uses_a_registered_parser(self, tmp_path: Path) -> None:
        ParserFactory.register("faketest", _FakeParser, ["faketest"])
        try:
            path = tmp_path / "case.faketest"
            path.write_text("anything\n")
            system = System.from_file(path)
            assert system.name == "parsed by the fake parser: case.faketest"
        finally:
            _registry.PARSERS._targets.pop("faketest", None)
            _registry.PARSERS._extensions.pop("faketest", None)

    def test_to_file_uses_a_registered_writer(self, tmp_path: Path) -> None:
        WriterFactory.register("faketest", _FakeWriter, ["faketest"])
        try:
            path = tmp_path / "out.faketest"
            System(name="the system under test").to_file(path)
            assert path.read_text() == "written by the fake writer: the system under test\n"
        finally:
            _registry.WRITERS._targets.pop("faketest", None)
            _registry.WRITERS._extensions.pop("faketest", None)


class TestPluginErrorDescription:
    def test_description_names_the_entry_point_and_the_distribution(self) -> None:
        error = PluginError("pop", "psforge-cpat", "RuntimeError('boom')")
        assert error.to_description() == "pop (from psforge-cpat): RuntimeError('boom')"
