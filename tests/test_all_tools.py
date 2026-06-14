#!/usr/bin/env python3
"""
Comprehensive test suite for HEC-RAS MCP tools
Saves outputs to markdown files for evaluation
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path to import server
sys.path.insert(0, str(Path(__file__).parent.parent))

from server import (
    hecras_project_summary,
    list_geometry_elements,
    read_plan_description,
    get_mesh_results,
    get_plan_summary,
    get_plan_results_summary,
    get_xsec_results,
    get_compute_messages,
    get_hdf_structure,
    get_projection_info,
    list_profiles,
    mcp,
)


class ToolTester:
    def __init__(self, project_name: str, project_path: Path):
        self.project_name = project_name
        self.project_path = project_path
        self.output_lines = []

    def add_header(self):
        """Add markdown header"""
        self.output_lines.extend([
            f"# HEC-RAS MCP Tool Test Results - {self.project_name}",
            f"",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"**Project Path:** `{self.project_path}`  ",
            f"",
            f"---",
            f""
        ])

    def add_tool_section(self, tool_name: str, description: str):
        """Add a section header for a tool"""
        self.output_lines.extend([
            f"## {tool_name}",
            f"",
            f"*{description}*",
            f""
        ])

    def add_tool_call(self, arguments: dict):
        """Add the tool call arguments"""
        self.output_lines.extend([
            f"**Arguments:**",
            f"```json",
            json.dumps(arguments, indent=2),
            f"```",
            f""
        ])

    def add_tool_output(self, output: str):
        """Add tool output in a code block"""
        self.output_lines.extend([
            f"**Tool Call Output:**",
            f"```",
            output,
            f"```",
            f"",
            f"---",
            f""
        ])

    def add_error(self, error: str):
        """Add error output"""
        self.output_lines.extend([
            f"**Error:**",
            f"```",
            f"{error}",
            f"```",
            f"",
            f"---",
            f""
        ])

    def test_tool(self, tool_func, tool_name: str, description: str, arguments: dict):
        """Test a single tool and record results"""
        self.add_tool_section(tool_name, description)
        self.add_tool_call(arguments)

        try:
            result = tool_func(**arguments)
            self.add_tool_output(result)
        except Exception as e:
            self.add_error(str(e))

    def run_all_tests(self):
        """Run all tool tests"""
        self.add_header()

        # Test 1: Default project summary (compact view)
        self.test_tool(
            hecras_project_summary,
            "hecras_project_summary",
            "Default HEC-RAS project summary (compact view)",
            {"project_path": str(self.project_path)}
        )

        # Test 2: Comprehensive project summary with boundaries (verbose)
        self.test_tool(
            hecras_project_summary,
            "hecras_project_summary",
            "Comprehensive HEC-RAS project summary with boundaries (verbose)",
            {
                "project_path": str(self.project_path),
                "show_boundaries": True,
                "showmore": True
            }
        )

        # Test 3: Get plans only (compact)
        self.test_tool(
            hecras_project_summary,
            "hecras_project_summary",
            "Get only plans information (compact)",
            {
                "project_path": str(self.project_path),
                "show_plan_df": True,
                "show_geom_df": False,
                "show_flow_df": False,
                "show_unsteady_df": False,
                "show_boundaries": False,
                "show_rasmap": False
            }
        )

        # Test 4: Get geometries only (compact)
        self.test_tool(
            hecras_project_summary,
            "hecras_project_summary",
            "Get only geometries information (compact)",
            {
                "project_path": str(self.project_path),
                "show_plan_df": False,
                "show_geom_df": True,
                "show_flow_df": False,
                "show_unsteady_df": False,
                "show_boundaries": False,
                "show_rasmap": False
            }
        )

        # Test 5: Get plans only (verbose)
        self.test_tool(
            hecras_project_summary,
            "hecras_project_summary",
            "Get only plans information (verbose - all columns)",
            {
                "project_path": str(self.project_path),
                "show_plan_df": True,
                "show_geom_df": False,
                "show_flow_df": False,
                "show_unsteady_df": False,
                "show_boundaries": False,
                "show_rasmap": False,
                "showmore": True
            }
        )

        # Test 5.5: List geometry elements
        self.test_tool(
            list_geometry_elements,
            "list_geometry_elements",
            "List major geometry elements (XS, reference lines, boundary lines, structures, mesh areas)",
            {
                "project_path": str(self.project_path),
                "element_type": "all"
            }
        )

        # Test 6: Get plan results summary
        test_plan = "01"
        self.test_tool(
            get_plan_results_summary,
            "get_plan_results_summary",
            f"Get comprehensive results summary for plan {test_plan}",
            {
                "project_path": str(self.project_path),
                "plan_number": test_plan
            }
        )

        # Test 6.1: List available result profiles/time steps
        self.test_tool(
            list_profiles,
            "list_profiles",
            f"List available result profiles/time steps for plan {test_plan}",
            {
                "project_path": str(self.project_path),
                "plan_number": test_plan
            }
        )

        # Test 6.2: Plan-level result summary metrics
        self.test_tool(
            get_plan_summary,
            "get_plan_summary",
            f"Get plan-level summary metrics for plan {test_plan}",
            {
                "project_path": str(self.project_path),
                "plan_number": test_plan,
                "max_rows": 50
            }
        )

        # Test 6.3: 2D mesh results
        self.test_tool(
            get_mesh_results,
            "get_mesh_results",
            f"Get 2D mesh max-over-time WSEL/depth/velocity for plan {test_plan}",
            {
                "project_path": str(self.project_path),
                "plan_number": test_plan,
                "profile": "max",
                "max_rows": 25
            }
        )

        # Test 6.4: 1D cross-section results
        self.test_tool(
            get_xsec_results,
            "get_xsec_results",
            f"Get 1D cross-section max-over-time WSEL/flow/velocity for plan {test_plan}",
            {
                "project_path": str(self.project_path),
                "plan_number": test_plan,
                "profile": "max",
                "max_rows": 25
            }
        )

        # Test 6.5: Get compute messages
        self.test_tool(
            get_compute_messages,
            "get_compute_messages",
            f"Get compute messages and performance metrics for plan {test_plan}",
            {
                "project_path": str(self.project_path),
                "plan_number": test_plan
            }
        )

        # Test 7: Get HDF structure
        plan_hdf_files = list(self.project_path.glob("*.p01.hdf"))
        if not plan_hdf_files:
            plan_hdf_files = list(self.project_path.glob("*.p*.hdf"))

        if plan_hdf_files:
            self.test_tool(
                get_hdf_structure,
                "get_hdf_structure",
                "Explore HDF file structure - Summary paths only (exploratory)",
                {
                    "hdf_path": str(plan_hdf_files[0]),
                    "group_path": "/Results/Summary",
                    "paths_only": True
                }
            )

            self.test_tool(
                get_hdf_structure,
                "get_hdf_structure",
                "Explore HDF file structure - Unsteady Summary Output (detailed)",
                {
                    "hdf_path": str(plan_hdf_files[0]),
                    "group_path": "/Results/Unsteady/Output/Output Blocks/Base Output/Summary Output"
                }
            )

        # Test 8: Get projection info
        if plan_hdf_files:
            self.test_tool(
                get_projection_info,
                "get_projection_info",
                "Get spatial projection from plan HDF",
                {"hdf_path": str(plan_hdf_files[0])}
            )

        geom_hdf_files = list(self.project_path.glob("*.g*.hdf"))
        if geom_hdf_files:
            self.test_tool(
                get_projection_info,
                "get_projection_info",
                "Get spatial projection from geometry HDF",
                {"hdf_path": str(geom_hdf_files[0])}
            )

    def save_output(self, output_path: Path):
        """Save the output to a markdown file"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.output_lines))
        print(f"Output saved to: {output_path}")


def main():
    """Main test runner"""
    repo_root = Path(__file__).parent.parent

    test_configs = [
        {
            "name": "beaverlake",
            "path": repo_root / "testdata" / "BeaverLake",
            "output": repo_root / "tests" / "outputs" / "toolcalloutput-beaverlake.md"
        },
        {
            "name": "muncie",
            "path": repo_root / "testdata" / "Muncie",
            "output": repo_root / "tests" / "outputs" / "toolcalloutput-muncie.md"
        }
    ]

    # List available tools (async API)
    import asyncio
    print("Available MCP Tools:")
    print("=" * 60)
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
    print()

    # Run tests for each project
    for config in test_configs:
        print(f"\nTesting {config['name'].upper()} project...")
        print("=" * 60)

        if not config["path"].exists():
            print(f"ERROR: Test data not found at {config['path']}")
            continue

        tester = ToolTester(config["name"].title(), config["path"])
        tester.run_all_tests()
        tester.save_output(config["output"])

        print(f"Completed testing {config['name']}")

    print("\nAll tests completed!")
    print(f"Check the outputs in: {repo_root / 'tests' / 'outputs'}")


if __name__ == "__main__":
    main()
