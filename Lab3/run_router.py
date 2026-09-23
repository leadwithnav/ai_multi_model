#!/usr/bin/env python3

"""
Lab 3 — Benchmark-Derived Model Router

Flow:
1. Read engineering request.
2. task-classifier determines task_type.
3. routing_policy.yaml maps task_type to an agent.
4. Run the selected OpenCode agent.
5. Save raw JSONL for metrics analysis.

No fallback.
No acceptance testing.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml


# ============================================================
# CONFIGURATION
# ============================================================

LAB_DIR = Path(__file__).resolve().parent

POLICY_FILE = (
    LAB_DIR
    / "config"
    / "routing_policy.yaml"
)

RUNS_DIR = LAB_DIR / "runs"

CLASSIFIER_AGENT = "task-classifier"


# ============================================================
# OPENCODE EXECUTABLE
# ============================================================

def opencode_binary():

    if os.name == "nt":
        return "opencode.cmd"

    return "opencode"


# ============================================================
# SAVE RAW JSONL
# ============================================================

def save_jsonl(request_name, role, stdout):

    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        RUNS_DIR
        / f"{request_name}_{role}.jsonl"
    )

    path.write_text(
        stdout,
        encoding="utf-8",
    )

    return path


# ============================================================
# EXTRACT TEXT FROM OPENCODE JSONL
# ============================================================

def parse_opencode_output(stdout):

    text_parts = []

    for line in stdout.splitlines():

        line = line.strip()

        if not line:
            continue

        try:
            event = json.loads(line)

        except json.JSONDecodeError:
            continue

        part = event.get("part", {})

        if part.get("type") == "text":

            text = part.get("text")

            if text:
                text_parts.append(text)

    return "\n".join(text_parts).strip()


# ============================================================
# STEP 1 — CLASSIFY TASK
# ============================================================

def classify_task(request_text, request_name):

    print()
    print("=" * 60)
    print("1. TASK CLASSIFICATION")
    print("=" * 60)

    # Compact request only for classification.
    compact_request = " ".join(
        request_text.split()
    )

    command = [
        opencode_binary(),
        "run",
        "--agent",
        CLASSIFIER_AGENT,
        "--format",
        "json",
        compact_request,
    ]

    try:

        result = subprocess.run(
            command,
            cwd=LAB_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )

    except subprocess.TimeoutExpired:

        raise RuntimeError(
            "Task classifier timed out."
        )


    # Save classifier telemetry.
    classifier_path = save_jsonl(
        request_name,
        "classifier",
        result.stdout,
    )


    if result.returncode != 0:

        raise RuntimeError(
            "Task classifier failed.\n\n"
            + result.stderr[-2000:]
        )


    response = parse_opencode_output(
        result.stdout
    )


    # Remove accidental Markdown fences.
    response = (
        response
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )


    try:

        classification = json.loads(
            response
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "Task classifier did not return valid JSON."
            "\n\nClassifier response:\n"
            + response
        ) from exc


    task_type = classification.get(
        "task_type"
    )


    allowed_task_types = {
        "implementation",
        "refactoring",
        "debugging",
        "testing",
    }


    if task_type not in allowed_task_types:

        raise RuntimeError(
            f"Invalid task_type returned "
            f"by classifier: {task_type}"
        )


    print(
        f"Task Type : {task_type}"
    )


    signals = classification.get(
        "signals",
        [],
    )

    if signals:

        print("\nSignals:")

        for signal in signals:
            print(f"  - {signal}")


    print(
        f"\nClassifier telemetry:\n"
        f"{classifier_path}"
    )


    return classification


# ============================================================
# STEP 2 — LOAD ROUTING POLICY
# ============================================================

def load_policy():

    if not POLICY_FILE.exists():

        raise FileNotFoundError(
            f"Routing policy not found:\n"
            f"{POLICY_FILE}"
        )


    with POLICY_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:

        return yaml.safe_load(f)


# ============================================================
# STEP 3 — SELECT AGENT
# ============================================================

def select_agent(
    classification,
    policy,
):

    task_type = classification["task_type"]


    try:

        agent = (
            policy["routing_policy"]
                  [task_type]
                  ["primary"]
        )

    except KeyError as exc:

        raise RuntimeError(
            "Routing policy is missing "
            f"a mapping for: {exc}"
        ) from exc


    return agent


# ============================================================
# STEP 4 — RUN SELECTED AGENT
# ============================================================

def execute_agent(
    agent,
    request_text,
    request_name,
):

    print()
    print("=" * 60)
    print("3. AGENT EXECUTION")
    print("=" * 60)


    print(
        f"Agent : {agent}"
    )


    command = [
        opencode_binary(),
        "run",
        "--agent",
        agent,
        "--format",
        "json",
        request_text,
    ]


    start = time.perf_counter()


    try:

        result = subprocess.run(
            command,
            cwd=LAB_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )

    except subprocess.TimeoutExpired as exc:

        elapsed = (
            time.perf_counter()
            - start
        )

        stdout = exc.stdout or ""

        if isinstance(stdout, bytes):

            stdout = stdout.decode(
                errors="replace"
            )


        jsonl_path = save_jsonl(
            request_name,
            "primary",
            stdout,
        )


        print(
            "\nExecution Status: TIMEOUT"
        )


        return {
            "status": "TIMEOUT",
            "wall_seconds": elapsed,
            "jsonl_path": str(jsonl_path),
        }


    elapsed = (
        time.perf_counter()
        - start
    )


    jsonl_path = save_jsonl(
        request_name,
        "primary",
        result.stdout,
    )


    if result.returncode != 0:

        print()
        print(
            "Execution Status: MODEL_ERROR"
        )

        if result.stderr:

            print(
                result.stderr[-2000:]
            )


        return {
            "status": "MODEL_ERROR",
            "wall_seconds": elapsed,
            "jsonl_path": str(jsonl_path),
        }


    print()
    print(
        "Execution Status: COMPLETED"
    )

    print(
        f"Wall Time       : "
        f"{elapsed:.2f}s"
    )

    print(
        f"Telemetry       : "
        f"{jsonl_path}"
    )


    return {
        "status": "COMPLETED",
        "wall_seconds": elapsed,
        "jsonl_path": str(jsonl_path),
    }


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(
    request_name,
    classification,
    agent,
    execution,
):

    result = {

        "request":
            request_name,

        "classification":
            classification,

        "selected_agent":
            agent,

        "execution":
            execution,
    }


    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    path = (
        RUNS_DIR
        / f"{request_name}_result.json"
    )


    path.write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )


    return path


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) != 2:

        print()
        print(
            "Usage:"
        )

        print(
            "python run_router.py "
            "tasks/request_01.md"
        )

        sys.exit(1)


    # --------------------------------------------------------
    # Read engineering request
    # --------------------------------------------------------

    request_path = Path(
        sys.argv[1]
    ).resolve()


    if not request_path.exists():

        raise FileNotFoundError(
            request_path
        )


    request_name = (
        request_path.stem
    )


    request_text = (
        request_path.read_text(
            encoding="utf-8"
        )
    )


    print()
    print("=" * 60)
    print(
        "LAB 3 — BENCHMARK-DERIVED MODEL ROUTER"
    )
    print("=" * 60)

    print(
        f"\nRequest: {request_name}"
    )


    # ========================================================
    # 1. CLASSIFY
    # ========================================================

    classification = classify_task(
        request_text,
        request_name,
    )


    # ========================================================
    # 2. LOAD POLICY + SELECT AGENT
    # ========================================================

    policy = load_policy()


    agent = select_agent(
        classification,
        policy,
    )


    print()
    print("=" * 60)
    print("2. ROUTING DECISION")
    print("=" * 60)


    print(
        f"Task Type : "
        f"{classification['task_type']}"
    )

    print(
        f"Agent     : "
        f"{agent}"
    )


    # ========================================================
    # 3. EXECUTE
    # ========================================================

    execution = execute_agent(
        agent,
        request_text,
        request_name,
    )


    # ========================================================
    # 4. SAVE RESULT
    # ========================================================

    result_path = save_result(
        request_name,
        classification,
        agent,
        execution,
    )


    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    print("=" * 60)
    print("FINAL RESULT")
    print("=" * 60)


    print(
        f"Status : "
        f"{execution['status']}"
    )

    print(
        f"Agent  : "
        f"{agent}"
    )

    print(
        f"\nResult artifact:\n"
        f"{result_path}"
    )


    print()
    print(
        "Run metrics with:"
    )

    print(
        "python metrics_helper.py "
        f"runs/{request_name}_primary.jsonl"
    )


    if execution["status"] == "COMPLETED":
        sys.exit(0)

    sys.exit(2)


if __name__ == "__main__":
    main()