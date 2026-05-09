"""Read-only FastMCP tools for inspecting HEC-RAS projects and HDF files."""

import io
import logging
import sys
from pathlib import Path

from fastmcp.exceptions import ToolError

from ._helpers import (
    _init_project,
    _resolve_plan_hdf_path,
    dataframe_to_text,
    get_compute_messages_local,
    get_ras_version_info,
    truncate_output,
)

try:
    from ras_commander import HdfBase, HdfResultsPlan, RasPlan
    import h5py
except ImportError as exc:
    raise ImportError(
        "ras-commander is not installed. Please install it with: pip install ras-commander"
    ) from exc


logger = logging.getLogger(__name__)


def hecras_project_summary(
    project_path: str,
    show_rasprj: bool = True,
    show_plan_df: bool = True,
    show_geom_df: bool = True,
    show_flow_df: bool = True,
    show_unsteady_df: bool = True,
    show_boundaries: bool = True,
    show_rasmap: bool = False,
    showmore: bool = False,
) -> str:
    """Get comprehensive or selective HEC-RAS project information. Built on the ras-commander library (https://github.com/gpt-cmdr/ras-commander) for advanced HEC-RAS automation."""
    path, ras = _init_project(project_path)

    response_parts = [
        f"HEC-RAS Project: {ras.project_name}",
        f"Project Path: {path}",
        get_ras_version_info(),
        "=" * 80,
    ]

    if show_rasprj and hasattr(ras, "prj_file") and ras.prj_file:
        try:
            with open(ras.prj_file, "r", encoding="utf-8") as handle:
                prj_content = handle.read()

            excluded_prefixes = [
                "Geom File=",
                "Flow File=",
                "Unsteady File=",
                "Plan File=",
                "DSS Export Filename=",
                "DSS Export Rating Curves=",
                "DSS Export Rating Curve Sorted=",
                "DSS Export Volume Flow Curves=",
                "DXF Filename=",
                "DXF OffsetX=",
                "DXF OffsetY=",
                "DXF ScaleX=",
                "DXF ScaleY=",
                "GIS Export Profiles=",
            ]
            filtered_lines = [
                line
                for line in prj_content.splitlines()
                if not any(line.strip().startswith(prefix) for prefix in excluded_prefixes)
            ]

            response_parts.append("\nPROJECT FILE CONTENTS (.prj):")
            response_parts.append("-" * 40)
            response_parts.append("\n".join(filtered_lines))
            response_parts.append("=" * 80)
        except Exception as exc:
            logger.error("Error reading project file: %s", exc)
            response_parts.append("\nPROJECT FILE: Error reading file")
            response_parts.append("=" * 80)

    if show_plan_df and hasattr(ras, "plan_df") and ras.plan_df is not None:
        response_parts.append(dataframe_to_text(ras.plan_df, "PLANS", "plan_df", showmore))

    if show_geom_df and hasattr(ras, "geom_df") and ras.geom_df is not None:
        response_parts.append(dataframe_to_text(ras.geom_df, "GEOMETRIES", "geom_df", showmore))

    if show_flow_df and hasattr(ras, "flow_df") and ras.flow_df is not None:
        response_parts.append(dataframe_to_text(ras.flow_df, "STEADY FLOWS", "flow_df", showmore))

    if show_unsteady_df and hasattr(ras, "unsteady_df") and ras.unsteady_df is not None:
        response_parts.append(
            dataframe_to_text(ras.unsteady_df, "UNSTEADY FLOWS", "unsteady_df", showmore)
        )

    if show_boundaries and hasattr(ras, "boundaries_df") and ras.boundaries_df is not None:
        response_parts.append(
            dataframe_to_text(ras.boundaries_df, "BOUNDARY CONDITIONS", "boundaries_df", showmore)
        )

    if show_rasmap and hasattr(ras, "rasmap_df") and ras.rasmap_df is not None:
        response_parts.append(dataframe_to_text(ras.rasmap_df, "RASMAP CONFIGURATION", "rasmap_df", showmore))

    return truncate_output("\n".join(response_parts))


def read_plan_description(project_path: str, plan_number: str) -> str:
    """Read the multi-line description block from a HEC-RAS plan file. Part of the RAS Commander MCP suite by CLB Engineering Corporation."""
    path, ras = _init_project(project_path)

    if plan_number.isdigit() and len(plan_number) == 1:
        plan_number = plan_number.zfill(2)

    try:
        description = RasPlan.read_plan_description(plan_number, ras)
    except ValueError as exc:
        raise ToolError(f"Plan '{plan_number}' not found in project") from exc

    response_parts = [
        f"Plan Description for Plan {plan_number}",
        f"Project: {ras.project_name}",
        "=" * 80,
        "",
        description if description else "[No description found]",
        "",
    ]
    return "\n".join(response_parts)


