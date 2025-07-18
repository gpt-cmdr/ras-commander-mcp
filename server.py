#!/usr/bin/env python3
"""
HEC-RAS MCP Server

An MCP server that provides tools for querying HEC-RAS project information
using the ras-commander library.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Sequence
import pandas as pd
import io

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import ras-commander
try:
    from ras_commander import init_ras_project, HdfBase, HdfResultsPlan, RasPlan
    import h5py
    import numpy as np
except ImportError:
    raise ImportError("ras-commander is not installed. Please install it with: pip install ras-commander")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the MCP server
server = Server("hecras-mcp-server")

# Configuration
DEFAULT_RAS_VERSION = "6.6"
# Get HEC-RAS version from environment variable or use default
HECRAS_VERSION = os.environ.get("HECRAS_VERSION", DEFAULT_RAS_VERSION)
# Allow specifying a direct path to HEC-RAS executable
HECRAS_PATH = os.environ.get("HECRAS_PATH", None)

def get_ras_version_info():
    """Get the configured HEC-RAS version or path for display."""
    if HECRAS_PATH:
        return f"HEC-RAS Path: {HECRAS_PATH}"
    else:
        return f"HEC-RAS Version: {HECRAS_VERSION}"

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
            
            # Extract the compute messages
            compute_messages_dataset = hdf_file[compute_messages_path]
            
            # Handle different data types
            if isinstance(compute_messages_dataset, h5py.Dataset):
                data = compute_messages_dataset[()]
                
                # Convert to string based on data type
                if isinstance(data, bytes):
                    messages_text = data.decode('utf-8')
                elif isinstance(data, np.ndarray):
                    if data.dtype.kind == 'S':  # String array
                        # Join array of strings
                        messages_text = '\n'.join([item.decode('utf-8') if isinstance(item, bytes) else str(item) 
                                                  for item in data])
                    else:
                        messages_text = str(data)
                else:
                    messages_text = str(data)
            else:
                return f"Unexpected data type for compute messages: {type(compute_messages_dataset)}"
            
            # Format the compute messages (stops at "Computation Tasks:")
            formatted_output = format_compute_messages_local(messages_text, str(hdf_path))
            
            # Check token count and truncate if necessary
            # Rough approximation: 1 token ≈ 4 characters
            max_chars = 10000 * 4  # 40,000 characters for 10k tokens
            
            if len(formatted_output) > max_chars:
                # Truncate but preserve last 50 lines
                lines = formatted_output.split('\n')
                last_50_lines = lines[-50:] if len(lines) > 50 else lines
                
                # Find how many characters we can include from the beginning
                last_50_text = '\n'.join(last_50_lines)
                truncation_notice = "\n\n[OUTPUT TRUNCATED: Response exceeded 10,000 tokens. Showing beginning and last 50 lines.]\n\n"
                
                available_chars = max_chars - len(last_50_text) - len(truncation_notice)
                truncated_beginning = formatted_output[:available_chars]
                
                # Find last complete line in truncated beginning
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
    """
    Format compute messages for better readability.
    Stops processing when reaching "Computation Tasks:" section.
    """
    lines = messages_text.split('\r\n') if '\r\n' in messages_text else messages_text.split('\n')
    
    formatted_parts = [
        f"Compute Messages from: {Path(hdf_file_path).name}",
        "=" * 80,
        ""
    ]
    
    # Only collect general messages, skip computation tasks and speeds
    general_messages = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Stop processing when we hit computation tasks or speeds
        if 'Computation Task' in line and '\t' in line:
            break
        elif 'Computation Speed' in line and '\t' in line:
            break
        else:
            general_messages.append(line)
    
    # Add general messages only
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
    # Rough approximation: 1 token = 4 characters
    max_chars = max_tokens * 4
    
    if len(text) <= max_chars:
        return text
    
    truncated_text = text[:max_chars]
    # Try to truncate at a word boundary
    last_space = truncated_text.rfind(' ')
    if last_space > max_chars * 0.9:  # Only if we don't lose too much
        truncated_text = truncated_text[:last_space]
    
    return truncated_text + "\n\n[OUTPUT TRUNCATED: Response exceeded 10,000 tokens. Please use a more specific query for complete results.]"

def filter_dataframe_columns(df: pd.DataFrame, df_type: str, showmore: bool = False) -> tuple[pd.DataFrame, int]:
    """Filter DataFrame columns for default vs verbose output.
    
    Returns:
        tuple: (filtered_dataframe, omitted_columns_count)
    """
    if df is None or df.empty or showmore:
        return df, 0
    
    # Define columns to omit for each dataframe type
    omit_columns = {
        'plan_df': {
            'Geom File', 'Flow File', 'full_path', 'Geom Path', 'Flow Path',
            'Computation Interval', 'Output Interval', 'Instantaneous Interval',
            'Mapping Interval', 'Detailed Interval', 'HDF Compression', 
            'Computation Threads', 'Tolerated Iterations', 'WS Tolerance',
            'Flow Tolerance', 'Computation Mode', 'Mixed Flow', 'Computation Level',
            'Run WQNet'
        },
        'geom_df': {
            'full_path', 'hdf_path'
        },
        'flow_df': {
            'full_path', 'Number of Profiles', 'River Stations'
        },
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
    
    # Only drop columns that actually exist in the dataframe
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
    
    # Filter columns if df_type is provided
    display_df = df
    omitted_count = 0
    if df_type and not showmore:
        display_df, omitted_count = filter_dataframe_columns(df, df_type, showmore)
    
    # Use StringIO to capture the DataFrame string representation
    buffer = io.StringIO()
    display_df.to_string(buf=buffer, max_rows=100, max_cols=None)
    
    result = f"\n{name}:"
    if omitted_count > 0:
        result += f" ({omitted_count} columns omitted - use showmore=True to see all)"
    result += f"\n{buffer.getvalue()}\n"
    
    return result

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="hecras_project_summary",
            description="Get comprehensive or selective HEC-RAS project information",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Full path to the HEC-RAS project folder"
                    },
                    "show_rasprj": {
                        "type": "boolean",
                        "description": "Show project file contents",
                        "default": True
                    },
                    "show_plan_df": {
                        "type": "boolean",
                        "description": "Show plan files and metadata",
                        "default": True
                    },
                    "show_geom_df": {
                        "type": "boolean",
                        "description": "Show geometry files",
                        "default": True
                    },
                    "show_flow_df": {
                        "type": "boolean",
                        "description": "Show steady flow data",
                        "default": True
                    },
                    "show_unsteady_df": {
                        "type": "boolean",
                        "description": "Show unsteady flow data",
                        "default": True
                    },
                    "show_boundaries": {
                        "type": "boolean",
                        "description": "Show boundary conditions",
                        "default": True
                    },
                    "show_rasmap": {
                        "type": "boolean",
                        "description": "Show RASMapper configuration",
                        "default": False
                    },
                    "showmore": {
                        "type": "boolean",
                        "description": "Show all columns (verbose mode)",
                        "default": False
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="read_plan_description",
            description="Read the multi-line description block from a HEC-RAS plan file",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Full path to the HEC-RAS project folder"
                    },
                    "plan_number": {
                        "type": "string",
                        "description": "Plan number (e.g., '1', '01', '02') or full path to plan file"
                    }
                },
                "required": ["project_path", "plan_number"]
            }
        ),
        Tool(
            name="get_plan_results_summary",
            description="Get comprehensive results summary from a HEC-RAS plan including unsteady info, volume accounting, and runtime data. Accepts plan numbers (e.g., '1' or '01') or full HDF path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Full path to the HEC-RAS project folder"
                    },
                    "plan_number": {
                        "type": "string",
                        "description": "Plan number (e.g., '1', '01', '02') or full path to plan HDF file. Single digits will be zero-padded."
                    }
                },
                "required": ["project_path", "plan_number"]
            }
        ),
        Tool(
            name="get_hdf_structure",
            description="Explore the structure of a HEC-RAS HDF file showing groups, datasets, attributes, shapes, and dtypes. CAUTION: Use on 3rd level data structures or deeper (e.g., /Event Conditions/Unsteady/Boundary Conditions) to avoid output truncation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "hdf_path": {
                        "type": "string",
                        "description": "Full path to the HDF file"
                    },
                    "group_path": {
                        "type": "string",
                        "description": "Internal HDF path to start exploration from",
                        "default": "/"
                    },
                    "paths_only": {
                        "type": "boolean",
                        "description": "If true, only show group paths without datasets/attributes/details. More appropriate for exploratory queries to understand file structure.",
                        "default": False
                    }
                },
                "required": ["hdf_path"]
            }
        ),
        Tool(
            name="get_projection_info",
            description="Get spatial projection information (WKT string) from a HEC-RAS HDF file",
            inputSchema={
                "type": "object",
                "properties": {
                    "hdf_path": {
                        "type": "string",
                        "description": "Full path to the HDF file"
                    }
                },
                "required": ["hdf_path"]
            }
        ),
        Tool(
            name="get_compute_messages",
            description="Get computation messages and performance metrics from a HEC-RAS plan including timing, tasks completed, and computation speeds. Accepts plan numbers (e.g., '1' or '01') or full HDF path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Full path to the HEC-RAS project folder"
                    },
                    "plan_number": {
                        "type": "string",
                        "description": "Plan number (e.g., '1', '01', '02') or full path to plan HDF file. Single digits will be zero-padded."
                    }
                },
                "required": ["project_path", "plan_number"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """Handle tool calls."""
    
    if name == "hecras_project_summary":
        try:
            project_path = Path(arguments["project_path"])
            show_rasprj = arguments.get("show_rasprj", True)
            show_plan_df = arguments.get("show_plan_df", True)
            show_geom_df = arguments.get("show_geom_df", True)
            show_flow_df = arguments.get("show_flow_df", True)
            show_unsteady_df = arguments.get("show_unsteady_df", True)
            show_boundaries = arguments.get("show_boundaries", True)
            show_rasmap = arguments.get("show_rasmap", False)
            showmore = arguments.get("showmore", False)
            
            # Use configured version or path
            ras_version = HECRAS_PATH if HECRAS_PATH else HECRAS_VERSION
            
            # Validate project path
            if not project_path.exists() or not project_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified project folder does not exist or is not a directory: {project_path}"
                )]
            
            # Initialize the RAS project
            logger.info(f"Initializing HEC-RAS project at: {project_path}")
            ras = init_ras_project(project_path, ras_version)
            
            # Build the response
            response_parts = [
                f"HEC-RAS Project: {ras.project_name}",
                f"Project Path: {project_path}",
                get_ras_version_info(),
                "=" * 80
            ]
            
            # Add project file contents if requested
            if show_rasprj and hasattr(ras, 'prj_file') and ras.prj_file:
                try:
                    with open(ras.prj_file, 'r', encoding='utf-8') as f:
                        prj_content = f.read()
                    
                    # Filter out lines that start with specific patterns
                    excluded_prefixes = [
                        'Geom File=', 'Flow File=', 'Unsteady File=', 'Plan File=',
                        'DSS Export Filename=', 'DSS Export Rating Curves=', 'DSS Export Rating Curve Sorted=',
                        'DSS Export Volume Flow Curves=', 'DXF Filename=', 'DXF OffsetX=', 'DXF OffsetY=',
                        'DXF ScaleX=', 'DXF ScaleY=', 'GIS Export Profiles='
                    ]
                    filtered_lines = []
                    
                    for line in prj_content.splitlines():
                        if not any(line.strip().startswith(prefix) for prefix in excluded_prefixes):
                            filtered_lines.append(line)
                    
                    response_parts.append("\nPROJECT FILE CONTENTS (.prj):")
                    response_parts.append("-" * 40)
                    response_parts.append('\n'.join(filtered_lines))
                    response_parts.append("=" * 80)
                except Exception as e:
                    logger.error(f"Error reading project file: {str(e)}")
                    response_parts.append("\nPROJECT FILE: Error reading file")
                    response_parts.append("=" * 80)
            
            # Add plan information
            if show_plan_df and hasattr(ras, 'plan_df') and ras.plan_df is not None:
                response_parts.append(dataframe_to_text(ras.plan_df, "PLANS", "plan_df", showmore))
            
            # Add geometry information
            if show_geom_df and hasattr(ras, 'geom_df') and ras.geom_df is not None:
                response_parts.append(dataframe_to_text(ras.geom_df, "GEOMETRIES", "geom_df", showmore))
            
            # Add flow information
            if show_flow_df and hasattr(ras, 'flow_df') and ras.flow_df is not None:
                response_parts.append(dataframe_to_text(ras.flow_df, "STEADY FLOWS", "flow_df", showmore))
                
            if show_unsteady_df and hasattr(ras, 'unsteady_df') and ras.unsteady_df is not None:
                response_parts.append(dataframe_to_text(ras.unsteady_df, "UNSTEADY FLOWS", "unsteady_df", showmore))
            
            # Add boundary conditions if requested
            if show_boundaries and hasattr(ras, 'boundaries_df') and ras.boundaries_df is not None:
                response_parts.append(dataframe_to_text(ras.boundaries_df, "BOUNDARY CONDITIONS", "boundaries_df", showmore))
            
            # Add RASMapper information if requested
            if show_rasmap and hasattr(ras, 'rasmap_df') and ras.rasmap_df is not None:
                response_parts.append(dataframe_to_text(ras.rasmap_df, "RASMAP CONFIGURATION", "rasmap_df", showmore))
            
            return [TextContent(
                type="text",
                text=truncate_output("\n".join(response_parts))
            )]
            
        except Exception as e:
            logger.error(f"Error querying HEC-RAS project: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error querying HEC-RAS project: {str(e)}\n\nPlease ensure:\n1. The project path is correct\n2. HEC-RAS version is installed at the expected location\n3. The project files are valid"
            )]
    
    
    elif name == "read_plan_description":
        try:
            project_path = Path(arguments["project_path"])
            plan_number = arguments["plan_number"]
            
            # Handle single-digit plan numbers
            if plan_number.isdigit() and len(plan_number) == 1:
                plan_number = plan_number.zfill(2)
            
            if not project_path.exists() or not project_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified project folder does not exist: {project_path}"
                )]
            
            # Initialize project to get plan info
            ras_version = HECRAS_PATH if HECRAS_PATH else HECRAS_VERSION
            ras = init_ras_project(project_path, ras_version)
            
            # Read the plan description
            description = RasPlan.read_plan_description(plan_number, ras)
            
            response_parts = [
                f"Plan Description for Plan {plan_number}",
                f"Project: {ras.project_name}",
                "=" * 80,
                "",
                description if description else "[No description found]",
                ""
            ]
            
            return [TextContent(
                type="text",
                text="\n".join(response_parts)
            )]
            
        except ValueError as e:
            logger.error(f"Error reading plan description: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error: Plan '{plan_number}' not found in project"
            )]
        except Exception as e:
            logger.error(f"Error reading plan description: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error reading plan description: {str(e)}"
            )]
    
    elif name == "get_plan_results_summary":
        try:
            project_path = Path(arguments["project_path"])
            plan_number = arguments["plan_number"]
            
            # Handle single-digit plan numbers
            if plan_number.isdigit() and len(plan_number) == 1:
                plan_number = plan_number.zfill(2)
            
            if not project_path.exists() or not project_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified project folder does not exist: {project_path}"
                )]
            
            # Initialize project to get plan info
            ras_version = HECRAS_PATH if HECRAS_PATH else HECRAS_VERSION
            ras = init_ras_project(project_path, ras_version)
            
            # Handle plan identification like ras-commander: plan number ("01", "02") or full HDF path
            plan_hdf_path = None
            
            # Check if plan_number is a full path to an HDF file
            if plan_number.endswith('.hdf') and Path(plan_number).exists():
                plan_hdf_path = Path(plan_number)
            else:
                # Assume it's a plan number (01, 02, etc.) - construct HDF path
                if hasattr(ras, 'plan_df') and ras.plan_df is not None:
                    # Look for plan by plan_number
                    plan_row = ras.plan_df[ras.plan_df['plan_number'] == plan_number]
                    
                    if not plan_row.empty and 'HDF_Results_Path' in plan_row.columns:
                        hdf_rel_path = plan_row['HDF_Results_Path'].iloc[0]
                        if hdf_rel_path:
                            plan_hdf_path = project_path / hdf_rel_path
                
                # If still not found, try direct file construction (common pattern)
                if not plan_hdf_path:
                    # Try common HEC-RAS naming patterns
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
                return [TextContent(
                    type="text",
                    text=f"Error: Plan '{plan_number}' not found or has no results HDF file"
                )]
            
            response_parts = [
                f"Plan Results Summary: {plan_number}",
                f"HDF Path: {plan_hdf_path}",
                "=" * 80
            ]
            
            # Get unsteady info
            try:
                unsteady_info = HdfResultsPlan.get_unsteady_info(plan_hdf_path)
                response_parts.append(dataframe_to_text(unsteady_info, "UNSTEADY INFO"))
            except Exception as e:
                response_parts.append(f"\nUnsteady info not available: {str(e)}")
            
            # Get unsteady summary
            try:
                unsteady_summary = HdfResultsPlan.get_unsteady_summary(plan_hdf_path)
                response_parts.append(dataframe_to_text(unsteady_summary, "UNSTEADY SUMMARY"))
            except Exception as e:
                response_parts.append(f"\nUnsteady summary not available: {str(e)}")
            
            # Get volume accounting
            try:
                volume_accounting = HdfResultsPlan.get_volume_accounting(plan_hdf_path)
                if volume_accounting is not None:
                    response_parts.append(dataframe_to_text(volume_accounting, "VOLUME ACCOUNTING"))
                else:
                    response_parts.append("\nVolume accounting not available")
            except Exception as e:
                response_parts.append(f"\nVolume accounting error: {str(e)}")
            
            # Get runtime data
            try:
                runtime_data = HdfResultsPlan.get_runtime_data(plan_hdf_path)
                if runtime_data is not None:
                    response_parts.append(dataframe_to_text(runtime_data, "RUNTIME DATA"))
                else:
                    response_parts.append("\nRuntime data not available")
            except Exception as e:
                response_parts.append(f"\nRuntime data error: {str(e)}")
            
            return [TextContent(
                type="text",
                text=truncate_output("\n".join(response_parts))
            )]
            
        except Exception as e:
            logger.error(f"Error getting plan results summary: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error getting plan results summary: {str(e)}"
            )]
    
    elif name == "get_compute_messages":
        try:
            project_path = Path(arguments["project_path"])
            plan_number = arguments["plan_number"]
            
            # Handle single-digit plan numbers
            if plan_number.isdigit() and len(plan_number) == 1:
                plan_number = plan_number.zfill(2)
            
            if not project_path.exists() or not project_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified project folder does not exist: {project_path}"
                )]
            
            # Initialize project to get plan info
            ras_version = HECRAS_PATH if HECRAS_PATH else HECRAS_VERSION
            ras = init_ras_project(project_path, ras_version)
            
            # Handle plan identification (reuse logic from get_plan_results_summary)
            plan_hdf_path = None
            
            # Check if plan_number is a full path to an HDF file
            if plan_number.endswith('.hdf') and Path(plan_number).exists():
                plan_hdf_path = Path(plan_number)
            else:
                # Assume it's a plan number - construct HDF path
                if hasattr(ras, 'plan_df') and ras.plan_df is not None:
                    # Look for plan by plan_number
                    plan_row = ras.plan_df[ras.plan_df['plan_number'] == plan_number]
                    
                    if not plan_row.empty and 'HDF_Results_Path' in plan_row.columns:
                        hdf_rel_path = plan_row['HDF_Results_Path'].iloc[0]
                        if hdf_rel_path:
                            plan_hdf_path = project_path / hdf_rel_path
                
                # If still not found, try direct file construction
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
                return [TextContent(
                    type="text",
                    text=f"Error: Plan '{plan_number}' not found or has no results HDF file"
                )]
            
            # Get compute messages using local implementation
            compute_messages = get_compute_messages_local(plan_hdf_path)
            
            return [TextContent(
                type="text",
                text=compute_messages
            )]
            
        except Exception as e:
            logger.error(f"Error getting compute messages: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error getting compute messages: {str(e)}"
            )]
    
    elif name == "get_hdf_structure":
        try:
            hdf_path = Path(arguments["hdf_path"])
            group_path = arguments.get("group_path", "/")
            paths_only = arguments.get("paths_only", False)
            
            if not hdf_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified HDF file does not exist: {hdf_path}"
                )]
            
            if paths_only:
                # Custom implementation for paths-only exploration
                import h5py
                paths = []
                
                def collect_paths(name, obj):
                    if isinstance(obj, h5py.Group):
                        paths.append(f"Group: /{name}")
                    elif isinstance(obj, h5py.Dataset):
                        paths.append(f"Dataset: /{name}")
                
                with h5py.File(hdf_path, 'r') as f:
                    if group_path != "/":
                        if group_path in f:
                            f[group_path].visititems(collect_paths)
                        else:
                            return [TextContent(
                                type="text",
                                text=f"Error: Group path '{group_path}' not found in HDF file"
                            )]
                    else:
                        f.visititems(collect_paths)
                
                response_parts = [
                    f"HDF File Structure (Paths Only): {hdf_path}",
                    f"Starting from: {group_path}",
                    "=" * 80,
                    "\n".join(sorted(paths))
                ]
            else:
                # Capture the full structure output
                import io
                import sys
                old_stdout = sys.stdout
                sys.stdout = buffer = io.StringIO()
                
                try:
                    HdfBase.get_dataset_info(hdf_path, group_path)
                    structure_output = buffer.getvalue()
                finally:
                    sys.stdout = old_stdout
                
                response_parts = [
                    f"HDF File Structure: {hdf_path}",
                    f"Starting from: {group_path}",
                    "=" * 80,
                    structure_output
                ]
            
            return [TextContent(
                type="text",
                text=truncate_output("\n".join(response_parts))
            )]
            
        except Exception as e:
            logger.error(f"Error getting HDF structure: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error getting HDF structure: {str(e)}"
            )]
    
    elif name == "get_projection_info":
        try:
            hdf_path = Path(arguments["hdf_path"])
            
            if not hdf_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified HDF file does not exist: {hdf_path}"
                )]
            
            projection_wkt = HdfBase.get_projection(hdf_path)
            
            response_parts = [
                f"Projection Info for: {hdf_path}",
                "=" * 80
            ]
            
            if projection_wkt:
                response_parts.append(f"\nWKT String:\n{projection_wkt}")
            else:
                response_parts.append("\nNo projection information found")
            
            return [TextContent(
                type="text",
                text=truncate_output("\n".join(response_parts))
            )]
            
        except Exception as e:
            logger.error(f"Error getting projection info: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error getting projection info: {str(e)}"
            )]
    
    else:
        return [TextContent(
            type="text",
            text=f"Error: Unknown tool: {name}"
        )]

async def main():
    """Main entry point for the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Starting HEC-RAS MCP Server...")
        
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="hecras-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())