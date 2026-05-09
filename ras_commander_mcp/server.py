"""FastMCP entrypoint for RAS Commander MCP."""

import logging

from fastmcp import FastMCP

from .tools_execution import register_execution_tools
from .tools_qaqc import register_qaqc_tools
from .tools_remote import register_remote_tools
from .tools_review import (
    get_compute_messages,
    get_hdf_structure,
    get_plan_results_summary,
    get_projection_info,
    hecras_project_summary,
    read_plan_description,
    register_review_tools,
)


logging.basicConfig(level=logging.INFO)

mcp = FastMCP(
    name="RAS Commander",
    version="0.2.0",
    instructions="HEC-RAS MCP server powered by ras-commander. By CLB Engineering Corporation.",
)


def register_tools() -> None:
    """Register all MCP tool groups."""
    register_review_tools(mcp)
    register_execution_tools(mcp)
    register_remote_tools(mcp)
    register_qaqc_tools(mcp)


register_tools()


def run() -> None:
    """Entry point for console script."""
    mcp.run()


__all__ = [
    "mcp",
    "run",
    "register_tools",
    "hecras_project_summary",
    "read_plan_description",
    "get_plan_results_summary",
    "get_compute_messages",
    "get_hdf_structure",
    "get_projection_info",
]


if __name__ == "__main__":
    run()
