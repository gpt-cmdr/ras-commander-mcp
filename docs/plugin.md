# Install and update the agent plugin

The `ras-commander` plugin is published from the
[gpt-cmdr/ras-commander-plugin](https://github.com/gpt-cmdr/ras-commander-plugin)
marketplace for Claude Code and Codex. Install it on the workstation where the
agent, the project files, and HEC-RAS or HEC-HMS are.

## What the plugin contains

| Part | Claude Code | Codex |
|---|---|---|
| Skills: RAS and HMS entry points, RAS API discovery, HMS-to-RAS integration, cloud-native GIS, and each library's contributing skill | Yes | Yes |
| `ras-text` and `hms-text` MCP servers, launched with `uvx` from PyPI | Yes | No |
| Read-only subagents `ras-commander:ras-text` and `ras-commander:hms-text` | Yes | No |
| Guard hook that denies MCP calls from the main conversation | Yes | No |
| Session-start update notice | Yes | No |

Codex receives the skills only, because subagent-only MCP access has not been
demonstrated on Codex. On Codex, project reads use the `ras-commander` and
`hms-commander` Python APIs.

## Requirements

- Claude Code with plugin support, or the Codex CLI.
- [uv](https://docs.astral.sh/uv/) on `PATH`. It provides `uvx`, which starts the
  MCP servers, and it runs the plugin's hook scripts.
- Optional: enable Windows long paths, as described in the
  [overview](index.md#why-local-agents-on-windows).

## Install

Claude Code:

```sh
claude plugin marketplace add gpt-cmdr/ras-commander-plugin
claude plugin install ras-commander@ras-commander-plugin
```

Restart Claude Code after installing. Inside a session you can use
`/plugin marketplace add gpt-cmdr/ras-commander-plugin` and
`/plugin install ras-commander@ras-commander-plugin` instead.

Codex:

```sh
codex plugin marketplace add gpt-cmdr/ras-commander-plugin
codex plugin add ras-commander@ras-commander-plugin
```

Installing does not write to `~/.claude/agents`, your project folders, or any
Python environment. On first use, `uvx` downloads the MCP servers into uv's cache.

Organizations can enable the plugin for every Claude Code user with managed
settings. Add the marketplace under `extraKnownMarketplaces` and set
`"ras-commander@ras-commander-plugin": true` under `enabledPlugins`.

## Allowed project roots

By default, both servers can read only the current Claude Code project folder.
The optional `extra_roots` setting adds folders:

```sh
claude plugin install ras-commander@ras-commander-plugin --config extra_roots="D:\Models"
```

To change it later, use `/plugin` → `ras-commander` → *Configure options*.
Separate paths with `;` on Windows or `:` on macOS and Linux, or enter a JSON
array. Paths that do not exist are skipped.

## Usage

Ask normally, for example "what units does `models/thames.prj` use?". The main
conversation delegates the lookup to `ras-commander:ras-text` or
`ras-commander:hms-text`. The subagent returns the value, the source file and
its SHA-256 hash, and the package versions. For geometry, results, execution, or
edits, the skills direct the agent to the Python libraries.

## Updates

**Update notice.** When a Claude Code session starts, the plugin shows a one-line
notice if a newer plugin or MCP server release is available, with the exact
command to run. The check runs in the background at most once a day, never
blocks the session, and never installs anything. If it fails, for example
offline, nothing is shown.

**Plugin.** Update the skills, subagents, and hooks, then restart Claude Code:

```sh
claude plugin marketplace update ras-commander-plugin
claude plugin update ras-commander@ras-commander-plugin
```

On Codex, run `codex plugin marketplace upgrade ras-commander-plugin`, then
`codex plugin add ras-commander@ras-commander-plugin`, and start a new session.

**MCP servers.** The plugin launches the servers with `uvx`, which reuses its
cached copy. Once uv's PyPI index cache is more than 10 minutes old, the next
launch, which happens when Claude Code restarts, uses the newest release. To
update immediately, clear both each server and its library, then restart Claude
Code:

```sh
uv cache clean ras-commander-mcp ras-commander
uv cache clean hms-commander-mcp hms-commander
```

Naming only the server updates the server but keeps the old library.

## Reporting problems and requesting features

Each library includes a contributing skill that the plugin installs:

- When an agent run by a maintainer finds a defect, it reproduces the problem
  with public or synthetic data, fixes it in a separate clone, adds a regression
  test, and opens a pull request. A maintainer is a user whose GitHub account can
  push to the affected repository.
- Other users get a drafted issue or pull request. Feature requests are first
  checked against the API consistency criteria.
- Nothing is submitted publicly without the user's approval, and private project
  data stays out of issues, pull requests, and tests.

## Limitations

- **Tool names are visible in the main conversation.** Claude Code registers a
  plugin's MCP tools for the whole session. The guard hook denies calls from the
  main conversation, but the names still count as registered tools.
- **Plugin subagents cannot carry their own MCP servers.** Claude Code ignores
  `mcpServers`, `hooks`, and `permissionMode` in plugin agent definitions, so
  the servers are defined at plugin level and isolated by each subagent's tool
  list and the guard hook.
- **Hosts that import only skills** get the instructions without the servers,
  subagents, or hooks. The skills then use the Python libraries.
- **uv is required.** Without `uv` on `PATH`, the servers and hooks do not start.
