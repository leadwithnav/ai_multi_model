#!/usr/bin/env python3
"""
Lab 3 — Agent Task Execution & Metrics Runner (run_agent.py)

Automates:
1. Pre-run workspace baseline reset & cleanup
2. Agent execution via OpenCode against specified task
3. Metrics measurement (metrics_helper.py / measure_metrics.py)
(Leaves code changes intact for manual acceptance testing)

Usage:
    python run_agent.py --agent claude-3-5-sonnet --task tasks/request_01.md
    python run_agent.py --agent claude-3-5-haiku --task tasks/request_02.md
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def get_opencode_binary():
    """Returns the appropriate opencode binary command based on OS."""
    return "opencode.cmd" if os.name == "nt" else "opencode"


def reset_repository(workspace_root: Path):
    """Resets order_flow_service directory back to git HEAD state and cleans cache."""
    service_dir = workspace_root / "order_flow_service"
    
    # 1. Run bash reset.sh if present in workspace or lab directory
    reset_sh = workspace_root / "reset.sh"
    if reset_sh.exists():
        subprocess.run(["bash", str(reset_sh)], capture_output=True, cwd=workspace_root)
    else:
        # Fallback to git restore and clean
        subprocess.run(
            ["git", "restore", "--source=HEAD", "--staged", "--worktree", "order_flow_service/"],
            capture_output=True, cwd=workspace_root
        )
        subprocess.run(
            ["git", "clean", "-fd", "order_flow_service/"],
            capture_output=True, cwd=workspace_root
        )

    # 2. Remove .pytest_cache if present
    pytest_cache = service_dir / ".pytest_cache"
    if pytest_cache.exists():
        shutil.rmtree(pytest_cache, ignore_errors=True)


def run_experiment(agent_name: str, task_path: Path):
    # Resolve directories
    task_file = task_path.resolve()
    if not task_file.exists():
        print(f"Error: Task file not found: {task_file}")
        sys.exit(1)

    # Infer Lab Directory (parent of tasks/ directory)
    lab_dir = task_file.parent.parent if task_file.parent.name in ["task", "tasks"] else task_file.parent
    workspace_root = lab_dir.parent
    service_root = workspace_root / "order_flow_service"
    runs_dir = lab_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize JSONL log file name (e.g. claude-3-5-sonnet -> sonnet.jsonl or agent_name.jsonl)
    short_agent_name = agent_name.replace("claude-3-5-", "").replace("claude-", "")
    output_jsonl = runs_dir / f"{short_agent_name}.jsonl"

    # ------------------------------------------------------------
    # STEP 1: INITIAL CLEANUP & RESET BASELINE BEFORE RUN
    # ------------------------------------------------------------
    reset_repository(workspace_root)

    # Sync lab agents if .opencode/agent exists in lab_dir
    lab_agents = lab_dir / ".opencode" / "agent"
    service_agents = service_root / ".opencode" / "agent"
    if lab_agents.exists():
        service_agents.mkdir(parents=True, exist_ok=True)
        for item in lab_agents.glob("*.md"):
            shutil.copy2(item, service_agents / item.name)

    # ------------------------------------------------------------
    # STEP 2: RUN TASK AGAINST AGENT VIA OPENCODE
    # ------------------------------------------------------------
    task_content = task_file.read_text(encoding="utf-8")
    clean_prompt = " ".join(task_content.split())

    cmd = [
        get_opencode_binary(),
        "run",
        "--agent", agent_name,
        "--format", "json",
        clean_prompt
    ]

    print(f"--> Executing Agent [{agent_name}] on {task_file.name}...")
    with open(output_jsonl, "w", encoding="utf-8") as out_f:
        proc = subprocess.Popen(
            cmd,
            stdout=out_f,
            stderr=subprocess.PIPE,
            cwd=service_root,
            text=True
        )
        _, stderr = proc.communicate()

    if proc.returncode != 0 and stderr:
        print(f"OpenCode Notice (Exit {proc.returncode}): {stderr[:200]}")

    # ------------------------------------------------------------
    # STEP 3: MEASURE METRICS
    # ------------------------------------------------------------
    # Find metrics script (metrics_helper.py or measure_metrics.py)
    metrics_script = lab_dir / "metrics_helper.py"
    if not metrics_script.exists():
        metrics_script = lab_dir / "measure_metrics.py"

    if metrics_script.exists():
        try:
            jsonl_rel_path = output_jsonl.relative_to(lab_dir)
        except ValueError:
            jsonl_rel_path = output_jsonl

        metrics_cmd = [sys.executable, str(metrics_script.name), agent_name, str(jsonl_rel_path)]
        res = subprocess.run(metrics_cmd, capture_output=True, text=True, cwd=lab_dir)
        print(res.stdout)
        if res.stderr:
            print(res.stderr, file=sys.stderr)
    else:
        print(f"Notice: Metrics script not found in {lab_dir}. Log saved to: {output_jsonl}")


def main():
    parser = argparse.ArgumentParser(description="Lab 3 Agent Execution & Metrics Runner")
    parser.add_argument("--agent", required=True, help="Agent name (e.g. claude-3-5-sonnet, claude-3-5-haiku, haiku, terra)")
    parser.add_argument("--task", required=True, help="Path to task file (e.g. tasks/request_01.md)")

    args = parser.parse_args()

    run_experiment(
        agent_name=args.agent,
        task_path=Path(args.task)
    )


if __name__ == "__main__":
    main()
