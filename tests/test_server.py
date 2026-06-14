#!/usr/bin/env python3
"""
Direct test of the MCP server functionality
"""

import sys
from pathlib import Path

# Add parent directory to path to import server
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the tool functions directly
from server import (
    hecras_project_summary,
    list_geometry_elements,
    read_plan_description,
    get_compute_messages,
    get_mesh_results,
    get_plan_summary,
    get_plan_results_summary,
    get_xsec_results,
    get_hdf_structure,
    get_projection_info,
    list_profiles,
    mcp,
)


def test_server():
    """Test the server functions directly"""
    print("Testing HEC-RAS MCP Server...")
    print("=" * 60)

    # Test listing tools via FastMCP (async API)
    import asyncio
    print("\n1. Testing tool listing...")
    tools = asyncio.run(mcp.list_tools())
    print(f"Found {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")

    # Test querying the Muncie project
    print("\n2. Testing hecras_project_summary with Muncie data...")
    muncie_path = Path(__file__).parent.parent / "testdata" / "Muncie"
    muncie_path = muncie_path.resolve()

    try:
        result = hecras_project_summary(project_path=str(muncie_path))
        print("Result:")
        print(result[:1000] + "..." if len(result) > 1000 else result)
    except Exception as e:
        print(f"Error: {e}")

    # Test getting project summary (plans only)
    print("\n3. Testing hecras_project_summary (plans only)...")
    try:
        result = hecras_project_summary(
            project_path=str(muncie_path),
            show_plan_df=True,
            show_geom_df=False,
            show_flow_df=False,
            show_unsteady_df=False,
            show_boundaries=False,
        )
        print("Result:")
        print(result[:500] + "..." if len(result) > 500 else result)
    except Exception as e:
        print(f"Error: {e}")


def test_new_tools():
    """Test the new HEC-RAS tools"""
    print("\n\nTesting NEW HEC-RAS MCP Tools...")
    print("=" * 60)

    muncie_path = Path(__file__).parent.parent / "testdata" / "Muncie"
    muncie_path = muncie_path.resolve()

    # Test compute messages
    print("\n4. Testing get_compute_messages...")
    try:
        result = get_compute_messages(
            project_path=str(muncie_path),
            plan_number="01",
        )
        print("Result:")
        print(result[:800] + "..." if len(result) > 800 else result)
    except Exception as e:
        print(f"Error: {e}")

    # Test plan results summary
    print("\n5. Testing get_plan_results_summary...")
    try:
        result = get_plan_results_summary(
            project_path=str(muncie_path),
            plan_number="01",
        )
        print("Result:")
        print(result[:1000] + "..." if len(result) > 1000 else result)
    except Exception as e:
        print(f"Error: {e}")

    # Test output profile listing
    print("\n5.1. Testing list_profiles...")
    try:
        result = list_profiles(
            project_path=str(muncie_path),
            plan_number="01",
        )
        print("Result:")
        print(result[:1000] + "..." if len(result) > 1000 else result)
    except Exception as e:
        print(f"Error: {e}")

    # Test plan summary metrics
    print("\n5.2. Testing get_plan_summary...")
    try:
        result = get_plan_summary(
            project_path=str(muncie_path),
            plan_number="01",
        )
        print("Result:")
        print(result[:1000] + "..." if len(result) > 1000 else result)
    except Exception as e:
        print(f"Error: {e}")

    # Test 2D mesh results
    print("\n5.3. Testing get_mesh_results...")
    try:
        result = get_mesh_results(
            project_path=str(muncie_path),
            plan_number="01",
            profile="max",
            max_rows=10,
        )
        print("Result:")
        print(result[:1000] + "..." if len(result) > 1000 else result)
    except Exception as e:
        print(f"Error: {e}")

    # Test 1D cross-section results
    print("\n5.4. Testing get_xsec_results...")
    try:
        result = get_xsec_results(
            project_path=str(muncie_path),
            plan_number="01",
            profile="max",
            max_rows=10,
        )
        print("Result:")
        print(result[:1000] + "..." if len(result) > 1000 else result)
    except Exception as e:
        print(f"Error: {e}")

    # Find a plan HDF file to test with
    plan_hdf_files = list(muncie_path.glob("*.p*.hdf"))
    if plan_hdf_files:
        test_hdf = plan_hdf_files[0]

        # Test HDF structure (paths only for Summary)
        print(f"\n6. Testing get_hdf_structure with {test_hdf.name}...")
        try:
            result = get_hdf_structure(
                hdf_path=str(test_hdf),
                group_path="/Results/Summary",
                paths_only=True,
            )
            print("Result (first 1000 chars):")
            print(result[:1000] + "..." if len(result) > 1000 else result)
        except Exception as e:
            print(f"Error: {e}")

    # Test geometry element listing
    print("\n7.5. Testing list_geometry_elements...")
    try:
        result = list_geometry_elements(
            project_path=str(muncie_path),
            element_type="all",
        )
        print("Result:")
        print(result[:1200] + "..." if len(result) > 1200 else result)
    except Exception as e:
        print(f"Error: {e}")

    # Find a geometry HDF file for projection test
    geom_hdf_files = list(muncie_path.glob("*.g*.hdf"))
    if geom_hdf_files:
        geom_hdf = geom_hdf_files[0]

        # Test projection info
        print(f"\n7. Testing get_projection_info with {geom_hdf.name}...")
        try:
            result = get_projection_info(hdf_path=str(geom_hdf))
            print("Result:")
            print(result)
        except Exception as e:
            print(f"Error: {e}")


def test_read_plan_description():
    """Test the read_plan_description tool"""
    print("\n\nTesting read_plan_description tool...")
    print("=" * 60)

    muncie_path = Path(__file__).parent.parent / "testdata" / "Muncie"
    muncie_path = muncie_path.resolve()

    print("\n8. Testing read_plan_description...")
    try:
        result = read_plan_description(
            project_path=str(muncie_path),
            plan_number="01",
        )
        print("Result:")
        print(result)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_server()
    test_new_tools()
    test_read_plan_description()