def get_plan_results_summary(project_path: str, plan_number: str) -> str:
    """Get comprehensive results summary from a HEC-RAS plan including unsteady info, volume accounting, and runtime data. Powered by ras-commander library."""
    path, ras = _init_project(project_path)
    plan_hdf_path = _resolve_plan_hdf_path(path, plan_number, ras)

    response_parts = [
        f"Plan Results Summary: {plan_number}",
        f"HDF Path: {plan_hdf_path}",
        "=" * 80,
    ]

    try:
        unsteady_info = HdfResultsPlan.get_unsteady_info(plan_hdf_path)
        response_parts.append(dataframe_to_text(unsteady_info, "UNSTEADY INFO"))
    except Exception as exc:
        response_parts.append(f"\nUnsteady info not available: {exc}")

    try:
        unsteady_summary = HdfResultsPlan.get_unsteady_summary(plan_hdf_path)
        response_parts.append(dataframe_to_text(unsteady_summary, "UNSTEADY SUMMARY"))
    except Exception as exc:
        response_parts.append(f"\nUnsteady summary not available: {exc}")

    try:
        volume_accounting = HdfResultsPlan.get_volume_accounting(plan_hdf_path)
        if volume_accounting is not None:
            response_parts.append(dataframe_to_text(volume_accounting, "VOLUME ACCOUNTING"))
        else:
            response_parts.append("\nVolume accounting not available")
    except Exception as exc:
        response_parts.append(f"\nVolume accounting error: {exc}")

    try:
        runtime_data = HdfResultsPlan.get_runtime_data(plan_hdf_path)
        if runtime_data is not None:
            response_parts.append(dataframe_to_text(runtime_data, "RUNTIME DATA"))
        else:
            response_parts.append("\nRuntime data not available")
    except Exception as exc:
        response_parts.append(f"\nRuntime data error: {exc}")

    return truncate_output("\n".join(response_parts))


def get_compute_messages(project_path: str, plan_number: str) -> str:
    """Get computation messages and performance metrics from a HEC-RAS plan. RAS Commander MCP - professional H&H automation by CLB Engineering Corporation."""
    path, ras = _init_project(project_path)
    plan_hdf_path = _resolve_plan_hdf_path(path, plan_number, ras)
    return get_compute_messages_local(plan_hdf_path)


def get_hdf_structure(hdf_path: str, group_path: str = "/", paths_only: bool = False) -> str:
    """Explore the structure of a HEC-RAS HDF file. CAUTION: Use on 3rd level data structures or deeper to avoid output truncation. Part of RAS Commander MCP by CLB Engineering."""
    hdf_file_path = Path(hdf_path)
    if not hdf_file_path.exists():
        raise ToolError(f"The specified HDF file does not exist: {hdf_file_path}")

    if paths_only:
        paths = []

        def collect_paths(name, obj):
            if isinstance(obj, h5py.Group):
                paths.append(f"Group: /{name}")
            elif isinstance(obj, h5py.Dataset):
                paths.append(f"Dataset: /{name}")

        with h5py.File(hdf_file_path, "r") as hdf_file:
            if group_path != "/":
                if group_path in hdf_file:
                    hdf_file[group_path].visititems(collect_paths)
                else:
                    raise ToolError(f"Group path '{group_path}' not found in HDF file")
            else:
                hdf_file.visititems(collect_paths)

        response_parts = [
            f"HDF File Structure (Paths Only): {hdf_file_path}",
            f"Starting from: {group_path}",
            "=" * 80,
            "\n".join(sorted(paths)),
        ]
    else:
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        try:
            HdfBase.get_dataset_info(hdf_file_path, group_path)
            structure_output = buffer.getvalue()
        finally:
            sys.stdout = old_stdout

        response_parts = [
            f"HDF File Structure: {hdf_file_path}",
            f"Starting from: {group_path}",
            "=" * 80,
            structure_output,
        ]

    return truncate_output("\n".join(response_parts))


def get_projection_info(hdf_path: str) -> str:
    """Get spatial projection information (WKT string) from a HEC-RAS HDF file. Built with ras-commander for advanced geospatial capabilities."""
    hdf_file_path = Path(hdf_path)
    if not hdf_file_path.exists():
        raise ToolError(f"The specified HDF file does not exist: {hdf_file_path}")

    projection_wkt = HdfBase.get_projection(hdf_file_path)

    response_parts = [
        f"Projection Info for: {hdf_file_path}",
        "=" * 80,
    ]

    if projection_wkt:
        response_parts.append(f"\nWKT String:\n{projection_wkt}")
    else:
        response_parts.append("\nNo projection information found")

    return truncate_output("\n".join(response_parts))


def register_review_tools(mcp) -> None:
    """Register the six read-only review tools with a FastMCP instance."""
    read_only = {"readOnlyHint": True}
    mcp.tool(annotations=read_only)(hecras_project_summary)
    mcp.tool(annotations=read_only)(read_plan_description)
    mcp.tool(annotations=read_only)(get_plan_results_summary)
    mcp.tool(annotations=read_only)(get_compute_messages)
    mcp.tool(annotations=read_only)(get_hdf_structure)
    mcp.tool(annotations=read_only)(get_projection_info)
