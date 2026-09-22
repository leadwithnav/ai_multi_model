"""
Lab 3 Main Entrypoint — Evidence-Driven Router Runner

Usage:
    python run_router.py tasks/debugging.md
    python run_router.py tasks/implementation.md --strategy evidence
    python run_router.py tasks/refactoring.md --strategy cheapest
    python run_router.py tasks/testing.md --strategy strongest
"""

import sys
import os
import json
import time
import shutil
import argparse
import subprocess
from pathlib import Path

from router import TaskClassifier, RoutingPolicy
from verify import run_verification

LAB3_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = LAB3_DIR.parent
ARTIFACTS_DIR = LAB3_DIR / "artifacts"


def parse_opencode_jsonl(raw_jsonl_str: str, agent_name: str) -> dict:
    """Parses JSONL output from opencode run --format json to extract metrics."""
    llm_steps = 0
    direct_input_tokens = 0
    cache_read_tokens = 0
    cache_write_tokens = 0
    output_tokens = 0
    reasoning_tokens = 0
    total_cost = 0.0

    first_timestamp = None
    last_timestamp = None

    for line in raw_jsonl_str.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        timestamp = event.get("timestamp")
        if isinstance(timestamp, (int, float)):
            if first_timestamp is None:
                first_timestamp = timestamp
            last_timestamp = timestamp

        if event.get("type") != "step_finish":
            continue

        llm_steps += 1
        part = event.get("part", {}) or {}
        tokens = part.get("tokens", {}) or {}
        cache = tokens.get("cache", {}) or {}

        direct_input_tokens += tokens.get("input", 0) or 0
        output_tokens += tokens.get("output", 0) or 0
        reasoning_tokens += tokens.get("reasoning", 0) or 0

        cache_read_tokens += cache.get("read", 0) or 0
        cache_write_tokens += cache.get("write", 0) or 0

        total_cost += part.get("cost", 0.0) or 0.0

    if first_timestamp is not None and last_timestamp is not None:
        latency_seconds = (last_timestamp - first_timestamp) / 1000.0
    else:
        latency_seconds = 0.0

    return {
        "agent": agent_name,
        "llm_steps": llm_steps,
        "tokens": {
            "direct_input": direct_input_tokens,
            "cache_read": cache_read_tokens,
            "cache_write": cache_write_tokens,
            "output": output_tokens,
            "reasoning": reasoning_tokens
        },
        "latency_seconds": round(latency_seconds, 2),
        "cost_usd": round(total_cost, 6)
    }


def execute_opencode_agent(agent: str, prompt: str) -> tuple[str, str]:
    """Executes opencode run --agent <agent> --format json "<prompt>"."""
    # Find opencode executable (opencode / opencode.cmd)
    opencode_bin = shutil.which("opencode") or shutil.which("opencode.cmd") or "opencode"

    cmd = [
        opencode_bin,
        "run",
        "--agent", agent,
        "--format", "json",
        prompt
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            timeout=300
        )
        return proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return "", "OpenCode execution timed out"
    except Exception as e:
        return "", str(e)


