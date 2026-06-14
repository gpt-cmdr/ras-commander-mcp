#!/usr/bin/env python3
"""
HEC-RAS MCP Server

An MCP server that provides tools for querying HEC-RAS project information
using the ras-commander library.
"""

import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import urlsplit, quote
import pandas as pd
import io

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

# Import ras-commander
try:
    from ras_commander import (
        init_ras_project,
        HdfBase,
        HdfPlan,
        HdfResultsMesh,
        HdfResultsPlan,
        HdfResultsXsec,
        RasPlan,
    )
    import h5py
    import numpy as np
except ImportError:
    raise ImportError("ras-commander is not installed. Please install it with: pip install ras-commander")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the FastMCP server
mcp = FastMCP(
    name="RAS Commander",
    version="0.2.0",
    instructions="HEC-RAS MCP server powered by ras-commander. By CLB Engineering Corporation.",
)

# Configuration
DEFAULT_RAS_VERSION = "6.6"
HECRAS_VERSION = os.environ.get("HECRAS_VERSION", DEFAULT_RAS_VERSION)
HECRAS_PATH = os.environ.get("HECRAS_PATH", None)

# Docs retrieval configuration (read-only, network-backed)
DEFAULT_DOCS_URL = "https://rascommander.info"
DOCS_BASE_URL = os.environ.get("RASCOMMANDER_DOCS_URL", DEFAULT_DOCS_URL).rstrip("/")
DOCS_HTTP_TIMEOUT = 10.0  # seconds
DOCS_CACHE_TTL = 15 * 60  # seconds (15 minutes)

# Module-level caches: {url_key: (fetch_time, payload)}
_SEARCH_INDEX_CACHE: dict[str, tuple[float, Any]] = {}
_LLMS_FULL_CACHE: dict[str, tuple[float, str]] = {}

RAS_COMMANDER_REPO_URL = "https://github.com/gpt-cmdr/ras-commander"
MCP_SCOPE_TIP = (
    "Tip: this MCP exposes a subset of ras-commander. For full functionality "
    "(custom queries, batch runs, notebooks), use the ras-commander library "
    f"directly with a local agent: {RAS_COMMANDER_REPO_URL}"
)
_NO_SCOPE_TIP_PREFIXES = (
    "Error ",
    "Error:",
    "HDF file not found:",
    "Compute messages not found.",
    "Unexpected data type",
    "No documentation matches found",
)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_ras_version_info():
    """Get the configured HEC-RAS version or path for display."""
    if HECRAS_PATH:
        return f"HEC-RAS Path: {HECRAS_PATH}"
    else:
        return f"HEC-RAS Version: {HECRAS_VERSION}"


def _init_project(project_path: str) -> tuple[Path, Any]:
    """Validate path and initialise HEC-RAS project. Raises ToolError on failure."""
    path = Path(project_path)
    if not path.exists() or not path.is_dir():
        raise ToolError(f"The specified project folder does not exist or is not a directory: {path}")
    ras_version = HECRAS_PATH if HECRAS_PATH else HECRAS_VERSION
    logger.info(f"Initializing HEC-RAS project at: {path}")
    ras = init_ras_project(path, ras_version)
    return path, ras


def _resolve_plan_hdf_path(project_path: Path, plan_number: str, ras) -> Path:
    """Resolve plan number to HDF path. Raises ToolError if not found."""
    # Handle single-digit plan numbers
    if plan_number.isdigit() and len(plan_number) == 1:
        plan_number = plan_number.zfill(2)

    # Check if plan_number is a full path to an HDF file
    if plan_number.endswith('.hdf') and Path(plan_number).exists():
        return Path(plan_number)

    plan_hdf_path = None

    # Look up in plan_df
    if hasattr(ras, 'plan_df') and ras.plan_df is not None:
        plan_row = ras.plan_df[ras.plan_df['plan_number'] == plan_number]
        if not plan_row.empty and 'HDF_Results_Path' in plan_row.columns:
            hdf_rel_path = plan_row['HDF_Results_Path'].iloc[0]
            if hdf_rel_path:
                plan_hdf_path = project_path / hdf_rel_path

    # Fallback: try common HEC-RAS naming patterns
    if not plan_hdf_path:
        project_name = project_path.name
        potential_paths = [
            project_path / f"{project_name}.p{plan_number}.hdf",
            project_path / f"*.p{plan_number}.hdf"
        ]
        for pattern in potential_paths:
            if '*' in str(pattern):
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
        with h5py.File(hdf_path, 'r') as hdf_file:
            compute_messages_path = '/Results/Summary/Compute Messages (text)'

            if compute_messages_path not in hdf_file:
                return "Compute messages not found. The simulation may not have completed or results were not saved properly."

            compute_messages_dataset = hdf_file[compute_messages_path]

            if isinstance(compute_messages_dataset, h5py.Dataset):
                data = compute_messages_dataset[()]

                if isinstance(data, bytes):
                    messages_text = data.decode('utf-8')
                elif isinstance(data, np.ndarray):
                    if data.dtype.kind == 'S':
                        messages_text = '\n'.join([item.decode('utf-8') if isinstance(item, bytes) else str(item)
                                                   for item in data])
                    else:
                        messages_text = str(data)
                else:
                    messages_text = str(data)
            else:
                return f"Unexpected data type for compute messages: {type(compute_messages_dataset)}"

            formatted_output = format_compute_messages_local(messages_text, str(hdf_path))

            # Truncate if necessary (~10k tokens ≈ 40k chars)
            max_chars = 10000 * 4
            if len(formatted_output) > max_chars:
                lines = formatted_output.split('\n')
                last_50_lines = lines[-50:] if len(lines) > 50 else lines
                last_50_text = '\n'.join(last_50_lines)
                truncation_notice = "\n\n[OUTPUT TRUNCATED: Response exceeded 10,000 tokens. Showing beginning and last 50 lines.]\n\n"
                available_chars = max_chars - len(last_50_text) - len(truncation_notice)
                truncated_beginning = formatted_output[:available_chars]
                last_newline = truncated_beginning.rfind('\n')
                if last_newline > 0:
                    truncated_beginning = truncated_beginning[:last_newline]
                formatted_output = truncated_beginning + truncation_notice + last_50_text

            return formatted_output

    except FileNotFoundError:
        return f"HDF file not found: {hdf_path}"
    except Exception as e:
        logger.error(f"Error reading compute messages: {str(e)}")
        return f"Error reading compute messages: {str(e)}"


def format_compute_messages_local(messages_text: str, hdf_file_path: str) -> str:
    """Format compute messages for better readability.
    Stops processing when reaching "Computation Tasks:" section.
    """
    lines = messages_text.split('\r\n') if '\r\n' in messages_text else messages_text.split('\n')

    formatted_parts = [
        f"Compute Messages from: {Path(hdf_file_path).name}",
        "=" * 80,
        ""
    ]

    general_messages = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if 'Computation Task' in line and '\t' in line:
            break
        elif 'Computation Speed' in line and '\t' in line:
            break
        else:
            general_messages.append(line)

    if general_messages:
        formatted_parts.append("General Messages:")
        formatted_parts.append("-" * 40)
        for msg in general_messages:
            if ':' in msg and not msg.startswith('http'):
                key, value = msg.split(':', 1)
                formatted_parts.append(f"{key.strip():40} : {value.strip()}")
            else:
                formatted_parts.append(msg)

    return '\n'.join(formatted_parts)


