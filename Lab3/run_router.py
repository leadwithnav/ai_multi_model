#!/usr/bin/env python3

"""
Lab 3 — Evidence-Driven Model Routing

Purpose:
    Compare three model-selection strategies:

    1. cheapest
       Always use the cheapest model.

    2. strongest
       Always use the strongest model.

    3. evidence
       Classify the engineering task and use the routing
       policy created from Lab 2 benchmark evidence.

Important:
    This script DOES NOT verify code quality.

    Verification is performed manually after the model run.

Example:

    python run_router.py tasks/implementation.md --strategy cheapest

    python run_router.py tasks/implementation.md --strategy strongest

    python run_router.py tasks/implementation.md --strategy evidence
"""

import sys
import json
import time
import shutil
import argparse
import subprocess
from pathlib import Path

from router import TaskClassifier, RoutingPolicy


# ============================================================
# PATHS
# ============================================================

LAB3_DIR = Path(__file__).resolve().parent

WORKSPACE_ROOT = LAB3_DIR.parent

SERVICE_ROOT = (
    WORKSPACE_ROOT
    / "order_flow_service"
)

ARTIFACTS_DIR = (
    LAB3_DIR
    / "artifacts"
)


# ============================================================
# OPENCode JSONL METRICS
# ============================================================

def parse_opencode_jsonl(
    raw_jsonl: str,
    agent_name: str
) -> dict:
    """
    Parse one complete OpenCode JSONL execution.

    Measures:

    - LLM steps
    - input tokens
    - cache read tokens
    - cache write tokens
    - output tokens
    - reasoning tokens
    - OpenCode event latency
    - total OpenCode-reported cost
    """

    llm_steps = 0

    direct_input_tokens = 0
    cache_read_tokens = 0
    cache_write_tokens = 0

    output_tokens = 0
    reasoning_tokens = 0

    total_cost = 0.0

    first_timestamp = None
    last_timestamp = None

    for line in raw_jsonl.splitlines():

        line = line.strip()

        if not line:
            continue

        try:
            event = json.loads(line)

        except json.JSONDecodeError:
            continue

        # ----------------------------------------------------
        # Capture timestamps from all events
        # ----------------------------------------------------

        timestamp = event.get("timestamp")

        if isinstance(timestamp, (int, float)):

            if first_timestamp is None:
                first_timestamp = timestamp

            last_timestamp = timestamp

        # ----------------------------------------------------
        # Metrics come from step_finish events
        # ----------------------------------------------------

        if event.get("type") != "step_finish":
            continue

        llm_steps += 1

        part = (
            event.get("part", {})
            or {}
        )

        tokens = (
            part.get("tokens", {})
            or {}
        )

        cache = (
            tokens.get("cache", {})
            or {}
        )

        direct_input_tokens += (
            tokens.get("input", 0)
            or 0
        )

        cache_read_tokens += (
            cache.get("read", 0)
            or 0
        )

        cache_write_tokens += (
            cache.get("write", 0)
            or 0
        )

        output_tokens += (
            tokens.get("output", 0)
            or 0
        )

        reasoning_tokens += (
            tokens.get("reasoning", 0)
            or 0
        )

        total_cost += (
            part.get("cost", 0.0)
            or 0.0
        )

    # --------------------------------------------------------
    # OpenCode event latency
    # --------------------------------------------------------

    if (
        first_timestamp is not None
        and last_timestamp is not None
    ):

        event_latency_seconds = (
            last_timestamp
            - first_timestamp
        ) / 1000.0

    else:

        event_latency_seconds = 0.0

    # --------------------------------------------------------
    # Token totals
    # --------------------------------------------------------

    effective_input_tokens = (
        direct_input_tokens
        + cache_read_tokens
        + cache_write_tokens
    )

    generated_tokens = (
        output_tokens
        + reasoning_tokens
    )

    total_processed_tokens = (
        effective_input_tokens
        + generated_tokens
    )

    return {

        "agent": agent_name,

        "llm_steps": llm_steps,

        "tokens": {

            "direct_input":
                direct_input_tokens,

            "cache_read":
                cache_read_tokens,

            "cache_write":
                cache_write_tokens,

            "effective_input":
                effective_input_tokens,

            "output":
                output_tokens,

            "reasoning":
                reasoning_tokens,

            "total_processed":
                total_processed_tokens
        },

        "event_latency_seconds":
            round(
                event_latency_seconds,
                2
            ),

        "cost_usd":
            round(
                total_cost,
                6
            )
    }


