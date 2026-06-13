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
from typing import Any, Optional
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
        HdfResultsPlan,
        RasPlan,
        HdfXsec,
        HdfBndry,
        HdfStruc,
        HdfMesh,
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

# Geometry element listing configuration
GEOMETRY_ELEMENT_TYPES = [
    "rivers_reaches",
    "cross_sections",
    "reference_lines",
    "bc_lines",
    "breaklines",
    "structures",
    "mesh_areas",
]

GEOMETRY_ELEMENT_ALIASES = {
    "all": GEOMETRY_ELEMENT_TYPES,
    "everything": GEOMETRY_ELEMENT_TYPES,
    "rivers": ["rivers_reaches"],
    "river": ["rivers_reaches"],
    "reaches": ["rivers_reaches"],
    "reach": ["rivers_reaches"],
    "rivers_reaches": ["rivers_reaches"],
    "river_reaches": ["rivers_reaches"],
    "river_centerlines": ["rivers_reaches"],
    "xs": ["cross_sections"],
    "xsec": ["cross_sections"],
    "xsecs": ["cross_sections"],
    "cross_sections": ["cross_sections"],
    "cross_section": ["cross_sections"],
    "reference_lines": ["reference_lines"],
    "reference_line": ["reference_lines"],
    "ref_lines": ["reference_lines"],
    "ref_line": ["reference_lines"],
    "2d_reference_lines": ["reference_lines"],
    "bc_lines": ["bc_lines"],
    "bc_line": ["bc_lines"],
    "boundary_lines": ["bc_lines"],
    "boundary_line": ["bc_lines"],
    "boundary_condition_lines": ["bc_lines"],
    "boundary_condition_line": ["bc_lines"],
    "2d_boundary_lines": ["bc_lines"],
    "breaklines": ["breaklines"],
    "breakline": ["breaklines"],
    "2d_breaklines": ["breaklines"],
    "structures": ["structures"],
    "structure": ["structures"],
    "mesh_areas": ["mesh_areas"],
    "mesh_area": ["mesh_areas"],
    "meshes": ["mesh_areas"],
    "mesh": ["mesh_areas"],
    "2d_areas": ["mesh_areas"],
    "2d_area": ["mesh_areas"],
}

GEOMETRY_COLUMN_PRIORITY = {
    "rivers_reaches": [
        "River",
        "River Name",
        "Reach",
        "Reach Name",
        "Name",
        "river_id",
        "geometry_type",
    ],
    "cross_sections": [
        "River",
        "River Name",
        "Reach",
        "Reach Name",
        "RS",
        "River Station",
        "Name",
        "Description",
        "Left Bank",
        "Right Bank",
        "n_lob",
        "n_channel",
        "n_rob",
        "geometry_type",
    ],
    "reference_lines": [
        "refln_id",
        "Name",
        "mesh_name",
        "SA-2D",
        "Type",
        "geometry_type",
    ],
    "bc_lines": [
        "bc_line_id",
        "Name",
        "SA-2D",
        "Type",
        "geometry_type",
    ],
    "breaklines": [
        "bl_id",
        "breakline_id",
        "Name",
        "mesh_name",
        "SA-2D",
        "Type",
        "geometry_type",
    ],
    "structures": [
        "Structure ID",
        "Name",
        "Type",
        "River",
        "River Name",
        "Reach",
        "Reach Name",
        "RS",
        "River Station",
        "Description",
        "geometry_type",
    ],
}

GEOMETRY_RAW_COLUMNS = {
    "geometry",
    "station_elevation",
    "mannings_n",
    "ineffective_blocks",
    "obstruction_blocks",
    "profile_data",
    "profiles",
    "points",
    "stations",
    "centerline points",
    "centerline info",
    "polyline points",
    "polyline parts",
    "polyline info",
}


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


