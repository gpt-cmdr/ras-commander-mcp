from concurrent.futures import ThreadPoolExecutor
import multiprocessing
from pathlib import Path
import threading
import time
import pytest
from ras_commander_mcp import worker, server
from ras_commander_mcp.contracts import Request
from ras_commander_mcp.policy import PolicyError
from tests.support import slow_query, eof_query, partial_package_query


def query(project, seconds=10):
    return Request(root=str(project), file="hec_ras_70_template.prj", max_seconds=seconds)


def test_spawned_current_api_read_no_writes(policy, project, tmp_path, monkeypatch):
    temp = tmp_path / "private"
    temp.mkdir()
    monkeypatch.setattr(worker.tempfile, "tempdir", str(temp))
    before = {p.name: p.read_bytes() for p in project.iterdir()}
    result = worker.execute(policy, "project_units", query(project))
    assert result.units == "ft"
    assert {p.name: p.read_bytes() for p in project.iterdir()} == before
    assert list(temp.iterdir()) == []


def test_timeout_kills_child_and_cleans_scratch(policy, project, tmp_path, monkeypatch):
    temp = tmp_path / "private"
    temp.mkdir()
    monkeypatch.setattr(worker.tempfile, "tempdir", str(temp))
    monkeypatch.setattr(worker, "_query", slow_query)
    start = time.monotonic()
    with pytest.raises(PolicyError, match="time budget"):
        worker.execute(policy, "project_units", query(project, 1))
    assert time.monotonic() - start < 3.5
    assert not multiprocessing.active_children()
    assert list(temp.iterdir()) == []


def test_busy_concurrency_limit_is_immediate(policy, project):
    assert worker._slots.acquire(blocking=False)
    assert worker._slots.acquire(blocking=False)
    try:
        start = time.monotonic()
        with pytest.raises(PolicyError, match="busy"):
            worker.execute(policy, "project_units", query(project))
        assert time.monotonic() - start < 0.2
    finally:
        worker._slots.release()
        worker._slots.release()


def test_concurrent_real_queries_have_isolated_state(policy, project):
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(worker.execute, policy, "project_units", query(project)) for _ in range(2)]
        assert [future.result().units for future in pending] == ["ft", "ft"]
    assert not multiprocessing.active_children()


def test_allocation_failure_releases_slots(policy, project, monkeypatch):
    monkeypatch.setattr(worker.multiprocessing, "get_context", lambda *a: (_ for _ in ()).throw(OSError("allocation failed")))
    with pytest.raises(OSError):
        worker.execute(policy, "project_units", query(project))
    assert worker._slots.acquire(blocking=False)
    assert worker._slots.acquire(blocking=False)
    worker._slots.release()
    worker._slots.release()


def test_worker_eof_has_actionable_error(policy, project, monkeypatch):
    monkeypatch.setattr(worker, "_query", eof_query)
    with pytest.raises(PolicyError, match="exited without a result"):
        worker.execute(policy, "project_units", query(project))


def test_staging_never_inside_project(policy, project, monkeypatch):
    monkeypatch.setattr(worker.tempfile, "tempdir", str(project))
    with pytest.raises(PolicyError, match="outside approved"):
        worker.execute(policy, "project_units", query(project))


def test_optional_network_total_timeout(monkeypatch):
    monkeypatch.setattr(worker, "_package_query", partial_package_query)
    before = time.monotonic()
    latest, status = worker.check_pypi(seconds=0.5)
    assert status == "offline" and not any(latest.values())
    assert time.monotonic() - before < 2.5
    assert not multiprocessing.active_children()


def test_update_cache_no_automatic_install_and_offline(monkeypatch):
    from importlib.metadata import version
    pins = {name: version(name) for name in ("ras-commander", "mcp")}
    monkeypatch.setattr(server, "_update_cache", None)
    calls = []
    monkeypatch.setattr(server, "check_pypi", lambda **kwargs: (calls.append(kwargs) or {name: None for name in ("ras-commander", "mcp", "ras-commander-mcp")}, "offline"))
    assert server._updates(False)[1] == "not_checked" and not calls
    assert server._updates(True)[1] == "offline"
    assert server._updates(True)[1] == "offline" and len(calls) == 1
    assert {name: version(name) for name in pins} == pins


def test_uncached_concurrent_update_never_blocks(monkeypatch):
    monkeypatch.setattr(server, "_update_cache", None)
    assert server._update_lock.acquire(blocking=False)
    try:
        start = time.monotonic()
        assert server._updates(True)[1] == "offline"
        assert time.monotonic() - start < 0.2
    finally:
        server._update_lock.release()


def test_stable_yanked_selection_and_response_bound(monkeypatch):
    import json
    import urllib.request
    class Connection:
        def send(self, value): self.value = value
        def close(self): pass
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit):
            return json.dumps({"releases": {"2.3.0": [{"yanked": False}], "99.0rc1": [{"yanked": False}], "99.0": [{"yanked": True}]}}).encode()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Response())
    connection = Connection()
    worker._package_query(connection)
    assert set(connection.value[0].values()) == {"2.3.0"}
    assert connection.value[1] == "checked"
    monkeypatch.setattr(Response, "read", lambda self, limit: b"x" * limit)
    worker._package_query(connection)
    assert not any(connection.value[0].values()) and connection.value[1] == "offline"


def test_live_pypi_metadata_is_optional_and_preserves_pins():
    import os
    from importlib.metadata import version
    if os.environ.get("RAS_MCP_LIVE_PYPI") != "1":
        pytest.skip("Optional live PyPI metadata check")
    pins = {name: version(name) for name in ("ras-commander", "mcp")}
    start = time.monotonic()
    latest, status = worker.check_pypi(seconds=5)
    assert time.monotonic() - start < 7.5
    assert status in {"checked", "offline"}
    if status == "checked":
        from packaging.version import Version
        assert all(value and not Version(value).is_prerelease for value in latest.values())
    assert {name: version(name) for name in pins} == pins
