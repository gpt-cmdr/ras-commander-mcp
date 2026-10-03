# Contributing

Read [AGENTS.md](AGENTS.md) and the [architecture](docs/architecture.md) before
changing tools. Domain parsing stays upstream in ras-commander. Changes must
preserve explicit roots, text-only fields, source identity, input/output bounds,
subagent routing and public API release compatibility.

Build with `python -m build`. Run authorized contract checks across the declared
minimum and current stable upstream releases before changing dependency bounds.
Do not run HEC-RAS or mutate sample projects for MCP qualification.

Repository writing should state supported capabilities and observations directly,
use HEC terminology where applicable, and keep HEC references passive. These
contribution rules do not govern users' external work.
