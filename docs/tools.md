# Tools

The MCP server exposes the following tools. All of them are built on the
[ras-commander](https://github.com/gpt-cmdr/ras-commander) Python library. Once the server is
[configured](installation.md), Claude calls these tools on your behalf in response to natural
language requests.

## `hecras_project_summary`

Get comprehensive or selective project information (plans, geometries, flows, boundaries, and
RASMapper configuration).

| Parameter | Required | Default | Description |
|---|---|---|---|
| `project_path` | yes | — | Full path to the HEC-RAS project folder |
| `show_rasprj` | no | `true` | Show project file contents |
| `show_plan_df` | no | `true` | Show plan files and metadata |
| `show_geom_df` | no | `true` | Show geometry files |
| `show_flow_df` | no | `true` | Show steady flow data |
| `show_unsteady_df` | no | `true` | Show unsteady flow data |
| `show_boundaries` | no | `true` | Show boundary conditions |
| `show_rasmap` | no | `false` | Show RASMapper configuration |
| `showmore` | no | `false` | Show all columns / verbose mode |

## `read_plan_description`

Read the multi-line description from a plan file.

| Parameter | Required | Description |
|---|---|---|
| `project_path` | yes | Full path to the HEC-RAS project folder |
| `plan_number` | yes | Plan number (e.g. `'1'`, `'01'`, `'02'`) |

## `get_plan_results_summary`

Get comprehensive results from a specific plan, including unsteady simulation info and runtime
metrics.

| Parameter | Required | Description |
|---|---|---|
| `project_path` | yes | Full path to the HEC-RAS project folder |
| `plan_number` | yes | Plan number or full path to the plan HDF file |

## `get_compute_messages`

Get computation messages and performance metrics for a plan.

| Parameter | Required | Description |
|---|---|---|
| `project_path` | yes | Full path to the HEC-RAS project folder |
| `plan_number` | yes | Plan number or full path to the plan HDF file |

## `get_hdf_structure`

Explore the internal structure of an HDF file.

| Parameter | Required | Default | Description |
|---|---|---|---|
| `hdf_path` | yes | — | Full path to the HDF file |
| `group_path` | no | `"/"` | Internal HDF path to start exploration from |
| `paths_only` | no | `false` | Show only paths without details |

## `get_projection_info`

Get spatial projection information (WKT) from an HDF file.

| Parameter | Required | Description |
|---|---|---|
| `hdf_path` | yes | Full path to the HDF file |

---

For automation beyond these query tools, use the
[ras-commander library](https://rascommander.info/ras/) directly.
