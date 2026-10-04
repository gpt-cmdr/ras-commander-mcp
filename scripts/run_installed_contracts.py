"""Run maintained contracts against the installed wheel, away from source imports."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="ras-mcp-wheel-contracts-") as directory:
        location = Path(directory)
        shutil.copytree(root / "tests", location / "tests",
                        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
        env = dict(os.environ)
        # No checkout/candidate on sys.path: subprocesses also exercise the wheel.
        env["PYTHONPATH"] = str(location)
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--timeout=60",
                                 "--junitxml=" + str(root / "contract-results.xml")],
                                cwd=location, env=env, check=False, timeout=600)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
