#!/usr/bin/env python3
"""
HEC-RAS MCP Server

An MCP server that provides tools for querying HEC-RAS project information
using the ras-commander library.
"""

import asyncio
import json
import logging
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
    from ras_commander import init_ras_project
except ImportError:
    raise ImportError("ras-commander is not installed. Please install it with: pip install ras-commander")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the MCP server
server = Server("hecras-mcp-server")

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
                    "ras_version": {
                        "type": "string",
                        "description": "HEC-RAS version (e.g., '6.5', '6.6')",
                        "default": "6.6"
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
                    },
                    "ras_version": {
                        "type": "string",
                        "description": "HEC-RAS version (e.g., '6.5', '6.6')",
                        "default": "6.6"
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
                    },
                    "ras_version": {
                        "type": "string",
                        "description": "HEC-RAS version (e.g., '6.5', '6.6')",
                        "default": "6.6"
                    }
                },
                "required": ["project_path"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """Handle tool calls."""
    
    if name == "query_hecras_project":
        try:
            project_path = Path(arguments["project_path"])
            ras_version = arguments.get("ras_version", "6.6")
            include_boundaries = arguments.get("include_boundaries", False)
            
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
                f"HEC-RAS Version: {ras_version}",
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
            ras_version = arguments.get("ras_version", "6.6")
            
            if not project_path.exists() or not project_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified project folder does not exist: {project_path}"
                )]
            
            ras = init_ras_project(project_path, ras_version)
            
            response_parts = [
                f"HEC-RAS Project: {ras.project_name}",
                f"Project Path: {project_path}",
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
            ras_version = arguments.get("ras_version", "6.6")
            
            if not project_path.exists() or not project_path.is_dir():
                return [TextContent(
                    type="text",
                    text=f"Error: The specified project folder does not exist: {project_path}"
                )]
            
            ras = init_ras_project(project_path, ras_version)
            
            response_parts = [
                f"HEC-RAS Project: {ras.project_name}",
                f"Project Path: {project_path}",
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