# ============================================================
# OPENCode EXECUTION
# ============================================================

def execute_opencode_agent(
    agent: str,
    prompt: str
) -> tuple[str, str, int, float]:
    """
    Execute one OpenCode coding agent.

    The model receives the complete engineering request.

    Returns:

        stdout
        stderr
        return_code
        wall_latency_seconds
    """

    opencode_bin = (
        shutil.which("opencode")
        or shutil.which("opencode.cmd")
        or "opencode"
    )

    cmd = [
        opencode_bin,
        "run",
        "--agent",
        agent,
        "--format",
        "json"
    ]

    start_time = time.perf_counter()

    try:

        proc = subprocess.run(

            cmd,

            cwd=str(SERVICE_ROOT),

            input=prompt,

            capture_output=True,

            text=True,

            timeout=300
        )

        wall_latency = (
            time.perf_counter()
            - start_time
        )

        return (
            proc.stdout or "",
            proc.stderr or "",
            proc.returncode,
            wall_latency
        )

    except subprocess.TimeoutExpired as exc:

        wall_latency = (
            time.perf_counter()
            - start_time
        )

        stdout = (
            exc.stdout
            or ""
        )

        stderr = (
            exc.stderr
            or ""
        )

        if isinstance(stdout, bytes):

            stdout = stdout.decode(
                "utf-8",
                errors="replace"
            )

        if isinstance(stderr, bytes):

            stderr = stderr.decode(
                "utf-8",
                errors="replace"
            )

        stderr += (
            "\nOpenCode execution timed out."
        )

        return (
            stdout,
            stderr,
            -1,
            wall_latency
        )

    except Exception as exc:

        wall_latency = (
            time.perf_counter()
            - start_time
        )

        return (
            "",
            str(exc),
            -1,
            wall_latency
        )


# ============================================================
# SAVE RAW OPENCode EXECUTION
# ============================================================

def save_raw_execution(
    task_type: str,
    strategy: str,
    stdout: str,
    stderr: str
) -> dict:
    """
    Save raw OpenCode JSONL and stderr.

    Useful for inspecting:

    - model reasoning flow
    - tool calls
    - token usage
    - cost
    - provider errors
    """

    raw_dir = (
        ARTIFACTS_DIR
        / task_type
        / "raw"
    )

    raw_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = time.time_ns()

    jsonl_path = (
        raw_dir
        / f"{strategy}_{timestamp}.jsonl"
    )

    jsonl_path.write_text(
        stdout or "",
        encoding="utf-8"
    )

    stderr_path = None

    if stderr:

        stderr_path = (
            raw_dir
            / f"{strategy}_{timestamp}.stderr.txt"
        )

        stderr_path.write_text(
            stderr,
            encoding="utf-8"
        )

    return {

        "jsonl":
            str(jsonl_path),

        "stderr":
            (
                str(stderr_path)
                if stderr_path
                else None
            )
    }


# ============================================================
# BASIC EXECUTION VALIDATION
# ============================================================

def detect_incomplete_prompt_response(
    stdout: str
) -> bool:
    """
    Detect an invalid benchmark run where the model
    appears not to have received the engineering task.

    This is an execution problem, not a model-quality failure.
    """

    lower = stdout.lower()

    indicators = [

        "message got cut off",

        "share the details",

        "provide the task",

        "actual task description"
    ]

    return any(
        indicator in lower
        for indicator in indicators
    )


# ============================================================
# DETERMINE TASK TYPE
# ============================================================

