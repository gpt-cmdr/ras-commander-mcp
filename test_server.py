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
            "ras_version": "6.6",
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
            "project_path": str(muncie_path),
            "ras_version": "6.6"
        })
        print("Result:")
        print(result[0].text[:500] + "..." if len(result[0].text) > 500 else result[0].text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_server())