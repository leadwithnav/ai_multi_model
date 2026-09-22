"""
Lab 3 Deterministic Verifier

CRITICAL PRINCIPLE:
Do not use an LLM to determine whether generated code is correct.
Use pytest / deterministic code execution.
"""

import sys
import subprocess
from pathlib import Path

LAB3_DIR = Path(__file__).resolve().parent
INSTRUCTOR_TESTS_DIR = LAB3_DIR / "instructor_tests"

TASK_TEST_MAP = {
    "implementation": "test_implementation.py",
    "refactoring": "test_refactoring.py",
    "debugging": "test_debugging.py",
    "testing": "test_testing.py"
}

def run_verification(task_type: str) -> dict:
    test_file_name = TASK_TEST_MAP.get(task_type, f"test_{task_type}.py")
    test_file_path = INSTRUCTOR_TESTS_DIR / test_file_name

    if not test_file_path.exists():
        return {
            "passed": False,
            "stdout": f"Test file not found: {test_file_path}",
            "stderr": "",
            "exit_code": 1
        }

    cmd = [sys.executable, "-m", "pytest", str(test_file_path), "-v", "--tb=short"]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(LAB3_DIR),
            capture_output=True,
            text=True,
            timeout=60
        )
        passed = (proc.returncode == 0)
        return {
            "passed": passed,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode
        }
    except Exception as e:
        return {
            "passed": False,
            "stdout": "",
            "stderr": str(e),
            "exit_code": 1
        }

if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "implementation"
    res = run_verification(task)
    print(f"Verification Result for '{task}': {'PASS' if res['passed'] else 'FAIL'}")
    print(res["stdout"])
