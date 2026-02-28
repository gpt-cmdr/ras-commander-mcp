#!/usr/bin/env python3
"""
Test a single tool for quick iteration
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from server import get_hdf_structure


def test_single_tool():
    """Test a single tool call"""
    hdf_path = str(Path(__file__).parent.parent / "testdata" / "BeaverLake" / "BeaverLakeSWMMImpor.p01.hdf")
    print(f"Testing get_hdf_structure...")
    print(f"hdf_path: {hdf_path}")
    print(f"group_path: /Results")
    print("-" * 60)

    try:
        result = get_hdf_structure(hdf_path=hdf_path, group_path="/Results")
        print("Output:")
        print(result)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_single_tool()