def _is_blank(value: Any) -> bool:
    """Return True when a scalar-like value should be treated as unset."""
    if value is None:
        return True
    text = str(value).strip()
    return text == "" or text.lower() in {"none", "nan", "nat"}


def _normalize_geometry_number(value: Any) -> str:
    """Normalize HEC-RAS geometry selectors like 1, 01, and g01."""
    if _is_blank(value):
        return ""

    text = str(value).strip()
    name = Path(text).name
    if name.lower().endswith(".hdf"):
        name = Path(name).stem

    token = name.split(".")[-1]
    if token.lower().startswith("g") and token[1:].isdigit():
        token = token[1:]

    if token.isdigit():
        return token.zfill(2)

    return token.lower()


def _geometry_hdf_candidates(project_path: Path, project_name: str, geometry_number: str) -> list[Path]:
    """Build likely geometry HDF paths for a normalized geometry number."""
    if not geometry_number:
        return []

    geom_file = f"g{geometry_number}"
    candidates = [
        project_path / f"{project_name}.{geom_file}.hdf",
        project_path / f"{project_path.name}.{geom_file}.hdf",
    ]

    unique_candidates = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def _path_from_project_value(project_path: Path, value: Any) -> Path | None:
    """Convert a path-like project metadata value to an absolute path."""
    if _is_blank(value):
        return None

    path = Path(str(value).strip())
    if not path.is_absolute():
        path = project_path / path
    return path


def _geometry_hdf_from_row(project_path: Path, project_name: str, row: pd.Series) -> Path | None:
    """Resolve a geometry HDF path from a ras.geom_df row."""
    hdf_columns = [
        "hdf_path",
        "HDF Geometry Path",
        "Geometry HDF Path",
        "Geom HDF Path",
        "HDF Path",
    ]
    for column in hdf_columns:
        if column in row and not _is_blank(row[column]):
            path = _path_from_project_value(project_path, row[column])
            if path:
                return path

    file_path_columns = ["full_path", "Geom Path", "Geometry Path"]
    for column in file_path_columns:
        if column in row and not _is_blank(row[column]):
            path = _path_from_project_value(project_path, row[column])
            if path:
                if path.suffix.lower() != ".hdf":
                    path = Path(f"{path}.hdf")
                return path

    for column in ["geom_number", "geometry_number", "Geom File", "geom_file"]:
        if column in row and not _is_blank(row[column]):
            geom_number = _normalize_geometry_number(row[column])
            for path in _geometry_hdf_candidates(project_path, project_name, geom_number):
                return path

    return None


def _row_matches_geometry_selector(row: pd.Series, selector: str) -> bool:
    """Return True when a ras.geom_df row matches a user geometry selector."""
    if not selector:
        return True

    selector_number = _normalize_geometry_number(selector)
    selector_text = str(selector).strip().lower()

    for value in row.values:
        if _is_blank(value):
            continue

        value_text = str(value).strip().lower()
        value_number = _normalize_geometry_number(value)
        if value_number and selector_number and value_number == selector_number:
            return True
        if value_text == selector_text:
            return True
        if Path(value_text).name == selector_text:
            return True

    return False


def _geometry_label(path: Path, row: pd.Series | None = None) -> str:
    """Create a concise label for a geometry HDF path."""
    if row is not None:
        for column in ["geom_file", "Geom File", "geom_number", "geometry_number"]:
            if column in row and not _is_blank(row[column]):
                geom_number = _normalize_geometry_number(row[column])
                if geom_number:
                    return f"g{geom_number}"
                return str(row[column]).strip()
    return path.stem


