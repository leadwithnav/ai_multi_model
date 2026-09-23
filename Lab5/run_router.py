#!/usr/bin/env python3

"""
Adaptive Model + Reasoning Router

Flow:
1. Read engineering request.
2. Classifier determines:
      - task_type
      - complexity
3. Routing policy determines:
      - model from task_type
      - reasoning effort from complexity
4. Construct the OpenCode agent name.
5. Run the selected agent.
6. Save raw JSONL for metrics analysis.

Example:

    implementation + low
            ↓
        terra-low

    debugging + high
            ↓
         sol-high
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

CLASSIFIER_AGENT = "classifier"


# ============================================================
# OPENCODE EXECUTABLE
# ============================================================

def opencode_binary():
    """Return correct OpenCode executable for the OS."""

    if os.name == "nt":
        return "opencode.cmd"

    return "opencode"


# ============================================================
# SAVE RAW OPENCODE JSONL
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
# STEP 1 — CLASSIFY REQUEST
# ============================================================

def classify_request(request_text, request_name):

    print()
    print("=" * 60)
    print("1. CLASSIFICATION")
    print("=" * 60)

    # Keep classifier input compact.
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
            "Classifier timed out."
        )

    # Save classifier telemetry.
    classifier_path = save_jsonl(
        request_name,
        "classifier",
        result.stdout,
    )

    if result.returncode != 0:

        raise RuntimeError(
            "Classifier failed.\n\n"
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
            "Classifier did not return valid JSON."
            "\n\nClassifier response:\n"
            + response
        ) from exc


    # --------------------------------------------------------
    # Validate classifier output
    # --------------------------------------------------------

    allowed_task_types = {
        "implementation",
        "debugging",
        "refactoring",
        "testing",
    }

    allowed_complexities = {
        "low",
        "medium",
        "high",
    }

    task_type = classification.get(
        "task_type"
    )

    complexity = classification.get(
        "complexity"
    )

    if task_type not in allowed_task_types:

        raise RuntimeError(
            f"Invalid task_type returned "
            f"by classifier: {task_type}"
        )

    if complexity not in allowed_complexities:

        raise RuntimeError(
            f"Invalid complexity returned "
            f"by classifier: {complexity}"
        )


    print(
        f"Task Type  : {task_type}"
    )

    print(
        f"Complexity : {complexity}"
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
# STEP 3 — SELECT MODEL + REASONING
# ============================================================

def select_route(classification, policy):

    task_type = classification["task_type"]
    complexity = classification["complexity"]

    try:

        # Task type determines MODEL.
        model = (
            policy["model_policy"]
                  [task_type]
                  ["primary"]
        )

        # Complexity determines REASONING.
        reasoning_effort = (
            policy["reasoning_policy"]
                  [complexity]
        )

    except KeyError as exc:

        raise RuntimeError(
            "Routing policy is missing "
            f"a required mapping: {exc}"
        ) from exc


    # Agent names must match files in:
    #
    # .opencode/agent/
    #
    # terra-low.md
    # terra-medium.md
    # terra-high.md
    # sol-low.md
    # sol-medium.md
    # sol-high.md

    agent = (
        f"{model}-"
        f"{reasoning_effort}"
    )


    return {
        "model": model,
        "reasoning_effort": reasoning_effort,
        "agent": agent,
    }


# ============================================================
# STEP 4 — RUN SELECTED AGENT
# ============================================================

def execute_agent(
    route,
    request_text,
    request_name,
):

    print()
    print("=" * 60)
    print("3. AGENT EXECUTION")
    print("=" * 60)

    print(
        f"Model     : {route['model']}"
    )

    print(
        f"Reasoning : "
        f"{route['reasoning_effort']}"
    )

    print(
        f"Agent     : {route['agent']}"
    )


    command = [
        opencode_binary(),
        "run",
        "--agent",
        route["agent"],
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
        print("Execution Status: MODEL_ERROR")

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
    print("Execution Status: COMPLETED")

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
# SAVE RESULT SUMMARY
# ============================================================

def save_result(
    request_name,
    classification,
    route,
    execution,
):

    result = {

        "request": request_name,

        "classification": classification,

        "routing": {
            "model":
                route["model"],

            "reasoning_effort":
                route["reasoning_effort"],

            "agent":
                route["agent"],
        },

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

        print(
            "\nUsage:"
        )

        print(
            "python run_router.py "
            "tasks/request_01.md"
        )

        sys.exit(1)


    # --------------------------------------------------------
    # Read request
    # --------------------------------------------------------

    request_path = Path(
        sys.argv[1]
    ).resolve()


    if not request_path.exists():

        raise FileNotFoundError(
            request_path
        )


    request_name = request_path.stem


    request_text = (
        request_path.read_text(
            encoding="utf-8"
        )
    )


    print()
    print("=" * 60)
    print(
        "ADAPTIVE MODEL + REASONING ROUTER"
    )
    print("=" * 60)

    print(
        f"\nRequest: {request_name}"
    )


    # ========================================================
    # 1. CLASSIFY
    # ========================================================

    classification = classify_request(
        request_text,
        request_name,
    )


    # ========================================================
    # 2. ROUTE
    # ========================================================

    policy = load_policy()


    route = select_route(
        classification,
        policy,
    )


    print()
    print("=" * 60)
    print("2. ROUTING DECISION")
    print("=" * 60)


    print(
        f"Task Type  : "
        f"{classification['task_type']}"
    )

    print(
        f"Complexity : "
        f"{classification['complexity']}"
    )

    print(
        f"Model      : "
        f"{route['model']}"
    )

    print(
        f"Reasoning  : "
        f"{route['reasoning_effort']}"
    )

    print(
        f"Agent      : "
        f"{route['agent']}"
    )


    # ========================================================
    # 3. EXECUTE
    # ========================================================

    execution = execute_agent(
        route,
        request_text,
        request_name,
    )


    # ========================================================
    # 4. SAVE RESULT
    # ========================================================

    result_path = save_result(
        request_name,
        classification,
        route,
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
        f"Status      : "
        f"{execution['status']}"
    )

    print(
        f"Model       : "
        f"{route['model']}"
    )

    print(
        f"Reasoning   : "
        f"{route['reasoning_effort']}"
    )

    print(
        f"Agent       : "
        f"{route['agent']}"
    )

    print(
        f"\nResult:\n"
        f"{result_path}"
    )


    print()
    print("Run metrics with:")

    print(
        "python metrics_helper.py "
        f"runs/{request_name}_primary.jsonl"
    )


    if execution["status"] == "COMPLETED":
        sys.exit(0)

    sys.exit(2)


if __name__ == "__main__":
    main()