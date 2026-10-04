from pathlib import Path
import shutil
import pytest
from ras_commander_mcp.policy import ReadPolicy


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    fixtures = Path(__file__).parent / "fixtures"
    for item in fixtures.iterdir():
        if item.suffix.lower() == ".prj" or item.suffix.lower().startswith(".p0"):
            shutil.copyfile(item, root / item.name)
    return root


@pytest.fixture
def policy(project):
    return ReadPolicy((project.resolve(),))
