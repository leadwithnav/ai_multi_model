#!/usr/bin/env python3
"""
Lab 7 - Vertical Tiering Runner

Demonstrates intra-vendor scaling across capability tiers within the same vendor family:
    FAST / ENTRY (Luna / Terra)  -->  MID TIER (Terra)  -->  HIGH TIER (Sol)

Question answered:
    "Need more capability or reasoning?" -> Move vertically within vendor family.

Features:
    Baselines and resets working directory before each model run so every tier operates on a fresh repo.

Usage:
    python run_vertical.py task/request_01.md
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path


# ============================================================
# PATHS & CONFIGURATION
# ============================================================

LAB_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = LAB_DIR.parent
SERVICE_ROOT = WORKSPACE_ROOT / "order_flow_service"
RUNS_DIR = LAB_DIR / "runs"

# Vertical Tier Progression for Vendor A (OpenAI / Bedrock)
VERTICAL_TIERS = [
    {"tier": "FAST", "agent": "terra", "vendor": "OpenAI/Bedrock", "model": "GPT-5.6 Terra"},
    {"tier": "HIGH", "agent": "sol", "vendor": "OpenAI/Bedrock", "model": "GPT-5.6 Sol"}
]


def opencode_binary():
    return "opencode.cmd" if os.name == "nt" else "opencode"


def reset_repository():
    """
    Baselines and resets working directory using git restore and git clean directly.
    Ensures every model run starts on a clean, un-mutated target repository.
    Works reliably on Windows, macOS, and Linux without depending on bash executable.
    """
    print("--> Baselining & resetting working directory (order_flow_service)...")
    res1 = subprocess.run(
        ["git", "restore", "--source=HEAD", "--staged", "--worktree", "order_flow_service/"],
        capture_output=True,
        text=True,
        cwd=WORKSPACE_ROOT
    )
    res2 = subprocess.run(
        ["git", "clean", "-fd", "order_flow_service/"],
        capture_output=True,
        text=True,
        cwd=WORKSPACE_ROOT
    )
    if res1.returncode != 0 or res2.returncode != 0:
        print(f"Reset warning: restore exit code {res1.returncode}, clean exit code {res2.returncode}")


def run_opencode_agent(agent_name: str, prompt_text: str, output_jsonl: Path):
    """
    Executes selected agent via OpenCode subprocess and streams JSONL output.
    Prompt text is normalized to a single string to avoid Windows shell newline truncation.
    """
    clean_prompt = " ".join(prompt_text.split())

    cmd = [
        opencode_binary(),
        "run",
        "--agent", agent_name,
        "--format", "json",
        clean_prompt
    ]

    print(f"--> Executing Agent: {agent_name} [{cmd[0]}]...")
    start_time = time.time()

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_jsonl, "w", encoding="utf-8") as out_f:
        process = subprocess.Popen(
            cmd,
            stdout=out_f,
            stderr=subprocess.PIPE,
            cwd= SERVICE_ROOT, 
            text=True
        )
        _, stderr = process.communicate()

    elapsed = time.time() - start_time
    if process.returncode != 0:
        print(f"Warning: OpenCode finished with exit code {process.returncode}")
        if stderr:
            print(f"Error output: {stderr[:300]}")

    return elapsed


def run_acceptance_tests():
    """
    Runs deterministic pytest evaluation for Lab 7 task.
    """
    test_file = LAB_DIR / "hidden_eval" / "test_request_01.py"
    if not test_file.exists():
        return {"status": "UNKNOWN", "details": "Test file not found"}

    cmd = ["pytest", str(test_file), "-v"]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=LAB_DIR)
    passed = (res.returncode == 0)
    return {"status": "PASS" if passed else "FAIL", "output": res.stdout}


def main():
    task_file_arg = sys.argv[1] if len(sys.argv) > 1 else "task/request_01.md"
    task_path = LAB_DIR / task_file_arg if not Path(task_file_arg).is_absolute() else Path(task_file_arg)

    if not task_path.exists():
        print(f"Error: Task file not found: {task_path}")
        sys.exit(1)

    prompt_text = task_path.read_text(encoding="utf-8")

    print("=" * 60)
    print("LAB 7 — VERTICAL TIERING EXECUTION PIPELINE")
    print("=" * 60)
    print(f"Task File       : {task_path}")
    print("Direction       : Vertical (Intra-Vendor Scaling)")
    print("Tier Chain      : Luna -> Terra -> Sol")
    print("=" * 60)

    summary_results = []

    for item in VERTICAL_TIERS:
        tier_name = item["tier"]
        agent_name = item["agent"]
        model_name = item["model"]
        jsonl_path = RUNS_DIR / f"vertical_{agent_name}.jsonl"

        # Reset repo BEFORE executing each tier agent
        reset_repository()

        print(f"\n--- Vertical Step: [{tier_name} TIER] -> Agent: '{agent_name}' ({model_name}) ---")
        elapsed = run_opencode_agent(agent_name, prompt_text, jsonl_path)
        test_res = run_acceptance_tests()

        print(f"Latency       : {elapsed:.2f}s")
        print(f"Test Status   : {test_res['status']}")

        summary_results.append({
            "tier": tier_name,
            "agent": agent_name,
            "model": model_name,
            "latency": round(elapsed, 2),
            "test_status": test_res['status'],
            "jsonl": str(jsonl_path)
        })

    # Reset working directory at the end of vertical pipeline
    reset_repository()

    # Save final aggregate vertical run file
    combined_jsonl = RUNS_DIR / "vertical_run.jsonl"
    if summary_results:
        primary_jsonl = RUNS_DIR / f"vertical_{summary_results[-1]['agent']}.jsonl"
        if primary_jsonl.exists():
            combined_jsonl.write_bytes(primary_jsonl.read_bytes())

    print("\n" + "=" * 60)
    print("VERTICAL TIERING SUMMARY")
    print("=" * 60)
    for res in summary_results:
        print(f"Tier: {res['tier']:<6} | Model: {res['model']:<16} | Time: {res['latency']}s | Status: {res['test_status']}")
    print(f"\nSaved metrics source to: {combined_jsonl}")


if __name__ == "__main__":
    main()
