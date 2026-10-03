# Installation

Install `ras-commander-mcp` with Python 3.10+ in an authorized environment. Use
`python -m pip install --upgrade ras-commander-mcp` for a managed current install;
retain an existing lock or pin when reproducibility requires it.

Set `RAS_MCP_ALLOWED_ROOTS` to a nonempty JSON array of resolved absolute project
roots, then run `ras-commander-mcp` or `python -m ras_commander_mcp`. Missing root
configuration fails startup. Relative file arguments are resolved only within the
named configured root. No engine installation or HEC terms acceptance is involved.

A client must restrict project tools to bounded subagents. Transport configuration
alone does not provide that restriction. Clients that cannot isolate those tools
should use scoped public Python APIs instead.

The server speaks local stdio through the official MCP Python SDK v2. There is no
HTTP server, authentication configuration, remote hosting, or model sampling.
See [compatibility](compatibility.md) for released-library support and refreshes.
