# Installation

This MCP server uses [`uv`](https://docs.astral.sh/uv/) to manage its Python virtual
environment. Once `uv` is installed, the Claude Desktop configuration handles package
installation and runs the server locally whenever Claude Desktop (or Claude Code) starts.

## Prerequisites

1. **HEC-RAS Installation** — HEC-RAS must be installed on your system (the default expects
   version 6.6).
2. **Python** — Python 3.10 or newer.
3. **Claude Desktop** — for MCP integration.
4. **uv** — Python package manager (recommended).

## Install uv

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Configure Claude Desktop

Add the following to your Claude Desktop configuration file
(`claude_desktop_config.json`). This installs the published package and sets up a virtual
environment through `uvx` to run the server.

```json
{
  "mcpServers": {
    "hecras": {
      "command": "uvx",
      "args": ["ras-commander-mcp"],
      "env": {
        "HECRAS_VERSION": "6.6"
      }
    }
  }
}
```

### Alternate: install from the Git repository

For the latest, unreleased version, install directly from GitHub:

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

### Alternate: local development install

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

## Settings

The server reads HEC-RAS configuration from environment variables in the `env` block.

- **`HECRAS_VERSION`** — the installed HEC-RAS version to target (default `6.6`). Set this if
  you have a different version, e.g. `"6.5"`.
- **`HECRAS_PATH`** — the full path to `HEC-RAS.exe` if HEC-RAS is installed in a non-standard
  location, e.g. `"C:\\Program Files\\HEC\\HEC-RAS\\6.5\\HEC-RAS.exe"`.

!!! info
    These settings exist for forthcoming functionality (executing HEC-RAS runs from the MCP
    server). They are not yet required for the current query-only tools, but `HECRAS_VERSION`
    should match your installation to avoid version errors.

## Test the configuration

Before adding the server to Claude Desktop, you can test it from the project directory:

```bash
# For local development:
cd path/to/ras-commander-mcp-main
set HECRAS_VERSION=6.6
uv run ras-commander-mcp

# Should start successfully showing:
# Starting HEC-RAS MCP Server...
# RAS Commander MCP by CLB Engineering Corporation
```

## Troubleshooting

- **ImportError for ras-commander** — ensure HEC-RAS is properly installed.
- **Project not found** — verify the project path exists and contains `.prj` files.
- **Version errors** — check that the specified HEC-RAS version matches your installation.
- **MCP connection issues** — verify the Claude Desktop configuration and restart Claude.
