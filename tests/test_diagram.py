"""Tests for diagram data models and normalization."""

import tempfile
from pathlib import Path

import pytest

from psforge_grid.models.diagram import (
    BranchRoute,
    BusPosition,
    DiagramData,
    DiagramLabel,
    normalize_coordinates,
)
from psforge_grid.models.system import System

# =========================================================================
# BusPosition tests
# =========================================================================


class TestBusPosition:
    def test_basic_creation(self):
        bp = BusPosition(x=100, y=200)
        assert bp.x == 100
        assert bp.y == 200
        assert bp.points is None

    def test_with_points(self):
        bp = BusPosition(x=150, y=250, points=[(100, 250), (200, 250)])
        assert bp.points == [(100, 250), (200, 250)]


# =========================================================================
# BranchRoute tests
# =========================================================================


class TestBranchRoute:
    def test_basic_creation(self):
        br = BranchRoute(waypoints=[(0, 0), (100, 50), (200, 100)])
        assert len(br.waypoints) == 3

    def test_empty_waypoints(self):
        br = BranchRoute()
        assert br.waypoints == []


# =========================================================================
# DiagramLabel tests
# =========================================================================


class TestDiagramLabel:
    def test_bus_label(self):
        lbl = DiagramLabel(
            element_type="bus",
            element_id=1,
            text_type="name",
            offset_x=10,
            offset_y=20,
        )
        assert lbl.element_type == "bus"
        assert lbl.element_id == 1
        assert lbl.visible is True
        assert lbl.angle == 0.0

    def test_branch_label(self):
        lbl = DiagramLabel(
            element_type="branch",
            element_id=(1, 2, "1"),
            text_type="code",
            visible=False,
        )
        assert lbl.element_id == (1, 2, "1")
        assert lbl.visible is False


# =========================================================================
# DiagramData tests
# =========================================================================


class TestDiagramData:
    def test_default_schematic(self):
        dd = DiagramData()
        assert dd.coordinate_system == "schematic"
        assert dd.crs is None
        assert dd.normalization_ref == 1920
        assert dd.bus_positions == {}
        assert dd.branch_routes == {}
        assert dd.labels == []
        assert dd.import_meta is None

    def test_geographic(self):
        dd = DiagramData(
            coordinate_system="geographic",
            crs="EPSG:4326",
            bus_positions={1: BusPosition(x=141, y=43)},
        )
        assert dd.coordinate_system == "geographic"
        assert dd.crs == "EPSG:4326"

    def test_system_fields(self):
        system = System()
        assert system.diagram_schematic is None
        assert system.diagram_geographic is None

        system.diagram_schematic = DiagramData(bus_positions={1: BusPosition(x=100, y=200)})
        assert system.diagram_schematic is not None
        assert system.diagram_schematic.bus_positions[1].x == 100


# =========================================================================
# normalize_coordinates tests
# =========================================================================


class TestNormalizeCoordinates:
    def test_basic_normalization(self):
        """Short edge should map to normalization_ref."""
        # 100x50 rectangle → short edge (50) maps to 1920
        raw = [(0.0, 0.0), (100.0, 0.0), (100.0, 50.0), (0.0, 50.0)]
        normalized, meta = normalize_coordinates(raw, normalization_ref=1920)

        assert meta.y_flipped is False
        assert meta.source_bbox == (0.0, 0.0, 100.0, 50.0)

        # Check short edge spans usable area (1920 * 0.9 = 1728)
        ys = [p[1] for p in normalized]
        assert min(ys) == round(1920 * 0.05)  # padding = 96
        assert max(ys) == round(1920 * 0.05 + 1920 * 0.9)  # 96 + 1728 = 1824

    def test_y_flip(self):
        """Y-flip should invert Y coordinates."""
        raw = [(0.0, 0.0), (100.0, 100.0)]
        norm_no_flip, _ = normalize_coordinates(raw, normalization_ref=1000, y_flip=False)
        norm_flipped, _ = normalize_coordinates(raw, normalization_ref=1000, y_flip=True)

        # Without flip: (0,0) → bottom-left, (100,100) → top-right
        # With flip: (0,0) → top-right (y inverted), (100,100) → bottom-left
        assert norm_no_flip[0][1] < norm_no_flip[1][1]  # y increases
        assert norm_flipped[0][1] > norm_flipped[1][1]  # y decreases (flipped)

    def test_custom_normalization_ref(self):
        """Custom normalization_ref should be respected."""
        raw = [(0.0, 0.0), (100.0, 100.0)]
        norm, _ = normalize_coordinates(raw, normalization_ref=3840)

        ys = [p[1] for p in norm]
        # Short edge should use usable area of 3840
        assert max(ys) - min(ys) == round(3840 * 0.9)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_coordinates([])

    def test_single_point(self):
        """Single point should be placed at center."""
        norm, _ = normalize_coordinates([(500.0, 500.0)], normalization_ref=1920)
        assert len(norm) == 1
        assert norm[0] == (960, 960)  # center of 1920

    def test_integer_output(self):
        """All output coordinates should be integers."""
        raw = [(0.0, 0.0), (333.0, 777.0)]
        norm, _ = normalize_coordinates(raw)
        for x, y in norm:
            assert isinstance(x, int)
            assert isinstance(y, int)

    def test_aspect_ratio_preserved(self):
        """Aspect ratio should be preserved."""
        # 200x100 rectangle → 2:1 ratio
        raw = [(0.0, 0.0), (200.0, 0.0), (200.0, 100.0), (0.0, 100.0)]
        norm, _ = normalize_coordinates(raw, normalization_ref=1000, padding_ratio=0.0)

        xs = [p[0] for p in norm]
        ys = [p[1] for p in norm]
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)

        # Short edge = 1000, long edge = 2000
        assert y_range == 1000
        assert x_range == 2000


