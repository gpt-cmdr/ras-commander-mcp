# HEC-RAS MCP Server

<div align="center">
  <img src="ras_commander_mcp_logo.svg" alt="RAS Commander MCP Logo" width="70%">
</div>  

The RAS Commander MCP (Model Context Protocol) server provides tools for querying HEC-RAS project information using the ras-commander library. This allows Claude Desktop to interact with HEC-RAS hydraulic modeling projects.

**RAS Commander MCP** is an open-source, LLM-forward H&H automation tool provided under MIT license by [CLB Engineering Corporation](https://clbengineering.com/). This is third-party software and is not made by or endorsed by the U.S. Army Corps of Engineers (USACE) Hydrologic Engineering Center (HEC).

For a demonstration of CLB's H&H automation services, contact us at info@clbengineering.com

## Features

- Query comprehensive HEC-RAS project information (plans, geometries, flows, boundaries)
- Extract detailed plan results including unsteady simulation info and runtime metrics
- Explore HDF file structures and extract computation messages
- Support for multiple HEC-RAS versions (6.5, 6.6, etc.)
- Formatted text output suitable for LLM interaction
- Error handling with helpful diagnostics

## Prerequisites

1. **HEC-RAS Installation**: HEC-RAS must be installed on your system (default expects version 6.6)
2. **Python**: Python 3.10+
3. **Claude Desktop**: For MCP integration
4. **uv**: Python package manager (recommended)

## Installation

### Using uv (Recommended)

1. Install uv if you haven't already:
```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone this repository:
```bash
git clone <repository-url>
cd ras-commander-mcp
```

3. The dependencies will be automatically installed when you run the server with uvx (see Configuration below).

### Using pip (Alternative)

If you prefer to use pip:
```bash
pip install mcp ras-commander pandas
```

## Configuration

### Claude Desktop Integration (Recommended)

Add the following to your Claude Desktop configuration file (`claude_desktop_config.json`):

#### Option 1: From Git Repository (Automatic Updates)
```json
{
  "mcpServers": {
    "hecras": {
      "command": "uvx",
      "args": [
        "--from", "ras-commander-mcp@git+https://github.com/gpt-cmdr/ras-commander-mcp.git",
        "ras-commander-mcp"
      ],
      "env": {
        "HECRAS_VERSION": "6.6"
      }
    }
  }
}
```

#### Option 2: Local Development Installation
If you've cloned the repository locally for development:

```json
{
  "mcpServers": {
    "hecras": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\ras-commander-mcp-main", "ras-commander-mcp"],
      "env": {
        "HECRAS_VERSION": "6.6"
      }
    }
  }
}
```

#### Option 3: Direct Python Execution
Alternative approach using Python directly:

```json
{
  "mcpServers": {
    "hecras": {
      "command": "uv",
      "args": ["run", "python", "C:\\path\\to\\ras-commander-mcp-main\\server.py"],
      "env": {
        "HECRAS_VERSION": "6.6"
      }
    }
  }
}
```

### HEC-RAS Version Configuration

The MCP server uses HEC-RAS version 6.6 by default. To use a different version:

1. **Set HEC-RAS Version** (if you have a different version installed):
   ```json
   {
     "mcpServers": {
       "hecras": {
         "command": "uvx",
         "args": [
           "--from", "ras-commander-mcp@git+https://github.com/gpt-cmdr/ras-commander-mcp.git",
           "ras-commander-mcp"
         ],
         "env": {
           "HECRAS_VERSION": "6.5"
         }
       }
     }
   }
   ```

2. **Set HEC-RAS Path** (if HEC-RAS is installed in a non-standard location):
   ```json
   {
     "mcpServers": {
       "hecras": {
         "command": "uvx",
         "args": [
           "--from", "ras-commander-mcp@git+https://github.com/gpt-cmdr/ras-commander-mcp.git",
           "ras-commander-mcp"
         ],
         "env": {
           "HECRAS_PATH": "C:\\Program Files\\HEC\\HEC-RAS\\6.5\\HEC-RAS.exe"
         }
       }
     }
   }
   ```

### Testing Configuration

Before adding to Claude Desktop, test your configuration:

```bash
# For local development:
cd path/to/ras-commander-mcp-main
set HECRAS_VERSION=6.6
uv run ras-commander-mcp

