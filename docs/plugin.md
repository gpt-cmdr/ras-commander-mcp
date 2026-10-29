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

### Before the first task

**Windows: put `claude` on `PATH`.** The Claude Code native installer
(`irm https://claude.ai/install.ps1 | iex`) installs `claude.exe` to
`%USERPROFILE%\.local\bin` but may not add that folder to `PATH`. If
`claude --version` is not found, add the folder to your user `PATH` in
PowerShell, then open a new terminal:

```powershell
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "User") + ";$env:USERPROFILE\.local\bin", "User")
```

**HEC-RAS Terms and Conditions.** HEC-RAS shows its Terms and Conditions for
Use once per Windows user and version. Until they are accepted, RAS Commander
cannot run plans for that user; it detects this and says so. Open each
installed HEC-RAS version once in the GUI as the Windows user who will run the
agent and accept the terms. Reading project text, HDF results, and geometry
does not need this step.

**Python library for the agent.** The MCP servers need no Python setup. Tasks
that read results, geometry, or GIS data use the `ras-commander` library in a
Python environment the agent can run. Install the full feature set there:

```sh
uv venv
uv pip install "ras-commander[full]>=0.110.2"
```

Plugin 0.1.1 and later include the `[full]` installation guidance; older plugin
skills may omit it. Update the plugin before relying on that setup step. Agents
create an environment when the library is unavailable; an existing shared or
user-pinned environment needs an agreed upgrade. Installing the dependencies
ahead of time avoids setup during the first task.

Release 0.110.2 installs the Rust HDF engine, `ras-commander-fast-hdf`, as a base
dependency on supported CPython platforms (Windows x64, Linux x64, macOS arm64).
The `[full]` extra also installs the Rust mapping engine,
`ras-commander-fast-map`, on Windows x64 and Linux x64. There is no macOS mapping
wheel. These engines run through the Python APIs; the text MCP servers do not
perform HDF extraction or mapping. Check the installed engine distributions and
library capabilities before starting a task that requires them.

## Install

Claude Code:

```sh
claude plugin marketplace add gpt-cmdr/ras-commander-plugin
claude plugin install ras-commander@ras-commander-plugin
```

The shell install prints `1 userConfig option not yet set — run /plugin
configure … or pass --config KEY=VALUE.` This message is expected and you can
ignore it. It refers to the optional `extra_roots` setting described under
[Allowed project roots](#allowed-project-roots). Claude Code prints it for
every unset option, including optional ones that have a default.

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

**Plugin.** To receive updates automatically, run `/plugin`, open **Marketplaces**,
select `ras-commander-plugin`, and choose **Enable auto-update**. Third-party
marketplaces require this setting; publication alone does not update every
installation. To update the skills, subagents, and hooks by hand, then restart
Claude Code:

```sh
claude plugin marketplace update ras-commander-plugin
claude plugin update ras-commander@ras-commander-plugin
```

On Codex, run `codex plugin marketplace upgrade ras-commander-plugin`, then
`codex plugin add ras-commander@ras-commander-plugin`, and start a new session.

The marketplace tracks the libraries' `main` branches. Upstream push notifications
trigger a rebuild; a weekly Monday check at 10:23 UTC recovers missed
notifications. The job validates the generated content before publishing a patch,
and unchanged skills/resources produce no release. Python environments use
compatible stable PyPI releases, starting with 0.110.2 for new RAS environments.
Because `main` can describe unreleased APIs, agents inspect the installed version,
signatures and schemas and report capability gaps before using them.

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
