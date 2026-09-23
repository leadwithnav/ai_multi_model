#!/usr/bin/env python3
"""
Lab 6 - Initial Model + Reasoning Router

Responsibilities:
1. Read engineering request.
2. Ask classifier for:
      - task_type
      - complexity
3. Apply deterministic routing_policy.yaml.
4. Return:
      - selected model
      - reasoning effort
      - OpenCode agent name

This script DOES NOT execute the coding agent.
It only decides the initial route.

Can be:
    python run_router.py tasks/request_01.md

or imported:
    from run_router import route_request
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml


# ============================================================
# PATHS
# ============================================================

LAB_DIR = Path(__file__).resolve().parent

ROUTING_POLICY_FILE = (
    LAB_DIR
    / "config"
    / "routing_policy.yaml"
)

RUNS_DIR = LAB_DIR / "runs"


# ============================================================
# CONSTANTS
# ============================================================

ALLOWED_TASK_TYPES = {
    "implementation",
    "debugging",
    "refactoring",
    "testing",
}

ALLOWED_COMPLEXITIES = {
    "low",
    "medium",
    "high",
}


# ============================================================
# HELPERS
# ============================================================

def opencode_binary():
    """
    Windows installs OpenCode as opencode.cmd.
    Linux/macOS normally use opencode.
    """

    if os.name == "nt":
        return "opencode.cmd"

    return "opencode"


def load_routing_policy():

    if not ROUTING_POLICY_FILE.exists():
        raise FileNotFoundError(
            f"Routing policy not found:\n"
            f"{ROUTING_POLICY_FILE}"
        )

    with open(
        ROUTING_POLICY_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        return yaml.safe_load(f)


def extract_text_from_jsonl(raw_output):
    """
    Extract text produced by OpenCode from JSONL events.
    """

    text_parts = []

    for line in raw_output.splitlines():

        line = line.strip()

        if not line:
            continue

        try:
            event = json.loads(line)

        except json.JSONDecodeError:
            continue

        if event.get("type") != "text":
            continue

        text = (
            event
            .get("part", {})
            .get("text", "")
        )

        if text:
            text_parts.append(text)

    return "\n".join(text_parts).strip()


def parse_json_response(text):
    """
    Parse classifier JSON.

    Also tolerates accidental markdown fences.
    """

    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    return json.loads(text)


# ============================================================
# CLASSIFIER
# ============================================================

def classify_request(
    request_text,
    request_name
):

    print()
    print("=" * 60)
    print("1. CLASSIFY REQUEST")
    print("=" * 60)

    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        RUNS_DIR
        / f"{request_name}_classifier.jsonl"
    )

    command = [
        opencode_binary(),
        "run",
        "--agent",
        "classifier",
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
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

    except subprocess.TimeoutExpired as exc:

        raise RuntimeError(
            "Classifier timed out."
        ) from exc

    elapsed = (
        time.perf_counter()
        - start
    )

    # Always save telemetry.
    output_file.write_text(
        result.stdout or "",
        encoding="utf-8"
    )

    if result.returncode != 0:

        raise RuntimeError(
            "Classifier failed.\n\n"
            + (result.stderr or "")
        )

    classifier_text = (
        extract_text_from_jsonl(
            result.stdout
        )
    )

    if not classifier_text:

        raise RuntimeError(
            "Classifier returned no text."
        )

    try:

        classification = (
            parse_json_response(
                classifier_text
            )
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "Classifier did not return "
            "valid JSON.\n\n"
            f"Received:\n{classifier_text}"
        ) from exc

    task_type = (
        classification
        .get("task_type", "")
        .lower()
    )

    complexity = (
        classification
        .get("complexity", "")
        .lower()
    )

    if task_type not in ALLOWED_TASK_TYPES:

        raise RuntimeError(
            "Invalid task_type returned "
            f"by classifier: {task_type}"
        )

    if complexity not in ALLOWED_COMPLEXITIES:

        raise RuntimeError(
            "Invalid complexity returned "
            f"by classifier: {complexity}"
        )

    classification[
        "task_type"
    ] = task_type

    classification[
        "complexity"
    ] = complexity

    classification[
        "classifier_wall_clock_seconds"
    ] = round(elapsed, 2)

    classification[
        "classifier_jsonl"
    ] = str(output_file)

    print(
        f"Task Type  : {task_type}"
    )

    print(
        f"Complexity : {complexity}"
    )

    signals = classification.get(
        "signals",
        []
    )

    if signals:

        print(
            "Signals    : "
            + ", ".join(signals)
        )

    return classification


# ============================================================
# DETERMINISTIC ROUTING POLICY
# ============================================================

def select_route(
    classification,
    policy
):

    task_type = classification[
        "task_type"
    ]

    complexity = classification[
        "complexity"
    ]

    try:

        model_rule = (
            policy["model_policy"]
            [task_type]
        )

        primary_model = (
            model_rule["primary"]
        )

        escalation_model = (
            model_rule.get(
                "escalation"
            )
        )

        reasoning = (
            policy["reasoning_policy"]
            [complexity]
        )

    except KeyError as exc:

        raise RuntimeError(
            "routing_policy.yaml is missing "
            f"required configuration: {exc}"
        ) from exc

    agent = (
        f"{primary_model}-"
        f"{reasoning}"
    )

    route = {

        "task_type":
            task_type,

        "complexity":
            complexity,

        "model":
            primary_model,

        "reasoning":
            reasoning,

        "agent":
            agent,

        "escalation_model":
            escalation_model,
    }

    print()
    print("=" * 60)
    print("2. INITIAL ROUTING DECISION")
    print("=" * 60)

    print(
        f"Task Type        : {task_type}"
    )

    print(
        f"Complexity       : {complexity}"
    )

    print(
        f"Primary Model    : {primary_model}"
    )

    print(
        f"Reasoning Effort : {reasoning}"
    )

    print(
        f"Selected Agent   : {agent}"
    )

    if escalation_model:

        print(
            f"Escalation Model : "
            f"{escalation_model}"
        )

    return route


# ============================================================
# PUBLIC FUNCTION USED BY run_recovery.py
# ============================================================

def route_request(task_path):

    task_path = Path(task_path)

    if not task_path.is_absolute():
        task_path = (
            LAB_DIR
            / task_path
        )

    if not task_path.exists():

        raise FileNotFoundError(
            f"Task file not found:\n"
            f"{task_path}"
        )

    request_name = task_path.stem

    request_text = (
        task_path.read_text(
            encoding="utf-8"
        )
    )

    classification = classify_request(
        request_text,
        request_name,
    )

    policy = load_routing_policy()

    route = select_route(
        classification,
        policy,
    )

    return {
        "request_name":
            request_name,

        "request_text":
            request_text,

        "task_path":
            str(task_path),

        "classification":
            classification,

        "route":
            route,
    }


# ============================================================
# CLI
# ============================================================

def main():

    if len(sys.argv) != 2:

        print(
            "Usage:\n"
            "  python run_router.py "
            "tasks/request_01.md"
        )

        sys.exit(1)

    result = route_request(
        sys.argv[1]
    )

    print()
    print("=" * 60)
    print("ROUTER RESULT")
    print("=" * 60)

    print(
        json.dumps(
            result["route"],
            indent=2
        )
    )

def main():
    if len(sys.argv) != 2:
        print(
            "Usage: python run_router.py "
            "tasks/request_01.md"
        )
        sys.exit(1)

    result = route_request(sys.argv[1])

    print()
    print("=" * 60)
    print("ROUTER RESULT")
    print("=" * 60)

    print(
        json.dumps(
            result["route"],
            indent=2
        )
    )


if __name__ == "__main__":
    main()