#!/usr/bin/env python3
"""
Example client for testing the HEC-RAS MCP Server
"""

import asyncio
import json
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    """Example of using the HEC-RAS MCP server"""
    
    # Create server parameters - adjust the path to your server.py
    server_params = StdioServerParameters(
        command=r"C:\Users\billk\anaconda3\envs\claude_test_env\python.exe",
        args=["./server.py"],
        env=None
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            # List available tools
            tools_response = await session.list_tools()
            print("Available tools:")
            # tools_response is a tuple, extract the tools list
            tools_list = tools_response[0] if isinstance(tools_response, tuple) else tools_response
            for tool in tools_list:
                print(f"  - {tool.name}: {tool.description}")
            print()
            
            # Get the absolute path to the Muncie test data
            muncie_path = Path(__file__).parent / "testdata" / "Muncie"
            muncie_path = muncie_path.resolve()
            
            # Example 1: Query comprehensive project information
            print("Example 1: Querying comprehensive HEC-RAS project information...")
            result = await session.call_tool(
                "query_hecras_project",
                arguments={
                    "project_path": str(muncie_path),
                    "ras_version": "6.6",
                    "include_boundaries": False
                }
            )
            print("Result:")
            print(result.content[0].text)
            print("-" * 80)
            
            # Example 2: Get only plans
            print("\nExample 2: Getting only plans information...")
            result = await session.call_tool(
                "get_hecras_plans",
                arguments={
                    "project_path": str(muncie_path),
                    "ras_version": "6.6"
                }
            )
            print("Plans Result:")
            print(result.content[0].text[:500] + "...")  # Show first 500 chars
            print("-" * 80)
            
            # Example 3: Get only geometries
            print("\nExample 3: Getting only geometries information...")
            result = await session.call_tool(
                "get_hecras_geometries",
                arguments={
                    "project_path": str(muncie_path),
                    "ras_version": "6.6"
                }
            )
            print("Geometries Result:")
            print(result.content[0].text[:500] + "...")  # Show first 500 chars

if __name__ == "__main__":
    asyncio.run(main())