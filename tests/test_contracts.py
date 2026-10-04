import json
from types import SimpleNamespace
from pathlib import Path
import pytest
from pydantic import ValidationError
from ras_commander_mcp import adapter
from ras_commander_mcp.adapter import RasAdapter, bounded_result, metadata_api_present
from ras_commander_mcp.contracts import MetadataRequest, Request
from ras_commander_mcp.policy import PolicyError


def request(project, file="representative.p01", **kwargs):
    return Request(root=str(project), file=file, **kwargs)


def test_released_units_description_and_no_initialization(policy, project, monkeypatch):
    from ras_commander import RasPrj, RasPlan
    import ras_commander
    monkeypatch.setattr(ras_commander, "init_ras_project", lambda *a, **k: pytest.fail("initialized project"))
    monkeypatch.setattr(RasPrj, "initialize", lambda *a, **k: pytest.fail("initialized project"))
    original = {p.name: p.read_bytes() for p in project.iterdir()}
    units = RasAdapter(policy).project_units(request(project, "hec_ras_70_template.prj"))
    desc = RasAdapter(policy).plan_description(request(project))
    assert units.units == "ft"
    assert units.records[0].value == "ft"
    assert desc.records[0].value == "Representative syntax fixture, not a computed model."
    assert {p.name: p.read_bytes() for p in project.iterdir()} == original
    import logging
    assert not [h for h in logging.getLogger().handlers if isinstance(h, logging.FileHandler)
                and Path(h.baseFilename).is_relative_to(project)]


def test_missing_description_and_units(policy, project):
    (project / "empty.prj").write_text("Proj Title=Empty\n")
    (project / "empty.p01").write_text("Plan Title=Empty\n")
    api = RasAdapter(policy)
    assert api.project_units(request(project, "empty.prj")).missing_fields == ["length_units"]
    assert api.plan_description(request(project, "empty.p01")).missing_fields == ["Description"]


@pytest.mark.parametrize("kwargs", [{"max_characters": 1}, {"max_characters": 16001}, {"max_seconds": 0}, {"max_seconds": 31}, {"root": ""}, {"extra": True}, {"max_seconds": "10"}])
def test_strict_requests(project, kwargs):
    data = {"root": str(project), "file": "a.prj"} | kwargs
    with pytest.raises(ValidationError):
        Request.model_validate(data)


def test_metadata_requires_upstream_api_without_parser_fallback(policy, project, monkeypatch):
    monkeypatch.setattr(adapter, "metadata_api", lambda: None)
    with pytest.raises(PolicyError, match="lacks RasText"):
        RasAdapter(policy).metadata(MetadataRequest(root=str(project), file="hec_ras_70_template.prj", fields=["Proj Title"]), "project")


@pytest.mark.skipif(not metadata_api_present(), reason="Published 0.103.0 lacks new RasText")
def test_current_candidate_metadata_repeated_values_paging_and_units(policy, project):
    (project / "repeated.prj").write_text("Proj Title=Example\nEnglish Units\nPlan File=p01\nPlan File=p02\nGeom File=g99\n")
    q = MetadataRequest(root=str(project), file="repeated.prj", fields=["Plan File", "Units", "Current Plan"], limit=1)
    result = RasAdapter(policy).metadata(q, "project")
    assert result.total_records == 3 and result.returned_records == 1 and result.next_offset == 1
    assert result.records[0].value == "p01" and result.units == "English"
    assert result.missing_fields == ["Current Plan"]
    later = RasAdapter(policy).metadata(q.model_copy(update={"offset": 1}), "project")
    assert later.records[0].value == "p02"
    plan = RasAdapter(policy).metadata(MetadataRequest(root=str(project), file="representative.p01", fields=["Simulation Date", "UNET D1 Cores", "Geom File"]), "plan")
    assert {r.field: r.value for r in plan.records}["UNET D1 Cores"] == "4"
    assert "timezone" in plan.time_basis


def test_future_upstream_fields_cannot_expand_mcp(policy, project, monkeypatch):
    fake = SimpleNamespace(PROJECT_FIELDS={"Proj Title", "Coordinates"})
    monkeypatch.setattr(adapter, "metadata_api", lambda: fake)
    with pytest.raises(PolicyError, match="fixed non-spatial"):
        RasAdapter(policy).metadata(MetadataRequest(root=str(project), file="hec_ras_70_template.prj", fields=["Coordinates"]), "project")


def test_unrequested_upstream_output_rejected(policy, project, monkeypatch):
    fake = SimpleNamespace(PROJECT_FIELDS={"Proj Title"}, read_project_metadata=lambda *a, **k: {"fields": {"Coordinates": ["never return"]}, "missing_fields": []})
    monkeypatch.setattr(adapter, "metadata_api", lambda: fake)
    with pytest.raises(PolicyError, match="unrequested"):
        RasAdapter(policy).metadata(MetadataRequest(root=str(project), file="hec_ras_70_template.prj", fields=["Proj Title"]), "project")


@pytest.mark.parametrize("value", ["é水🙂" * 3000, '\\"\n\t' * 3000, "long narrative " * 1500], ids=["unicode", "json-escapes", "long-ascii"])
def test_narrative_bounds_unicode_json_and_truncation(policy, project, value):
    snap = policy.read(str(project), "representative.p01", "plan")
    q = request(project, max_characters=1600)
    result = bounded_result(snap, {"Description": [value]}, q)
    encoded = result.model_dump_json(indent=2)
    assert len(encoded) <= 1600 and result.truncated
    assert result.records[0].value == value[:len(result.records[0].value)]
    assert result.warnings and json.loads(encoded)["records"][0]["value"] == result.records[0].value


@pytest.mark.parametrize("field", ["Plan Title", "Short Identifier", "UNET D1 Cores", "Simulation Date", "Plan File"])
def test_scalars_and_identifiers_never_sliced(policy, project, field):
    snap = policy.read(str(project), "representative.p01", "plan")
    with pytest.raises(PolicyError, match="never sliced"):
        bounded_result(snap, {field: ["1234567890" * 3000]}, request(project, max_characters=1200))


@pytest.mark.skipif(not metadata_api_present(), reason="Published 0.103.0 lacks new RasText")
def test_explicit_actual_source_key_variants_retain_precision(policy, project):
    (project / "variants.p01").write_text("Run PostProcess=0001\nRun WQNet=0000\nRun Post Process=1\nRun WQNET=0\n")
    fields = ["Run PostProcess", "Run WQNet", "Run Post Process", "Run WQNET"]
    result = RasAdapter(policy).metadata(MetadataRequest(root=str(project), file="variants.p01", fields=fields), "plan")
    assert {record.field: record.value for record in result.records} == {
        "Run PostProcess": "0001", "Run WQNet": "0000", "Run Post Process": "1", "Run WQNET": "0"}
