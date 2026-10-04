"""Optional local official text fixtures; no model files are redistributed."""
import hashlib
import os
from pathlib import Path
import pytest
from ras_commander_mcp.adapter import RasAdapter, metadata_api_present
from ras_commander_mcp.contracts import MetadataRequest, Request
from ras_commander_mcp.policy import ReadPolicy


def test_official_muncie_text_only_contracts():
    location = os.environ.get("RAS_MCP_REAL_TEXT_FIXTURES")
    if not location:
        pytest.skip("Set RAS_MCP_REAL_TEXT_FIXTURES to separately acquired official Muncie directory")
    root = Path(location).resolve()
    # These names are explicit; do not inventory or open other model inputs/results.
    paths = [root / name for name in ("Muncie.prj", "Muncie.p01", "Muncie.p03", "Muncie.p04")]
    before = {item.name: hashlib.sha256(item.read_bytes()).hexdigest() for item in paths}
    api = RasAdapter(ReadPolicy((root,)))
    assert api.project_units(Request(root=str(root), file="Muncie.prj")).units == "ft"
    for path in paths[1:]:
        result = api.plan_description(Request(root=str(root), file=path.name))
        assert result.source.sha256 == before[path.name]
        assert len(result.model_dump_json(indent=2)) <= 6000
    if metadata_api_present():
        project = api.metadata(MetadataRequest(root=str(root), file="Muncie.prj", fields=["Plan File", "Current Plan", "Units"]), "project")
        assert project.total_records == 5 and project.units == "English"
        plan = api.metadata(MetadataRequest(root=str(root), file="Muncie.p01", fields=["Program Version", "Computation Interval", "Run PostProcess", "Run WQNet"]), "plan")
        assert {record.field: record.value for record in plan.records} == {"Program Version": "5.00", "Computation Interval": "15SEC", "Run PostProcess": "1", "Run WQNet": "0"}
    assert {item.name: hashlib.sha256(item.read_bytes()).hexdigest() for item in paths} == before
