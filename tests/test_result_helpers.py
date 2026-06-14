import asyncio

import h5py
import numpy as np
import pandas as pd
import xarray as xr

from fastmcp.exceptions import ToolError

import server


class DummyRas:
    pass


def _patch_project_resolution(monkeypatch, tmp_path, hdf_path):
    monkeypatch.setattr(server, "_init_project", lambda project_path: (tmp_path, DummyRas()))
    monkeypatch.setattr(server, "_resolve_plan_hdf_path", lambda project_path, plan_number, ras: hdf_path)


def test_new_result_tools_are_registered():
    tool_names = {tool.name for tool in asyncio.run(server.mcp.list_tools())}

    assert "list_profiles" in tool_names
    assert "get_plan_summary" in tool_names
    assert "get_mesh_results" in tool_names
    assert "get_xsec_results" in tool_names


def test_collect_output_profiles_reads_unsteady_time_stamps(tmp_path):
    hdf_path = tmp_path / "computed.p01.hdf"
    time_path = (
        "Results/Unsteady/Output/Output Blocks/Base Output/"
        "Unsteady Time Series/Time Date Stamp (ms)"
    )
    with h5py.File(hdf_path, "w") as hdf_file:
        hdf_file.create_dataset(time_path, data=np.array([b"01JAN2024 00:00:00:000", b"01JAN2024 01:00:00:000"]))

    profiles = server._collect_output_profiles(hdf_path)

    assert list(profiles["result_type"]) == ["unsteady", "unsteady"]
    assert list(profiles["profile_index"]) == [0, 1]
    assert pd.to_datetime(profiles["profile"].iloc[1]) == pd.Timestamp("2024-01-01 01:00:00")


def test_select_xarray_profile_by_index_and_max():
    data = xr.DataArray(
        [[1.0, 3.0], [5.0, 2.0]],
        dims=["time", "cell_id"],
        coords={
            "time": pd.to_datetime(["2024-01-01 00:00", "2024-01-01 01:00"]),
            "cell_id": [0, 1],
        },
    )

    selected, label = server._select_xarray_time_profile(data, "1")
    maximum, max_label = server._select_xarray_time_profile(data, "max")

    assert "profile index 1" in label
    assert selected.sel(cell_id=0).item() == 5.0
    assert "maximum across all output time steps" == max_label
    assert maximum.sel(cell_id=1).item() == 3.0


def test_ensure_results_available_explains_uncomputed_hdf(tmp_path):
    hdf_path = tmp_path / "uncomputed.p01.hdf"
    with h5py.File(hdf_path, "w") as hdf_file:
        hdf_file.create_group("Plan Data")

    try:
        server._ensure_results_available(hdf_path)
    except ToolError as exc:
        assert "No computed steady or unsteady results" in str(exc)
    else:
        raise AssertionError("Expected ToolError for an HDF file without result groups")


def test_list_profiles_tool_uses_computed_plan_hdf(monkeypatch, tmp_path):
    hdf_path = tmp_path / "computed.p01.hdf"
    time_path = (
        "Results/Unsteady/Output/Output Blocks/Base Output/"
        "Unsteady Time Series/Time Date Stamp (ms)"
    )
    with h5py.File(hdf_path, "w") as hdf_file:
        hdf_file.create_dataset(time_path, data=np.array([b"01JAN2024 00:00:00:000"]))

    _patch_project_resolution(monkeypatch, tmp_path, hdf_path)

    result = server.list_profiles(str(tmp_path), "01")

    assert "AVAILABLE PROFILES" in result
    assert "unsteady" in result


