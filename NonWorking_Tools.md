# Removed tool scope

The 0.4 redesign removes the historical HDF, projection, result and broad project
introspection tools. These operations belong to the public Python library outside
MCP. See [migration](docs/migration.md) for the supported handoff.

No legacy tool aliases or optional binary modes are planned. New project/plan
metadata tools require a released upstream `RasText` API and explicitly report
when that capability is unavailable.
