#!/usr/bin/env python3
"""
Lab 3 — Evidence-Driven Model Routing

Flow:
    Engineering Request
        -> Task Classifier
        -> Lab 2 Routing Policy
        -> Primary Model
        -> Deterministic Verification
        -> Fallback Model only when acceptance tests genuinely fail

There are no cheapest/strongest baseline strategies in this lab.
"""

import sys
import json
import time
import shutil
import argparse
import subprocess
from pathlib import Path

from router import TaskClassifier, RoutingPolicy


LAB3_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = LAB3_DIR.parent
SERVICE_ROOT = WORKSPACE_ROOT / "order_flow_service"
ARTIFACTS_DIR = LAB3_DIR / "artifacts"


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
# DETERMINISTIC VERIFICATION
# ============================================================

VERIFICATION_TESTS = {
    "implementation": "test_implementation.py",
    "refactoring": "test_refactoring.py",
    "debugging": "test_debugging.py",
    "testing": "test_testing.py",
}


def run_verification(task_type: str, timeout_seconds: int = 120) -> dict:
    """
    PASSED  -> acceptance tests passed
    FAILED  -> tests ran and assertions failed; fallback is allowed
    TIMEOUT -> verifier timed out; fallback is NOT allowed
    ERROR   -> verifier/collection/infrastructure problem; no fallback
    """

    test_name = VERIFICATION_TESTS.get(task_type)

    if not test_name:
        return {
            "status": "ERROR",
            "passed": False,
            "stdout": "",
            "stderr": f"No verification configured for: {task_type}",
            "exit_code": None,
        }

    test_file = LAB3_DIR / "instructor_tests" / test_name

    if not test_file.exists():
        return {
            "status": "ERROR",
            "passed": False,
            "stdout": "",
            "stderr": f"Verification test not found: {test_file}",
            "exit_code": None,
        }

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-v",
        "--tb=short",
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(SERVICE_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")

        return {
            "status": "TIMEOUT",
            "passed": False,
            "stdout": stdout,
            "stderr": stderr or f"pytest timed out after {timeout_seconds}s",
            "exit_code": None,
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "passed": False,
            "stdout": "",
            "stderr": str(exc),
            "exit_code": None,
        }

    if proc.returncode == 0:
        status = "PASSED"
    elif proc.returncode == 1:
        status = "FAILED"
    else:
        status = "ERROR"

    return {
        "status": status,
        "passed": status == "PASSED",
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "exit_code": proc.returncode,
    }


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_pipeline(task_path: str) -> dict:

    path = Path(task_path)

    if not path.is_absolute():
        path = LAB3_DIR / task_path

    if not path.exists():
        raise FileNotFoundError(f"Task file not found: {path}")

    if not SERVICE_ROOT.exists():
        raise FileNotFoundError(
            f"Service repository not found: {SERVICE_ROOT}"
        )

    request_text = path.read_text(encoding="utf-8")

    if not request_text.strip():
        raise ValueError("Task file is empty.")

    print("\nINCOMING TASK")
    print("-" * 50)
    preview = request_text.strip()[:300]
    print(preview + ("..." if len(request_text) > 300 else ""))

    # 1. Classify every incoming request.
    print("\nCLASSIFICATION")
    print("-" * 50)

    task_type = TaskClassifier.classify_request(request_text)
    print(f"Task Type: {task_type}")

    # 2. Apply the Lab 2 evidence policy.
    policy = RoutingPolicy()
    decision = policy.select_model(task_type)

    primary_model = decision["primary"]
    fallback_model = decision["fallback"]
    max_attempts = min(decision.get("max_attempts", 2), 2)

    print("\nEVIDENCE-BASED ROUTING")
    print("-" * 50)
    print(f"Primary Model:  {primary_model}")
    print(f"Fallback Model: {fallback_model}")
    print(f"Max Attempts:   {max_attempts}")
    print(f"Reason:         {decision['reason']}")

    attempts_detail = []
    total_cost = 0.0
    total_latency = 0.0
    escalated = False
    final_status = "NOT_RUN"
    final_model = primary_model

    current_model = primary_model
    prompt_to_run = request_text

    for attempt_num in range(1, max_attempts + 1):

        print(
            f"\nMODEL EXECUTION "
            f"(Attempt {attempt_num}/{max_attempts})"
        )
        print("-" * 50)
        print(f"Running: {current_model}")

        stdout, stderr, return_code, wall_latency = (
            execute_opencode_agent(
                current_model,
                prompt_to_run
            )
        )

        raw_files = save_raw_execution(
            task_type,
            "evidence",
            stdout,
            stderr
        )

        metrics = parse_opencode_jsonl(
            stdout,
            current_model
        )
        metrics["latency_seconds"] = round(wall_latency, 2)

        total_cost += metrics["cost_usd"]
        total_latency += metrics["latency_seconds"]

        print(
            f"Steps: {metrics['llm_steps']} | "
            f"Latency: {metrics['latency_seconds']}s | "
            f"Cost: ${metrics['cost_usd']:.6f}"
        )

        if return_code != 0:
            attempts_detail.append({
                "attempt": attempt_num,
                "model": current_model,
                "execution_status": "ERROR",
                "return_code": return_code,
                "metrics": metrics,
                "raw_files": raw_files,
                "verification": None,
            })
            final_model = current_model
            final_status = "EXECUTION_ERROR"
            break

        if detect_incomplete_prompt_response(stdout):
            attempts_detail.append({
                "attempt": attempt_num,
                "model": current_model,
                "execution_status": "INVALID_PROMPT",
                "return_code": return_code,
                "metrics": metrics,
                "raw_files": raw_files,
                "verification": None,
            })
            final_model = current_model
            final_status = "INVALID_EXECUTION"
            break

        # 3. Deterministic quality gate.
        print("\nVERIFICATION")
        print("-" * 50)

        verify_result = run_verification(task_type)
        verification_status = verify_result["status"]

        print(f"Acceptance Tests: {verification_status}")

        attempts_detail.append({
            "attempt": attempt_num,
            "model": current_model,
            "execution_status": "SUCCESS",
            "return_code": return_code,
            "metrics": metrics,
            "raw_files": raw_files,
            "verification": verify_result,
        })

        final_model = current_model

        if verification_status == "PASSED":
            final_status = "PASS"
            break

        # Verifier failure is not model failure.
        if verification_status in {"TIMEOUT", "ERROR"}:
            print(
                "\nVerification could not complete correctly. "
                "Fallback will NOT be triggered."
            )
            final_status = "VERIFICATION_ERROR"
            break

        # 4. Only a genuine acceptance-test failure can escalate.
        can_escalate = (
            verification_status == "FAILED"
            and attempt_num < max_attempts
            and fallback_model
            and current_model != fallback_model
        )

        if not can_escalate:
            final_status = "FAIL"
            break

        escalated = True

        print("\nESCALATION")
        print("-" * 50)
        print(f"{current_model} did not meet the quality bar.")
        print(f"Escalating to: {fallback_model}")

        failure_text = (
            verify_result.get("stdout")
            or verify_result.get("stderr")
            or "Acceptance tests failed."
        )

        failure_snippet = failure_text[-1500:]
        current_model = fallback_model

        prompt_to_run = (
            f"{request_text}\n\n"
            "### ESCALATION CONTEXT\n\n"
            "A previous model attempted this task, but deterministic "
            "acceptance tests failed.\n\n"
            "Verification failure:\n\n"
            f"```text\n{failure_snippet}\n```\n\n"
            "Inspect the CURRENT repository state.\n"
            "Do not start from scratch.\n"
            "Repair the implementation so the original requirement "
            "and acceptance tests are satisfied.\n"
        )

    summary = {
        "task_file": path.name,
        "task_type": task_type,
        "routing": "evidence",
        "primary_model": primary_model,
        "fallback_model": fallback_model,
        "attempts": len(attempts_detail),
        "escalated": escalated,
        "final_model": final_model,
        "final_status": final_status,
        "total_cost_usd": round(total_cost, 6),
        "total_latency_seconds": round(total_latency, 2),
        "attempts_detail": attempts_detail,
    }

    print("\nRESULT SUMMARY")
    print("=" * 50)
    print(f"Task Type:       {task_type}")
    print(f"Primary Model:   {primary_model}")
    print(f"Fallback Model:  {fallback_model}")
    print(f"Attempts:        {summary['attempts']}")
    print(f"Escalated:       {'YES' if escalated else 'NO'}")
    print(f"Final Model:     {final_model}")
    print(f"Final Status:    {final_status}")
    print(f"Total Cost:      ${total_cost:.6f}")
    print(f"Total Latency:   {total_latency:.2f} seconds")
    print("=" * 50)

    save_artifact(summary)
    return summary


# ============================================================
# SAVE SUMMARY
# ============================================================

def save_artifact(summary: dict):

    out_dir = ARTIFACTS_DIR / summary["task_type"]
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"run_{time.time_ns()}.json"

    with open(out_path, "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print(f"\nArtifact saved to: {out_path}")


# ============================================================
# CLI
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Lab 3 — Evidence-Driven Model Routing"
    )

    parser.add_argument(
        "task",
        help="Engineering request file, e.g. tasks/request_01.md"
    )

    args = parser.parse_args()
    run_pipeline(args.task)


if __name__ == "__main__":
    main()
