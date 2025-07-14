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
    from ras_commander import init_ras_project, HdfBase, HdfInfiltration, HdfResultsPlan
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

def dataframe_to_text(df: pd.DataFrame, name: str) -> str:
    """Convert a pandas DataFrame to a formatted text string."""
    if df is None or df.empty:
        return f"\n{name}: No data available\n"
    
    # Use StringIO to capture the DataFrame string representation
    buffer = io.StringIO()
    df.to_string(buf=buffer, max_rows=100, max_cols=None)
    return f"\n{name}:\n{buffer.getvalue()}\n"

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="query_hecras_project",
            description="Query a HEC-RAS project and return information about plans, geometries, flows, and boundaries",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Full path to the HEC-RAS project folder"
                    },
                    "include_boundaries": {
                        "type": "boolean",
                        "description": "Include boundary conditions data (can be large)",
                        "default": False
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="get_hecras_plans",
            description="Get only the plans information from a HEC-RAS project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Full path to the HEC-RAS project folder"
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="get_hecras_geometries",
            description="Get only the geometries information from a HEC-RAS project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Full path to the HEC-RAS project folder"
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="get_infiltration_data",
            description="Get infiltration layer data and soil statistics from a HEC-RAS project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Full path to the HEC-RAS project folder"
                    },
                    "significant_threshold": {
                        "type": "number",
                        "description": "Minimum percentage threshold for significant mukeys",
                        "default": 1.0
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="get_plan_results_summary",
            description="Get comprehensive results summary from a HEC-RAS plan including unsteady info, volume accounting, and runtime data",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Full path to the HEC-RAS project folder"
                    },
                    "plan_name": {
                        "type": "string",
                        "description": "Name of the plan to get results from"
                    }
                },
                "required": ["project_path", "plan_name"]
            }
        ),
        Tool(
            name="get_hdf_structure",
            description="Explore the structure of a HEC-RAS HDF file showing groups, datasets, attributes, shapes, and dtypes",
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
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """Handle tool calls."""
    
    if name == "query_hecras_project":
        try:
            project_path = Path(arguments["project_path"])
            include_boundaries = arguments.get("include_boundaries", False)
            
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
            
            # Add plan information
            if hasattr(ras, 'plan_df') and ras.plan_df is not None:
                response_parts.append(dataframe_to_text(ras.plan_df, "PLANS"))
            
            # Add geometry information
            if hasattr(ras, 'geom_df') and ras.geom_df is not None:
                response_parts.append(dataframe_to_text(ras.geom_df, "GEOMETRIES"))
            
            # Add flow information
            if hasattr(ras, 'flow_df') and ras.flow_df is not None:
                response_parts.append(dataframe_to_text(ras.flow_df, "STEADY FLOWS"))
                
            if hasattr(ras, 'unsteady_df') and ras.unsteady_df is not None:
                response_parts.append(dataframe_to_text(ras.unsteady_df, "UNSTEADY FLOWS"))
            
            # Add boundary conditions if requested
            if include_boundaries and hasattr(ras, 'boundaries_df') and ras.boundaries_df is not None:
                response_parts.append(dataframe_to_text(ras.boundaries_df, "BOUNDARY CONDITIONS"))
            
            return [TextContent(
                type="text",
                text="\n".join(response_parts)
            )]
            
        except Exception as e:
            logger.error(f"Error querying HEC-RAS project: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error querying HEC-RAS project: {str(e)}\n\nPlease ensure:\n1. The project path is correct\n2. HEC-RAS version is installed at the expected location\n3. The project files are valid"
            )]
    
    elif name == "get_hecras_plans":
        try:
            project_path = Path(arguments["project_path"])
            
            # Use configured version or path
            ras_version = HECRAS_PATH if HECRAS_PATH else HECRAS_VERSION
            
            if not project_path.exists() or not project_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified project folder does not exist: {project_path}"
                )]
            
            ras = init_ras_project(project_path, ras_version)
            
            response_parts = [
                f"HEC-RAS Project: {ras.project_name}",
                f"Project Path: {project_path}",
                get_ras_version_info(),
                "=" * 80
            ]
            
            if hasattr(ras, 'plan_df') and ras.plan_df is not None:
                response_parts.append(dataframe_to_text(ras.plan_df, "PLANS"))
            else:
                response_parts.append("\nNo plan data available")
            
            return [TextContent(
                type="text",
                text="\n".join(response_parts)
            )]
            
        except Exception as e:
            logger.error(f"Error getting plans: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error getting HEC-RAS plans: {str(e)}"
            )]
    
    elif name == "get_hecras_geometries":
        try:
            project_path = Path(arguments["project_path"])
            
            # Use configured version or path
            ras_version = HECRAS_PATH if HECRAS_PATH else HECRAS_VERSION
            
            if not project_path.exists() or not project_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified project folder does not exist: {project_path}"
                )]
            
            ras = init_ras_project(project_path, ras_version)
            
            response_parts = [
                f"HEC-RAS Project: {ras.project_name}",
                f"Project Path: {project_path}",
                get_ras_version_info(),
                "=" * 80
            ]
            
            if hasattr(ras, 'geom_df') and ras.geom_df is not None:
                response_parts.append(dataframe_to_text(ras.geom_df, "GEOMETRIES"))
            else:
                response_parts.append("\nNo geometry data available")
            
            return [TextContent(
                type="text",
                text="\n".join(response_parts)
            )]
            
        except Exception as e:
            logger.error(f"Error getting geometries: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error getting HEC-RAS geometries: {str(e)}"
            )]
    
    elif name == "get_infiltration_data":
        try:
            project_path = Path(arguments["project_path"])
            significant_threshold = arguments.get("significant_threshold", 1.0)
            
            if not project_path.exists() or not project_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified project folder does not exist: {project_path}"
                )]
            
            # Initialize project to get rasmap_df
            ras_version = HECRAS_PATH if HECRAS_PATH else HECRAS_VERSION
            ras = init_ras_project(project_path, ras_version)
            
            response_parts = [
                f"HEC-RAS Project: {ras.project_name}",
                f"Project Path: {project_path}",
                get_ras_version_info(),
                "=" * 80
            ]
            
            # Check if infiltration data exists in rasmap_df
            if hasattr(ras, 'rasmap_df') and ras.rasmap_df is not None and not ras.rasmap_df.empty:
                # Look for infiltration layer path
                infiltration_path = None
                if 'InfiltrationLayerFilename' in ras.rasmap_df.columns:
                    infiltration_files = ras.rasmap_df['InfiltrationLayerFilename'].dropna()
                    if not infiltration_files.empty:
                        infiltration_path = Path(project_path) / infiltration_files.iloc[0]
                
                if infiltration_path and infiltration_path.exists():
                    # Get infiltration data
                    infiltration_data = HdfInfiltration.get_infiltration_layer_data(infiltration_path)
                    if infiltration_data is not None:
                        response_parts.append(dataframe_to_text(infiltration_data, "INFILTRATION LAYER DATA"))
                        
                        # Get significant mukeys if soil stats available
                        if 'percentage' in infiltration_data.columns:
                            significant_mukeys = HdfInfiltration.get_significant_mukeys(
                                infiltration_data, threshold=significant_threshold
                            )
                            if not significant_mukeys.empty:
                                response_parts.append(dataframe_to_text(
                                    significant_mukeys, 
                                    f"SIGNIFICANT MUKEYS (>{significant_threshold}%)"
                                ))
                                total_percentage = HdfInfiltration.calculate_total_significant_percentage(
                                    significant_mukeys
                                )
                                response_parts.append(f"\nTotal significant percentage: {total_percentage:.2f}%")
                    else:
                        response_parts.append("\nNo infiltration data found in layer file")
                else:
                    response_parts.append("\nNo infiltration layer file found in project")
            else:
                response_parts.append("\nNo RASMapper configuration found")
            
            return [TextContent(
                type="text",
                text="\n".join(response_parts)
            )]
            
        except Exception as e:
            logger.error(f"Error getting infiltration data: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error getting infiltration data: {str(e)}"
            )]
    
    elif name == "get_plan_results_summary":
        try:
            project_path = Path(arguments["project_path"])
            plan_name = arguments["plan_name"]
            
            if not project_path.exists() or not project_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified project folder does not exist: {project_path}"
                )]
            
            # Initialize project to get plan info
            ras_version = HECRAS_PATH if HECRAS_PATH else HECRAS_VERSION
            ras = init_ras_project(project_path, ras_version)
            
            # Find the plan HDF file
            plan_hdf_path = None
            if hasattr(ras, 'plan_df') and ras.plan_df is not None:
                plan_row = ras.plan_df[ras.plan_df['Plan Title'] == plan_name]
                if plan_row.empty:
                    plan_row = ras.plan_df[ras.plan_df['Short Identifier'] == plan_name]
                
                if not plan_row.empty and 'HDF_Results_Path' in plan_row.columns:
                    hdf_rel_path = plan_row['HDF_Results_Path'].iloc[0]
                    if hdf_rel_path:
                        plan_hdf_path = project_path / hdf_rel_path
            
            if not plan_hdf_path or not plan_hdf_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: Plan '{plan_name}' not found or has no results HDF file"
                )]
            
            response_parts = [
                f"Plan Results Summary: {plan_name}",
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
                text="\n".join(response_parts)
            )]
            
        except Exception as e:
            logger.error(f"Error getting plan results summary: {str(e)}")
            return [TextContent(
                type="text",
                text=f"Error getting plan results summary: {str(e)}"
            )]
    
    elif name == "get_hdf_structure":
        try:
            hdf_path = Path(arguments["hdf_path"])
            group_path = arguments.get("group_path", "/")
            
            if not hdf_path.exists():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified HDF file does not exist: {hdf_path}"
                )]
            
            # Capture the structure output
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
                text="\n".join(response_parts)
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
                text="\n".join(response_parts)
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