def truncate_output(text: str, max_tokens: int = 10000) -> str:
    """Truncate output to maximum tokens and add notice if truncated."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    truncated_text = text[:max_chars]
    last_space = truncated_text.rfind(' ')
    if last_space > max_chars * 0.9:
        truncated_text = truncated_text[:last_space]
    return truncated_text + "\n\n[OUTPUT TRUNCATED: Response exceeded 10,000 tokens. Please use a more specific query for complete results.]"


def _should_append_scope_tip(text: str) -> bool:
    """Return True when a tool response is substantive enough for the scope tip."""
    stripped = text.strip()
    if not stripped:
        return False
    if any(stripped.startswith(prefix) for prefix in _NO_SCOPE_TIP_PREFIXES):
        return False
    if "\n" not in stripped and len(stripped) < 160:
        return False
    return True


def _append_scope_tip(text: str) -> str:
    """Append the ras-commander scope tip to substantive MCP responses."""
    if not _should_append_scope_tip(text):
        return text
    return f"{text.rstrip()}\n\n{MCP_SCOPE_TIP}"


def _format_tool_response(text: str, max_tokens: int = 10000, apply_truncation: bool = True) -> str:
    """Format a substantive tool response, preserving truncation before the footer."""
    output = truncate_output(text, max_tokens=max_tokens) if apply_truncation else text
    return _append_scope_tip(output)


def _format_response_parts(response_parts: Iterable[str], max_tokens: int = 10000) -> str:
    """Join response parts and apply shared tool response formatting."""
    return _format_tool_response("\n".join(response_parts), max_tokens=max_tokens)


def filter_dataframe_columns(df: pd.DataFrame, df_type: str, showmore: bool = False) -> tuple[pd.DataFrame, int]:
    """Filter DataFrame columns for default vs verbose output."""
    if df is None or df.empty or showmore:
        return df, 0

    omit_columns = {
        'plan_df': {
            'Geom File', 'Flow File', 'full_path', 'Geom Path', 'Flow Path',
            'Computation Interval', 'Output Interval', 'Instantaneous Interval',
            'Mapping Interval', 'Detailed Interval', 'HDF Compression',
            'Computation Threads', 'Tolerated Iterations', 'WS Tolerance',
            'Flow Tolerance', 'Computation Mode', 'Mixed Flow', 'Computation Level',
            'Run WQNet'
        },
        'geom_df': {'full_path', 'hdf_path'},
        'flow_df': {'full_path', 'Number of Profiles', 'River Stations'},
        'unsteady_df': {
            'full_path', 'Initial Conditions', 'Flow Multiplier',
            'Base Flow', 'Wave Celerity'
        },
        'boundaries_df': {
            'full_path', 'hydrograph_data', 'hydrograph_data_path',
            'hydrograph_units', 'hydrograph_description', 'bc_data_path',
            'hydrograph_values', 'Is Critical Boundary', 'Critical Boundary Flow',
            'geometry_number'
        }
    }

    columns_to_drop = omit_columns.get(df_type, set())
    existing_columns_to_drop = [col for col in columns_to_drop if col in df.columns]

    if existing_columns_to_drop:
        filtered_df = df.drop(columns=existing_columns_to_drop)
        return filtered_df, len(existing_columns_to_drop)
    else:
        return df, 0


def dataframe_to_text(df: pd.DataFrame, name: str, df_type: str = None, showmore: bool = False) -> str:
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


def _decode_hdf_value(value: Any) -> Any:
    """Decode common HDF scalar/string values for display."""
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8", errors="ignore").strip()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        if value.size == 0:
            return ""
        if value.size == 1:
            return _decode_hdf_value(value.flat[0])
        return [_decode_hdf_value(item) for item in value.tolist()]
    return value


def _format_cell_value(value: Any) -> Any:
    """Convert values that do not render cleanly in pandas text tables."""
    value = _decode_hdf_value(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        preview = ", ".join(str(item) for item in value[:5])
        if len(value) > 5:
            preview += f", ... ({len(value)} items)"
        return preview
    return value


def _normalize_key(value: Any) -> str:
    """Normalize names for loose matching of HEC-RAS variable/column labels."""
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _coerce_max_rows(max_rows: int, default: int = 100, upper: int = 1000) -> int:
    """Keep result tables bounded for LLM-friendly MCP responses."""
    try:
        value = int(max_rows)
    except (TypeError, ValueError):
        value = default
    return max(1, min(value, upper))


def _prepare_dataframe_for_output(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with geometry and byte/object values simplified for text output."""
    if df is None:
        return df

    output_df = df.copy()

    if "geometry" in output_df.columns:
        geometry = output_df["geometry"]
        x_values = []
        y_values = []
        point_geometry = True
        for geom in geometry:
            if geom is None:
                x_values.append(np.nan)
                y_values.append(np.nan)
            elif hasattr(geom, "x") and hasattr(geom, "y"):
                x_values.append(geom.x)
                y_values.append(geom.y)
            else:
                point_geometry = False
                break

        if point_geometry:
            output_df["x"] = x_values
            output_df["y"] = y_values
        else:
            output_df["geometry_wkt"] = geometry.map(
                lambda geom: "" if geom is None else str(geom)[:160]
            )
        output_df = output_df.drop(columns=["geometry"])

    for column in output_df.columns:
        if pd.api.types.is_object_dtype(output_df[column]) or pd.api.types.is_string_dtype(output_df[column]):
            output_df[column] = output_df[column].map(_format_cell_value)

    return output_df


def dataframe_to_text_limited(
    df: pd.DataFrame,
    name: str,
    max_rows: int = 100,
    max_cols: int | None = None,
) -> str:
    """Convert a DataFrame to bounded text, preserving total row counts."""
    if df is None or df.empty:
        return f"\n{name}: No data available\n"

    max_rows = _coerce_max_rows(max_rows)
    display_df = _prepare_dataframe_for_output(df)
    total_rows = len(display_df)
    shown_df = display_df.head(max_rows)

    buffer = io.StringIO()
    shown_df.to_string(buf=buffer, index=False, max_rows=max_rows, max_cols=max_cols)

    result = f"\n{name}:"
    if total_rows > max_rows:
        result += f" showing first {max_rows} of {total_rows} rows"
    else:
        result += f" {total_rows} rows"
    result += f"\n{buffer.getvalue()}\n"
    return result


def _parse_variables(
    variables: str | Sequence[str] | None,
    default_variables: Sequence[str],
    aliases: dict[str, str],
) -> list[str]:
    """Parse comma-separated variables and normalize common aliases."""
    if variables is None:
        raw_variables = list(default_variables)
    elif isinstance(variables, str):
        raw_variables = [item.strip() for item in variables.split(",") if item.strip()]
    else:
        raw_variables = [str(item).strip() for item in variables if str(item).strip()]

    if not raw_variables:
        raw_variables = list(default_variables)

    parsed = []
    for variable in raw_variables:
        normalized = _normalize_key(variable)
        parsed.append(aliases.get(normalized, variable))

    deduped = []
    for variable in parsed:
        if variable not in deduped:
            deduped.append(variable)
    return deduped


