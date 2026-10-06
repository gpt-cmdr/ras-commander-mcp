# Installation

Use Python 3.10+ in an authorized environment. Install the published package with
`python -m pip install --upgrade ras-commander-mcp`, or let a uv-based client run
`uvx ras-commander-mcp`; retain an existing lock or pin when reproducibility
requires it. Version 0.4 needs ras-commander 0.104.0 or later for project metadata
and plan configuration. Update commands for pip, cached `uvx` and `uv tool`
installations, and Windows long-path guidance, are in the
[README](https://github.com/gpt-cmdr/ras-commander-mcp#update-an-installation).

Set `RAS_MCP_ALLOWED_ROOTS` to a nonempty JSON array of resolved absolute project
roots, then run `ras-commander-mcp` or `python -m ras_commander_mcp`. Missing root
configuration fails startup. Relative file arguments are resolved only within the
named configured root. No engine installation or HEC terms acceptance is involved.

A client must restrict project tools to bounded subagents. Transport configuration
alone does not provide that restriction. Clients that cannot isolate those tools
should use scoped public Python APIs instead. For Claude Code, the
`ras-commander@ras-commander-plugin` plugin from
[gpt-cmdr/ras-commander-plugin](https://github.com/gpt-cmdr/ras-commander-plugin)
(forthcoming) provides the server, a plugin subagent and a `PreToolUse` guard.

The server speaks local stdio through the official MCP Python SDK v2. There is no
HTTP server, authentication configuration, remote hosting, or model sampling.
See [compatibility](compatibility.md) for released-library support and refreshes.
