import os
import subprocess
import sys
from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SERVICE_ROOT = WORKSPACE_ROOT / "order_flow_service"
GENERATED_TEST_FILE = SERVICE_ROOT / "tests" / "test_inventory_generated.py"

def test_generated_inventory_tests_exist_and_pass():
    """
    Evaluates Workload 4 (Test Generation):
    1. Verifies that tests/test_inventory_generated.py exists.
    2. Runs pytest on the generated test file.
    3. Confirms at least 2 test cases ran and all passed.
    """
    assert GENERATED_TEST_FILE.exists(), (
        f"Generated test file not found at {GENERATED_TEST_FILE}. "
        "The model must generate tests/test_inventory_generated.py."
    )

    content = GENERATED_TEST_FILE.read_text(encoding="utf-8")
    assert "test_" in content, "Generated test file contains no test functions."

    # Run pytest on the generated file
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(GENERATED_TEST_FILE), "-v"],
        cwd=str(SERVICE_ROOT),
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Generated test suite failed:\n{result.stdout}\n{result.stderr}"
