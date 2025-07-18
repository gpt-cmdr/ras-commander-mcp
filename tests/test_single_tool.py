#!/usr/bin/env python3
"""
Test a single tool for quick iteration
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from server import handle_call_tool

async def test_single_tool(tool_name: str, arguments: dict):
    """Test a single tool call"""
    print(f"Testing {tool_name}...")
    print(f"Arguments: {arguments}")
    print("-" * 60)
    
    try:
        result = await handle_call_tool(tool_name, arguments)
        print("Output:")
        print(result[0].text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Example: Test get_hdf_structure with /Results path for BeaverLake
    asyncio.run(test_single_tool(
        "get_hdf_structure",
        {
            "hdf_path": str(Path(__file__).parent.parent / "testdata" / "BeaverLake" / "BeaverLakeSWMMImpor.p01.hdf"),
            "group_path": "/Results"
        }
    ))