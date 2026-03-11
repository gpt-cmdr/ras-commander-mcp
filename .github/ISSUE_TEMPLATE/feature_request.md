---
name: Feature Request
about: Suggest a new MCP tool or improvement
title: "[Feature] "
labels: enhancement
assignees: ''
---

## Problem / Use Case

<!-- What problem does this solve? What workflow does it enable for LLM users? -->

## Proposed Solution

<!-- Describe the feature. If proposing a new MCP tool, sketch the definition: -->

```python
@mcp.tool()
def proposed_tool_name(
    project_path: str,      # Full path to HEC-RAS project folder
    # other_param: str,     # Description
) -> str:
    """Brief description of what this tool returns."""
    ...
```

## Alternatives Considered

<!-- What other approaches did you consider? Why is this one better? -->

## Additional Context

<!-- Anything else: related tools, ras-commander methods that could be exposed, example output. -->

> Tip: Try asking your LLM to prototype the tool by reading `server.py` for patterns and the ras-commander docs for available methods. A working prototype makes feature requests much easier to evaluate.