def _resolve_geometry_hdf_paths(project_path: Path, geometry_number: str, ras) -> list[tuple[str, Path]]:
    """Resolve one or more geometry HDF paths from project metadata."""
    selector = (geometry_number or "").strip()
    project_name = getattr(ras, "project_name", project_path.name)

    if selector:
        selector_path = Path(selector)
        if selector_path.suffix.lower() == ".hdf":
            if not selector_path.is_absolute():
                selector_path = project_path / selector_path
            if not selector_path.exists():
                raise ToolError(f"The specified geometry HDF file does not exist: {selector_path}")
            return [(_geometry_label(selector_path), selector_path)]

    resolved_paths: list[tuple[str, Path]] = []
    geom_df = getattr(ras, "geom_df", None)
    if geom_df is not None and not geom_df.empty:
        for _, row in geom_df.iterrows():
            if not _row_matches_geometry_selector(row, selector):
                continue

            hdf_path = _geometry_hdf_from_row(project_path, project_name, row)
            if hdf_path and hdf_path.exists():
                resolved_paths.append((_geometry_label(hdf_path, row), hdf_path))

    if not resolved_paths:
        selector_number = _normalize_geometry_number(selector)
        globbed_paths = sorted(project_path.glob("*.g*.hdf"))
        for hdf_path in globbed_paths:
            if selector_number and _normalize_geometry_number(hdf_path.name) != selector_number:
                continue
            resolved_paths.append((_geometry_label(hdf_path), hdf_path))

    if resolved_paths:
        unique_paths: list[tuple[str, Path]] = []
        seen = set()
        for label, hdf_path in resolved_paths:
            resolved = hdf_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            unique_paths.append((label, hdf_path))
        return unique_paths

    if selector:
        raise ToolError(
            f"Geometry '{selector}' was not found or does not have an existing geometry HDF file"
        )

    raise ToolError(
        "No geometry HDF files were found for this project. "
        "Run or save the HEC-RAS geometry so a .gNN.hdf file exists."
    )


def _normalize_geometry_element_type(element_type: str) -> list[str]:
    """Normalize a geometry element type or alias to one or more internal keys."""
    normalized = (element_type or "all").strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_").replace("/", "_")

    element_types = GEOMETRY_ELEMENT_ALIASES.get(normalized)
    if not element_types:
        valid_types = ", ".join(["all"] + GEOMETRY_ELEMENT_TYPES)
        raise ToolError(f"Unknown geometry element type '{element_type}'. Use one of: {valid_types}")
    return element_types


def _format_geometry_dataframe(df: Any, name: str, element_type: str, showmore: bool = False) -> str:
    """Format geometry GeoDataFrames as concise element listings."""
    if df is None:
        return f"\n{name}: No elements found\n"

    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)

    if df.empty:
        return f"\n{name}: No elements found\n"

    display_df = pd.DataFrame(df).copy()
    raw_column_names = {column.lower() for column in GEOMETRY_RAW_COLUMNS}
    raw_columns = [
        column for column in display_df.columns
        if str(column).strip().lower() in raw_column_names
    ]

    geometry_columns = [
        column for column in raw_columns
        if str(column).strip().lower() == "geometry"
    ]
    if geometry_columns and "geometry_type" not in display_df.columns:
        geometry_series = display_df[geometry_columns[0]]
        display_df["geometry_type"] = geometry_series.apply(
            lambda geom: getattr(geom, "geom_type", type(geom).__name__) if geom is not None else ""
        )

    omitted_count = len(raw_columns)
    if raw_columns:
        display_df = display_df.drop(columns=raw_columns)

    if not showmore:
        priority_columns = [
            column for column in GEOMETRY_COLUMN_PRIORITY.get(element_type, [])
            if column in display_df.columns
        ]
        supplemental_columns = [
            column for column in display_df.columns
            if column not in priority_columns
            and (
                "name" in str(column).lower()
                or "river" in str(column).lower()
                or "reach" in str(column).lower()
                or str(column).lower().endswith("id")
            )
        ]
        selected_columns = (priority_columns + supplemental_columns)[:12]
        if not selected_columns:
            selected_columns = list(display_df.columns[:8])

        omitted_count += len([column for column in display_df.columns if column not in selected_columns])
        display_df = display_df[selected_columns]

    if display_df.empty:
        return f"\n{name} ({len(df)} element(s)): No concise attributes available\n"

    buffer = io.StringIO()
    display_df.to_string(buf=buffer, max_rows=100, max_cols=None, index=False)

    result = f"\n{name} ({len(df)} element(s))"
    if omitted_count > 0:
        if showmore:
            result += f" ({omitted_count} raw/detail column(s) omitted)"
        else:
            result += f" ({omitted_count} columns omitted - use showmore=True to see more attributes)"
    result += f":\n{buffer.getvalue()}\n"
    return result


