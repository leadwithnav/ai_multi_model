"""Lab 1 Quality + Cost + Latency Multi-Model Benchmark Harness.

Executes the rate limiter implementation task against 6 specified Amazon Bedrock models:
- Claude 3.5 Sonnet
- Claude 3.5 Haiku
- Claude 3 Opus
- GPT-5.6 Luna (Fast & Cost Efficient)
- GPT-5.6 Terra (Balanced for Production)
- GPT-5.6 Sol (High Reasoning & Agentic)

Resets the repository between runs, executes Pytest acceptance tests,
measures wall-clock latency & cost, and outputs structured benchmark results.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LAB_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = (LAB_DIR / ".." / "order-flow-service").resolve()
TASK_PATH = LAB_DIR / "benchmark" / "TASK.md"
ARTIFACTS_DIR = LAB_DIR / "artifacts"
RAW_DIR = ARTIFACTS_DIR / "raw"
RESULTS_DIR = ARTIFACTS_DIR / "results"

MODELS = [
    {
        "agent": "claude-3-5-sonnet",
        "name": "Claude 3.5 Sonnet",
        "vendor": "anthropic",
        "model_id": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        "input_usd_per_million": 3.00,
        "output_usd_per_million": 15.00,
    },
    {
        "agent": "claude-3-5-haiku",
        "name": "Claude 3.5 Haiku",
        "vendor": "anthropic",
        "model_id": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "input_usd_per_million": 1.00,
        "output_usd_per_million": 5.00,
    },
    {
        "agent": "claude-3-opus",
        "name": "Claude 3 Opus",
        "vendor": "anthropic",
        "model_id": "us.anthropic.claude-3-opus-20240229-v1:0",
        "input_usd_per_million": 15.00,
        "output_usd_per_million": 75.00,
    },
    {
        "agent": "gpt-5-6-luna",
        "name": "GPT-5.6 Luna (Fast & Efficient)",
        "vendor": "openai",
        "model_id": "us.openai.gpt-5.6-luna",
        "input_usd_per_million": 0.25,
        "output_usd_per_million": 1.25,
    },
    {
        "agent": "gpt-5-6-terra",
        "name": "GPT-5.6 Terra (Balanced Production)",
        "vendor": "openai",
        "model_id": "us.openai.gpt-5.6-terra",
        "input_usd_per_million": 1.00,
        "output_usd_per_million": 5.00,
    },
    {
        "agent": "gpt-5-6-sol",
        "name": "GPT-5.6 Sol (High Reasoning)",
        "vendor": "openai",
        "model_id": "us.openai.gpt-5.6-sol",
        "input_usd_per_million": 3.00,
        "output_usd_per_million": 15.00,
    },
]

APPROX_CHARS_PER_TOKEN = 4

def reset_repository() -> None:
    if sys.platform == "win32":
        reset_script = LAB_DIR / "reset.ps1"
        if reset_script.exists():
            subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(reset_script)], check=True)
            return
    else:
        reset_script = LAB_DIR / "reset.sh"
        if reset_script.exists():
            subprocess.run(["bash", str(reset_script)], check=True)
            return

    # Fallback git reset
    if (REPO_DIR / ".git").exists():
        subprocess.run(["git", "reset", "--hard", "HEAD"], cwd=REPO_DIR, check=True)
        subprocess.run(["git", "clean", "-fd"], cwd=REPO_DIR, check=True)

def approx_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + APPROX_CHARS_PER_TOKEN - 1) // APPROX_CHARS_PER_TOKEN)

def run_acceptance_tests() -> dict[str, Any]:
    """Runs pytest in order-flow-service and measures test pass/fail quality."""
    cmd = [sys.executable, "-m", "pytest", "-q", "tests/"]
    try:
        proc = subprocess.run(cmd, cwd=REPO_DIR, capture_output=True, text=True, timeout=60)
        output = proc.stdout + "\n" + proc.stderr
        
        passed_match = re.search(r"(\d+)\s+passed", output)
        failed_match = re.search(r"(\d+)\s+failed", output)
        
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        total = passed + failed
        
        pass_rate = round((passed / total) * 100, 1) if total > 0 else 0.0
        quality_bar_met = (failed == 0 and passed > 0)
        
        return {
            "total_tests": total,
            "tests_passed": passed,
            "tests_failed": failed,
            "pass_rate_pct": pass_rate,
            "quality_bar_met": quality_bar_met,
            "pytest_returncode": proc.returncode,
            "raw_test_output": output.strip()
        }
    except Exception as e:
        return {
            "total_tests": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "pass_rate_pct": 0.0,
            "quality_bar_met": False,
            "pytest_returncode": -1,
            "raw_test_output": f"Error running pytest: {e}"
        }

def run_benchmark_for_model(model: dict[str, Any], task_text: str, timeout_seconds: int) -> dict[str, Any]:
    agent = model["agent"]
    print(f"\n[BENCHMARK] Resetting repository state for {agent} ({model['name']})...")
    reset_repository()

    print(f"[BENCHMARK] Executing task with agent '{agent}'...")
    start_time = time.perf_counter()
    
    try:
        proc = subprocess.run(
            ["opencode", "run", "--agent", agent, task_text],
            cwd=LAB_DIR,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=os.environ.copy()
        )
        latency_seconds = round(time.perf_counter() - start_time, 2)
        raw_output = proc.stdout.strip() or proc.stderr.strip()
        timed_out = False
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        latency_seconds = round(time.perf_counter() - start_time, 2)
        raw_output = "Task timed out during execution."
        timed_out = True
        returncode = -1

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{agent}_output.txt"
    raw_path.write_text(raw_output, encoding="utf-8")

    print(f"[BENCHMARK] Model execution completed in {latency_seconds}s. Running acceptance tests...")
    test_results = run_acceptance_tests()

    input_tokens = approx_tokens(task_text)
    output_tokens = approx_tokens(raw_output)
    est_cost = (
        (input_tokens / 1_000_000) * model["input_usd_per_million"] +
        (output_tokens / 1_000_000) * model["output_usd_per_million"]
    )
    est_cost = round(est_cost, 6)

    print(f"  -> Quality  : {test_results['tests_passed']}/{test_results['total_tests']} tests passed ({test_results['pass_rate_pct']}%)")
    print(f"  -> Latency  : {latency_seconds} seconds")
    print(f"  -> Est Cost : ${est_cost:.6f} USD")

    return {
        "agent": agent,
        "name": model["name"],
        "vendor": model["vendor"],
        "model_id": model["model_id"],
        "timed_out": timed_out,
        "returncode": returncode,
        "latency_seconds": latency_seconds,
        "quality": test_results,
        "input_tokens_approx": input_tokens,
        "output_tokens_approx": output_tokens,
        "estimated_cost_usd": est_cost,
        "raw_output_file": f"artifacts/raw/{agent}_output.txt"
    }

def write_results(results: list[dict[str, Any]], run_id: str | None = None) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = f"_{run_id}" if run_id else ""
    
    json_path = RESULTS_DIR / f"benchmark_results{suffix}.json"
    csv_path = RESULTS_DIR / f"benchmark_results{suffix}.csv"

    passing_models = [m for m in results if m["quality"]["quality_bar_met"]]
    fastest_model = min(results, key=lambda x: x["latency_seconds"])["agent"] if results else None
    cheapest_passing = min(passing_models, key=lambda x: x["estimated_cost_usd"])["agent"] if passing_models else None

    summary = {
        "lab": "Lab 1 — Quality + Cost + Latency Multi-Model Benchmark",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "models_benchmarked": len(results),
        "models_passing_quality_bar": len(passing_models),
        "fastest_model": fastest_model,
        "lowest_cost_passing_model": cheapest_passing,
        "quality_bar_definition": "All Pytest acceptance tests pass (100% pass rate)"
    }

    full_payload = {
        "summary": summary,
        "results": results
    }

    json_path.write_text(json.dumps(full_payload, indent=2), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Agent", "Model Name", "Quality (Pass Rate %)", "Tests Passed", "Latency (s)", "Est Cost (USD)", "Quality Bar Met"])
        for r in results:
            writer.writerow([
                r["agent"],
                r["name"],
                f"{r['quality']['pass_rate_pct']}%",
                f"{r['quality']['tests_passed']}/{r['quality']['total_tests']}",
                r["latency_seconds"],
                f"${r['estimated_cost_usd']:.6f}",
                "YES" if r["quality"]["quality_bar_met"] else "NO"
            ])

    return json_path, csv_path

def main() -> None:
    parser = argparse.ArgumentParser(description="Lab 1 Quality + Cost + Latency Multi-Model Benchmark Harness")
    parser.add_argument("--run-id", help="Optional run identifier (e.g. run1)")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    args = parser.parse_args()

    if not TASK_PATH.exists():
        print(f"Error: Task prompt missing at {TASK_PATH}")
        sys.exit(1)

    task_text = TASK_PATH.read_text(encoding="utf-8")
    
    print("=================================================================")
    print("   LAB 1 — MULTI-MODEL BENCHMARK: QUALITY + COST + LATENCY      ")
    print("=================================================================")

    benchmark_results = []
    for model in MODELS:
        res = run_benchmark_for_model(model, task_text, args.timeout_seconds)
        benchmark_results.append(res)

    json_path, csv_path = write_results(benchmark_results, args.run_id)

    print("\n=================================================================")
    print("                      BENCHMARK SUMMARY                          ")
    print("=================================================================")
    print(f"Results JSON : {json_path.relative_to(LAB_DIR)}")
    print(f"Results CSV  : {csv_path.relative_to(LAB_DIR)}\n")

    for r in benchmark_results:
        q_status = "PASS" if r['quality']['quality_bar_met'] else "FAIL"
        print(f"  • {r['name']:<35} | Quality: [{q_status}] ({r['quality']['tests_passed']}/{r['quality']['total_tests']}) | Latency: {r['latency_seconds']}s | Cost: ${r['estimated_cost_usd']:.6f}")

if __name__ == "__main__":
    main()
