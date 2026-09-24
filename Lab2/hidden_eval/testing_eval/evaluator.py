#!/usr/bin/env python3
"""
Task 4 Test Suite Evaluator (Mutation Testing Framework)

Evaluates participant model-generated tests in `tests/test_inventory_generated.py`
by running them against:
1. Baseline Production Code (Must PASS 100%)
2. 5 Hidden Defective Mutants (Must FAIL / Detect the defects)

Calculates Defect Detection Score: (Mutants Killed / Total Mutants) * 100%
"""

import os
import sys
import shutil
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MUTATIONS_DIR = os.path.join(SCRIPT_DIR, "mutations")

# Locate order-flow-service directory dynamically
candidate_dirs = [
    os.path.abspath(os.path.join(SCRIPT_DIR, "../../../order-flow-service")),
    os.path.abspath(os.path.join(SCRIPT_DIR, "../../order-flow-service")),
    os.path.abspath(os.path.join(SCRIPT_DIR, "../order-flow-service")),
]

ORDER_FLOW_DIR = None
for c in candidate_dirs:
    if os.path.exists(os.path.join(c, "src")):
        ORDER_FLOW_DIR = c
        break

if not ORDER_FLOW_DIR:
    print("ERROR: Could not locate order-flow-service directory.", flush=True)
    sys.exit(1)

TARGET_SERVICE_PATH = os.path.join(ORDER_FLOW_DIR, "src/services/inventory_service.py")
GENERATED_TEST_PATH = os.path.join(ORDER_FLOW_DIR, "tests/test_inventory_generated.py")

def backup_file(filepath):
    backup_path = filepath + ".bak"
    shutil.copyfile(filepath, backup_path)
    return backup_path

def restore_file(filepath, backup_path):
    if os.path.exists(backup_path):
        shutil.copyfile(backup_path, filepath)
        os.remove(backup_path)

def run_pytest(test_file):
    """Runs pytest on the test_file within order-flow-service directory."""
    cmd = [sys.executable, "-m", "pytest", "-q", test_file]
    result = subprocess.run(cmd, cwd=ORDER_FLOW_DIR, capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr

def evaluate_test_suite():
    if not os.path.exists(GENERATED_TEST_PATH):
        print(f"ERROR: Generated test file not found at: {GENERATED_TEST_PATH}", flush=True)
        sys.exit(1)

    print("=" * 60, flush=True)
    print("TASK 4 EVALUATOR: Testing Mutation Defect Detection Score", flush=True)
    print("=" * 60, flush=True)

    service_backup = backup_file(TARGET_SERVICE_PATH)

    try:
        # Step 1: Run against Baseline
        print("\n[1/2] Running generated test suite against Baseline Code...", flush=True)
        baseline_passed, output = run_pytest("tests/test_inventory_generated.py")
        if not baseline_passed:
            print("❌ FAIL: Generated tests failed on the baseline correct implementation!", flush=True)
            print(output, flush=True)
            print("Quality Bar Status: FAIL (Baseline tests must pass)", flush=True)
            return

        print("✅ PASS: Generated tests pass cleanly on Baseline Code.", flush=True)

        # Step 2: Run against Mutants
        print("\n[2/2] Running generated test suite against 5 Defective Mutants...", flush=True)
        mutants = [f for f in os.listdir(MUTATIONS_DIR) if f.startswith("mutation_") and f.endswith(".py")]
        mutants.sort()

        killed_count = 0
        total_mutants = len(mutants)

        for mutant_file in mutants:
            mutant_path = os.path.join(MUTATIONS_DIR, mutant_file)
            shutil.copyfile(mutant_path, TARGET_SERVICE_PATH)

            passed, _ = run_pytest("tests/test_inventory_generated.py")
            if not passed:
                killed_count += 1
                print(f"  - {mutant_file}: 🎯 KILLED (Defect Detected)", flush=True)
            else:
                print(f"  - {mutant_file}: ⚠️ SURVIVED (Defect Missed by Test Suite)", flush=True)

        detection_score = (killed_count / total_mutants) * 100.0
        print("\n" + "=" * 60, flush=True)
        print(f"RESULTS SUMMARY:", flush=True)
        print(f"- Mutants Killed: {killed_count} / {total_mutants}", flush=True)
        print(f"- Defect Detection Score: {detection_score:.1f}%", flush=True)

        if detection_score >= 80.0:
            print(f"- Quality Bar: PASS (Score {detection_score:.1f}% >= 80%)", flush=True)
        else:
            print(f"- Quality Bar: FAIL (Score {detection_score:.1f}% < 80%)", flush=True)
        print("=" * 60, flush=True)

    finally:
        restore_file(TARGET_SERVICE_PATH, service_backup)

if __name__ == "__main__":
    evaluate_test_suite()