def _format_mesh_area_names(mesh_area_names: list[str]) -> str:
    """Format 2D mesh area names as a concise list."""
    if not mesh_area_names:
        return "\n2D MESH AREAS: No elements found\n"

    lines = [f"\n2D MESH AREAS ({len(mesh_area_names)} element(s)):"]
    for index, mesh_area_name in enumerate(mesh_area_names, start=1):
        lines.append(f"{index}. {mesh_area_name}")
    lines.append("")
    return "\n".join(lines)


def _get_river_reaches(hdf_path: Path) -> pd.DataFrame:
    """Extract 1D river/reach lines, falling back to centerlines when needed."""
    try:
        river_reaches = HdfXsec.get_river_reaches(hdf_path, datetime_to_str=True)
        if river_reaches is not None and not river_reaches.empty:
            return river_reaches
    except Exception:
        logger.info("River reaches unavailable; trying river centerlines", exc_info=True)

    return HdfXsec.get_river_centerlines(hdf_path, datetime_to_str=True)


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

    return truncate_output("\n".join(response_parts))


@mcp.tool(annotations={"readOnlyHint": True})
def list_geometry_elements(
    project_path: str,
    geometry_number: str = "",
    element_type: str = "all",
    mesh_name: str = "",
    showmore: bool = False,
) -> str:
    """List HEC-RAS geometry elements from geometry HDF files. Element types: rivers_reaches are 1D river/reach lines; cross_sections are 1D XS cut lines by river/reach/station; reference_lines are 2D profile-output lines; bc_lines are 2D boundary condition lines; breaklines are 2D mesh enforcement lines; structures are bridges, culverts, inline structures, and lateral structures; mesh_areas are named 2D flow areas."""
    path, ras = _init_project(project_path)
    geometry_hdf_paths = _resolve_geometry_hdf_paths(path, geometry_number, ras)
    selected_element_types = _normalize_geometry_element_type(element_type)
    mesh_filter = mesh_name.strip() or None

    response_parts = [
        f"Geometry Elements for: {ras.project_name}",
        f"Project Path: {path}",
        get_ras_version_info(),
        f"Geometry filter: {geometry_number or 'all geometries'}",
        f"Element type: {element_type or 'all'}",
        "=" * 80,
        "Geometry type guide:",
        "- 1D rivers/reaches: river and reach alignment lines used by 1D geometry",
        "- Cross sections: 1D XS cut lines listed by river, reach, and station",
        "- Reference lines: 2D profile-output lines, optionally filtered by mesh_name",
        "- Boundary condition lines: 2D flow area boundary condition lines",
        "- Breaklines: 2D mesh enforcement lines",
        "- Structures: bridges, culverts, inline structures, and lateral structures",
        "- Mesh areas: named 2D flow areas",
    ]

    if mesh_filter:
        response_parts.append(f"Reference line mesh filter: {mesh_filter}")

    def append_dataframe_section(section_name: str, key: str, extractor) -> None:
        try:
            section_df = extractor()
            response_parts.append(_format_geometry_dataframe(section_df, section_name, key, showmore))
        except Exception as e:
            logger.error(f"Error listing {section_name}: {str(e)}")
            response_parts.append(f"\n{section_name}: Error reading elements: {str(e)}\n")

    for label, hdf_path in geometry_hdf_paths:
        response_parts.extend([
            "",
            f"GEOMETRY {label}: {hdf_path}",
            "-" * 80,
        ])

        if "rivers_reaches" in selected_element_types:
            append_dataframe_section(
                "1D RIVERS/REACHES",
                "rivers_reaches",
                lambda hdf_path=hdf_path: _get_river_reaches(hdf_path),
            )

        if "cross_sections" in selected_element_types:
            append_dataframe_section(
                "1D CROSS SECTIONS",
                "cross_sections",
                lambda hdf_path=hdf_path: HdfXsec.get_cross_sections(
                    hdf_path,
                    datetime_to_str=True,
                    ras_object=ras,
                ),
            )

        if "reference_lines" in selected_element_types:
            append_dataframe_section(
                "2D REFERENCE LINES",
                "reference_lines",
                lambda hdf_path=hdf_path: HdfBndry.get_reference_lines(
                    hdf_path,
                    mesh_name=mesh_filter,
                ),
            )

        if "bc_lines" in selected_element_types:
            append_dataframe_section(
                "2D BOUNDARY CONDITION LINES",
                "bc_lines",
                lambda hdf_path=hdf_path: HdfBndry.get_bc_lines(hdf_path),
            )

        if "breaklines" in selected_element_types:
            append_dataframe_section(
                "2D BREAKLINES",
                "breaklines",
                lambda hdf_path=hdf_path: HdfBndry.get_breaklines(hdf_path),
            )

        if "structures" in selected_element_types:
            append_dataframe_section(
                "STRUCTURES",
                "structures",
                lambda hdf_path=hdf_path: HdfStruc.get_structures(
                    hdf_path,
                    datetime_to_str=True,
                ),
            )

        if "mesh_areas" in selected_element_types:
            try:
                mesh_area_names = HdfMesh.get_mesh_area_names(hdf_path)
                response_parts.append(_format_mesh_area_names(mesh_area_names))
            except Exception as e:
                logger.error(f"Error listing mesh areas: {str(e)}")
                response_parts.append(f"\n2D MESH AREAS: Error reading elements: {str(e)}\n")

    return truncate_output("\n".join(response_parts))


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
    return "\n".join(response_parts)


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

    return truncate_output("\n".join(response_parts))