def test_get_mesh_results_formats_selected_profile(monkeypatch, tmp_path):
    hdf_path = tmp_path / "computed.p01.hdf"
    with h5py.File(hdf_path, "w") as hdf_file:
        hdf_file.create_group("Results/Unsteady")

    _patch_project_resolution(monkeypatch, tmp_path, hdf_path)

    def fake_get_mesh_cells_timeseries(hdf_path, mesh_names=None, var=None, truncate=False, ras_object=None):
        data = xr.DataArray(
            [[1.0, 2.0], [3.0, 4.0]],
            dims=["time", "cell_id"],
            coords={
                "time": pd.to_datetime(["2024-01-01 00:00", "2024-01-01 01:00"]),
                "cell_id": [0, 1],
            },
        )
        return {"Area 1": xr.Dataset({var: data})}

    monkeypatch.setattr(server.HdfResultsMesh, "get_mesh_cells_timeseries", fake_get_mesh_cells_timeseries)

    result = server.get_mesh_results(
        str(tmp_path),
        "01",
        profile="1",
        variables="Water Surface,Depth",
        max_rows=10,
    )

    assert "MESH RESULTS - Area 1" in result
    assert "profile index 1" in result
    assert "Water Surface" in result
    assert "Depth" in result


def test_get_xsec_results_formats_unsteady_max_profile(monkeypatch, tmp_path):
    hdf_path = tmp_path / "computed.p01.hdf"
    with h5py.File(hdf_path, "w") as hdf_file:
        hdf_file.create_group("Results/Unsteady")

    _patch_project_resolution(monkeypatch, tmp_path, hdf_path)
    monkeypatch.setattr(server.HdfResultsPlan, "is_steady_plan", lambda hdf_path: False)

    def fake_get_xsec_timeseries(hdf_path):
        times = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 01:00"])
        cross_sections = ["XS 1", "XS 2"]
        return xr.Dataset(
            {
                "Water_Surface": (["time", "cross_section"], [[10.0, 11.0], [12.0, 9.0]]),
                "Flow": (["time", "cross_section"], [[100.0, 110.0], [90.0, 125.0]]),
                "Velocity_Total": (["time", "cross_section"], [[2.0, 2.5], [3.0, 2.2]]),
            },
            coords={
                "time": times,
                "cross_section": cross_sections,
                "River": ("cross_section", ["River", "River"]),
                "Reach": ("cross_section", ["Reach", "Reach"]),
                "Station": ("cross_section", ["1", "2"]),
                "Name": ("cross_section", ["XS 1", "XS 2"]),
            },
        )

    monkeypatch.setattr(server.HdfResultsXsec, "get_xsec_timeseries", fake_get_xsec_timeseries)

    result = server.get_xsec_results(
        str(tmp_path),
        "01",
        profile="max",
        variables="wsel,flow,velocity",
        max_rows=10,
    )

    assert "UNSTEADY CROSS-SECTION RESULTS" in result
    assert "maximum across all output time steps" in result
    assert "Water_Surface" in result
    assert "Flow" in result


def test_get_xsec_results_selects_steady_profile_by_index(monkeypatch, tmp_path):
    hdf_path = tmp_path / "computed.p01.hdf"
    with h5py.File(hdf_path, "w") as hdf_file:
        hdf_file.create_group("Results/Steady")

    _patch_project_resolution(monkeypatch, tmp_path, hdf_path)
    monkeypatch.setattr(server.HdfResultsPlan, "is_steady_plan", lambda hdf_path: True)
    monkeypatch.setattr(
        server.HdfResultsPlan,
        "get_steady_results",
        lambda hdf_path: pd.DataFrame(
            {
                "river": ["River", "River"],
                "reach": ["Reach", "Reach"],
                "node_id": ["XS 1", "XS 1"],
                "profile": ["Base", "Future"],
                "wsel": [10.0, 12.5],
                "flow": [100.0, 140.0],
                "velocity": [2.0, 2.8],
            }
        ),
    )

    result = server.get_xsec_results(
        str(tmp_path),
        "01",
        profile="1",
        variables="wsel,flow",
        max_rows=10,
    )

    assert "STEADY CROSS-SECTION RESULTS" in result
    assert "Future" in result
    assert "12.5" in result
    assert "Base" not in result