def determine_task_type(
    path: Path,
    request_text: str,
    strategy: str
) -> str:
    """
    Evidence strategy:
        Use the dedicated task-classifier OpenCode agent.

    Cheapest / strongest:
        Classification is unnecessary because the model
        does not depend on task type.

        The task type is therefore taken from the filename.
    """

    # ========================================================
    # Evidence-driven strategy
    # ========================================================

    if strategy == "evidence":

        print("\nCLASSIFICATION")
        print("-" * 50)

        task_type = (
            TaskClassifier.classify_request(
                request_text
            )
        )

        print(
            f"Task Type: {task_type}"
        )

        return task_type

    # ========================================================
    # Baseline strategies
    # ========================================================

    task_type = (
        path.stem.lower()
    )

    if (
        task_type
        not in TaskClassifier.VALID_TASK_TYPES
    ):

        raise ValueError(

            f"Cannot determine task type "
            f"from '{path.name}'.\n"

            f"For baseline strategies, "
            f"the task filename must be one of:\n"

            f"{TaskClassifier.VALID_TASK_TYPES}"
        )

    print("\nTASK TYPE")
    print("-" * 50)

    print(
        f"Task Type: {task_type}"
    )

    print(
        "LLM Classification: "
        "Not required for baseline strategy"
    )

    return task_type


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_pipeline(
    task_path: str,
    strategy: str = "evidence"
) -> dict:

    # --------------------------------------------------------
    # Resolve task file
    # --------------------------------------------------------

    path = Path(task_path)

    if not path.is_absolute():

        path = (
            LAB3_DIR
            / task_path
        )

    if not path.exists():

        print(
            f"ERROR: Task file not found: "
            f"{path}"
        )

        sys.exit(1)

    if not SERVICE_ROOT.exists():

        print(
            f"ERROR: Service repository "
            f"not found: {SERVICE_ROOT}"
        )

        sys.exit(1)

    # --------------------------------------------------------
    # Read engineering request
    # --------------------------------------------------------

    request_text = (
        path.read_text(
            encoding="utf-8"
        )
    )

    if not request_text.strip():

        print(
            "ERROR: Task file is empty."
        )

        sys.exit(1)

    # --------------------------------------------------------
    # Display task
    # --------------------------------------------------------

    print("\nINCOMING TASK")
    print("-" * 50)

    preview = (
        request_text
        .strip()[:300]
    )

    if len(request_text) > 300:

        preview += "..."

    print(preview)

    print(
        f"\nTask prompt length: "
        f"{len(request_text)} characters"
    )

    # ========================================================
    # 1. DETERMINE TASK TYPE
    # ========================================================

    try:

        task_type = (
            determine_task_type(
                path,
                request_text,
                strategy
            )
        )

    except Exception as exc:

        print("\nCLASSIFICATION ERROR")
        print("-" * 50)

        print(str(exc))

        sys.exit(1)

    # ========================================================
    # 2. SELECT MODEL
    # ========================================================

    try:

        policy = RoutingPolicy()

        decision = (
            policy.select_model(
                task_type,
                strategy=strategy
            )
        )

    except Exception as exc:

        print("\nROUTING ERROR")
        print("-" * 50)

        print(str(exc))

        sys.exit(1)

    primary_model = (
        decision["primary"]
    )

    fallback_model = (
        decision.get("fallback")
    )

    print("\nROUTING DECISION")
    print("-" * 50)

    print(
        f"Strategy:       {strategy}"
    )

    print(
        f"Selected Model: {primary_model}"
    )

    if strategy == "evidence":

        print(
            f"Configured Fallback: "
            f"{fallback_model}"
        )

        print(
            "Automatic Fallback: DISABLED"
        )

    print(
        f"Reason:         "
        f"{decision['reason']}"
    )

    # ========================================================
    # 3. EXECUTE SELECTED MODEL
    # ========================================================

    print("\nMODEL EXECUTION")
    print("-" * 50)

    print(
        f"Running: {primary_model}"
    )

    print(
        f"Prompt size: "
        f"{len(request_text)} characters"
    )

    (
        stdout,
        stderr,
        return_code,
        wall_latency
    ) = execute_opencode_agent(
        primary_model,
        request_text
    )

    # ========================================================
    # 4. SAVE RAW EXECUTION
    # ========================================================

    raw_files = (
        save_raw_execution(
            task_type,
            strategy,
            stdout,
            stderr
        )
    )

    # ========================================================
    # 5. EXTRACT METRICS
    # ========================================================

    metrics = (
        parse_opencode_jsonl(
            stdout,
            primary_model
        )
    )

    metrics["latency_seconds"] = (
        round(
            wall_latency,
            2
        )
    )

    print(
        f"\nLLM Steps: "
        f"{metrics['llm_steps']}"
    )

    print(
        f"Task Cost: "
        f"${metrics['cost_usd']:.6f}"
    )

    print(
        f"Task Latency: "
        f"{metrics['latency_seconds']} seconds"
    )

    # ========================================================
    # 6. CHECK OPENCode EXECUTION
    # ========================================================

    if return_code != 0:

        execution_status = (
            "EXECUTION_ERROR"
        )

        print("\nEXECUTION ERROR")
        print("-" * 50)

        print(
            f"OpenCode exited with "
            f"return code {return_code}."
        )

        if stderr:

            print(
                stderr[-1500:]
            )

    elif detect_incomplete_prompt_response(
        stdout
    ):

        execution_status = (
            "INVALID_EXECUTION"
        )

        print("\nINVALID EXECUTION")
        print("-" * 50)

        print(
            "The model appears not to have "
            "received the complete task."
        )

        print(
            "Do not count this as a "
            "model-quality result."
        )

    else:

        execution_status = (
            "MODEL_EXECUTION_COMPLETE"
        )

    # ========================================================
    # 7. BUILD SUMMARY
    # ========================================================

    summary = {

        "task_file":
            path.name,

        "task_type":
            task_type,

        "strategy":
            strategy,

        "selected_model":
            primary_model,

        "configured_fallback":
            (
                fallback_model
                if strategy == "evidence"
                else None
            ),

        "automatic_fallback":
            False,

        "execution_status":
            execution_status,

        "return_code":
            return_code,

        "metrics":
            metrics,

        "raw_files":
            raw_files,

        "verification":
            "NOT_RUN"
    }

    # ========================================================
    # 8. DISPLAY RESULT
    # ========================================================

    print("\nRESULT SUMMARY")
    print("=" * 50)

    print(
        f"Task Type:       "
        f"{task_type}"
    )

    print(
        f"Strategy:        "
        f"{strategy}"
    )

    print(
        f"Selected Model:  "
        f"{primary_model}"
    )

    print(
        f"Execution:       "
        f"{execution_status}"
    )

    print(
        f"LLM Steps:       "
        f"{metrics['llm_steps']}"
    )

    print(
        f"Task Cost:       "
        f"${metrics['cost_usd']:.6f}"
    )

    print(
        f"Task Latency:    "
        f"{metrics['latency_seconds']:.2f} seconds"
    )

    print(
        "Verification:    NOT RUN"
    )

    print("=" * 50)

    if (
        execution_status
        == "MODEL_EXECUTION_COMPLETE"
    ):

        print(
            "\nModel execution completed."
        )

        print(
            "Now run the acceptance test "
            "manually to measure quality."
        )

    # ========================================================
    # 9. SAVE RESULT
    # ========================================================

    save_artifact(
        summary
    )

    return summary


# ============================================================
# SAVE SUMMARY
# ============================================================

def save_artifact(
    summary: dict
):

    task_type = (
        summary["task_type"]
    )

    out_dir = (
        ARTIFACTS_DIR
        / task_type
    )

    out_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    timestamp = (
        time.time_ns()
    )

    out_path = (
        out_dir
        / f"run_{timestamp}.json"
    )

    with open(
        out_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            summary,
            file,
            indent=2
        )

    print(
        f"\nArtifact saved to: "
        f"{out_path}"
    )


# ============================================================
# CLI
# ============================================================

def main():

    parser = (
        argparse.ArgumentParser(
            description=(
                "Lab 3 — Evidence-Driven "
                "Model Routing"
            )
        )
    )

    parser.add_argument(

        "task",

        help=(
            "Task file, for example: "
            "tasks/implementation.md"
        )
    )

    parser.add_argument(

        "--strategy",

        choices=[
            "evidence",
            "cheapest",
            "strongest"
        ],

        default="evidence",

        help=(
            "Routing strategy "
            "(default: evidence)"
        )
    )

    args = parser.parse_args()

    run_pipeline(
        args.task,
        strategy=args.strategy
    )


if __name__ == "__main__":

    main()