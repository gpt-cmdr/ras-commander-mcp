import sys

import pytest
from fastmcp.exceptions import ToolError

import server


def test_get_hdf_structure_detailed_output_uses_hdfbase(monkeypatch, plan_hdf_path):
    calls = []

    def fake_get_dataset_info(hdf_path, group_path):
        calls.append((hdf_path, group_path))
        sys.stdout.write(f"Dataset info for {group_path}")

    monkeypatch.setattr(server.HdfBase, "get_dataset_info", fake_get_dataset_info)

    result = server.get_hdf_structure(
        hdf_path=str(plan_hdf_path),
        group_path="/Results/Summary",
        paths_only=False,
    )

    assert calls == [(plan_hdf_path, "/Results/Summary")]
    assert "HDF File Structure:" in result
    assert "Dataset info for /Results/Summary" in result


def test_get_hdf_structure_missing_file_raises_tool_error(tmp_path):
    with pytest.raises(ToolError, match="The specified HDF file does not exist"):
        server.get_hdf_structure(hdf_path=str(tmp_path / "missing.hdf"))


def test_get_projection_info_without_projection_returns_explicit_message(
    monkeypatch, geom_hdf_path
):
    monkeypatch.setattr(server.HdfBase, "get_projection", lambda hdf_path: "")

    result = server.get_projection_info(hdf_path=str(geom_hdf_path))

    assert "No projection information found" in result
