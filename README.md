# HEC-RAS MCP Server

An MCP (Model Context Protocol) server that provides tools for querying HEC-RAS project information using the ras-commander library. This allows Claude Desktop to interact with HEC-RAS hydraulic modeling projects.

## Features

- Query comprehensive HEC-RAS project information (plans, geometries, flows, boundaries)
- Get specific components (plans only, geometries only)
- Support for multiple HEC-RAS versions (6.5, 6.6, etc.)
- Formatted text output suitable for LLM interaction
- Error handling with helpful diagnostics

## Prerequisites

1. **HEC-RAS Installation**: HEC-RAS must be installed on your system
2. **Python**: Python 3.8+ with Anaconda recommended
3. **Claude Desktop**: For MCP integration

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd ras-commander-mcp
```

2. Install dependencies using the Anaconda environment:
```bash
# Using the specified Anaconda environment
C:\Users\billk\anaconda3\envs\claude_test_env\python.exe -m pip install -r requirements.txt
```

Or create a new conda environment:
```bash
conda create -n hecras-mcp python=3.9
conda activate hecras-mcp
pip install -r requirements.txt
```

## Configuration

### Claude Desktop Integration

Add the following to your Claude Desktop configuration file (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "hecras": {
      "command": "C:\\Users\\billk\\anaconda3\\envs\\claude_test_env\\python.exe",
      "args": ["C:\\GH\\ras-commander-mcp\\server.py"]
    }
  }
}
```

Adjust the paths to match your installation.

## Usage

### Available Tools

1. **query_hecras_project**: Get comprehensive project information
   - Parameters:
     - `project_path` (required): Full path to HEC-RAS project folder
     - `ras_version` (optional): HEC-RAS version (default: "6.6")
     - `include_boundaries` (optional): Include boundary conditions (default: false)

2. **get_hecras_plans**: Get only plan information
   - Parameters:
     - `project_path` (required): Full path to HEC-RAS project folder
     - `ras_version` (optional): HEC-RAS version (default: "6.6")

3. **get_hecras_geometries**: Get only geometry information
   - Parameters:
     - `project_path` (required): Full path to HEC-RAS project folder
     - `ras_version` (optional): HEC-RAS version (default: "6.6")

### Example Usage in Claude

Once configured, you can ask Claude:

- "Query the HEC-RAS project at C:/Projects/MyRiverModel"
- "Show me the plans in the Muncie test project"
- "Get the geometries from my HEC-RAS model"

### Testing

Run the example client to test the server:

```bash
# Using the Anaconda environment
C:\Users\billk\anaconda3\envs\claude_test_env\python.exe example_client.py
```

This will query the included Muncie test data and display the results.

## Test Data

The `testdata/Muncie/` folder contains a complete HEC-RAS project for testing, including:
- HDF5 result files
- Terrain data
- Geometry files
- Plan files
- Boundary conditions
- GIS shapefiles

## Troubleshooting

1. **ImportError for ras-commander**: Ensure ras-commander is installed and HEC-RAS is properly installed
2. **Project not found**: Verify the project path exists and contains .prj files
3. **Version errors**: Check that the specified HEC-RAS version matches your installation

## Development

To modify or extend the server:

1. Edit `server.py` to add new tools or modify existing ones
2. Test changes with `example_client.py`
3. Update Claude Desktop configuration if paths change

## License

This project is provided as-is for interfacing with HEC-RAS projects through Claude Desktop.