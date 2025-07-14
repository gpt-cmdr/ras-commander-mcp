#!/usr/bin/env python3
"""
Direct test of the MCP server functionality
"""

import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import the server components
from server import handle_list_tools, handle_call_tool

async def test_server():
    """Test the server functions directly"""
    print("Testing HEC-RAS MCP Server...")
    print("=" * 60)
    
    # Test listing tools
    print("\n1. Testing tool listing...")
    tools = await handle_list_tools()
    print(f"Found {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
    
    # Test querying the Muncie project
    print("\n2. Testing query_hecras_project with Muncie data...")
    muncie_path = Path(__file__).parent / "testdata" / "Muncie"
    muncie_path = muncie_path.resolve()
    
    try:
        result = await handle_call_tool("query_hecras_project", {
            "project_path": str(muncie_path),
            "include_boundaries": False
        })
        print("Result:")
        print(result[0].text[:1000] + "..." if len(result[0].text) > 1000 else result[0].text)
    except Exception as e:
        print(f"Error: {e}")
    
    # Test getting plans only
    print("\n3. Testing get_hecras_plans...")
    try:
        result = await handle_call_tool("get_hecras_plans", {
            "project_path": str(muncie_path)
        })
        print("Result:")
        print(result[0].text[:500] + "..." if len(result[0].text) > 500 else result[0].text)
    except Exception as e:
        print(f"Error: {e}")

async def test_new_tools():
    """Test the new HEC-RAS tools"""
    print("\n\nTesting NEW HEC-RAS MCP Tools...")
    print("=" * 60)
    
    muncie_path = Path(__file__).parent / "testdata" / "Muncie"
    muncie_path = muncie_path.resolve()
    
    # Test infiltration data
    print("\n4. Testing get_infiltration_data...")
    try:
        result = await handle_call_tool("get_infiltration_data", {
            "project_path": str(muncie_path),
            "significant_threshold": 5.0
        })
        print("Result:")
        print(result[0].text[:800] + "..." if len(result[0].text) > 800 else result[0].text)
    except Exception as e:
        print(f"Error: {e}")
    
    # Test plan results summary
    print("\n5. Testing get_plan_results_summary...")
    try:
        result = await handle_call_tool("get_plan_results_summary", {
            "project_path": str(muncie_path),
            "plan_name": "9-SAs"
        })
        print("Result:")
        print(result[0].text[:1000] + "..." if len(result[0].text) > 1000 else result[0].text)
    except Exception as e:
        print(f"Error: {e}")
    
    # Find an HDF file to test with
    hdf_files = list(muncie_path.glob("*.hdf"))
    if hdf_files:
        test_hdf = hdf_files[0]
        
        # Test HDF structure
        print(f"\n6. Testing get_hdf_structure with {test_hdf.name}...")
        try:
            result = await handle_call_tool("get_hdf_structure", {
                "hdf_path": str(test_hdf),
                "group_path": "/"
            })
            print("Result (first 1000 chars):")
            print(result[0].text[:1000] + "..." if len(result[0].text) > 1000 else result[0].text)
        except Exception as e:
            print(f"Error: {e}")
        
        # Test projection info
        print(f"\n7. Testing get_projection_info with {test_hdf.name}...")
        try:
            result = await handle_call_tool("get_projection_info", {
                "hdf_path": str(test_hdf)
            })
            print("Result:")
            print(result[0].text)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_server())
    asyncio.run(test_new_tools())