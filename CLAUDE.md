# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**You prefer to read full file contents before editing**

## Commands

### Build & Development
- **Install dependencies**: `uv pip install mcp ras-commander pandas` or `uv sync`
- **Run MCP server**: `uv run python server.py`
- **Alternative for testing**: `uvx --from . ras-commander-mcp`
- **Debug mode**: `uv run python server.py 2>&1 | grep DEBUG` - Shows comprehensive stderr logging for troubleshooting

### Testing & Validation
- **Comprehensive testing**: `uv run python tests/test_all_tools.py` - Tests all MCP tools on both Muncie and BeaverLake projects
- **Single tool testing**: `uv run python tests/test_single_tool.py` - Modify the script to test specific tools quickly
- **Direct server testing**: `uv run python tests/test_server.py` - Basic functionality validation
- **Test data locations**: `testdata/Muncie/` and `testdata/BeaverLake/` contain complete HEC-RAS projects
- **Test outputs**: Check `tests/outputs/` for markdown reports of tool functionality
- **Integration testing**: Configure in Claude Desktop and test with actual HEC-RAS queries

### Required Post-Update Testing
After making changes to the MCP server, run these tests in order:
1. `uv run python tests/test_server.py` - Verify basic server functionality
2. `uv run python tests/test_all_tools.py` - Comprehensive tool validation
3. Review output files in `tests/outputs/` directory
4. Test Claude Desktop integration with sample queries

### Debugging & Troubleshooting
- **View debug output**: `uv run python tests/test_server.py 2>&1 | grep "\[DEBUG\]"` - Shows all debug messages
- **Diagnose import issues**: Check stderr for "Error importing" messages during server startup
- **Monitor tool calls**: Debug output shows exact function calls and arguments passed to each tool
- **Claude Desktop logs**: stderr output appears in Claude Desktop application logs for real-time debugging
- **Server startup sequence**: Debug messages trace: imports → server creation → configuration → tool registration → MCP protocol initialization
- **Error context**: All exceptions include full debug context showing exactly where failures occur

## Project Structure

```
ras-commander-mcp-main/
├── server.py                    # Main MCP server implementation
├── pyproject.toml              # Package configuration with dependencies
├── requirements.txt            # Legacy pip dependencies (for compatibility)
├── claude_desktop_config.json  # Example Claude Desktop configuration
├── tests/                      # Testing suite
│   ├── __init__.py
│   ├── test_server.py         # Basic server functionality tests
│   ├── test_all_tools.py      # Comprehensive tool testing suite
│   ├── test_single_tool.py    # Single tool testing utility
│   └── outputs/               # Test output markdown files
├── testdata/
│   ├── Muncie/                # Complete HEC-RAS project for testing
│   └── BeaverLake/            # Additional test project
├── ras-commander reference files/ # API documentation and examples
└── NonWorking_Tools.md         # Documentation of removed/broken tools
```

## Architecture

### MCP Server Implementation
This repository implements a Model Context Protocol (MCP) server that bridges HEC-RAS hydraulic modeling software with Claude Desktop. The server is built on top of the [ras-commander](https://github.com/gpt-cmdr/ras-commander) Python library.

**Core MCP Tools** (server.py:285-451):
- `hecras_project_summary`: Comprehensive or selective project information with boolean flags controlling output sections
- `read_plan_description`: Extract the multi-line description from a specific plan file
- `get_plan_results_summary`: Detailed plan results including unsteady simulation info, volume accounting, and runtime performance data
- `get_compute_messages`: Computation messages and performance metrics from HEC-RAS simulations with smart truncation
- `get_hdf_structure`: HDF file structure exploration with group/dataset details and attributes
- `get_projection_info`: Spatial projection information (WKT format) extraction from HDF files

**Data Processing Pipeline**:
1. HEC-RAS project files (.prj, .g*, .p*, .u*, etc.) 
2. ras-commander library parsing → pandas DataFrames
3. DataFrame filtering and formatting (server.py:215-283)
4. Text conversion with truncation limits (server.py:199-213)
5. Structured output to Claude via MCP protocol

**ras-commander Integration**:
- Uses `ras_commander.init_ras_project()` for project initialization
- Leverages `HdfBase`, `HdfResultsPlan` classes for HDF data access
- Implements local `get_compute_messages_local()` for simulation performance analysis
- Plan identification supports both numeric ("1", "01") and full HDF path inputs with auto-padding
- Follows ras-commander naming conventions and API patterns
- Supports HEC-RAS versions 6.5, 6.6 (configurable via environment variables)

### Key Dependencies
- **mcp**: Model Context Protocol server framework
- **ras-commander**: HEC-RAS project interface library (requires HEC-RAS installation)
- **pandas**: DataFrame handling and data manipulation
- **h5py**: Direct HDF5 file access for structure exploration

### Error Handling & Robustness
- Path validation before project initialization (server.py:476-480)
- Graceful handling of missing data components (plans, geometries, boundaries)
- Detailed error messages for common issues (version mismatches, missing files)
- Output truncation to prevent token limit exceeded errors (server.py:199-213)
- DataFrame column filtering for concise vs verbose output modes (server.py:215-283)

### Debugging & Diagnostics Architecture
- **Comprehensive stderr logging**: `debug_print()` function outputs detailed diagnostic messages to stderr (server.py:20-22)
- **Import validation**: Step-by-step verification of MCP and ras-commander library imports with specific error reporting (server.py:26-48)
- **Server lifecycle tracking**: Debug messages for server initialization, tool calls, and execution flow (server.py:924-967)
- **Tool call instrumentation**: Detailed logging of function calls, arguments, and execution paths (server.py:454-921)
- **Dual logging system**: Both stderr debug messages and standard Python logging for comprehensive diagnostics
- **Error context preservation**: All exceptions include debug output with full context for troubleshooting
- **Claude Desktop integration debugging**: stderr output appears in Claude Desktop logs for real-time troubleshooting

## HEC-RAS Integration Requirements
- HEC-RAS installation required at standard location: `C:\Program Files (x86)\HEC\HEC-RAS\`
- Project paths must point to folders containing `.prj` files
- Test projects (Muncie, BeaverLake) include complete model components
- Environment variables: `HECRAS_VERSION` (default: "6.6"), `HECRAS_PATH` (custom installation path)

## About This Tool
**RAS Commander MCP** is an open-source, LLM-forward H&H automation tool provided under MIT license by CLB Engineering Corporation. This is third-party software and is not made by or endorsed by USACE HEC. For more Python functionality, see the [ras-commander](https://github.com/gpt-cmdr/ras-commander) repository.