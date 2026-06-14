#!/usr/bin/env python3
"""Unit coverage for geometry element listing helpers and tool output."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from fastmcp.exceptions import ToolError

sys.path.insert(0, str(Path(__file__).parent.parent))

import server  # noqa: E402


class FakeGeometry:
    geom_type = "LineString"


def _fake_ras_project(tmp_path: Path):
    geom_hdf = tmp_path / "Demo.g01.hdf"
    geom_hdf.write_bytes(b"placeholder")
    ras = SimpleNamespace(
        project_name="Demo",
        geom_df=pd.DataFrame(
            [
                {
                    "geom_file": "g01",
                    "geom_number": "01",
                    "hdf_path": str(geom_hdf),
                }
            ]
        ),
    )
    return geom_hdf, ras


def _patch_project(monkeypatch, tmp_path: Path):
    geom_hdf, ras = _fake_ras_project(tmp_path)
    monkeypatch.setattr(server, "_init_project", lambda project_path: (tmp_path, ras))
    return geom_hdf, ras


def test_list_geometry_elements_formats_all_major_sections(monkeypatch, tmp_path):
    _patch_project(monkeypatch, tmp_path)
    mesh_filters = []

    monkeypatch.setattr(
        server.HdfXsec,
        "get_river_reaches",
        staticmethod(
            lambda hdf_path, datetime_to_str=True: pd.DataFrame(
                [{"River": "White River", "Reach": "Lower", "geometry": FakeGeometry()}]
            )
        ),
    )
    monkeypatch.setattr(
        server.HdfXsec,
        "get_cross_sections",
        staticmethod(
            lambda hdf_path, datetime_to_str=True, ras_object=None: pd.DataFrame(
                [
                    {
                        "River": "White River",
                        "Reach": "Lower",
                        "RS": "10.0",
                        "station_elevation": [(0, 100), (10, 99)],
                        "geometry": FakeGeometry(),
                    }
                ]
            )
        ),
    )

    def fake_reference_lines(hdf_path, mesh_name=None):
        mesh_filters.append(mesh_name)
        return pd.DataFrame(
            [{"refln_id": 1, "Name": "Ref A", "mesh_name": "2D Area", "geometry": FakeGeometry()}]
        )

    monkeypatch.setattr(server.HdfBndry, "get_reference_lines", staticmethod(fake_reference_lines))
    monkeypatch.setattr(
        server.HdfBndry,
        "get_bc_lines",
        staticmethod(
            lambda hdf_path: pd.DataFrame(
                [{"bc_line_id": 2, "Name": "Upstream BC", "Type": "Flow", "geometry": FakeGeometry()}]
            )
        ),
    )
    monkeypatch.setattr(
        server.HdfBndry,
        "get_breaklines",
        staticmethod(
            lambda hdf_path: pd.DataFrame(
                [{"bl_id": 3, "Name": "Road", "geometry": FakeGeometry()}]
            )
        ),
    )
    monkeypatch.setattr(
        server.HdfStruc,
        "get_structures",
        staticmethod(
            lambda hdf_path, datetime_to_str=True: pd.DataFrame(
                [{"Structure ID": 4, "Name": "Bridge", "Type": "Bridge", "geometry": FakeGeometry()}]
            )
        ),
    )
    monkeypatch.setattr(
        server.HdfMesh,
        "get_mesh_area_names",
        staticmethod(lambda hdf_path: ["2D Area"]),
    )

    output = server.list_geometry_elements(str(tmp_path), geometry_number="1", mesh_name="2D Area")

    assert "1D RIVERS/REACHES (1 element(s))" in output
    assert "1D CROSS SECTIONS (1 element(s))" in output
    assert "2D REFERENCE LINES (1 element(s))" in output
    assert "2D BOUNDARY CONDITION LINES (1 element(s))" in output
    assert "2D BREAKLINES (1 element(s))" in output
    assert "STRUCTURES (1 element(s))" in output
    assert "2D MESH AREAS (1 element(s))" in output
    assert "White River" in output
    assert "Bridge" in output
    assert "station_elevation" not in output
    assert mesh_filters == ["2D Area"]


def test_list_geometry_elements_accepts_cross_section_alias(monkeypatch, tmp_path):
    _patch_project(monkeypatch, tmp_path)

    monkeypatch.setattr(
        server.HdfXsec,
        "get_cross_sections",
        staticmethod(
            lambda hdf_path, datetime_to_str=True, ras_object=None: pd.DataFrame(
                [{"River": "White River", "Reach": "Lower", "RS": "10.0", "geometry": FakeGeometry()}]
            )
        ),
    )

    output = server.list_geometry_elements(str(tmp_path), element_type="xs")

    assert "1D CROSS SECTIONS (1 element(s))" in output
    assert "2D BOUNDARY CONDITION LINES" not in output
    assert "2D MESH AREAS" not in output


def test_list_geometry_elements_accepts_direct_geometry_hdf_path(monkeypatch, tmp_path):
    geom_hdf, ras = _fake_ras_project(tmp_path)
    ras.geom_df = pd.DataFrame()
    monkeypatch.setattr(server, "_init_project", lambda project_path: (tmp_path, ras))
    monkeypatch.setattr(server.HdfMesh, "get_mesh_area_names", staticmethod(lambda hdf_path: ["2D Area"]))

    output = server.list_geometry_elements(
        str(tmp_path),
        geometry_number=str(geom_hdf),
        element_type="mesh",
    )

    assert f"GEOMETRY {geom_hdf.stem}: {geom_hdf}" in output
    assert "2D MESH AREAS (1 element(s))" in output


def test_invalid_geometry_element_type_raises_tool_error():
    with pytest.raises(ToolError):
        server._normalize_geometry_element_type("not_a_geometry_type")
