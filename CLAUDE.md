# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Build & Development
- **Install dependencies**: `pip install -r requirements.txt` or `pip install mcp ras-commander pandas`
- **Run MCP server**: `python server.py`
- **Test with example client**: `python example_client.py` (update project_path in the file first)
- **Python environment**: Use Anaconda3 installation in Windows user folder for consistency with ras-commander

### Testing
- **Test data location**: Use `testdata/Muncie/` folder for testing HEC-RAS functionality
- **Verify MCP tools**: Run example_client.py to test all three MCP tools
- **Integration test**: Configure in Claude Desktop and test with actual HEC-RAS queries

## Architecture

### MCP Server Pattern
This repository implements a Model Context Protocol (MCP) server that bridges HEC-RAS hydraulic modeling software with Claude:

1. **server.py**: Async Python MCP server exposing three tools:
   - `query_hecras_project`: Comprehensive project info (plans, geometries, flows, boundaries)
   - `get_hecras_plans`: Plan information only
   - `get_hecras_geometries`: Geometry information only

2. **Data Flow**:
   - HEC-RAS project files → ras-commander library → pandas DataFrames → formatted text → Claude
   - All DataFrames converted to text format for LLM interaction

3. **Integration Points**:
   - Uses `ras_commander.init_ras_project()` to load HEC-RAS projects
   - Supports HEC-RAS versions 6.5, 6.6 (configurable)
   - Claude Desktop integration via package.json configuration

### Key Dependencies
- **mcp**: Model Context Protocol server framework
- **ras-commander**: HEC-RAS project interface library (requires HEC-RAS installation)
- **pandas**: DataFrame handling for structured data

### Error Handling
- Validates project paths before initialization
- Provides detailed error messages for common issues (missing files, wrong version, etc.)
- Graceful handling of missing data components (plans, geometries, etc.)

## HEC-RAS Integration Notes
- Requires HEC-RAS to be installed at expected location (typically C:\Program Files (x86)\HEC\HEC-RAS\)
- Project paths must point to folder containing .prj files
- Muncie test data includes all necessary components (HDF5 results, terrain, boundaries, etc.)