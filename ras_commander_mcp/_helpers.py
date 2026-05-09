"""Shared helpers for RAS Commander MCP tools."""

import io
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastmcp.exceptions import ToolError

try:
    from ras_commander import init_ras_project
    import h5py
    import numpy as np
except ImportError as exc:
    raise ImportError(
        "ras-commander is not installed. Please install it with: pip install ras-commander"
    ) from exc


logger = logging.getLogger(__name__)

DEFAULT_RAS_VERSION = "6.6"
HECRAS_VERSION = os.environ.get("HECRAS_VERSION", DEFAULT_RAS_VERSION)
HECRAS_PATH = os.environ.get("HECRAS_PATH", None)


def get_ras_version_info() -> str:
    """Get the configured HEC-RAS version or path for display."""
    if HECRAS_PATH:
        return f"HEC-RAS Path: {HECRAS_PATH}"
    return f"HEC-RAS Version: {HECRAS_VERSION}"


def _init_project(project_path: str) -> tuple[Path, Any]:
    """Validate path and initialise HEC-RAS project. Raises ToolError on failure."""
    path = Path(project_path)
    if not path.exists() or not path.is_dir():
        raise ToolError(f"The specified project folder does not exist or is not a directory: {path}")
    ras_version = HECRAS_PATH if HECRAS_PATH else HECRAS_VERSION
    logger.info("Initializing HEC-RAS project at: %s", path)
    ras = init_ras_project(path, ras_version)
    return path, ras


def _resolve_plan_hdf_path(project_path: Path, plan_number: str, ras: Any) -> Path:
    """Resolve plan number to HDF path. Raises ToolError if not found."""
    if plan_number.isdigit() and len(plan_number) == 1:
        plan_number = plan_number.zfill(2)

    if plan_number.endswith(".hdf") and Path(plan_number).exists():
        return Path(plan_number)

    plan_hdf_path = None

    if hasattr(ras, "plan_df") and ras.plan_df is not None:
        plan_row = ras.plan_df[ras.plan_df["plan_number"] == plan_number]
        if not plan_row.empty and "HDF_Results_Path" in plan_row.columns:
            hdf_rel_path = plan_row["HDF_Results_Path"].iloc[0]
            if hdf_rel_path:
                plan_hdf_path = project_path / hdf_rel_path

    if not plan_hdf_path:
        project_name = project_path.name
        potential_paths = [
            project_path / f"{project_name}.p{plan_number}.hdf",
            project_path / f"*.p{plan_number}.hdf",
        ]
        for pattern in potential_paths:
            if "*" in str(pattern):
                matches = list(project_path.glob(pattern.name))
                if matches:
                    plan_hdf_path = matches[0]
                    break
            elif pattern.exists():
                plan_hdf_path = pattern
                break

    if not plan_hdf_path or not plan_hdf_path.exists():
        raise ToolError(f"Plan '{plan_number}' not found or has no results HDF file")

    return plan_hdf_path


def get_compute_messages_local(hdf_path: Path) -> str:
    """
    Local implementation of get_compute_messages for HEC-RAS plan HDF files.

    Extracts computation log messages stored in the HDF file, including timing
    information, computation tasks, and performance metrics.
    """
    try:
        with h5py.File(hdf_path, "r") as hdf_file:
            compute_messages_path = "/Results/Summary/Compute Messages (text)"

            if compute_messages_path not in hdf_file:
                return (
                    "Compute messages not found. The simulation may not have completed "
                    "or results were not saved properly."
                )

            compute_messages_dataset = hdf_file[compute_messages_path]

            if isinstance(compute_messages_dataset, h5py.Dataset):
                data = compute_messages_dataset[()]

                if isinstance(data, bytes):
                    messages_text = data.decode("utf-8")
                elif isinstance(data, np.ndarray):
                    if data.dtype.kind == "S":
                        messages_text = "\n".join(
                            item.decode("utf-8") if isinstance(item, bytes) else str(item)
                            for item in data
                        )
                    else:
                        messages_text = str(data)
                else:
                    messages_text = str(data)
            else:
                return f"Unexpected data type for compute messages: {type(compute_messages_dataset)}"

            formatted_output = format_compute_messages_local(messages_text, str(hdf_path))

            max_chars = 10000 * 4
            if len(formatted_output) > max_chars:
                lines = formatted_output.split("\n")
                last_50_lines = lines[-50:] if len(lines) > 50 else lines
                last_50_text = "\n".join(last_50_lines)
                truncation_notice = (
                    "\n\n[OUTPUT TRUNCATED: Response exceeded 10,000 tokens. "
                    "Showing beginning and last 50 lines.]\n\n"
                )
                available_chars = max_chars - len(last_50_text) - len(truncation_notice)
                truncated_beginning = formatted_output[:available_chars]
                last_newline = truncated_beginning.rfind("\n")
                if last_newline > 0:
                    truncated_beginning = truncated_beginning[:last_newline]
                formatted_output = truncated_beginning + truncation_notice + last_50_text

            return formatted_output

    except FileNotFoundError:
        return f"HDF file not found: {hdf_path}"
    except Exception as exc:
        logger.error("Error reading compute messages: %s", exc)
        return f"Error reading compute messages: {exc}"


