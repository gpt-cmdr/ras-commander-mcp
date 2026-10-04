# RAS Commander MCP

RAS Commander MCP provides bounded, read-only information from HEC-RAS project
and plan text through the public RAS Commander Python API. It requires no HEC-RAS
executable. The fuller modeling, analysis and GIS experience uses RAS Commander
and its Python workflows outside MCP.

This independent open-source project complements HEC's work. It is not affiliated
with or endorsed by USACE HEC. Official HEC references remain passive reader links.

## Scope

The explicit tool set covers server/version information, project length units,
plan descriptions, and selected project/plan metadata. Project metadata and plan
configuration require the new upstream `RasText` API; on ras-commander 0.103.0,
units and descriptions work and metadata tools return an actionable availability
error. See [release sequencing](docs/compatibility.md).

Project tools belong only in bounded informational subagents. Each delegation
specifies the question, configured root, named file, selected fields, row and
character limits, and answer format. The child returns a compact answer with source
identity, installed versions, missing data and truncation. A host without subagent
tool isolation should use a scoped Python workflow instead of exposing project
tools to its main coordinator.

MCP does not modify projects, compute, read HDF/DSS, inspect geometry/coordinates,
extract gridded data, export files, download into projects, or execute arbitrary
code. Large and repeated drilldowns use Python. Tool annotations describe this
boundary; descriptor checks, allowlists and bounded snapshots enforce the reads.

## Install and configure

Use Python 3.10+ and an authorized managed environment. This 0.4 redesign is an
unpublished candidate; the current PyPI package is 0.3.2 and has the previous tool
set. To review this candidate, install from its checkout:

```sh
python -m pip install .
```

After 0.4 is published and qualified, a managed current install can use
`python -m pip install --upgrade ras-commander-mcp`. Preserve an existing pin or
lock when required.

Set `RAS_MCP_ALLOWED_ROOTS` to a JSON array of absolute, resolved project roots.
No roots are trusted by default. On Linux/macOS:

```sh
export RAS_MCP_ALLOWED_ROOTS='["/home/user/projects/example"]'
ras-commander-mcp
```

On PowerShell:

```powershell
$env:RAS_MCP_ALLOWED_ROOTS = '["C:\\Projects\\Example"]'
ras-commander-mcp
```

The server uses stdio. Configure the executable and environment in a client that
routes project tools to subagents. `claude_desktop_config.json` illustrates transport
configuration, not proof that desktop clients provide this routing. No project
query performs package installation or an automatic upgrade.

## Dependencies and updates

Direct dependencies are the official MCP Python SDK (without CLI extras),
ras-commander and packaging. The SDK has protocol/validation/network dependencies;
ras-commander currently inherits numpy, pandas and h5py. This is a small adapter,
not a stdlib-only installation. No GIS, Java/DSS or remote-engine extras are added.

`server_information(check_updates=true)` optionally checks fixed PyPI metadata
endpoints with bounded responses and caching. It reports installed/latest versions
and update availability; offline use remains available. Preserve deliberate user
pins and refresh managed environments outside tool calls.

## Documentation

- [Tools](docs/tools.md)
- [Architecture and access limits](docs/architecture.md)
- [Migration from the previous tool set](docs/migration.md)
- [Compatibility and release maintenance](docs/compatibility.md)
- [Installation](docs/installation.md)

The full library documentation is at [RAS Commander](https://rascommander.info/ras/).
