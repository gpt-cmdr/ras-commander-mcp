# Non-Working Tools

This document contains tools that have been removed from the HEC-RAS MCP server due to issues or lack of proper functionality.

## get_infiltration_data Tool

**Status**: Removed  
**Reason**: Tool consistently returns "No infiltration layer file found in project" even for projects that should contain infiltration data. The issue appears to be related to how infiltration layer filenames are stored or referenced in the RASMapper configuration files.

### Original Tool Definition

```python
Tool(
    name="get_infiltration_data",
    description="Get infiltration layer data and soil statistics from a HEC-RAS project",
    inputSchema={
        "type": "object",
        "properties": {
            "project_path": {
                "type": "string",
                "description": "Full path to the HEC-RAS project folder"
            },
            "significant_threshold": {
                "type": "number",
                "description": "Minimum percentage threshold for significant mukeys",
                "default": 1.0
            }
        },
        "required": ["project_path"]
    }
)
```

### Original Implementation Code

```python
elif name == "get_infiltration_data":
    try:
        project_path = Path(arguments["project_path"])
        significant_threshold = arguments.get("significant_threshold", 1.0)
        
        if not project_path.exists() or not project_path.is_dir():
            return [TextContent(
                type="text",
                text=f"Error: The specified project folder does not exist: {project_path}"
            )]
        
        # Initialize project to get rasmap_df
        ras_version = HECRAS_PATH if HECRAS_PATH else HECRAS_VERSION
        ras = init_ras_project(project_path, ras_version)
        
        response_parts = [
            f"HEC-RAS Project: {ras.project_name}",
            f"Project Path: {project_path}",
            get_ras_version_info(),
            "=" * 80
        ]
        
        # Check if infiltration data exists in rasmap_df
        if hasattr(ras, 'rasmap_df') and ras.rasmap_df is not None and not ras.rasmap_df.empty:
            # Look for infiltration layer path
            infiltration_path = None
            if 'InfiltrationLayerFilename' in ras.rasmap_df.columns:
                infiltration_files = ras.rasmap_df['InfiltrationLayerFilename'].dropna()
                if not infiltration_files.empty:
                    infiltration_path = Path(project_path) / infiltration_files.iloc[0]
            
            if infiltration_path and infiltration_path.exists():
                # Get infiltration data
                infiltration_data = HdfInfiltration.get_infiltration_layer_data(infiltration_path)
                if infiltration_data is not None:
                    response_parts.append(dataframe_to_text(infiltration_data, "INFILTRATION LAYER DATA"))
                    
                    # Get significant mukeys if soil stats available
                    if 'percentage' in infiltration_data.columns:
                        significant_mukeys = HdfInfiltration.get_significant_mukeys(
                            infiltration_data, threshold=significant_threshold
                        )
                        if not significant_mukeys.empty:
                            response_parts.append(dataframe_to_text(
                                significant_mukeys, 
                                f"SIGNIFICANT MUKEYS (>{significant_threshold}%)"
                            ))
                            total_percentage = HdfInfiltration.calculate_total_significant_percentage(
                                significant_mukeys
                            )
                            response_parts.append(f"\nTotal significant percentage: {total_percentage:.2f}%")
                else:
                    response_parts.append("\nNo infiltration data found in layer file")
            else:
                response_parts.append("\nNo infiltration layer file found in project")
        else:
            response_parts.append("\nNo RASMapper configuration found")
        
        return [TextContent(
            type="text",
            text=truncate_output("\n".join(response_parts))
        )]
        
    except Exception as e:
        logger.error(f"Error getting infiltration data: {str(e)}")
        return [TextContent(
            type="text",
            text=f"Error getting infiltration data: {str(e)}"
        )]
```

### Required Import

The tool required this import in the server.py file:

```python
from ras_commander import init_ras_project, HdfBase, HdfInfiltration, HdfResultsPlan
```

### Original Test Code

The following test code was used in `tests/test_all_tools.py`:

```python
# Test 6: Get infiltration data (use project with infiltration data)
# Try multiple possible paths for BaldEagleCrkMulti2D project
infiltration_paths = [
    Path("C:\\GH\\ras-commander-mappingbranch\\examples\\example_projects\\BaldEagleCrkMulti2D"),
    Path("C:\\GH\\Claude_Code_Execution\\BaldEagleCrkMulti2D")
]

infiltration_project_path = None
for path in infiltration_paths:
    if path.exists():
        infiltration_project_path = path
        break

if infiltration_project_path:
    await self.test_tool(
        "get_infiltration_data",
        f"Get infiltration layer data and soil statistics (BaldEagleCrkMulti2D project: {infiltration_project_path.name})",
        {
            "project_path": str(infiltration_project_path),
            "significant_threshold": 5.0
        }
    )
else:
    # Fallback to current project if infiltration project not available
    await self.test_tool(
        "get_infiltration_data",
        "Get infiltration layer data and soil statistics (fallback - may not have data)",
        {
            "project_path": str(self.project_path),
            "significant_threshold": 5.0
        }
    )
```

### Test Results

The tool consistently returned:

```
HEC-RAS Project: BaldEagleDamBrk
Project Path: C:\GH\ras-commander-mappingbranch\examples\example_projects\BaldEagleCrkMulti2D
HEC-RAS Version: 6.6
================================================================================

No infiltration layer file found in project
```

Even when tested with projects that contained infiltration data files (e.g., BaldEagleCrkMulti2D project which has `Soils Data/Infiltration.hdf`).

### Potential Issues

1. **RASMapper Configuration**: The infiltration layer filename may not be properly stored in the `InfiltrationLayerFilename` column of the RASMapper DataFrame
2. **File Path Resolution**: The path construction logic may not correctly resolve relative paths from the RASMapper configuration
3. **ras-commander Library**: The underlying library may have issues with parsing infiltration layer references from RASMapper files

### Future Work

To restore this tool, investigation would be needed into:
1. How infiltration layer filenames are actually stored in RASMapper files
2. Alternative methods to locate infiltration data files
3. Updates to the ras-commander library to better handle infiltration data references