# Should start successfully showing:
# Starting HEC-RAS MCP Server...
# RAS Commander MCP by CLB Engineering Corporation
```

## Usage

### Available Tools

All tools provided by this MCP server leverage the [ras-commander](https://github.com/gpt-cmdr/ras-commander) Python library for advanced HEC-RAS automation capabilities.

1. **hecras_project_summary**: Get comprehensive or selective project information
   - Parameters:
     - `project_path` (required): Full path to HEC-RAS project folder
     - `show_rasprj` (optional): Show project file contents (default: true)
     - `show_plan_df` (optional): Show plan files and metadata (default: true)
     - `show_geom_df` (optional): Show geometry files (default: true)
     - `show_flow_df` (optional): Show steady flow data (default: true)
     - `show_unsteady_df` (optional): Show unsteady flow data (default: true)
     - `show_boundaries` (optional): Show boundary conditions (default: true)
     - `show_rasmap` (optional): Show RASMapper configuration (default: false)
     - `showmore` (optional): Show all columns/verbose mode (default: false)

2. **read_plan_description**: Read multi-line description from a plan file
   - Parameters:
     - `project_path` (required): Full path to HEC-RAS project folder
     - `plan_number` (required): Plan number (e.g., '1', '01', '02')

3. **get_plan_results_summary**: Get comprehensive results from a specific plan
   - Parameters:
     - `project_path` (required): Full path to HEC-RAS project folder
     - `plan_number` (required): Plan number or full path to plan HDF file

4. **get_compute_messages**: Get computation messages and performance metrics
   - Parameters:
     - `project_path` (required): Full path to HEC-RAS project folder
     - `plan_number` (required): Plan number or full path to plan HDF file

5. **get_hdf_structure**: Explore HDF file structure
   - Parameters:
     - `hdf_path` (required): Full path to the HDF file
     - `group_path` (optional): Internal HDF path to start exploration from (default: "/")
     - `paths_only` (optional): Show only paths without details (default: false)

6. **get_projection_info**: Get spatial projection information (WKT)
   - Parameters:
     - `hdf_path` (required): Full path to the HDF file

### Example Usage in Claude

Once configured, you can ask Claude:

- "Query the HEC-RAS project at C:/Projects/MyRiverModel"
- "Show me the plans in the Muncie test project"
- "Get the results summary for plan '01' in my project"
- "Show me the compute messages for plan '1'"
- "Explore the HDF structure of my results file"
- "Get the projection info from my terrain HDF"

## Python Library Reference

This MCP server is built on top of the [ras-commander](https://github.com/gpt-cmdr/ras-commander) Python library, which provides comprehensive programmatic access to HEC-RAS projects. For advanced Python scripting and automation beyond what's available through the MCP interface, refer to the ras-commander documentation.

## Testing

### Running Tests

From the project directory, run the complete test suite:

```bash
# Install dependencies and run all tests
uv sync
uv run python tests/test_server.py          # Basic server functionality
uv run python tests/test_all_tools.py       # Comprehensive tool validation  
uv run python tests/test_single_tool.py     # Single tool testing utility
```

Test outputs are saved to `tests/outputs/` as markdown files for review.

### Test Data

The `testdata/` folder contains complete HEC-RAS projects for testing:
- `Muncie/`: Complete project with terrain, results, and boundary conditions
- `BeaverLake/`: Additional test project

## Troubleshooting

1. **ImportError for ras-commander**: Ensure HEC-RAS is properly installed
2. **Project not found**: Verify the project path exists and contains .prj files
3. **Version errors**: Check that the specified HEC-RAS version matches your installation
4. **MCP connection issues**: Verify Claude Desktop configuration and restart Claude

## Development

To modify or extend the server:

1. Clone the repository
2. Make changes to `server.py`
3. Test with: `uv run python tests/test_all_tools.py`
4. Update Claude Desktop configuration if needed

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Trademarks

See [TRADEMARKS.md](TRADEMARKS.md) for trademark information and compliance policies.

## About

**RAS Commander MCP** is developed and maintained by [CLB Engineering Corporation](https://clbengineering.com/) as part of our commitment to advancing H&H automation through open-source tools.

For professional H&H automation services and custom solutions, contact us at info@clbengineering.com