# =========================================================================
# Pop parser diagram integration tests
# =========================================================================


class TestPopParserDiagram:
    @pytest.fixture
    def pop_system(self):
        fixture = Path(__file__).parent / "fixtures" / "WEST10peak.pop"
        if not fixture.exists():
            pytest.skip("WEST10peak.pop fixture not found")
        return System.from_pop(fixture)

    def test_diagram_created(self, pop_system):
        assert pop_system.diagram_schematic is not None
        assert pop_system.diagram_geographic is None

    def test_coordinate_system(self, pop_system):
        d = pop_system.diagram_schematic
        assert d.coordinate_system == "schematic"
        assert d.normalization_ref == 1920

    def test_bus_positions_populated(self, pop_system):
        d = pop_system.diagram_schematic
        assert len(d.bus_positions) > 0
        # All buses should have valid coordinates
        for _bus_id, pos in d.bus_positions.items():
            assert isinstance(pos.x, int)
            assert isinstance(pos.y, int)

    def test_branch_routes_populated(self, pop_system):
        d = pop_system.diagram_schematic
        assert len(d.branch_routes) > 0
        for key, route in d.branch_routes.items():
            assert len(key) == 3  # (from, to, ckt)
            assert len(route.waypoints) >= 2

    def test_y_axis_up_positive(self, pop_system):
        """Y values should use math convention (up is positive)."""
        d = pop_system.diagram_schematic
        ys = [pos.y for pos in d.bus_positions.values()]
        # All Y values should be positive (after normalization with padding)
        assert all(y >= 0 for y in ys)

    def test_import_meta(self, pop_system):
        meta = pop_system.diagram_schematic.import_meta
        assert meta is not None
        assert meta.source_format == "pop"
        assert meta.y_flipped is True
        assert meta.scale > 0

    def test_short_edge_within_1920(self, pop_system):
        """Short edge range should be within normalization_ref."""
        d = pop_system.diagram_schematic
        xs = [pos.x for pos in d.bus_positions.values()]
        ys = [pos.y for pos in d.bus_positions.values()]
        x_range = max(xs) - min(xs)
        y_range = max(ys) - min(ys)
        short_range = min(x_range, y_range)
        # Short edge should fit within 1920 (with padding margin)
        assert short_range <= 1920


# =========================================================================
# JSON round-trip tests
# =========================================================================


class TestJsonDiagramRoundTrip:
    @pytest.fixture
    def system_with_diagram(self):
        fixture = Path(__file__).parent / "fixtures" / "WEST10peak.pop"
        if not fixture.exists():
            pytest.skip("WEST10peak.pop fixture not found")
        return System.from_pop(fixture)

    def test_round_trip(self, system_with_diagram):
        """Diagram data should survive JSON write → read cycle."""
        with tempfile.NamedTemporaryFile(suffix=".psfg.json", delete=False) as f:
            tmp_path = f.name

        try:
            system_with_diagram.to_json(tmp_path)
            loaded = System.from_json(tmp_path)

            orig = system_with_diagram.diagram_schematic
            back = loaded.diagram_schematic

            assert back is not None
            assert back.coordinate_system == orig.coordinate_system
            assert back.normalization_ref == orig.normalization_ref
            assert len(back.bus_positions) == len(orig.bus_positions)
            assert len(back.branch_routes) == len(orig.branch_routes)

            # Verify specific bus position
            for bus_id in orig.bus_positions:
                assert back.bus_positions[bus_id].x == orig.bus_positions[bus_id].x
                assert back.bus_positions[bus_id].y == orig.bus_positions[bus_id].y

            # Verify import_meta
            assert back.import_meta is not None
            assert back.import_meta.source_format == orig.import_meta.source_format
            assert back.import_meta.scale == pytest.approx(orig.import_meta.scale)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_no_diagram_round_trip(self):
        """System without diagram should round-trip cleanly."""
        system = System(name="test")
        assert system.diagram_schematic is None

        with tempfile.NamedTemporaryFile(suffix=".psfg.json", delete=False) as f:
            tmp_path = f.name

        try:
            system.to_json(tmp_path)
            loaded = System.from_json(tmp_path)
            assert loaded.diagram_schematic is None
            assert loaded.diagram_geographic is None
        finally:
            Path(tmp_path).unlink(missing_ok=True)
