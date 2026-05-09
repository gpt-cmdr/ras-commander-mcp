#!/usr/bin/env python3
"""Compatibility wrapper for the packaged RAS Commander MCP server."""

from ras_commander_mcp.server import (
    get_compute_messages,
    get_hdf_structure,
    get_plan_results_summary,
    get_projection_info,
    hecras_project_summary,
    mcp,
    read_plan_description,
    run,
)


__all__ = [
    "mcp",
    "run",
    "hecras_project_summary",
    "read_plan_description",
    "get_plan_results_summary",
    "get_compute_messages",
    "get_hdf_structure",
    "get_projection_info",
]


if __name__ == "__main__":
    run()