def format_compute_messages_local(messages_text: str, hdf_file_path: str) -> str:
    """Format compute messages for better readability."""
    lines = messages_text.split("\r\n") if "\r\n" in messages_text else messages_text.split("\n")

    formatted_parts = [
        f"Compute Messages from: {Path(hdf_file_path).name}",
        "=" * 80,
        "",
    ]

    general_messages = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if "Computation Task" in line and "\t" in line:
            break
        if "Computation Speed" in line and "\t" in line:
            break
        general_messages.append(line)

    if general_messages:
        formatted_parts.append("General Messages:")
        formatted_parts.append("-" * 40)
        for msg in general_messages:
            if ":" in msg and not msg.startswith("http"):
                key, value = msg.split(":", 1)
                formatted_parts.append(f"{key.strip():40} : {value.strip()}")
            else:
                formatted_parts.append(msg)

    return "\n".join(formatted_parts)


def truncate_output(text: str, max_tokens: int = 10000) -> str:
    """Truncate output to maximum tokens and add notice if truncated."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    truncated_text = text[:max_chars]
    last_space = truncated_text.rfind(" ")
    if last_space > max_chars * 0.9:
        truncated_text = truncated_text[:last_space]
    return (
        truncated_text
        + "\n\n[OUTPUT TRUNCATED: Response exceeded 10,000 tokens. "
        "Please use a more specific query for complete results.]"
    )


def filter_dataframe_columns(
    df: pd.DataFrame,
    df_type: str,
    showmore: bool = False,
) -> tuple[pd.DataFrame, int]:
    """Filter DataFrame columns for default vs verbose output."""
    if df is None or df.empty or showmore:
        return df, 0

    omit_columns = {
        "plan_df": {
            "Geom File",
            "Flow File",
            "full_path",
            "Geom Path",
            "Flow Path",
            "Computation Interval",
            "Output Interval",
            "Instantaneous Interval",
            "Mapping Interval",
            "Detailed Interval",
            "HDF Compression",
            "Computation Threads",
            "Tolerated Iterations",
            "WS Tolerance",
            "Flow Tolerance",
            "Computation Mode",
            "Mixed Flow",
            "Computation Level",
            "Run WQNet",
        },
        "geom_df": {"full_path", "hdf_path"},
        "flow_df": {"full_path", "Number of Profiles", "River Stations"},
        "unsteady_df": {
            "full_path",
            "Initial Conditions",
            "Flow Multiplier",
            "Base Flow",
            "Wave Celerity",
        },
        "boundaries_df": {
            "full_path",
            "hydrograph_data",
            "hydrograph_data_path",
            "hydrograph_units",
            "hydrograph_description",
            "bc_data_path",
            "hydrograph_values",
            "Is Critical Boundary",
            "Critical Boundary Flow",
            "geometry_number",
        },
    }

    columns_to_drop = omit_columns.get(df_type, set())
    existing_columns_to_drop = [col for col in columns_to_drop if col in df.columns]

    if existing_columns_to_drop:
        filtered_df = df.drop(columns=existing_columns_to_drop)
        return filtered_df, len(existing_columns_to_drop)
    return df, 0


def dataframe_to_text(
    df: pd.DataFrame,
    name: str,
    df_type: str | None = None,
    showmore: bool = False,
) -> str:
    """Convert a pandas DataFrame to a formatted text string with optional column filtering."""
    if df is None or df.empty:
        return f"\n{name}: No data available\n"

    display_df = df
    omitted_count = 0
    if df_type and not showmore:
        display_df, omitted_count = filter_dataframe_columns(df, df_type, showmore)

    buffer = io.StringIO()
    display_df.to_string(buf=buffer, max_rows=100, max_cols=None)

    result = f"\n{name}:"
    if omitted_count > 0:
        result += f" ({omitted_count} columns omitted - use showmore=True to see all)"
    result += f"\n{buffer.getvalue()}\n"
    return result
