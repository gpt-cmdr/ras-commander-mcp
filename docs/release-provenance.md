# Release provenance: 0.4 redesign

On October 3, 2026, PyPI reported ras-commander-mcp 0.3.2 and ras-commander
0.103.0. The inspected repository main commit `08c72f0` declared MCP version
0.2.0 and FastMCP >=3, while published 0.3.2 wheel/sdist declared MCP SDK >=1
and a monolithic `server:run` entry point. GitHub returned no tags or releases
for the repository. This establishes drift, not its historical cause.

The published 0.3.2 server was 38,555 bytes (SHA-256
`e7ac991a97da12ae1ee23f19e99ed5c57f023623eba97f0e2f9d1aba0d405651`).
The wheel included repository-relative `./` entries, tests, personal local settings,
generated knowledge and copied library references because it packaged `.`. No
published installation was executed to infer whether those paths were importable.
Downloaded artifacts were checked against PyPI's SHA-256 digests; detailed URLs,
metadata, entry points and upload dates are retained in the implementation research
packet, outside this distribution.

Version 0.4.0 intentionally supersedes both version declarations and replaces the
broad tool set without aliases. It packages only `ras_commander_mcp`, points the
console script at `ras_commander_mcp.server:run`, and removes frozen library copies,
generated knowledge, obsolete tests and personal permission settings. The new
source distribution includes maintained docs and release-maintenance scripts.

The official MCP SDK v2.3.0 was selected over standalone FastMCP v4.0.10. A Linux
CPython 3.11 binary-only download comparison found 28 wheels/9.07 MiB compressed
for SDK alone versus 71 wheels/16.61 MiB for FastMCP alone. These are dependency
resolution observations, not installed size/import-time measurements; full server
installation also inherits ras-commander's numpy/pandas/h5py base dependencies.

Primary protocol/API references:

- [Official MCP Python SDK v2](https://py.sdk.modelcontextprotocol.io/)
- [Structured tool outputs](https://py.sdk.modelcontextprotocol.io/servers/structured-output/)
- [Tool contracts and annotation limitations](https://py.sdk.modelcontextprotocol.io/servers/tools/)
- [Current MCP specification](https://modelcontextprotocol.io/specification/latest)

The SDK implements protocol revision handling. This package does not hardcode an
initialize handshake or claim support for every older client without qualification.
