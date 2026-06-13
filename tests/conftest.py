from types import SimpleNamespace

import h5py
import pandas as pd
import pytest

import server


@pytest.fixture
def project_dir(tmp_path):
    path = tmp_path / "MockProject"
    path.mkdir()
    (path / "MockProject.prj").write_text(
        "\n".join(
            [
                "Proj Title=MockProject",
                "Plan File=p01",
                "Geom File=g01",
                "Current Plan=p01",
            ]
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def plan_hdf_path(project_dir):
    hdf_path = project_dir / "MockProject.p01.hdf"
    with h5py.File(hdf_path, "w") as hdf:
        summary = hdf.require_group("Results/Summary")
        summary.create_dataset(
            "Compute Messages (text)",
            data=(
                b"Simulation: Complete\n"
                b"Elapsed: 00:01\n"
                b"Computation Task\tSkipped details\n"
                b"Should not appear in formatted output"
            ),
        )
        summary.create_dataset("Flow", data=[1.0, 2.0, 3.0])
        output = hdf.require_group(
            "Results/Unsteady/Output/Output Blocks/Base Output/Summary Output"
        )
        output.create_dataset("Water Surface", data=[10.0, 11.0])
    return hdf_path


@pytest.fixture
def geom_hdf_path(project_dir):
    hdf_path = project_dir / "MockProject.g01.hdf"
    with h5py.File(hdf_path, "w") as hdf:
        hdf.attrs["Projection"] = 'PROJCS["Mock"]'
    return hdf_path


@pytest.fixture
def fake_ras(project_dir, plan_hdf_path):
    return SimpleNamespace(
        project_name="MockProject",
        prj_file=project_dir / "MockProject.prj",
        plan_df=pd.DataFrame(
            [
                {
                    "plan_number": "01",
                    "HDF_Results_Path": plan_hdf_path.name,
                    "Plan Title": "Existing Conditions",
                    "Geom File": "g01",
                    "Computation Interval": "1MIN",
                }
            ]
        ),
        geom_df=pd.DataFrame(
            [
                {
                    "geometry_number": "01",
                    "geometry_title": "Base Geometry",
                    "full_path": "omitted",
                }
            ]
        ),
        flow_df=pd.DataFrame(
            [
                {
                    "flow_number": "01",
                    "flow_title": "Base Flow",
                    "full_path": "omitted",
                }
            ]
        ),
        unsteady_df=pd.DataFrame(
            [
                {
                    "unsteady_number": "01",
                    "unsteady_title": "Base Unsteady Flow",
                    "full_path": "omitted",
                }
            ]
        ),
        boundaries_df=pd.DataFrame(
            [
                {
                    "boundary_name": "Upstream",
                    "boundary_type": "Flow Hydrograph",
                    "full_path": "omitted",
                }
            ]
        ),
        rasmap_df=pd.DataFrame([{"layer": "Terrain", "status": "available"}]),
    )


@pytest.fixture
def patch_init_project(monkeypatch, fake_ras):
    monkeypatch.setattr(server, "init_ras_project", lambda project_path, ras_version: fake_ras)
    return fake_ras
