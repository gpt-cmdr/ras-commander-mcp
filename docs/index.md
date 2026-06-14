# RAS Commander MCP

!!! note "A focused tool, not the full library"
    RAS Commander MCP exposes a **curated subset** of capabilities for LLMs. For the most powerful and complete way to automate HEC-RAS, use the [**ras-commander** library](https://rascommander.info/ras/) directly.

The **RAS Commander MCP** server is a [Model Context Protocol](https://modelcontextprotocol.io/)
server that lets Claude Desktop (and other MCP clients) query HEC-RAS hydraulic modeling
projects. It wraps the [ras-commander](https://github.com/gpt-cmdr/ras-commander) Python
library so an LLM can read project structure, plan metadata, simulation results, and HDF
internals through a small set of well-defined tools.

It is open-source software released under the MIT license by
[CLB Engineering Corporation](https://clbengineering.com/). This is third-party software and is
not made by or endorsed by the U.S. Army Corps of Engineers (USACE) Hydrologic Engineering
Center (HEC).

## What it does

With the MCP server configured, you can ask Claude things like:

- "Query the HEC-RAS project at `C:/Projects/MyRiverModel`"
- "Show me the plans in the Muncie test project"
- "Get the results summary for plan '01' in my project"
- "Show me the compute messages for plan '1'"
- "Explore the HDF structure of my results file"
- "Get the projection info from my terrain HDF"

Claude translates these requests into calls to the server's [tools](tools.md), then formats the
returned data for you.

## Features

- Query comprehensive HEC-RAS project information (plans, geometries, flows, boundaries)
- Extract detailed plan results including unsteady simulation info and runtime metrics
- Explore HDF file structures and extract computation messages
- Retrieve spatial projection information (WKT) from HDF files
- Support for multiple HEC-RAS versions (6.5, 6.6, etc.)
- Formatted text output suitable for LLM interaction
- Error handling with helpful diagnostics

## How it fits together

All tools provided by this server are built on top of the
[ras-commander](https://github.com/gpt-cmdr/ras-commander) Python library, which provides
comprehensive programmatic access to HEC-RAS projects. The MCP server deliberately exposes a
read-and-query subset suited to conversational use. For advanced scripting, batch automation,
or capabilities beyond the MCP interface, work with the
[ras-commander library](https://rascommander.info/ras/) directly.

## Next steps

- [Installation](installation.md) — set up `uv` and configure Claude Desktop.
- [Tools](tools.md) — reference for the query tools the server provides.
- [Source on GitHub](https://github.com/gpt-cmdr/ras-commander-mcp)

---

For professional H&H automation services and custom solutions, contact CLB Engineering
Corporation at info@clbengineering.com.
