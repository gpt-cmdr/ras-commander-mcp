# Migration to 0.4

The 0.4 tool set intentionally replaces the historical broad server. There are no
legacy-name aliases. Update client tool allowlists and route project tools to a
bounded informational subagent.

| Previous capability | Current path |
| --- | --- |
| Full project initialization/geometry/boundary dumps | Selected text metadata in MCP; fuller inventory through public Python APIs |
| Plan narrative | `plan_description` with explicit root and named plan file |
| HDF structure, projection, results, messages | Public RAS Commander Python HDF/result APIs outside MCP |
| Spatial/grid/binary extraction | Python with the appropriate extras, outside MCP |
| Live documentation search/download | Passive documentation links or installed API discovery outside MCP |

No project mutation or execution is introduced. On ras-commander 0.103.0, project
units and plan descriptions work, and metadata/configuration tools return a clear
availability error. Those tools use the pure `RasText` API published in
ras-commander 0.104.0. Do not enable a copied-parser or initialized-project fallback.

Replace `HECRAS_VERSION`/`HECRAS_PATH` configuration with `RAS_MCP_ALLOWED_ROOTS`.
No engine version or executable is required for these information queries.
