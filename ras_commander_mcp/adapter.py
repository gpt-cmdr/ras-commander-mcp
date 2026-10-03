"""Public library adapters; domain parsers remain in ras-commander."""

from importlib import import_module
from importlib.util import find_spec
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import TemporaryDirectory

from . import __version__
from .contracts import MetadataRequest, PLAN_FIELDS, PROJECT_FIELDS, Record, Request, Result, Source
from .policy import PolicyError, ReadPolicy, Snapshot


def versions() -> dict[str, str]:
    output = {"ras-commander-mcp": __version__}
    for name in ("ras-commander", "mcp"):
        try:
            output[name] = version(name)
        except PackageNotFoundError:
            output[name] = "not-installed"
    return output


def metadata_api_present() -> bool:
    """Inspect module availability without executing library package imports."""
    spec = find_spec("ras_commander")
    return bool(spec and spec.submodule_search_locations and any(
        (Path(location) / "RasText.py").is_file() for location in spec.submodule_search_locations))


def metadata_api():
    # The top-level exported symbol is the public contract. No private module
    # loader or copied fallback is used by the adapter.
    return getattr(import_module("ras_commander"), "RasText", None)


def _source(snapshot: Snapshot, encoding: str | None = None):
    return Source(root=str(snapshot.root), file=snapshot.relative,
                  size_bytes=len(snapshot.data), sha256=snapshot.digest, encoding=encoding)


def bounded_result(snapshot: Snapshot, fields: dict[str, list[str]], request: Request,
                   *, encoding=None, missing=(), offset=0, limit=100, warnings=(), units=None):
    """Keep a schema-valid JSON envelope within the requested character budget."""
    count = sum(len(values) for values in fields.values())
    result = Result(source=_source(snapshot, encoding), versions=versions(), records=[],
                    total_records=count, returned_records=0, missing_fields=list(missing),
                    warnings=list(warnings), units=units)
    index = 0
    stopped = False
    for key, values in fields.items():
        for occurrence, value in enumerate(values):
            if index < offset:
                index += 1
                continue
            if len(result.records) >= limit:
                stopped = True
                break
            record = Record(field=key, value=str(value), occurrence=occurrence)
            result.records.append(record)
            if len(result.model_dump_json(indent=2)) > request.max_characters - 180:
                result.records.pop()
                if not result.records:
                    if key != "Description":
                        raise PolicyError("Selected value exceeds output budget; increase the character "
                                          "budget or use Python. Numeric values and identifiers are never sliced.")
                    result.warnings.append("Description truncated; use Python for the complete narrative.")
                    # Only narrative text permits a prefix. Account for JSON
                    # escaping/indentation and the warning before choosing it.
                    left, right = 0, len(str(value))
                    while left < right:
                        middle = (left + right + 1) // 2
                        result.records = [Record(field=key, value=str(value)[:middle], occurrence=occurrence)]
                        if len(result.model_dump_json(indent=2)) <= request.max_characters - 180:
                            left = middle
                        else:
                            right = middle - 1
                    if left == 0:
                        raise PolicyError("Envelope exceeds output budget; shorten root/file or increase the budget")
                    result.records = [Record(field=key, value=str(value)[:left], occurrence=occurrence)]
                    index += 1
                stopped = True
                break
            index += 1
        if stopped:
            break
    result.returned_records = len(result.records)
    result.truncated = stopped or offset > 0
    result.next_offset = index if stopped and index < count and index > offset else None
    if len(result.model_dump_json(indent=2)) > request.max_characters:
        raise PolicyError("Envelope exceeds output budget; use a shorter root/file or fewer fields")
    return result


class RasAdapter:
    def __init__(self, policy: ReadPolicy):
        self.policy = policy

    def project_units(self, request: Request) -> Result:
        snapshot = self.policy.read(request.root, request.file, "project")
        # Current release API opens a path. Stage an immutable bounded snapshot
        # in disposable private scratch, never in the user's project.
        from ras_commander import RasPrj
        with TemporaryDirectory(prefix="ras-mcp-text-") as directory:
            path = Path(directory) / "snapshot.prj"
            path.write_bytes(snapshot.data)
            path.chmod(0o400)
            try:
                units = RasPrj.get_project_units(path)
            finally:
                path.chmod(0o600)
        return bounded_result(snapshot, {"length_units": [] if units is None else [units]}, request,
                              units=units, missing=() if units else ("length_units",))

    def plan_description(self, request: Request) -> Result:
        snapshot = self.policy.read(request.root, request.file, "plan")
        from ras_commander import RasPlan
        with TemporaryDirectory(prefix="ras-mcp-text-") as directory:
            path = Path(directory) / "snapshot.p01"
            path.write_bytes(snapshot.data)
            path.chmod(0o400)
            try:
                description = RasPlan.read_plan_description(path)
            finally:
                path.chmod(0o600)
        return bounded_result(snapshot, {"Description": [description] if description else []}, request,
                              missing=() if description else ("Description",))

    def metadata(self, request: MetadataRequest, kind: str) -> Result:
        api = metadata_api()
        if api is None:
            raise PolicyError("Installed ras-commander lacks RasText. Project units and plan description "
                              "remain available; install a qualified release containing RasText for metadata. "
                              "Do not initialize a project or substitute a copied parser.")
        policy_fields = PROJECT_FIELDS if kind == "project" else PLAN_FIELDS
        library_fields = api.PROJECT_FIELDS if kind == "project" else api.PLAN_FIELDS
        allowed = policy_fields.intersection(library_fields)
        if set(request.fields) - allowed:
            raise PolicyError("Selected fields must be approved by both MCP's fixed non-spatial policy "
                              "and the installed library contract")
        snapshot = self.policy.read(request.root, request.file, kind)
        method = api.read_project_metadata if kind == "project" else api.read_plan_metadata
        output = method(snapshot.data, fields=request.fields)
        if set(output["fields"]) - set(request.fields) or set(output["missing_fields"]) - set(request.fields):
            raise PolicyError("Installed library returned unrequested fields; compatibility review is required")
        unit_markers = output["fields"].get("Units", [])
        units = unit_markers[0] if len(set(unit_markers)) == 1 else None
        return bounded_result(snapshot, output["fields"], request, encoding=output["encoding"],
                              missing=output["missing_fields"], offset=request.offset,
                              limit=request.limit, units=units,
                              warnings=output.get("warnings", []))
