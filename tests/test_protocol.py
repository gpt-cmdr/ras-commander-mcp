import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
from jsonschema import Draft202012Validator
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters
from mcp.server.mcpserver.exceptions import ToolError
import pytest
from ras_commander_mcp.server import TOOLS, create_server
from ras_commander_mcp.contracts import Result
from ras_commander_mcp.adapter import metadata_api_present


def test_schema_tools_fallback_and_errors(policy, project):
    async def scenario():
        server = create_server(policy)
        tools = await server.list_tools()
        assert {item.name for item in tools} == set(TOOLS)
        assert await server.list_resources() == []
        by_name = {item.name: item for item in tools}
        for tool in tools:
            assert tool.output_schema and tool.annotations.read_only_hint
        request = {"root": str(project), "file": "representative.p01", "max_characters": 1600}
        result = await server.call_tool("plan_description", {"request": request})
        Draft202012Validator(by_name["plan_description"].output_schema).validate(result.structured_content)
        Result.model_validate(result.structured_content)
        assert json.loads(result.content[0].text) == result.structured_content
        assert len(result.content[0].text) <= 1600
        for name, args in [("unknown", {}), ("project_units", {"request": {"root": str(project), "file": "bad.hdf"}}), ("project_units", {"request": {"root": str(project), "file": "x.prj", "max_seconds": "1"}})]:
            with pytest.raises(ToolError):
                await server.call_tool(name, args)
        info = await server.call_tool("server_information", {})
        assert info.structured_content["update_status"] == "not_checked"
        assert info.structured_content["metadata_api_available"] == metadata_api_present()
    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_stdio_roundtrip_and_read_only_audit(project, tmp_path, mode):
    control = tmp_path / "audit"
    control.mkdir()
    audit_log = control / "project-access.jsonl"
    startup = '''import sys, os, json
root=os.environ.get("RAS_MCP_AUDIT_ROOT", "")
log=os.environ.get("RAS_MCP_AUDIT_LOG", "")
def audit(event,args):
    if event not in {"open", "os.mkdir", "os.remove", "os.rmdir", "os.rename"}: return
    target=args[0] if args else None
    if not isinstance(target,(str,bytes)): return
    path=os.path.abspath(os.fsdecode(target))
    if path != root and not path.startswith(root+os.sep): return
    if event == "open":
        mode=args[1]; flags=args[2]
        if (isinstance(mode,str) and any(c in mode for c in "wax+")) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)):
            raise RuntimeError("project write forbidden")
        if os.path.isfile(path) and not (path.lower().endswith(".prj") or path.lower().endswith(".p01")):
            raise RuntimeError("non-text project read forbidden")
    else: raise RuntimeError("project mutation forbidden")
    with open(log,"a") as stream: stream.write(json.dumps({"event":event,"path":path})+"\\n")
sys.addaudithook(audit)
real_open=os.open
def descriptor_open(path, flags, mode=0o777, *, dir_fd=None):
    resolved=os.fsdecode(path)
    if not os.path.isabs(resolved) and dir_fd is not None and os.name == "posix":
        resolved=os.path.join(os.readlink("/proc/self/fd/"+str(dir_fd)),resolved)
    absolute=os.path.abspath(resolved)
    if absolute == root or absolute.startswith(root+os.sep):
        if flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
            raise RuntimeError("project descriptor write forbidden")
        if os.path.isfile(absolute) and not (absolute.lower().endswith(".prj") or absolute.lower().endswith(".p01")):
            raise RuntimeError("non-text descriptor read forbidden")
        with open(log,"a") as stream: stream.write(json.dumps({"event":"open","path":absolute})+"\\n")
    if dir_fd is None: return real_open(path,flags,mode)
    return real_open(path,flags,mode,dir_fd=dir_fd)
os.open=descriptor_open
'''
    (control / "sitecustomize.py").write_text(startup)
    before = {item.name: hashlib.sha256(item.read_bytes()).hexdigest() for item in project.iterdir()}
    env = dict(os.environ)
    env.update({"RAS_MCP_ALLOWED_ROOTS": json.dumps([str(project)]), "RAS_MCP_AUDIT_ROOT": str(project), "RAS_MCP_AUDIT_LOG": str(audit_log),
                "PYTHONPATH": str(control) + os.pathsep + env.get("PYTHONPATH", "")})
    stderr = control / "stderr.log"
    async def scenario():
        with stderr.open("w") as errors:
            parameters = StdioServerParameters(command=sys.executable, args=["-m", "ras_commander_mcp"], env=env)
            async with Client(parameters, mode=mode) as client:
                tools = await client.list_tools()
                assert {tool.name for tool in tools.tools} == set(TOOLS)
                result = await client.call_tool("project_units", {"request": {"root": str(project), "file": "hec_ras_70_template.prj"}})
                assert result.structured_content["units"] == "ft"
                description = await client.call_tool("plan_description", {"request": {"root": str(project), "file": "representative.p01"}})
                assert "Representative syntax" in description.structured_content["records"][0]["value"]
                if metadata_api_present():
                    metadata = await client.call_tool("project_metadata", {"request": {"root": str(project), "file": "hec_ras_70_template.prj", "fields": ["Proj Title", "Units"]}})
                    assert metadata.structured_content["units"] == "English"
                else:
                    missing = await client.call_tool("project_metadata", {"request": {"root": str(project), "file": "hec_ras_70_template.prj", "fields": ["Proj Title"]}})
                    assert missing.is_error and "lacks RasText" in missing.content[0].text
                denied = await client.call_tool("project_units", {"request": {"root": str(project), "file": "../../other.prj"}})
                assert denied.is_error
    asyncio.run(scenario())
    assert {item.name: hashlib.sha256(item.read_bytes()).hexdigest() for item in project.iterdir()} == before
    assert audit_log.exists() and all(json.loads(line)["event"] == "open" for line in audit_log.read_text().splitlines())


@pytest.mark.parametrize("narrative", ["水🙂é" * 2500, '\\"\t' * 2500])
def test_actual_sdk_unicode_and_escaped_narrative_fallback(policy, project, narrative):
    (project / "unicode.p01").write_text("Plan Title=Unicode\nBEGIN DESCRIPTION:\n" + narrative + "\nEND DESCRIPTION:\n", encoding="utf-8")
    async def scenario():
        server = create_server(policy)
        tool = next(item for item in await server.list_tools() if item.name == "plan_description")
        result = await server.call_tool("plan_description", {"request": {"root": str(project), "file": "unicode.p01", "max_characters": 1600}})
        Draft202012Validator(tool.output_schema).validate(result.structured_content)
        assert result.structured_content["truncated"]
        assert result.structured_content["warnings"]
        assert json.loads(result.content[0].text) == result.structured_content
        assert len(result.content[0].text) <= 1600
        value = result.structured_content["records"][0]["value"]
        assert narrative.startswith(value)
    asyncio.run(scenario())