def _is_max_profile(profile: str | None) -> bool:
    """Return whether a profile selector requests maximum-over-time output."""
    if profile is None:
        return True
    return str(profile).strip().lower() in {"", "max", "maximum", "peak"}


def _select_xarray_time_profile(data_array: Any, profile: str | None) -> tuple[Any, str]:
    """Select a time profile from an xarray object or return max-over-time."""
    if "time" not in getattr(data_array, "dims", ()):
        return data_array, "no time dimension"

    times = pd.to_datetime(data_array.coords["time"].values)
    if len(times) == 0:
        return data_array, "no output time steps"

    if _is_max_profile(profile):
        return data_array.max(dim="time", skipna=True), "maximum across all output time steps"

    profile_text = str(profile).strip()
    try:
        index = int(profile_text)
        if index < 0 or index >= len(times):
            raise ToolError(
                f"Profile index {index} is out of range. Valid range is 0 to {len(times) - 1}."
            )
    except ValueError:
        try:
            target_time = pd.to_datetime(profile_text)
        except Exception as exc:
            raise ToolError(
                f"Profile '{profile}' is not a valid output index or datetime. "
                "Use list_profiles to see valid profile values."
            ) from exc

        time_index = pd.DatetimeIndex(times)
        exact_matches = np.where(time_index == target_time)[0]
        if len(exact_matches) > 0:
            index = int(exact_matches[0])
        else:
            index = int(time_index.get_indexer([target_time], method="nearest")[0])

    selected_time = times[index]
    return data_array.isel(time=index), f"profile index {index} ({selected_time})"


def _merge_result_frames(frames: Iterable[pd.DataFrame], value_columns: Sequence[str]) -> pd.DataFrame:
    """Outer-merge xarray-derived frames without duplicating shared coordinates."""
    result = None
    value_column_set = set(value_columns)
    for frame in frames:
        if frame is None or frame.empty:
            continue
        if result is None:
            result = frame
            continue

        merge_keys = [
            column
            for column in result.columns
            if column in frame.columns and column not in value_column_set
        ]
        result = pd.merge(result, frame, on=merge_keys, how="outer")

    return result if result is not None else pd.DataFrame()


def _dataarray_to_dataframe(data_array: Any, output_column: str, profile: str | None) -> tuple[pd.DataFrame, str]:
    """Convert a result DataArray to a DataFrame after applying profile selection."""
    selected, selection_label = _select_xarray_time_profile(data_array, profile)
    frame = selected.to_dataframe(name=output_column).reset_index()
    return frame, selection_label


def _find_matching_column(df: pd.DataFrame, candidates: Sequence[str]) -> str | None:
    """Find a DataFrame column by exact or loose normalized label matching."""
    if df is None or df.empty:
        return None

    normalized_columns = {_normalize_key(column): column for column in df.columns}
    for candidate in candidates:
        match = normalized_columns.get(_normalize_key(candidate))
        if match is not None:
            return match

    for candidate in candidates:
        normalized_candidate = _normalize_key(candidate)
        for column in df.columns:
            normalized_column = _normalize_key(column)
            if normalized_column.endswith("time"):
                continue
            if normalized_candidate in normalized_column:
                return column
    return None


def _row_label(row: pd.Series, columns: Sequence[str]) -> str:
    """Build a compact location label from selected row fields."""
    parts = []
    for column in columns:
        if column in row and pd.notna(row[column]):
            parts.append(f"{column}={row[column]}")
    return ", ".join(parts)


def _add_max_metric_from_dataframe(
    metrics: list[dict[str, Any]],
    df: pd.DataFrame,
    metric: str,
    candidates: Sequence[str],
    source: str,
    location_columns: Sequence[str],
) -> bool:
    """Append the maximum value from a matching DataFrame column to metrics."""
    column = _find_matching_column(df, candidates)
    if column is None:
        return False

    values = pd.to_numeric(df[column], errors="coerce")
    if values.dropna().empty:
        return False

    row_index = values.idxmax()
    row = df.loc[row_index]
    time_column = _find_matching_column(
        pd.DataFrame([row]),
        [f"{column}_time", "time", "peak_time", "maximum_time"],
    )

    metrics.append({
        "metric": metric,
        "value": values.loc[row_index],
        "source": source,
        "location": _row_label(row, location_columns),
        "time": row[time_column] if time_column and time_column in row else "",
    })
    return True


def _add_peak_metric_from_dataarray(
    metrics: list[dict[str, Any]],
    data_array: Any,
    metric: str,
    source: str,
) -> bool:
    """Append the maximum value from a DataArray to metrics."""
    values = np.asarray(data_array.values, dtype=float)
    if values.size == 0 or np.all(np.isnan(values)):
        return False

    flat_index = int(np.nanargmax(values))
    indices = np.unravel_index(flat_index, values.shape)
    dim_positions = dict(zip(data_array.dims, indices))

    location_parts = []
    time_value = ""
    for dim, position in dim_positions.items():
        if dim in data_array.coords:
            coord_value = data_array.coords[dim].values[position]
        else:
            coord_value = position

        if dim == "time":
            time_value = pd.to_datetime(coord_value)
        else:
            location_parts.append(f"{dim}={coord_value}")

    if "cross_section" in dim_positions:
        xs_position = dim_positions["cross_section"]
        for coord_name in ("River", "Reach", "Station", "Name"):
            if coord_name in data_array.coords:
                coord = data_array.coords[coord_name]
                if "cross_section" in coord.dims:
                    location_parts.append(f"{coord_name}={coord.values[xs_position]}")

    metrics.append({
        "metric": metric,
        "value": float(values[indices]),
        "source": source,
        "location": ", ".join(location_parts),
        "time": time_value,
    })
    return True


def _hdf_contains_any_path(hdf_path: Path, paths: Sequence[str]) -> bool:
    """Return whether any requested path is present in an HDF file."""
    with h5py.File(hdf_path, "r") as hdf_file:
        return any(path in hdf_file for path in paths)


def _ensure_results_available(hdf_path: Path) -> None:
    """Raise a ToolError when a plan HDF has no computed result groups."""
    try:
        has_results = _hdf_contains_any_path(hdf_path, ["Results/Unsteady", "Results/Steady"])
    except OSError as exc:
        raise ToolError(f"Unable to open plan results HDF file: {hdf_path}. {exc}") from exc

    if not has_results:
        raise ToolError(
            f"No computed steady or unsteady results were found in {hdf_path}. "
            "The plan may be uncomputed, incomplete, or saved without results."
        )


