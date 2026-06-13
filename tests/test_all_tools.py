import pandas as pd
import pytest
from fastmcp.exceptions import ToolError

import server


def test_hecras_project_summary_happy_path(project_dir, patch_init_project):
    result = server.hecras_project_summary(
        project_path=str(project_dir),
        show_rasmap=True,
    )

    assert "HEC-RAS Project: MockProject" in result
    assert f"Project Path: {project_dir}" in result
    assert "PROJECT FILE CONTENTS (.prj):" in result
    assert "PLANS:" in result
    assert "Existing Conditions" in result
    assert "GEOMETRIES:" in result
    assert "STEADY FLOWS:" in result
    assert "UNSTEADY FLOWS:" in result
    assert "BOUNDARY CONDITIONS:" in result
    assert "RASMAP CONFIGURATION:" in result
    assert "Geom File" not in result
    assert "Computation Interval" not in result


def test_hecras_project_summary_invalid_path_raises_tool_error(tmp_path):
    with pytest.raises(ToolError, match="does not exist or is not a directory"):
        server.hecras_project_summary(project_path=str(tmp_path / "missing"))


def test_read_plan_description_happy_path(monkeypatch, project_dir, patch_init_project):
    monkeypatch.setattr(
        server.RasPlan,
        "read_plan_description",
        lambda plan_number, ras: "Selected plan notes",
    )

    result = server.read_plan_description(project_path=str(project_dir), plan_number="1")

    assert "Plan Description for Plan 01" in result
    assert "Project: MockProject" in result
    assert "Selected plan notes" in result


def test_read_plan_description_missing_plan_raises_tool_error(
    monkeypatch, project_dir, patch_init_project
):
    def raise_missing_plan(plan_number, ras):
        raise ValueError("missing plan")

    monkeypatch.setattr(server.RasPlan, "read_plan_description", raise_missing_plan)

    with pytest.raises(ToolError, match="Plan '99' not found"):
        server.read_plan_description(project_path=str(project_dir), plan_number="99")


def test_get_plan_results_summary_happy_path(monkeypatch, project_dir, patch_init_project):
    monkeypatch.setattr(
        server.HdfResultsPlan,
        "get_unsteady_info",
        lambda hdf_path: pd.DataFrame([{"Metric": "Peak Flow", "Value": 100.0}]),
    )
    monkeypatch.setattr(
        server.HdfResultsPlan,
        "get_unsteady_summary",
        lambda hdf_path: pd.DataFrame([{"Summary": "Complete"}]),
    )
    monkeypatch.setattr(
        server.HdfResultsPlan,
        "get_volume_accounting",
        lambda hdf_path: pd.DataFrame([{"Volume": 1234.5}]),
    )
    monkeypatch.setattr(
        server.HdfResultsPlan,
        "get_runtime_data",
        lambda hdf_path: pd.DataFrame([{"Runtime": "00:01"}]),
    )

    result = server.get_plan_results_summary(project_path=str(project_dir), plan_number="1")

    assert "Plan Results Summary: 1" in result
    assert "MockProject.p01.hdf" in result
    assert "UNSTEADY INFO:" in result
    assert "Peak Flow" in result
    assert "UNSTEADY SUMMARY:" in result
    assert "VOLUME ACCOUNTING:" in result
    assert "RUNTIME DATA:" in result


def test_get_plan_results_summary_missing_plan_raises_tool_error(
    project_dir, patch_init_project
):
    with pytest.raises(ToolError, match="Plan '99' not found"):
        server.get_plan_results_summary(project_path=str(project_dir), plan_number="99")


def test_get_compute_messages_happy_path(project_dir, patch_init_project):
    result = server.get_compute_messages(project_path=str(project_dir), plan_number="01")

    assert "Compute Messages from: MockProject.p01.hdf" in result
    assert "Simulation" in result
    assert "Complete" in result
    assert "Elapsed" in result
    assert "00:01" in result
    assert "Should not appear in formatted output" not in result


def test_get_compute_messages_missing_plan_raises_tool_error(project_dir, patch_init_project):
    with pytest.raises(ToolError, match="Plan '99' not found"):
        server.get_compute_messages(project_path=str(project_dir), plan_number="99")


def test_get_hdf_structure_paths_only_happy_path(plan_hdf_path):
    result = server.get_hdf_structure(
        hdf_path=str(plan_hdf_path),
        group_path="/Results/Summary",
        paths_only=True,
    )

    assert "HDF File Structure (Paths Only):" in result
    assert "Starting from: /Results/Summary" in result
    assert "Dataset: /Flow" in result
    assert "Dataset: /Compute Messages (text)" in result


def test_get_hdf_structure_missing_group_raises_tool_error(plan_hdf_path):
    with pytest.raises(ToolError, match="Group path '/Missing' not found"):
        server.get_hdf_structure(
            hdf_path=str(plan_hdf_path),
            group_path="/Missing",
            paths_only=True,
        )


def test_get_projection_info_happy_path(monkeypatch, geom_hdf_path):
    monkeypatch.setattr(server.HdfBase, "get_projection", lambda hdf_path: 'PROJCS["Mock"]')

    result = server.get_projection_info(hdf_path=str(geom_hdf_path))

    assert "Projection Info for:" in result
    assert "WKT String:" in result
    assert 'PROJCS["Mock"]' in result


def test_get_projection_info_missing_file_raises_tool_error(tmp_path):
    with pytest.raises(ToolError, match="The specified HDF file does not exist"):
        server.get_projection_info(hdf_path=str(tmp_path / "missing.hdf"))
