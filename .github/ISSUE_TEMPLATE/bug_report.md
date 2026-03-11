---
name: Bug Report
about: Report a problem with the MCP server or its tools
title: "[Bug] "
labels: bug
assignees: ''
---

## Description

<!-- A clear description of the bug. -->

## Steps to Reproduce

<!-- How to trigger the bug. Include the MCP tool call or configuration that causes it. -->

1. Configure MCP server with: <!-- config snippet or description -->
2. Call tool: <!-- tool name and parameters -->
3. Observe: <!-- what happens -->

## Expected Behavior

<!-- What should have happened. -->

## Actual Behavior

<!-- What actually happened. Include error messages or unexpected output. -->

## Environment

- **ras-commander-mcp version**: <!-- e.g., 0.2.0 or git commit -->
- **ras-commander version**: <!-- pip show ras-commander -->
- **Python version**: <!-- python --version -->
- **MCP client**: <!-- Claude Desktop, Claude Code, other -->
- **OS**: <!-- Windows 11, etc. -->
- **HEC-RAS version**: <!-- 6.5, 6.6, etc. -->

## Additional Context

<!-- Logs, screenshots, HDF structure output, or anything else helpful. -->

> Tip: Try asking your LLM to investigate the bug by reading `server.py` and the relevant ras-commander source. It may be able to identify the root cause and suggest a fix.