def _collect_output_profiles(hdf_path: Path) -> pd.DataFrame:
    """Collect steady profile names and unsteady output timestamps for a plan HDF."""
    rows = []

    try:
        if HdfResultsPlan.is_steady_plan(hdf_path):
            for index, profile_name in enumerate(HdfResultsPlan.get_steady_profile_names(hdf_path)):
                rows.append({
                    "result_type": "steady",
                    "profile_index": index,
                    "profile": profile_name,
                    "time": "",
                })
    except Exception as exc:
        logger.info(f"Steady profiles not available for {hdf_path}: {exc}")

    try:
        with h5py.File(hdf_path, "r") as hdf_file:
            has_unsteady = "Results/Unsteady" in hdf_file
        if has_unsteady:
            timestamps = HdfPlan.get_plan_timestamps_list(hdf_path)
            for index, timestamp in enumerate(timestamps):
                rows.append({
                    "result_type": "unsteady",
                    "profile_index": index,
                    "profile": str(timestamp),
                    "time": timestamp,
                })
    except Exception as exc:
        logger.info(f"Unsteady profiles not available for {hdf_path}: {exc}")
        try:
            time_paths = [
                "Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/Time Date Stamp (ms)",
                "Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/Time Date Stamp",
                "Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/Time",
            ]
            with h5py.File(hdf_path, "r") as hdf_file:
                for time_path in time_paths:
                    if time_path not in hdf_file:
                        continue
                    values = hdf_file[time_path][()]
                    for index, value in enumerate(np.ravel(values)):
                        decoded_value = _decode_hdf_value(value)
                        rows.append({
                            "result_type": "unsteady",
                            "profile_index": index,
                            "profile": str(decoded_value),
                            "time": decoded_value,
                        })
                    break
        except Exception as fallback_exc:
            logger.info(f"Fallback unsteady profile scan failed for {hdf_path}: {fallback_exc}")

    return pd.DataFrame(rows)


MESH_RESULT_ALIASES = {
    "wsel": "Water Surface",
    "wse": "Water Surface",
    "watersurface": "Water Surface",
    "watersurfaceelevation": "Water Surface",
    "depth": "Depth",
    "velocity": "Velocity",
    "velocityx": "Velocity X",
    "velocityy": "Velocity Y",
    "froude": "Froude Number",
    "froudenumber": "Froude Number",
}

XSEC_RESULT_ALIASES = {
    "wsel": "Water_Surface",
    "wse": "Water_Surface",
    "watersurface": "Water_Surface",
    "watersurfaceelevation": "Water_Surface",
    "flow": "Flow",
    "velocity": "Velocity_Total",
    "velocitytotal": "Velocity_Total",
    "velocitychannel": "Velocity_Channel",
    "laterflow": "Flow_Lateral",
    "flowlateral": "Flow_Lateral",
}


# ---------------------------------------------------------------------------
# Docs retrieval helpers (live fetch from rascommander.info)
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    """Strip HTML tags / collapse whitespace from a search-index text blob."""
    no_tags = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", no_tags).strip()


def _normalize_doc_path(path: str) -> str:
    """Normalize and SANITIZE a docs page path to a safe relative slug.

    Rejects anything that could redirect the fetch off the docs base or inject a
    query/fragment: absolute URLs (scheme/netloc), protocol-relative ``//host``,
    ``..`` traversal, backslashes, query (``?``), fragment (``#``), userinfo
    (``@``), and control characters. Each path segment is percent-encoded.

    Raises ToolError on invalid input. Returns a clean ``a/b/c`` slug (no
    leading/trailing slash; trailing ``index.md``/``.md`` stripped).
    """
    if not isinstance(path, str):
        raise ToolError("Documentation path must be a string.")
    raw = path.strip()
    # Reject obvious injection vectors up front.
    if (
        "\\" in raw
        or "?" in raw
        or "#" in raw
        or "@" in raw
        or "://" in raw
        or raw.startswith("//")
        or any(ord(c) < 0x20 for c in raw)
    ):
        raise ToolError(
            f"Invalid documentation path {path!r}: must be a relative docs slug "
            "(e.g. 'reference/dataframe-reference'), not a URL or query."
        )
    # urlsplit catches any remaining scheme/netloc.
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise ToolError(
            f"Invalid documentation path {path!r}: only a relative docs slug is allowed."
        )
    p = parts.path.strip().strip("/")
    if p.endswith("/index.md"):
        p = p[: -len("/index.md")]
    elif p.endswith(".md"):
        p = p[: -len(".md")]
    p = p.strip("/")
    if not p:
        return ""
    safe_segments = []
    for seg in p.split("/"):
        if seg in ("", ".", ".."):
            raise ToolError(
                f"Invalid documentation path {path!r}: path traversal segments are not allowed."
            )
        safe_segments.append(quote(seg, safe=""))
    return "/".join(safe_segments)


def _assert_same_origin(resp: "httpx.Response") -> None:
    """Raise ToolError if a (possibly redirected) response left the docs base origin."""
    final = urlsplit(str(resp.url))
    base = urlsplit(DOCS_BASE_URL)
    if (final.scheme, final.netloc) != (base.scheme, base.netloc):
        raise ToolError(
            f"Refusing docs response from off-origin URL {resp.url} "
            f"(expected origin {base.scheme}://{base.netloc})."
        )


