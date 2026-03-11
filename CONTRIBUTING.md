# Contributing to RAS Commander MCP

Thank you for your interest in contributing to **ras-commander-mcp**, the MCP (Model Context Protocol) server for accessing HEC-RAS project data via Claude Desktop, Claude Code, and other LLMs. This project is maintained by [CLB Engineering Corporation](https://clbengineering.com/) and released under the MIT license.

## Our Philosophy: Don't Ask Me, Ask a GPT!

This project was built with LLMs and welcomes LLM-assisted contributions. We do not care which agent you use -- Claude Code, Codex, Aider, Cursor, Gemini, or anything else. What we care about is that your contribution is correct, well-tested, and follows the patterns already in the codebase.

The deal is simple: **use your LLM to self-review your work before opening a PR**. This reduces maintainer burden and gets your contribution merged faster.

Learn more about our approach: [LLM Forward Engineering](https://clbengineering.com/llm-forward)

## Quick Start

1. **Fork and clone** the repository:
   ```bash
   git clone https://github.com/<your-username>/ras-commander-mcp.git
   cd ras-commander-mcp
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Run the server locally** to verify everything works:
   ```bash
   uv run ras-commander-mcp
   ```

4. **Run the test suite**:
   ```bash
   uv run python tests/test_server.py
   uv run python tests/test_all_tools.py
   ```

5. **Launch your agent** (Claude Code, Codex, Cursor, etc.) and start working.

6. **Create a branch**, make your changes, self-review with your LLM, and open a PR.

## The Self-Review Contract

Before opening a pull request, ask your LLM to review your changes against the checklist below. Paste the diff or point your agent at the changed files and ask it to check each item. Include a note in your PR confirming you did this.

We trust you to do this honestly. In return, we review PRs faster and with less friction.

## LLM Self-Review Checklist

### Code Quality

- [ ] All public functions have docstrings describing purpose, parameters, and return values
- [ ] Logging is used for diagnostic output (`logger.info`, `logger.warning`, `logger.error`) -- not `print()`
- [ ] Errors are handled with `ToolError` for MCP tool failures and clear error messages
- [ ] File paths use `pathlib.Path`, not string concatenation
- [ ] Type hints are present on function signatures
- [ ] No hardcoded absolute paths or machine-specific values

### MCP Protocol Compliance

- [ ] New tools use the `@mcp.tool()` decorator with a clear description
- [ ] Tool parameters have proper type annotations and docstrings
- [ ] Tool descriptions are written for LLM consumption (clear, concise, explain what the tool returns)
- [ ] JSON schema for parameters is correct (required vs optional, defaults documented)
- [ ] Error responses use `ToolError` with actionable messages the LLM can interpret
- [ ] Tools return formatted text suitable for LLM processing, not raw data dumps

### HEC-RAS Domain

- [ ] Data extraction uses the [ras-commander](https://github.com/gpt-cmdr/ras-commander) library, not direct file parsing
- [ ] Project initialization uses `init_ras_project()` and the `_init_project()` helper
- [ ] No hardcoded HEC-RAS paths -- version and path come from environment variables
- [ ] HDF access uses ras-commander classes (`HdfBase`, `HdfResultsPlan`, etc.) where available
- [ ] Plan numbers are handled as strings (e.g., `"01"`, not `1`)

## What We Accept

- **New MCP tools** that expose ras-commander functionality to LLMs (geometry queries, results extraction, plan metadata, etc.)
- **Protocol improvements** that make tool responses more useful to LLMs
- **Bug fixes** with clear reproduction steps
- **Documentation improvements** (README, docstrings, examples)
- **Test coverage** for existing or new tools
- **Performance improvements** with before/after measurements

## What We Don't Accept

- **Breaking changes to existing tool schemas** without a deprecation path -- LLM clients depend on stable tool definitions
- **Dependencies without justification** -- explain why the dependency is needed and what alternatives you considered
- **Direct HEC-RAS file parsing** that bypasses ras-commander -- use the library
- **Tools that execute HEC-RAS plans** -- execution support is planned but not yet implemented; coordinate with maintainers first
- **Generated files** (`.pyc`, `__pycache__`, `.venv`, test outputs) -- these are gitignored

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(tools): add cross-section query tool
fix(server): handle missing HDF file gracefully
docs: update tool descriptions for clarity
test: add coverage for get_plan_results_summary
refactor(server): extract DataFrame formatting helper
```

If an LLM helped write the code, include attribution:

```
feat(tools): add geometry element listing tool

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Development Workflow

### Adding a New MCP Tool

1. Add the tool function in `server.py` with the `@mcp.tool()` decorator
2. Follow existing tool patterns for parameter validation and error handling
3. Use `_init_project()` for project path validation and initialization
4. Return formatted text (not raw DataFrames or dicts) -- LLMs consume text
5. Add a test in `tests/`
6. Update `README.md` with the new tool's description and parameters

### Running Tests

```bash
uv run python tests/test_server.py        # Basic server functionality
uv run python tests/test_all_tools.py      # Comprehensive tool validation
uv run python tests/test_single_tool.py    # Single tool testing utility
```

Test outputs are saved to `tests/outputs/` as markdown files for review.

### Local Development Configuration

For Claude Desktop testing during development, use the local configuration:

```json
{
  "mcpServers": {
    "hecras": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\ras-commander-mcp", "ras-commander-mcp"],
      "env": {
        "HECRAS_VERSION": "6.6"
      }
    }
  }
}
```

## Community Standards

### Professional Context

HEC-RAS is used for **safety-critical flood modeling**. Contributions that expose HEC-RAS data to LLMs carry responsibility:

- Tool descriptions should be accurate -- LLMs will relay this information to engineers
- Error messages should be clear and actionable -- vague errors waste engineering time
- Results formatting should preserve precision -- do not round or truncate hydraulic data without good reason

### Code of Conduct

- Be respectful and constructive in issues and pull requests
- Focus feedback on the code, not the contributor
- LLM-assisted contributions are welcome and encouraged -- this is an LLM Forward project
- If you are unsure about a design decision, open an issue to discuss before investing time in a PR

### Licensing

By contributing, you agree that your contributions will be licensed under the MIT License.

## Getting Help

- **Issues**: Open a [GitHub issue](https://github.com/gpt-cmdr/ras-commander-mcp/issues) for bugs or feature requests
- **ras-commander library**: See [ras-commander documentation](https://github.com/gpt-cmdr/ras-commander) for the underlying Python library
- **MCP protocol**: See [Model Context Protocol specification](https://modelcontextprotocol.io/) for protocol details
- **CLB Engineering**: Contact info@clbengineering.com for professional H&H automation services

---

Maintained by [CLB Engineering Corporation](https://clbengineering.com/) | [LLM Forward Engineering](https://clbengineering.com/llm-forward)
