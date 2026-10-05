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
configuration use the `RasText` API published in ras-commander 0.104.0. On
ras-commander 0.103.0, units and descriptions work and metadata tools return an
actionable availability error. See [compatibility](docs/compatibility.md).

Project tools belong only in bounded informational subagents. Each delegation
specifies the question, configured root, named file, selected fields, row and
character limits, and answer format. The child returns a compact answer with source
identity, installed versions, missing data and truncation. A host without subagent
tool isolation should use a scoped Python workflow instead of exposing project
tools to its main coordinator.

Claude Code users should install the `ras-commander@ras-commander-plugin` plugin
from the [gpt-cmdr/ras-commander-plugin](https://github.com/gpt-cmdr/ras-commander-plugin)
marketplace (forthcoming; the repository is not yet published). The plugin covers
the RAS and HMS text servers. It declares the server at plugin level, supplies a
plugin subagent for bounded reads, and adds a `PreToolUse` guard that denies
project tools to the main session. A subagent-only isolation check passed in
Claude Code 2.1.287 on October 5, 2026. The plugin does not copy agent files into
the user's `~/.claude/agents` directory. Other hosts require their own isolation
configuration.

MCP does not modify projects, compute, read HDF/DSS, inspect geometry/coordinates,
extract gridded data, export files, download into projects, or execute arbitrary
code. Large and repeated drilldowns use Python. Tool annotations describe this
boundary; descriptor checks, allowlists and bounded snapshots enforce the reads.

## Install and configure

Use Python 3.10+ and an authorized managed environment:

```sh
python -m pip install --upgrade ras-commander-mcp
```

Preserve an existing pin or lock when required. Version 0.4 replaces the 0.3 tool
set; it needs ras-commander 0.104.0 or later for project metadata and plan
configuration, and reports those tools as unavailable on older releases.

A client that launches servers through uv can run `uvx ras-commander-mcp` instead
of a separate install; uv builds and caches the environment on first launch.
`claude_desktop_config.json` shows the equivalent `uvx --from ras-commander-mcp
ras-commander-mcp` form.

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

## Update an installation

Close the MCP client before updating so that no running server holds the
environment. `server_information(check_updates=true)` reports the installed and
latest PyPI versions of ras-commander-mcp, ras-commander and the MCP SDK without
changing the environment.

**Managed pip environment.** Name both packages:

```sh
python -m pip install --upgrade ras-commander-mcp ras-commander
```

pip's default upgrade strategy keeps an installed dependency that still satisfies
the requirement. With pip 23.0.1, upgrading only `ras-commander-mcp` left
ras-commander 0.103.0 in place.

**Cached `uvx ras-commander-mcp`.** Keep the client configured with the plain
command. Each launch resolves current compatible releases, but uv reuses its
cached PyPI index data while that data is fresh (PyPI currently allows
10 minutes). To use a new release immediately, run once:

```sh
uvx --refresh --from ras-commander-mcp python -c "from importlib.metadata import version as v; print(v('ras-commander-mcp'), v('ras-commander'))"
```

The command refreshes the index data, builds the current environment and prints
both versions. The next plain `uvx ras-commander-mcp` launch reuses that
environment. The server accepts no command-line options, so the refresh runs
Python instead of starting the server. `uv cache clean ras-commander-mcp
ras-commander` has the same effect on the next launch; name both packages,
because cleaning only `ras-commander-mcp` left ras-commander 0.103.0 in place.

**`uv tool install ras-commander-mcp`.** `uvx` prefers an installed tool to its
cache, and `--refresh` does not change that tool. Run
`uv tool upgrade ras-commander-mcp`.

These results were observed on October 5, 2026, with uv 0.12.23 on Linux. A
local index served the 0.3.2/0.4.0 and 0.103.0/0.104.0 wheels with PyPI's cache
header, and the refresh command was repeated against PyPI. Preserve deliberate
pins and locks; no tool call installs or upgrades packages.

## Windows long paths

Version 0.4.0 opens validated project files through Windows extended-length
paths (`\\?\` and `\\?\UNC\`), so files beyond the 260-character `MAX_PATH`
limit are readable. Root, traversal and opened-handle checks are unchanged. Other
tools in a workflow, including Python scripts, may still fail on long paths. An
administrator can enable Windows long-path support from an elevated prompt:

```bat
reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1 /f
```

Or in an elevated PowerShell session:

```powershell
New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
```

No reboot is needed; processes started after the change use the setting, and
running processes, including an open MCP client, must be restarted. Each
application must also declare long-path awareness.

## Dependencies and version checks

Direct dependencies are the official MCP Python SDK (without CLI extras),
ras-commander and packaging. The SDK has protocol/validation/network dependencies;
ras-commander currently inherits numpy, pandas and h5py. This is a small adapter,
not a stdlib-only installation. No GIS, Java/DSS or remote-engine extras are added.

`server_information(check_updates=true)` optionally checks fixed PyPI metadata
endpoints with bounded responses and caching. It reports installed/latest versions
and update availability; offline use remains available. Preserve deliberate user
pins and refresh managed environments outside tool calls.

## Qualification

Version 0.4.0 with ras-commander 0.104.0 read a corpus of 983 HEC-RAS text files
with 0 errors on Linux and on Windows from a UNC project root. The 69 corpus files
whose Windows path reached 260 characters failed before the extended-length change
(PR #10) and passed after it. The PyPI packages reproduced the results obtained
from source. These are read-contract results, not engine, hydraulic or all-client
acceptance. See [compatibility](docs/compatibility.md).

## Documentation

- [Tools](docs/tools.md)
- [Architecture and access limits](docs/architecture.md)
- [Migration from the previous tool set](docs/migration.md)
- [Compatibility and release maintenance](docs/compatibility.md)
- [Installation](docs/installation.md)

The full library documentation is at [RAS Commander](https://rascommander.info/ras/).