def _get_search_index() -> list[dict]:
    """Fetch and cache the mkdocs Material search index. Raises ToolError on failure."""
    url = f"{DOCS_BASE_URL}/search/search_index.json"
    cached = _SEARCH_INDEX_CACHE.get(url)
    now = time.time()
    if cached and (now - cached[0]) < DOCS_CACHE_TTL:
        return cached[1]
    try:
        resp = httpx.get(url, timeout=DOCS_HTTP_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise ToolError(
            f"Failed to fetch docs search index from {url}: {e}. "
            f"This tool requires network access to {DOCS_BASE_URL}."
        )
    docs = data.get("docs", []) if isinstance(data, dict) else []
    _SEARCH_INDEX_CACHE[url] = (now, docs)
    return docs


def _get_llms_full() -> Optional[str]:
    """Fetch and cache llms-full.txt. Returns None (not an error) if unavailable."""
    url = f"{DOCS_BASE_URL}/llms-full.txt"
    cached = _LLMS_FULL_CACHE.get(url)
    now = time.time()
    if cached and (now - cached[0]) < DOCS_CACHE_TTL:
        return cached[1]
    try:
        resp = httpx.get(url, timeout=DOCS_HTTP_TIMEOUT, follow_redirects=True)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        text = resp.text
    except Exception:
        return None
    _LLMS_FULL_CACHE[url] = (now, text)
    return text


def _score_doc(query_terms: list[str], title: str, text: str) -> float:
    """Deterministic relevance score for a doc entry against query terms."""
    title_l = title.lower()
    text_l = text.lower()
    score = 0.0
    for term in query_terms:
        # Title matches weigh heavily; text matches weigh by frequency (capped).
        if term in title_l:
            score += 10.0
        text_hits = text_l.count(term)
        if text_hits:
            score += min(text_hits, 5)
    # Small bonus for matching all terms in the title (phrase relevance).
    if query_terms and all(t in title_l for t in query_terms):
        score += 5.0
    return score


def _extract_llms_full_section(llms_full: str, norm_path: str) -> Optional[str]:
    """
    Extract the section of llms-full.txt corresponding to ``norm_path``.

    llms-full.txt concatenates curated pages. mkdocs-llmstxt emits each page's
    source URL on a heading/comment line; we locate the line that references the
    page path EXACTLY, then return text up to the next page-boundary marker.
    Returns None if no exact page boundary is found (caller then falls back to the
    markdown mirror / rendered page) -- we never return a different page's content.
    """
    if not llms_full or not norm_path:
        return None

    lines = llms_full.splitlines()
    # Candidate boundary lines: those that look like a page URL or path reference.
    # Match either the full URL or the path itself appearing on a heading/source line.
    path_variants = {norm_path, f"{norm_path}/", f"/{norm_path}/", f"{norm_path}/index.md"}

    boundary_indices = []  # (line_index, is_target)
    for i, line in enumerate(lines):
        stripped = line.strip()
        # A boundary is a line that references a page path/URL. Heuristics:
        # - contains the docs base URL followed by a path
        # - or is a top-level markdown heading that contains a path-like token
        is_boundary = False
        if DOCS_BASE_URL in line:
            is_boundary = True
        elif re.match(r"^#{1,2}\s", line) and ("/" in stripped or stripped.startswith("# ")):
            is_boundary = True
        if is_boundary:
            line_l = line.lower()
            # Require an EXACT path/URL match on the boundary line. A weak
            # last-segment heading heuristic was removed: it could return a
            # different page's content mislabeled as the requested page. If no
            # exact boundary is found we return None and the caller falls back.
            is_target = any(pv.lower() in line_l for pv in path_variants)
            boundary_indices.append((i, is_target))

    if not boundary_indices:
        return None

    # Find the target boundary, then slice to the next boundary.
    for idx, (line_i, is_target) in enumerate(boundary_indices):
        if is_target:
            start = line_i
            end = boundary_indices[idx + 1][0] if idx + 1 < len(boundary_indices) else len(lines)
            section = "\n".join(lines[start:end]).strip()
            if section:
                return section
    return None


def _fetch_rendered_page(norm_path: str) -> str:
    """Final fallback: fetch the rendered HTML page and return its text. Raises ToolError."""
    url = f"{DOCS_BASE_URL}/{norm_path}/" if norm_path else f"{DOCS_BASE_URL}/"
    try:
        resp = httpx.get(url, timeout=DOCS_HTTP_TIMEOUT, follow_redirects=True)
        _assert_same_origin(resp)
        resp.raise_for_status()
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(
            f"Failed to fetch docs page '{norm_path}' from {url}: {e}. "
            f"This tool requires network access to {DOCS_BASE_URL}."
        )
    # Strip <head>, scripts, styles, then tags, to yield readable text.
    html = resp.text
    html = re.sub(r"(?is)<head\b.*?</head>", " ", html)
    html = re.sub(r"(?is)<script\b.*?</script>", " ", html)
    html = re.sub(r"(?is)<style\b.*?</style>", " ", html)
    html = re.sub(r"(?is)<nav\b.*?</nav>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations={"readOnlyHint": True})
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
        "=" * 80
    ]

    # Project file contents
    if show_rasprj and hasattr(ras, 'prj_file') and ras.prj_file:
        try:
            with open(ras.prj_file, 'r', encoding='utf-8') as f:
                prj_content = f.read()

            excluded_prefixes = [
                'Geom File=', 'Flow File=', 'Unsteady File=', 'Plan File=',
                'DSS Export Filename=', 'DSS Export Rating Curves=', 'DSS Export Rating Curve Sorted=',
                'DSS Export Volume Flow Curves=', 'DXF Filename=', 'DXF OffsetX=', 'DXF OffsetY=',
                'DXF ScaleX=', 'DXF ScaleY=', 'GIS Export Profiles='
            ]
            filtered_lines = [
                line for line in prj_content.splitlines()
                if not any(line.strip().startswith(prefix) for prefix in excluded_prefixes)
            ]

            response_parts.append("\nPROJECT FILE CONTENTS (.prj):")
            response_parts.append("-" * 40)
            response_parts.append('\n'.join(filtered_lines))
            response_parts.append("=" * 80)
        except Exception as e:
            logger.error(f"Error reading project file: {str(e)}")
            response_parts.append("\nPROJECT FILE: Error reading file")
            response_parts.append("=" * 80)

    if show_plan_df and hasattr(ras, 'plan_df') and ras.plan_df is not None:
        response_parts.append(dataframe_to_text(ras.plan_df, "PLANS", "plan_df", showmore))

    if show_geom_df and hasattr(ras, 'geom_df') and ras.geom_df is not None:
        response_parts.append(dataframe_to_text(ras.geom_df, "GEOMETRIES", "geom_df", showmore))

    if show_flow_df and hasattr(ras, 'flow_df') and ras.flow_df is not None:
        response_parts.append(dataframe_to_text(ras.flow_df, "STEADY FLOWS", "flow_df", showmore))

    if show_unsteady_df and hasattr(ras, 'unsteady_df') and ras.unsteady_df is not None:
        response_parts.append(dataframe_to_text(ras.unsteady_df, "UNSTEADY FLOWS", "unsteady_df", showmore))

    if show_boundaries and hasattr(ras, 'boundaries_df') and ras.boundaries_df is not None:
        response_parts.append(dataframe_to_text(ras.boundaries_df, "BOUNDARY CONDITIONS", "boundaries_df", showmore))

    if show_rasmap and hasattr(ras, 'rasmap_df') and ras.rasmap_df is not None:
        response_parts.append(dataframe_to_text(ras.rasmap_df, "RASMAP CONFIGURATION", "rasmap_df", showmore))

    return _format_response_parts(response_parts)


@mcp.tool(annotations={"readOnlyHint": True})
def read_plan_description(project_path: str, plan_number: str) -> str:
    """Read the multi-line description block from a HEC-RAS plan file. Part of the RAS Commander MCP suite by CLB Engineering Corporation."""
    path, ras = _init_project(project_path)

    # Handle single-digit plan numbers
    if plan_number.isdigit() and len(plan_number) == 1:
        plan_number = plan_number.zfill(2)

    try:
        description = RasPlan.read_plan_description(plan_number, ras)
    except ValueError:
        raise ToolError(f"Plan '{plan_number}' not found in project")

    response_parts = [
        f"Plan Description for Plan {plan_number}",
        f"Project: {ras.project_name}",
        "=" * 80,
        "",
        description if description else "[No description found]",
        ""
    ]
    return _format_response_parts(response_parts)


@mcp.tool(annotations={"readOnlyHint": True})
def get_plan_results_summary(project_path: str, plan_number: str) -> str:
    """Get comprehensive results summary from a HEC-RAS plan including unsteady info, volume accounting, and runtime data. Powered by ras-commander library."""
    path, ras = _init_project(project_path)
    plan_hdf_path = _resolve_plan_hdf_path(path, plan_number, ras)

    response_parts = [
        f"Plan Results Summary: {plan_number}",
        f"HDF Path: {plan_hdf_path}",
        "=" * 80
    ]

    try:
        unsteady_info = HdfResultsPlan.get_unsteady_info(plan_hdf_path)
        response_parts.append(dataframe_to_text(unsteady_info, "UNSTEADY INFO"))
    except Exception as e:
        response_parts.append(f"\nUnsteady info not available: {str(e)}")

    try:
        unsteady_summary = HdfResultsPlan.get_unsteady_summary(plan_hdf_path)
        response_parts.append(dataframe_to_text(unsteady_summary, "UNSTEADY SUMMARY"))
    except Exception as e:
        response_parts.append(f"\nUnsteady summary not available: {str(e)}")

    try:
        volume_accounting = HdfResultsPlan.get_volume_accounting(plan_hdf_path)
        if volume_accounting is not None:
            response_parts.append(dataframe_to_text(volume_accounting, "VOLUME ACCOUNTING"))
        else:
            response_parts.append("\nVolume accounting not available")
    except Exception as e:
        response_parts.append(f"\nVolume accounting error: {str(e)}")

    try:
        runtime_data = HdfResultsPlan.get_runtime_data(plan_hdf_path)
        if runtime_data is not None:
            response_parts.append(dataframe_to_text(runtime_data, "RUNTIME DATA"))
        else:
            response_parts.append("\nRuntime data not available")
    except Exception as e:
        response_parts.append(f"\nRuntime data error: {str(e)}")

    return _format_response_parts(response_parts)


@mcp.tool(annotations={"readOnlyHint": True})
def list_profiles(project_path: str, plan_number: str) -> str:
    """List available output profiles/time steps for a computed HEC-RAS plan."""
    path, ras = _init_project(project_path)
    plan_hdf_path = _resolve_plan_hdf_path(path, plan_number, ras)
    _ensure_results_available(plan_hdf_path)

    profiles_df = _collect_output_profiles(plan_hdf_path)
    if profiles_df.empty:
        raise ToolError(
            f"No output profiles or time steps were found in {plan_hdf_path}. "
            "The plan may be uncomputed or may not contain profile output."
        )

    response_parts = [
        f"Output Profiles for Plan {plan_number}",
        f"HDF Path: {plan_hdf_path}",
        "=" * 80,
        dataframe_to_text_limited(profiles_df, "AVAILABLE PROFILES", max_rows=500),
        "Use profile_index values with get_mesh_results/get_xsec_results, or use profile='max' for maximum-over-time results.",
    ]
    return _format_response_parts(response_parts)


@mcp.tool(annotations={"readOnlyHint": True})
def get_plan_summary(project_path: str, plan_number: str, max_rows: int = 100) -> str:
    """Return plan-level result statistics including max WSEL, peak flow, volumes, and timing."""
    path, ras = _init_project(project_path)
    plan_hdf_path = _resolve_plan_hdf_path(path, plan_number, ras)
    _ensure_results_available(plan_hdf_path)

    max_rows = _coerce_max_rows(max_rows)
    response_parts = [
        f"Plan Results Summary: {plan_number}",
        f"HDF Path: {plan_hdf_path}",
        "=" * 80,
    ]
    metrics: list[dict[str, Any]] = []
    unavailable_sections: list[str] = []

    try:
        if HdfResultsPlan.is_steady_plan(plan_hdf_path):
            steady_info = HdfResultsPlan.get_steady_info(plan_hdf_path)
            response_parts.append(dataframe_to_text_limited(steady_info, "STEADY INFO", max_rows=5))

            steady_results = HdfResultsPlan.get_steady_results(plan_hdf_path)
            _add_max_metric_from_dataframe(
                metrics,
                steady_results,
                "Max 1D steady WSEL",
                ["wsel", "WSE", "Water Surface"],
                "HdfResultsPlan.get_steady_results",
                ["river", "reach", "node_id", "profile"],
            )
            _add_max_metric_from_dataframe(
                metrics,
                steady_results,
                "Peak 1D steady flow",
                ["flow", "Flow"],
                "HdfResultsPlan.get_steady_results",
                ["river", "reach", "node_id", "profile"],
            )
            _add_max_metric_from_dataframe(
                metrics,
                steady_results,
                "Max 1D steady velocity",
                ["velocity", "Velocity"],
                "HdfResultsPlan.get_steady_results",
                ["river", "reach", "node_id", "profile"],
            )
    except Exception as exc:
        unavailable_sections.append(f"Steady plan summary not available: {exc}")

    try:
        unsteady_info = HdfResultsPlan.get_unsteady_info(plan_hdf_path)
        response_parts.append(dataframe_to_text_limited(unsteady_info, "UNSTEADY INFO", max_rows=5))
    except Exception as exc:
        unavailable_sections.append(f"Unsteady info not available: {exc}")

    try:
        unsteady_summary = HdfResultsPlan.get_unsteady_summary(plan_hdf_path)
        response_parts.append(dataframe_to_text_limited(unsteady_summary, "UNSTEADY SUMMARY", max_rows=5))
    except Exception as exc:
        unavailable_sections.append(f"Unsteady summary not available: {exc}")

    try:
        volume_accounting = HdfResultsPlan.get_volume_accounting(plan_hdf_path)
        if volume_accounting is not None and not volume_accounting.empty:
            response_parts.append(dataframe_to_text_limited(volume_accounting, "VOLUME ACCOUNTING", max_rows=10))
        else:
            unavailable_sections.append("Volume accounting not available")
    except Exception as exc:
        unavailable_sections.append(f"Volume accounting not available: {exc}")

    try:
        runtime_data = HdfResultsPlan.get_runtime_data(plan_hdf_path)
        if runtime_data is not None and not runtime_data.empty:
            response_parts.append(dataframe_to_text_limited(runtime_data, "RUNTIME DATA", max_rows=10))
        else:
            unavailable_sections.append("Runtime data not available")
    except Exception as exc:
        unavailable_sections.append(f"Runtime data not available: {exc}")

    try:
        xsec_dataset = HdfResultsXsec.get_xsec_timeseries(plan_hdf_path)
        if getattr(xsec_dataset, "data_vars", None):
            xsec_metric_map = [
                ("Water_Surface", "Max 1D unsteady WSEL"),
                ("Flow", "Peak 1D unsteady flow"),
                ("Velocity_Total", "Max 1D unsteady velocity"),
            ]
            for variable, metric_name in xsec_metric_map:
                if variable in xsec_dataset:
                    _add_peak_metric_from_dataarray(
                        metrics,
                        xsec_dataset[variable],
                        metric_name,
                        "HdfResultsXsec.get_xsec_timeseries",
                    )
        else:
            unavailable_sections.append("1D cross-section time series not available")
    except Exception as exc:
        unavailable_sections.append(f"1D cross-section time series not available: {exc}")

    try:
        mesh_max_ws = HdfResultsMesh.get_mesh_max_ws(plan_hdf_path)
        if mesh_max_ws is not None and not mesh_max_ws.empty:
            _add_max_metric_from_dataframe(
                metrics,
                mesh_max_ws,
                "Max 2D mesh WSEL",
                ["maximum_water_surface", "Maximum Water Surface", "water_surface"],
                "HdfResultsMesh.get_mesh_max_ws",
                ["mesh_name", "cell_id"],
            )
        else:
            unavailable_sections.append("2D mesh max WSEL not available")
    except Exception as exc:
        unavailable_sections.append(f"2D mesh max WSEL not available: {exc}")

    try:
        mesh_max_depth = HdfResultsMesh.get_mesh_max_depth(plan_hdf_path)
        if mesh_max_depth is not None and not mesh_max_depth.empty:
            _add_max_metric_from_dataframe(
                metrics,
                mesh_max_depth,
                "Max 2D mesh depth",
                ["maximum_depth", "max_depth", "Depth"],
                "HdfResultsMesh.get_mesh_max_depth",
                ["mesh_name", "cell_id"],
            )
    except Exception as exc:
        unavailable_sections.append(f"2D mesh max depth not available: {exc}")

    try:
        mesh_max_velocity = HdfResultsMesh.get_mesh_max_face_v(plan_hdf_path)
        if mesh_max_velocity is not None and not mesh_max_velocity.empty:
            _add_max_metric_from_dataframe(
                metrics,
                mesh_max_velocity,
                "Max 2D face velocity",
                ["maximum_face_velocity", "Maximum Face Velocity", "face_velocity"],
                "HdfResultsMesh.get_mesh_max_face_v",
                ["mesh_name", "face_id"],
            )
    except Exception as exc:
        unavailable_sections.append(f"2D mesh max face velocity not available: {exc}")

    if metrics:
        response_parts.insert(
            3,
            dataframe_to_text_limited(pd.DataFrame(metrics), "PLAN SUMMARY METRICS", max_rows=max_rows),
        )
    else:
        response_parts.insert(
            3,
            "\nPLAN SUMMARY METRICS: No plan-level maxima were found in the available result groups.\n",
        )

    if unavailable_sections:
        response_parts.append("\nUnavailable result sections:")
        response_parts.extend(f"- {message}" for message in unavailable_sections)

    return _format_response_parts(response_parts)


@mcp.tool(annotations={"readOnlyHint": True})
def get_mesh_results(
    project_path: str,
    plan_number: str,
    profile: str = "max",
    mesh_name: str = "",
    variables: str = "Water Surface,Depth,Velocity",
    max_rows: int = 100,
) -> str:
    """Return 2D mesh cell results for a plan profile/time step or maximum-over-time profile."""
    path, ras = _init_project(project_path)
    plan_hdf_path = _resolve_plan_hdf_path(path, plan_number, ras)
    _ensure_results_available(plan_hdf_path)

    with h5py.File(plan_hdf_path, "r") as hdf_file:
        if "Results/Unsteady" not in hdf_file:
            raise ToolError(
                f"2D mesh time-series results were not found in {plan_hdf_path}. "
                "Mesh result extraction requires a computed unsteady plan with 2D output."
            )

    requested_variables = _parse_variables(
        variables,
        ["Water Surface", "Depth", "Velocity"],
        MESH_RESULT_ALIASES,
    )
    max_rows = _coerce_max_rows(max_rows)
    mesh_filter = mesh_name.strip() if mesh_name and mesh_name.strip().lower() != "all" else None

    frames_by_mesh: dict[str, list[pd.DataFrame]] = {}
    selection_labels: set[str] = set()
    unavailable_variables: list[str] = []

    for variable in requested_variables:
        try:
            datasets = HdfResultsMesh.get_mesh_cells_timeseries(
                plan_hdf_path,
                mesh_names=mesh_filter,
                var=variable,
                truncate=False,
                ras_object=ras,
            )
        except Exception as exc:
            unavailable_variables.append(f"{variable}: {exc}")
            continue

        if not datasets:
            unavailable_variables.append(f"{variable}: not found")
            continue

        for resolved_mesh_name, dataset in datasets.items():
            if variable not in dataset:
                unavailable_variables.append(f"{variable}: not found in mesh '{resolved_mesh_name}'")
                continue
            frame, selection_label = _dataarray_to_dataframe(dataset[variable], variable, profile)
            frame.insert(0, "mesh_name", resolved_mesh_name)
            frames_by_mesh.setdefault(resolved_mesh_name, []).append(frame)
            selection_labels.add(selection_label)

    if not frames_by_mesh:
        raise ToolError(
            f"No 2D mesh results were available for variables {requested_variables} in {plan_hdf_path}. "
            "Use get_hdf_structure to inspect result paths if the plan was computed."
        )

    response_parts = [
        f"2D Mesh Results for Plan {plan_number}",
        f"HDF Path: {plan_hdf_path}",
        f"Profile: {profile}",
        f"Selection: {'; '.join(sorted(selection_labels)) if selection_labels else 'not selected'}",
        f"Variables: {', '.join(requested_variables)}",
        "=" * 80,
    ]

    for resolved_mesh_name, frames in frames_by_mesh.items():
        merged = _merge_result_frames(frames, requested_variables)
        response_parts.append(
            dataframe_to_text_limited(
                merged,
                f"MESH RESULTS - {resolved_mesh_name}",
                max_rows=max_rows,
            )
        )

    if unavailable_variables:
        response_parts.append("\nUnavailable mesh variables:")
        response_parts.extend(f"- {message}" for message in unavailable_variables)

    return _format_response_parts(response_parts)


@mcp.tool(annotations={"readOnlyHint": True})
def get_xsec_results(
    project_path: str,
    plan_number: str,
    profile: str = "max",
    variables: str = "Water_Surface,Flow,Velocity_Total",
    max_rows: int = 100,
) -> str:
    """Return 1D cross-section WSEL, flow, and velocity results for a plan profile/time step."""
    path, ras = _init_project(project_path)
    plan_hdf_path = _resolve_plan_hdf_path(path, plan_number, ras)
    _ensure_results_available(plan_hdf_path)

    requested_variables = _parse_variables(
        variables,
        ["Water_Surface", "Flow", "Velocity_Total"],
        XSEC_RESULT_ALIASES,
    )
    max_rows = _coerce_max_rows(max_rows)

    try:
        is_steady = HdfResultsPlan.is_steady_plan(plan_hdf_path)
    except Exception:
        is_steady = False

    response_parts = [
        f"Cross-Section Results for Plan {plan_number}",
        f"HDF Path: {plan_hdf_path}",
        f"Profile: {profile}",
        f"Variables: {', '.join(requested_variables)}",
        "=" * 80,
    ]

    if is_steady:
        try:
            steady_results = HdfResultsPlan.get_steady_results(plan_hdf_path)
        except Exception as exc:
            raise ToolError(f"Steady cross-section results are not available: {exc}") from exc

        if not _is_max_profile(profile) and "profile" in steady_results.columns:
            profile_text = str(profile).strip()
            profile_values = list(dict.fromkeys(steady_results["profile"].astype(str)))
            if profile_text.isdigit():
                profile_index = int(profile_text)
                if profile_index < 0 or profile_index >= len(profile_values):
                    raise ToolError(
                        f"Steady profile index {profile_index} is out of range. "
                        f"Valid range is 0 to {len(profile_values) - 1}."
                    )
                profile_text = profile_values[profile_index]
            profile_mask = steady_results["profile"].astype(str).str.lower() == profile_text.lower()
            steady_results = steady_results.loc[profile_mask]
            if steady_results.empty:
                raise ToolError(
                    f"Steady profile '{profile}' was not found. Use list_profiles to see valid profile names."
                )

        steady_column_map = {
            "Water_Surface": "wsel",
            "Flow": "flow",
            "Velocity_Total": "velocity",
            "Velocity_Channel": "velocity",
        }
        selected_columns = ["river", "reach", "node_id", "profile"]
        value_columns = []
        for variable in requested_variables:
            mapped_column = steady_column_map.get(variable)
            if mapped_column and mapped_column in steady_results.columns:
                value_columns.append(mapped_column)

        selected_columns = [column for column in selected_columns if column in steady_results.columns]
        value_columns = [column for column in value_columns if column not in selected_columns]
        if not value_columns:
            raise ToolError(
                f"None of the requested variables were available in steady results: {requested_variables}"
            )

        response_parts.append(
            dataframe_to_text_limited(
                steady_results[selected_columns + value_columns],
                "STEADY CROSS-SECTION RESULTS",
                max_rows=max_rows,
            )
        )
        return _format_response_parts(response_parts)

    try:
        xsec_dataset = HdfResultsXsec.get_xsec_timeseries(plan_hdf_path)
    except Exception as exc:
        raise ToolError(
            f"1D cross-section results were not found in {plan_hdf_path}. "
            "The plan may not contain 1D output or may not be computed."
        ) from exc

    available_variables = [variable for variable in requested_variables if variable in xsec_dataset]
    if not available_variables:
        raise ToolError(
            f"None of the requested cross-section variables were found: {requested_variables}. "
            f"Available variables: {list(xsec_dataset.data_vars)}"
        )

    frames = []
    selection_labels = set()
    for variable in available_variables:
        frame, selection_label = _dataarray_to_dataframe(xsec_dataset[variable], variable, profile)
        frames.append(frame)
        selection_labels.add(selection_label)

    merged = _merge_result_frames(frames, available_variables)
    response_parts.insert(
        4,
        f"Selection: {'; '.join(sorted(selection_labels)) if selection_labels else 'not selected'}",
    )
    response_parts.append(
        dataframe_to_text_limited(
            merged,
            "UNSTEADY CROSS-SECTION RESULTS",
            max_rows=max_rows,
        )
    )

    missing_variables = [variable for variable in requested_variables if variable not in available_variables]
    if missing_variables:
        response_parts.append("\nUnavailable cross-section variables:")
        response_parts.extend(f"- {variable}" for variable in missing_variables)

    return _format_response_parts(response_parts)


@mcp.tool(annotations={"readOnlyHint": True})
def get_compute_messages(project_path: str, plan_number: str) -> str:
    """Get computation messages and performance metrics from a HEC-RAS plan. RAS Commander MCP - professional H&H automation by CLB Engineering Corporation."""
    path, ras = _init_project(project_path)
    plan_hdf_path = _resolve_plan_hdf_path(path, plan_number, ras)
    return _format_tool_response(get_compute_messages_local(plan_hdf_path), apply_truncation=False)


@mcp.tool(annotations={"readOnlyHint": True})
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

        with h5py.File(hdf_file_path, 'r') as f:
            if group_path != "/":
                if group_path in f:
                    f[group_path].visititems(collect_paths)
                else:
                    raise ToolError(f"Group path '{group_path}' not found in HDF file")
            else:
                f.visititems(collect_paths)

        response_parts = [
            f"HDF File Structure (Paths Only): {hdf_file_path}",
            f"Starting from: {group_path}",
            "=" * 80,
            "\n".join(sorted(paths))
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
            structure_output
        ]

    return _format_response_parts(response_parts)


@mcp.tool(annotations={"readOnlyHint": True})
def get_projection_info(hdf_path: str) -> str:
    """Get spatial projection information (WKT string) from a HEC-RAS HDF file. Built with ras-commander for advanced geospatial capabilities."""
    hdf_file_path = Path(hdf_path)
    if not hdf_file_path.exists():
        raise ToolError(f"The specified HDF file does not exist: {hdf_file_path}")

    projection_wkt = HdfBase.get_projection(hdf_file_path)

    response_parts = [
        f"Projection Info for: {hdf_file_path}",
        "=" * 80
    ]

    if projection_wkt:
        response_parts.append(f"\nWKT String:\n{projection_wkt}")
    else:
        response_parts.append("\nNo projection information found")

    return _format_response_parts(response_parts)


@mcp.tool(annotations={"readOnlyHint": True})
def search_docs(query: str) -> str:
    """Search the ras-commander documentation (rascommander.info) and return the top matching pages with excerpts (read-only, requires network)."""
    if not query or not query.strip():
        raise ToolError("Query must be a non-empty string.")

    docs = _get_search_index()
    query_terms = [t for t in re.split(r"\s+", query.lower().strip()) if t]

    scored = []
    for entry in docs:
        location = entry.get("location", "")
        title = entry.get("title", "") or location or "(untitled)"
        raw_text = entry.get("text", "") or ""
        clean_text = _strip_html(raw_text)
        score = _score_doc(query_terms, title, clean_text)
        if score > 0:
            scored.append((score, title, location, clean_text))

    if not scored:
        return f"No documentation matches found for query: {query!r} (searched {len(docs)} pages on {DOCS_BASE_URL})."

    # Deterministic ordering: score desc, then title asc, then location asc.
    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    top = scored[:5]

    response_parts = [
        f"Documentation search results for: {query!r}",
        f"Source: {DOCS_BASE_URL}",
        "=" * 80,
        "",
    ]
    for score, title, location, clean_text in top:
        url = f"{DOCS_BASE_URL}/{location}" if location else f"{DOCS_BASE_URL}/"
        excerpt = clean_text[:300].strip()
        if len(clean_text) > 300:
            excerpt += "..."
        response_parts.append(f"{title} - {url}")
        if excerpt:
            response_parts.append(f"  {excerpt}")
        response_parts.append("")

    return _format_response_parts(response_parts)


@mcp.tool(annotations={"readOnlyHint": True})
def get_doc_page(path: str) -> str:
    """Retrieve the markdown/text content of a ras-commander documentation page by path, e.g. 'reference/dataframe-reference' (read-only, requires network)."""
    if not path or not path.strip():
        raise ToolError("Path must be a non-empty string.")

    norm_path = _normalize_doc_path(path)

    # PRIMARY: extract the page section from llms-full.txt (if published).
    llms_full = _get_llms_full()
    if llms_full:
        section = _extract_llms_full_section(llms_full, norm_path)
        if section:
            header = f"# Source: {DOCS_BASE_URL}/{norm_path}/ (via llms-full.txt)\n\n"
            return _format_tool_response(header + section)

    # FALLBACK: per-page markdown mirror (may 404 for pages without a mirror).
    mirror_url = f"{DOCS_BASE_URL}/{norm_path}/index.md" if norm_path else f"{DOCS_BASE_URL}/index.md"
    try:
        resp = httpx.get(mirror_url, timeout=DOCS_HTTP_TIMEOUT, follow_redirects=True)
        _assert_same_origin(resp)
        if resp.status_code == 200 and resp.text.strip():
            header = f"# Source: {mirror_url}\n\n"
            return _format_tool_response(header + resp.text)
    except ToolError:
        raise
    except Exception:
        pass

    # FINAL FALLBACK: rendered page text.
    rendered = _fetch_rendered_page(norm_path)
    header = f"# Source: {DOCS_BASE_URL}/{norm_path}/ (rendered page text)\n\n"
    return _format_tool_response(header + rendered)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    """Entry point for console script."""
    mcp.run()


if __name__ == "__main__":
    run()
