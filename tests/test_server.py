import asyncio
from types import SimpleNamespace

import pandas as pd
import pytest
from fastmcp.exceptions import ToolError

import server


def test_mcp_registers_expected_tools():
    tools = asyncio.run(server.mcp.list_tools())
    tool_names = {tool.name for tool in tools}

    assert {
        "hecras_project_summary",
        "read_plan_description",
        "get_plan_results_summary",
        "get_compute_messages",
        "get_hdf_structure",
        "get_projection_info",
        "search_docs",
        "get_doc_page",
    }.issubset(tool_names)


def test_init_project_returns_validated_path_and_ras(monkeypatch, project_dir, fake_ras):
    calls = []

    def fake_init_ras_project(project_path, ras_version):
        calls.append((project_path, ras_version))
        return fake_ras

    monkeypatch.setattr(server, "init_ras_project", fake_init_ras_project)

    path, ras = server._init_project(str(project_dir))

    assert path == project_dir
    assert ras is fake_ras
    assert calls == [(project_dir, server.HECRAS_VERSION)]


def test_init_project_invalid_folder_raises_tool_error(tmp_path):
    missing_path = tmp_path / "missing-project"

    with pytest.raises(ToolError, match="does not exist or is not a directory"):
        server._init_project(str(missing_path))


def test_resolve_plan_hdf_path_accepts_single_digit_plan(project_dir, fake_ras, plan_hdf_path):
    resolved = server._resolve_plan_hdf_path(project_dir, "1", fake_ras)

    assert resolved == plan_hdf_path


def test_resolve_plan_hdf_path_accepts_existing_hdf_path(project_dir, plan_hdf_path):
    ras_without_plans = SimpleNamespace(plan_df=pd.DataFrame())

    resolved = server._resolve_plan_hdf_path(project_dir, str(plan_hdf_path), ras_without_plans)

    assert resolved == plan_hdf_path


def test_resolve_plan_hdf_path_falls_back_to_project_name_pattern(project_dir, plan_hdf_path):
    ras_without_plans = SimpleNamespace(plan_df=None)

    resolved = server._resolve_plan_hdf_path(project_dir, "01", ras_without_plans)

    assert resolved == plan_hdf_path


def test_resolve_plan_hdf_path_missing_plan_raises_tool_error(project_dir, fake_ras):
    with pytest.raises(ToolError, match="Plan '99' not found"):
        server._resolve_plan_hdf_path(project_dir, "99", fake_ras)
