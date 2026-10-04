"""Inspect build metadata and package boundaries without running project APIs."""

from email.parser import Parser
from pathlib import Path
import tarfile
import tomllib
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    wheel = next((root / "dist").glob("*.whl"))
    source = next((root / "dist").glob("*.tar.gz"))
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata = Parser().parsestr(archive.read(next(n for n in names if n.endswith(".dist-info/METADATA"))).decode())
        points = archive.read(next(n for n in names if n.endswith(".dist-info/entry_points.txt"))).decode()
        assert metadata["Version"] == project["version"]
        assert metadata["Name"] == project["name"]
        assert set(metadata.get_all("Requires-Dist", [])) >= {"mcp<3,>=2.3.0", "ras-commander<1,>=0.103.0", "packaging>=24"}
        assert "ras-commander-mcp = ras_commander_mcp.server:run" in points
        assert all(n.startswith("ras_commander_mcp/") or ".dist-info/" in n for n in names)
        assert not any(n.startswith("./") or "settings.local" in n for n in names)
    with tarfile.open(source) as archive:
        names = archive.getnames()
        package_info = next(n for n in names if n.endswith("/PKG-INFO"))
        metadata = Parser().parsestr(archive.extractfile(package_info).read().decode())
        assert metadata["Version"] == project["version"]
        assert any(n.endswith("/ras_commander_mcp/server.py") for n in names)
        assert not any(".ai_tools" in n or "ras-commander reference files" in n for n in names)
    print("Wheel/sdist metadata and package boundaries match source")


if __name__ == "__main__":
    main()
