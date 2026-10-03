"""Record stable PyPI contracts for a reviewable update PR; never install/publish."""

from datetime import datetime, timezone
import json
from pathlib import Path
import urllib.request
from packaging.version import InvalidVersion, Version

PACKAGES = ("ras-commander", "mcp", "ras-commander-mcp")


def main():
    target = Path(__file__).resolve().parents[1] / "compatibility/pypi-snapshot.json"
    packages = {}
    for name in PACKAGES:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json", timeout=15) as response:
            data = response.read(2_097_153)
        if len(data) > 2_097_152:
            raise ValueError("PyPI metadata exceeded size limit")
        payload = json.loads(data)
        stable = []
        for label, files in payload["releases"].items():
            try:
                candidate = Version(label)
            except InvalidVersion:
                continue
            if not candidate.is_prerelease and not candidate.is_devrelease and any(
                    not artifact.get("yanked", False) for artifact in files):
                stable.append((candidate, label))
        if not stable:
            raise ValueError(f"No non-yanked stable release for {name}")
        selected = max(stable)[1]
        if payload["info"]["version"] != selected:
            with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{selected}/json", timeout=15) as response:
                data = response.read(2_097_153)
            if len(data) > 2_097_152:
                raise ValueError("PyPI release metadata exceeded size limit")
            payload = json.loads(data)
        info = payload["info"]
        packages[name] = {
            "version": info["version"], "requires_python": info["requires_python"],
            "requires_dist": sorted(info.get("requires_dist") or []),
            "artifacts": sorted(({
                "filename": artifact["filename"], "sha256": artifact["digests"]["sha256"],
                "url": artifact["url"], "upload_time": artifact["upload_time_iso_8601"],
            } for artifact in payload["urls"] if not artifact.get("yanked", False)), key=lambda artifact: artifact["filename"]),
        }
    previous = json.loads(target.read_text()) if target.exists() else {}
    if previous.get("packages") == packages:
        print("Stable PyPI contracts unchanged")
        return
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps({
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "packages": packages,
        "policy": "Review dependency bounds and qualify minimum/latest contracts; no unattended publication.",
    }, indent=2) + "\n")
    print("Updated snapshot; a maintainer must review new versions and compatibility")


if __name__ == "__main__":
    main()
