import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from ras_commander_mcp.policy import PolicyError, ReadPolicy


def test_real_template_snapshots(policy, project):
    for file in ("hec_ras_66_template.prj", "hec_ras_70_template.prj"):
        snapshot = policy.read(str(project), file, "project")
        assert snapshot.data.startswith(b"Proj Title=")
        assert snapshot.digest == hashlib.sha256((project / file).read_bytes()).hexdigest()


@pytest.mark.parametrize("file", ["../secret.prj", "sub/../a.prj", "/etc/a.prj", "C:\\a.prj", "C:a.prj", "\\\\host\\share\\a.prj", "a.prj:stream", "a\x00.prj", "./a.prj", "sub//a.prj", ""])
def test_traversal_and_drive_rejected(policy, project, file):
    with pytest.raises(PolicyError):
        policy.read(str(project), file, "project")


@pytest.mark.parametrize("file,kind", [("a.hdf", "project"), ("a.dss", "project"), ("a.g01", "plan"), ("a.u01", "plan"), ("a.rasmap", "project"), ("a.p00", "plan"), ("a.p100", "plan"), ("a.prj", "report")])
def test_unsupported_inputs_rejected_before_open(policy, project, file, kind, monkeypatch):
    monkeypatch.setattr(policy.__class__, "_open", lambda *args: pytest.fail("unapproved input was opened"))
    with pytest.raises(PolicyError):
        policy.read(str(project), file, kind)


def test_unconfigured_root_rejected(policy, project):
    with pytest.raises(PolicyError, match="configured"):
        policy.read(str(project.parent), "anything.prj", "project")


@pytest.mark.parametrize("value", ["[]", "{}", '"a"', "invalid", '[123]', '["relative"]'])
def test_environment_rejects_bad_configuration(monkeypatch, value):
    monkeypatch.setenv("RAS_MCP_ALLOWED_ROOTS", value)
    with pytest.raises(PolicyError):
        ReadPolicy.from_environment()


def test_environment_explicit_roots(monkeypatch, project):
    monkeypatch.setenv("RAS_MCP_ALLOWED_ROOTS", json.dumps([str(project), str(project)]))
    assert ReadPolicy.from_environment().roots == (project,)


def test_size_nul_directory_and_changed_file(policy, project, monkeypatch):
    file = project / "bad.prj"
    file.write_bytes(b"x" * (policy.max_file_bytes + 1))
    with pytest.raises(PolicyError, match="size"):
        policy.read(str(project), file.name, "project")
    file.write_bytes(b"x\x00y")
    with pytest.raises(PolicyError, match="NUL"):
        policy.read(str(project), file.name, "project")
    file.unlink()
    file.mkdir()
    with pytest.raises((PolicyError, OSError)):
        policy.read(str(project), file.name, "project")
    file.rmdir()
    file.write_bytes(b"Proj Title=stable")
    real = os.fstat
    calls = 0
    def changed(fd):
        nonlocal calls
        record = real(fd)
        calls += 1
        return SimpleNamespace(st_mode=record.st_mode, st_size=record.st_size,
                               st_mtime_ns=record.st_mtime_ns + (calls % 2), st_ctime_ns=record.st_ctime_ns)
    monkeypatch.setattr(os, "fstat", changed)
    with pytest.raises(PolicyError, match="changed"):
        policy.read(str(project), file.name, "project")


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor no-follow semantics")
def test_symlink_file_and_parent_cannot_escape(policy, project, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside.prj").write_text("Proj Title=secret")
    (project / "link.prj").symlink_to(outside / "outside.prj")
    (project / "directory").symlink_to(outside, target_is_directory=True)
    for path in ("link.prj", "directory/outside.prj"):
        with pytest.raises(OSError):
            policy.read(str(project), path, "project")


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor ancestry semantics")
def test_configured_root_ancestor_symlink_swap_rejected(tmp_path):
    original = tmp_path / "parent"
    root = original / "project"
    root.mkdir(parents=True)
    (root / "a.prj").write_text("Proj Title=safe")
    policy = ReadPolicy((root,))
    original.rename(tmp_path / "moved")
    original.symlink_to(tmp_path / "moved", target_is_directory=True)
    with pytest.raises(OSError):
        policy.read(str(root), "a.prj", "project")


@pytest.mark.skipif(os.name != "nt", reason="Windows MAX_PATH behavior")
def test_windows_reads_beyond_max_path(tmp_path):
    from ras_commander_mcp.policy import _extended_path
    root = tmp_path.resolve()
    parts = [f"Deeply Nested Consultant Folder {i:02d}" for i in range(8)] + ["Model.p01"]
    target = root.joinpath(*parts)
    assert len(str(target)) > 260
    os.makedirs(_extended_path(target.parent))
    blob = b"Plan Title=Long path\n"
    with open(_extended_path(target), "wb") as stream:
        stream.write(blob)
    snapshot = ReadPolicy((root,)).read(str(root), "\\".join(parts), "plan")
    assert snapshot.data == blob
    with pytest.raises(PolicyError):
        ReadPolicy((root,)).read(str(root), "\\".join(parts[:-1] + ["..", "..", "Model.p01"]), "plan")
