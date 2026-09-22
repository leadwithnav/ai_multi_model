"""
Lab 3 Strategy Comparison Runner

Compares three routing strategies across all 4 engineering tasks:
1. Strategy A — Cheapest Model Everywhere (claude-3-5-haiku)
2. Strategy B — Strongest Model Everywhere (claude-3-opus)
3. Strategy C — Evidence-Driven Routing (routing_policy.yaml)
"""

import os
import sys
import subprocess
from pathlib import Path

from run_router import run_pipeline

LAB3_DIR = Path(__file__).resolve().parent

TASKS = [
    "tasks/implementation.md",
    "tasks/refactoring.md",
    "tasks/debugging.md",
    "tasks/testing.md"
]

STRATEGIES = [
    ("Cheapest Everywhere", "cheapest"),
    ("Strongest Everywhere", "strongest"),
    ("Evidence-Driven Routing", "evidence")
]


def reset_repository():
    reset_script = LAB3_DIR / "reset.sh"
    if reset_script.exists():
        subprocess.run(["bash", str(reset_script)], cwd=str(LAB3_DIR), capture_output=True)


def run_comparison():
    results = []

    for label, strategy_code in STRATEGIES:
        print("\n" + "=" * 60)
        print(f"RUNNING STRATEGY: {label}")
        print("=" * 60)

        successful_tasks = 0
        total_cost = 0.0
        total_latency = 0.0
        total_escalations = 0

        for task_file in TASKS:
            reset_repository()
            try:
                res = run_pipeline(task_file, strategy=strategy_code)
                if res["final_status"] == "PASS":
                    successful_tasks += 1
                total_cost += res["total_cost_usd"]
                total_latency += res["total_latency_seconds"]
                if res.get("escalated"):
                    total_escalations += 1
            except Exception as e:
                print(f"Error running {task_file} under {label}: {e}")

        reset_repository()

        cost_per_success = (total_cost / successful_tasks) if successful_tasks > 0 else 0.0

        results.append({
            "label": label,
            "successes": f"{successful_tasks}/4",
            "total_cost": f"${total_cost:.4f}",
            "cost_per_success": f"${cost_per_success:.4f}",
            "total_latency": f"{total_latency:.1f}s",
            "escalations": total_escalations
        })

    # Print Final Comparison Table
    print("\n\n" + "=" * 75)
    print("FINAL STRATEGY COMPARISON TABLE")
    print("=" * 75)
    print(f"| {'Strategy':<25} | {'Successful Tasks':<16} | {'Total Cost':<10} | {'Cost / Success':<14} | {'Total Latency':<13} | {'Escalations':<11} |")
    print("|" + "-" * 27 + "|" + "-" * 18 + "|" + "-" * 12 + "|" + "-" * 16 + "|" + "-" * 15 + "|" + "-" * 13 + "|")

    for r in results:
        print(f"| {r['label']:<25} | {r['successes']:^16} | {r['total_cost']:>10} | {r['cost_per_success']:>14} | {r['total_latency']:>13} | {r['escalations']:^11} |")

    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_comparison()