def run_pipeline(task_path: str, strategy: str = "evidence") -> dict:
    path = Path(task_path)
    if not path.is_absolute():
        path = LAB3_DIR / task_path

    if not path.exists():
        print(f"Error: Task file not found: {path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        request_text = f.read()

    print("\nIncoming Task")
    print("-" * 50)
    print(request_text.strip()[:200] + ("..." if len(request_text) > 200 else ""))

    # 1. Classification
    task_type = TaskClassifier.classify_request(request_text)
    print("\nCLASSIFICATION")
    print("-" * 50)
    print(f"Task Type: {task_type}")

    # 2. Routing Decision
    policy = RoutingPolicy()
    decision = policy.select_model(task_type, strategy=strategy)
    primary_model = decision["primary"]
    fallback_model = decision["fallback"]
    max_attempts = decision["max_attempts"]

    print("\nROUTING DECISION")
    print("-" * 50)
    print(f"Strategy: {strategy}")
    print(f"Primary Model: {primary_model}")
    print(f"Fallback Model: {fallback_model}")
    print(f"Reason: {decision['reason']}")

    attempts_detail = []
    total_cost = 0.0
    total_latency = 0.0
    final_status = "FAIL"
    escalated = False

    # 3. Attempt 1 (Primary Model)
    current_model = primary_model
    prompt_to_run = request_text

    for attempt_num in range(1, max_attempts + 1):
        print(f"\nEXECUTION (Attempt {attempt_num}/{max_attempts})")
        print("-" * 50)
        print(f"Running {current_model}...")

        start_time = time.time()
        stdout, stderr = execute_opencode_agent(current_model, prompt_to_run)
        wall_latency = time.time() - start_time

        metrics = parse_opencode_jsonl(stdout, current_model)
        if metrics["latency_seconds"] == 0.0:
            metrics["latency_seconds"] = round(wall_latency, 2)

        print(f"Steps: {metrics['llm_steps']} | Latency: {metrics['latency_seconds']}s | Cost: ${metrics['cost_usd']:.6f}")

        # Deterministic Verification
        print("\nVERIFICATION")
        print("-" * 50)
        verify_result = run_verification(task_type)
        ver_status = "PASSED" if verify_result["passed"] else "FAILED"
        print(f"Acceptance Tests: {ver_status}")

        attempt_info = {
            "attempt": attempt_num,
            "model": current_model,
            "metrics": metrics,
            "verification": verify_result
        }
        attempts_detail.append(attempt_info)

        total_cost += metrics["cost_usd"]
        total_latency += metrics["latency_seconds"]

        if verify_result["passed"]:
            final_status = "PASS"
            break

        # Verification failed — prepare escalation for attempt 2 if possible
        if attempt_num < max_attempts and primary_model != fallback_model:
            escalated = True
            print("\nESCALATION")
            print("-" * 50)
            print(f"Primary model ({primary_model}) failed deterministic verification.")
            print(f"Escalating to fallback model: {fallback_model}")

            current_model = fallback_model
            failure_snippet = verify_result["stdout"][-500:] if verify_result["stdout"] else verify_result["stderr"][-500:]
            prompt_to_run = (
                f"{request_text}\n\n"
                f"### ESCALATION CONTEXT\n"
                f"Previous attempt did not satisfy acceptance tests.\n\n"
                f"Verification failure output:\n"
                f"```text\n{failure_snippet}\n```\n\n"
                f"Inspect current repository state and fix the implementation so all acceptance tests pass."
            )
        else:
            final_status = "FAIL"

    # Summary Result
    summary = {
        "task_file": str(path.name),
        "task_type": task_type,
        "strategy": strategy,
        "primary_model": primary_model,
        "fallback_model": fallback_model,
        "attempts": len(attempts_detail),
        "escalated": escalated,
        "final_model": current_model,
        "final_status": final_status,
        "total_cost_usd": round(total_cost, 6),
        "total_latency_seconds": round(total_latency, 2),
        "attempts_detail": attempts_detail
    }

    print("\nRESULT SUMMARY")
    print("=" * 50)
    print(f"Task Type:       {task_type}")
    print(f"Primary Model:   {primary_model}")
    print(f"Fallback Model:  {fallback_model}")
    print(f"Attempts:        {summary['attempts']}")
    print(f"Escalated:       {'YES' if escalated else 'NO'}")
    print(f"Final Status:    {final_status}")
    print(f"Total Cost:      ${total_cost:.6f}")
    print(f"Total Latency:   {total_latency:.2f} seconds")
    print("=" * 50 + "\n")

    # Save artifact
    save_artifact(summary)
    return summary


def save_artifact(summary: dict):
    task_type = summary["task_type"]
    out_dir = ARTIFACTS_DIR / task_type
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    out_path = out_dir / f"run_{timestamp}.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Artifact saved to: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Lab 3 Evidence-Driven Router")
    parser.add_argument("task", help="Path to task file (e.g. tasks/debugging.md)")
    parser.add_argument(
        "--strategy",
        choices=["evidence", "cheapest", "strongest"],
        default="evidence",
        help="Routing strategy to evaluate (default: evidence)"
    )

    args = parser.parse_args()
    run_pipeline(args.task, strategy=args.strategy)


if __name__ == "__main__":
    main()
