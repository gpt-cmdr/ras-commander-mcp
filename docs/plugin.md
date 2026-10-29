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

The marketplace provides two update channels:

| Channel | Marketplace branch | Packaged skill sources |
| --- | --- | --- |
| `release` (default) | `main` | Latest published stable library release tags |
| `latest` | `latest` | The libraries' `main` branches |

Release publication notifications update the release channel. Push notifications
update `latest`; a weekly Monday check at 10:23 UTC recovers missed notifications
for both channels. Runtime or packaged content changes produce a new plugin cache
version; source provenance changes alone do not. The job validates each bundle
before publishing it.

Select the channel through the marketplace source ref. Existing Claude Code
installations must first change the matching marketplace declaration in settings;
Codex requires removing and re-adding the marketplace registration. Follow the
[channel switching instructions](https://github.com/gpt-cmdr/ras-commander-plugin#update-channels)
and restart the host. Both channels retain the same plugin name.

Channels select plugin instructions. The text MCP launchers still use published
PyPI packages, and project Python environment pins are preserved. New RAS
environments start with compatible stable PyPI releases at 0.110.2 or newer.
Because `latest` can describe unreleased APIs, agents inspect the installed
version, signatures and schemas and report capability gaps before using them.

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

**Agent Python environment.** Updating the plugin or its MCP servers does not
upgrade an existing Python environment used for HDF extraction or mapping.
After agreeing to upgrade the intended environment, activate it and run:

```sh
uv pip install --upgrade "ras-commander[full]>=0.110.2"
```

Keep a project's existing dependency pins unless its owner authorizes a change.
The skills check installed versions and capabilities before using an API that
may exist only on library `main`.

## Release and maintenance notes, October 29, 2026

[Plugin 0.2.0](https://github.com/gpt-cmdr/ras-commander-plugin/pull/7) makes
`release` the default and adds the opt-in `latest` channel. Release bundles omit
optional contribution skills absent from the published library tag. The HMS
0.4.0 source predates the generator fixes, so its release bundle uses a separately
pinned canonical generator; provenance records both source and builder commits.
No unreleased skill text is borrowed for that release bundle.

[Plugin 0.1.2](https://github.com/gpt-cmdr/ras-commander-plugin/pull/5) includes
the current canonical skills, full-dependency setup for ras-commander 0.110.2
or newer, and Rust engine availability checks. A fresh Windows CPython 3.11
installation of `ras-commander[full]==0.110.2` installed fast-hdf 0.2.4 and
fast-map 0.10.1. RAS Commander and the HDF extension imported successfully,
and dependency consistency checks passed. This establishes installation and
import behavior; no model extraction or mapping run was part of that check.

Both libraries now notify the marketplace on pushes to `main`. The
[RAS-triggered rebuild](https://github.com/gpt-cmdr/ras-commander-plugin/actions/runs/40888556421)
and [HMS-triggered rebuild](https://github.com/gpt-cmdr/ras-commander-plugin/actions/runs/40888557419)
succeeded. Both found unchanged packaged content and correctly published no
additional version. The weekly Monday check at 10:23 UTC is a recovery path,
not a delay applied to push-triggered updates. GitHub may start scheduled jobs
later than their configured time.

The upstream generators now read UTF-8 and write LF explicitly and normalize
Markdown line endings before rewriting links and frontmatter. The marketplace
uses them directly; its local newline workaround has been removed. The MCP
development lock, compatibility snapshot, and setup documentation were also
[refreshed for 0.110.2](https://github.com/gpt-cmdr/ras-commander-mcp/pull/16).

**Maintainer credential.** `PLUGIN_DISPATCH_TOKEN` is configured as an Actions
secret in both `gpt-cmdr/ras-commander` and `gpt-cmdr/hms-commander`. The token
is limited to `gpt-cmdr/ras-commander-plugin`, with Contents read/write and the
required Metadata read access. It has no account permissions and expires
**November 28, 2026**. Replace both secrets before expiry using the
[marketplace renewal procedure](https://github.com/gpt-cmdr/ras-commander-plugin#dispatch-token-renewal).
The weekly marketplace job continues independently if notifications fail.
This credential targets the plugin repository; it does not configure the
MCP compatibility workflow's separate `ras-commander-release` dispatch hook.

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
