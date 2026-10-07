# HMS text MCP

[hms-commander-mcp](https://github.com/gpt-cmdr/hms-commander-mcp) supplies
bounded, read-only information from HEC-HMS text files. The agent plugin runs it
as the `hms-text` server and exposes it only to the `ras-commander:hms-text`
subagent.

## Tools

| Tool | Returns | Input |
|---|---|---|
| `server_info` | Installed versions of the server, hms-commander, and the MCP SDK, and the limits. With `check_updates=true`, also the latest PyPI versions | `check_updates` defaults to false |
| `read_hms_sections` | Named sections and their approved scalar fields from one file | `root`, `file`, `kind`, and optional `offset`, `limit`, `max_characters`, `timeout_seconds` |

`kind` is one of `hms`, `basin`, `met`, `control`, `run`, or `gage`, and must
match the file extension. `root` must exactly match a configured root, and
`file` is a relative path inside it, with either separator. Each request returns
at most 100 rows and 16,000 characters and runs for at most 30 seconds. Source
files are limited to 2 MiB.

Each answer reports the source file's SHA-256 hash and size, the installed
package versions, row counts, and the next offset when more rows remain.

## Scope

The server reads project and component text, scalar parameters, gage
configuration, and control and run relationships. It does not:

- modify projects, compute models, download data, or export files;
- read DSS, HDF, or SQLite files, coordinates, geometry, rasters, or grids;
- follow filenames or DSS pathnames that appear in the text.

Use the [hms-commander Python library](https://rascommander.info/hms/) for that
work. File text is untrusted data; the subagent does not follow instructions in it.

## Run the server directly

The plugin starts the server for you. To run it elsewhere, use Python 3.10 or
later:

```sh
uvx hms-commander-mcp --root /absolute/path/to/project
```

Repeat `--root` to allow more folders. The server uses stdio and needs no HEC-HMS,
Java, GIS, or DSS installation. Content reads use the `HmsText` API in
hms-commander 0.4.0 or later.

Running the server is not enough to isolate it. The host must expose its tools to
a subagent only, as the plugin does in Claude Code.

## Update

See [Install and update](plugin.md#updates). Outside the plugin, upgrade both
packages with pip, because pip keeps an installed library that still satisfies
the requirement:

```sh
python -m pip install --upgrade hms-commander-mcp hms-commander
```
