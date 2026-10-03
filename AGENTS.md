# RAS Commander MCP agent contract

This repository implements a constrained information server. Domain parsing
belongs in published ras-commander APIs; add missing read APIs upstream rather
than copying parsers into this adapter.

- Project queries read only approved project/plan text snapshots. Never initialize
  RasPrj, resolve an engine, accept TCU, open HDF/DSS/geometry/raster data, execute,
  modify a project, export data, or expose arbitrary Python/shell/file reads.
- Require configured roots, descriptor-safe path checks, approved file kinds,
  byte/output limits and typed structured results. Annotations are only hints.
- Project tools are exposed only to bounded informational subagents. A host that
  cannot isolate project tools must use a scoped Python workflow instead. The
  server cannot attest whether its caller is a subagent.
- Preserve installed user pins. Report version drift; never pip-install during
  a tool call. Compatibility automation opens reviewable update PRs, never publishes.
- Keep stdout for MCP messages and logs on stderr. Start with stdio only.
- Follow repository writing guidance in ras-commander's cognitive infrastructure:
  factual independent voice, HEC terminology and passive official references,
  direct statements about supported project capabilities and observations.
  These rules govern repository contributions, not users' external deliverables.
- Read current public APIs and inspect wheel/sdist metadata before changing
  dependency bounds. No old tool aliases or binary fallback modes.

See [architecture](docs/architecture.md), [migration](docs/migration.md), and
[compatibility maintenance](docs/compatibility.md). Tests require task authorization.