@mcp.tool(annotations={"readOnlyHint": True})
def get_compute_messages(project_path: str, plan_number: str) -> str:
    """Get computation messages and performance metrics from a HEC-RAS plan. RAS Commander MCP - professional H&H automation by CLB Engineering Corporation."""
    path, ras = _init_project(project_path)
    plan_hdf_path = _resolve_plan_hdf_path(path, plan_number, ras)
    return get_compute_messages_local(plan_hdf_path)


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

    return truncate_output("\n".join(response_parts))


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

    return truncate_output("\n".join(response_parts))


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

    return truncate_output("\n".join(response_parts))


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
            return truncate_output(header + section)

    # FALLBACK: per-page markdown mirror (may 404 for pages without a mirror).
    mirror_url = f"{DOCS_BASE_URL}/{norm_path}/index.md" if norm_path else f"{DOCS_BASE_URL}/index.md"
    try:
        resp = httpx.get(mirror_url, timeout=DOCS_HTTP_TIMEOUT, follow_redirects=True)
        _assert_same_origin(resp)
        if resp.status_code == 200 and resp.text.strip():
            header = f"# Source: {mirror_url}\n\n"
            return truncate_output(header + resp.text)
    except ToolError:
        raise
    except Exception:
        pass

    # FINAL FALLBACK: rendered page text.
    rendered = _fetch_rendered_page(norm_path)
    header = f"# Source: {DOCS_BASE_URL}/{norm_path}/ (rendered page text)\n\n"
    return truncate_output(header + rendered)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run():
    """Entry point for console script."""
    mcp.run()


if __name__ == "__main__":
    run()
