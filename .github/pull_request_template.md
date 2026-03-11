## Summary

<!-- Briefly describe what this PR does and why. -->

## Type of Change

- [ ] New MCP tool
- [ ] Bug fix
- [ ] Protocol / schema improvement
- [ ] Documentation
- [ ] Test coverage
- [ ] Refactoring (no behavior change)
- [ ] Other: <!-- describe -->

## LLM Self-Review

I have asked my LLM to review this PR against the self-review checklist in [CONTRIBUTING.md](../CONTRIBUTING.md).

### Code Quality

- [ ] Docstrings on all public functions
- [ ] Logging used instead of print()
- [ ] Errors handled with ToolError and clear messages
- [ ] File paths use pathlib.Path
- [ ] Type hints on function signatures

### MCP Protocol Compliance

- [ ] @mcp.tool() decorator with clear description
- [ ] Parameters have proper type annotations
- [ ] Tool returns formatted text suitable for LLM consumption
- [ ] Error responses are actionable for LLMs

### HEC-RAS Patterns

- [ ] Uses ras-commander library for data extraction
- [ ] Uses _init_project() helper for path validation
- [ ] No hardcoded paths or machine-specific values
- [ ] Plan numbers handled as strings

## Test Plan

<!-- How did you verify this works? -->

- [ ] Ran `uv run python tests/test_all_tools.py`
- [ ] Tested with Claude Desktop or Claude Code (if applicable)
- [ ] Tested with real HEC-RAS project data
- [ ] Other: <!-- describe -->

## LLM Attribution

<!-- Which LLM(s) assisted with this contribution? This is optional but encouraged. -->

- [ ] Claude (Anthropic)
- [ ] GPT / Codex (OpenAI)
- [ ] Gemini (Google)
- [ ] Other: <!-- name -->
- [ ] No LLM assistance used
