#!/usr/bin/env python3
"""
Lab 7 - OpenCode Tiering Metrics Aggregator

Reads OpenCode JSONL files and calculates:

LLM metrics
-----------
- Number of LLM steps
- Direct input tokens
- Cache read / write tokens
- Output tokens
- Reasoning tokens
- Total processed tokens
- Total cost reported by OpenCode

Agent execution metrics
-----------------------
- Total tool calls
- Read calls
- Edit / write / apply_patch calls
- Bash / test calls
- Glob calls
- Other tool calls
- Files read
- Files modified
- Bash commands executed

Timing
------
- JSONL event latency

IMPORTANT:
JSONL event latency measures the time between the first and last
timestamped OpenCode events.

For the actual developer wait / end-to-end task latency, prefer the
wall-clock time measured around the complete `opencode run` command
inside run_vertical.py or run_horizontal.py.

Usage:
    python measure_metrics.py runs/vertical_terra.jsonl
    python measure_metrics.py runs/vertical_sol.jsonl

Multiple files:
    python measure_metrics.py \
        runs/vertical_terra.jsonl \
        runs/vertical_sol.jsonl

This module can also be imported:

    from measure_metrics import parse_jsonl

    metrics = parse_jsonl("runs/vertical_terra.jsonl")
"""

import json
import sys
from pathlib import Path
from collections import Counter


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _get_tool_input(part):
    """
    Extract tool input safely from an OpenCode tool_use event.

    Expected structure:

        part
          └── state
                └── input
    """

    state = part.get("state", {}) or {}
    tool_input = state.get("input", {}) or {}

    if isinstance(tool_input, dict):
        return tool_input

    return {}


def _add_unique(items, value):
    """
    Append value only if it is meaningful and has not already
    been recorded.
    """

    if value and value not in items:
        items.append(value)


# ---------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------

def parse_jsonl(path):

    path = Path(path)

    # --------------------------------------------------------------
    # LLM metrics
    # --------------------------------------------------------------

    llm_steps = 0

    direct_input_tokens = 0
    cache_read_tokens = 0
    cache_write_tokens = 0
    output_tokens = 0
    reasoning_tokens = 0

    total_cost = 0.0

    # --------------------------------------------------------------
    # Tool metrics
    # --------------------------------------------------------------

    tool_calls = 0

    read_calls = 0
    edit_calls = 0
    bash_calls = 0
    glob_calls = 0
    other_tool_calls = 0

    tool_counts = Counter()

    files_read = []
    files_modified = []
    bash_commands = []

    # --------------------------------------------------------------
    # Timing
    # --------------------------------------------------------------

    first_timestamp = None
    last_timestamp = None

    # --------------------------------------------------------------
    # Missing file
    # --------------------------------------------------------------

    if not path.exists():

        return {
            "file": str(path),
            "status": "FILE_NOT_FOUND",

            "latency_seconds": 0.0,
            "cost_usd": 0.0,

            "llm_steps": 0,
            "tool_calls": 0,

            "read_calls": 0,
            "edit_calls": 0,
            "bash_calls": 0,
            "glob_calls": 0,
            "other_tool_calls": 0,

            "processed_tokens": 0,

            "tokens": {
                "direct_input": 0,
                "cache_read": 0,
                "cache_write": 0,
                "output": 0,
                "reasoning": 0
            },

            "tool_breakdown": {},

            "files_read": [],
            "files_modified": [],
            "bash_commands": []
        }

    # --------------------------------------------------------------
    # Parse JSONL
    # --------------------------------------------------------------

    with open(path, "r", encoding="utf-8") as stream:

        for line in stream:

            line = line.strip()

            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            # ------------------------------------------------------
            # Timestamp tracking
            # ------------------------------------------------------

            timestamp = event.get("timestamp")

            if isinstance(timestamp, (int, float)):

                if first_timestamp is None:
                    first_timestamp = timestamp

                last_timestamp = timestamp

            event_type = event.get("type")
            part = event.get("part", {}) or {}

            # ======================================================
            # LLM STEP
            # ======================================================

            if event_type == "step_finish":

                llm_steps += 1

                tokens = part.get("tokens", {}) or {}
                cache = tokens.get("cache", {}) or {}

                direct_input_tokens += (
                    tokens.get("input", 0) or 0
                )

                output_tokens += (
                    tokens.get("output", 0) or 0
                )

                reasoning_tokens += (
                    tokens.get("reasoning", 0) or 0
                )

                cache_read_tokens += (
                    cache.get("read", 0) or 0
                )

                cache_write_tokens += (
                    cache.get("write", 0) or 0
                )

                total_cost += (
                    part.get("cost", 0.0) or 0.0
                )

            # ======================================================
            # TOOL CALL
            # ======================================================

            elif event_type == "tool_use":

                tool_calls += 1

                tool = part.get("tool", "unknown") or "unknown"

                tool_counts[tool] += 1

                tool_input = _get_tool_input(part)

                # --------------------------------------------------
                # READ
                # --------------------------------------------------

                if tool == "read":

                    read_calls += 1

                    file_path = (
                        tool_input.get("filePath")
                        or tool_input.get("path")
                    )

                    _add_unique(files_read, file_path)

                # --------------------------------------------------
                # EDIT / WRITE
                # --------------------------------------------------

                elif tool in (
                    "edit",
                    "write",
                    "apply_patch",
                    "patch"
                ):

                    edit_calls += 1

                    file_path = (
                        tool_input.get("filePath")
                        or tool_input.get("path")
                    )

                    _add_unique(files_modified, file_path)

                # --------------------------------------------------
                # BASH
                # --------------------------------------------------

                elif tool == "bash":

                    bash_calls += 1

                    command = (
                        tool_input.get("command")
                        or tool_input.get("cmd")
                    )

                    _add_unique(bash_commands, command)

                # --------------------------------------------------
                # GLOB
                # --------------------------------------------------

                elif tool == "glob":

                    glob_calls += 1

                # --------------------------------------------------
                # OTHER TOOL
                # --------------------------------------------------

                else:

                    other_tool_calls += 1

    # -----------------------------------------------------------------
    # Derived metrics
    # -----------------------------------------------------------------

    if (
        first_timestamp is not None
        and last_timestamp is not None
    ):
        latency_seconds = (
            last_timestamp - first_timestamp
        ) / 1000.0

    else:
        latency_seconds = 0.0

    # Context / tokens processed across all LLM steps.
    #
    # This is useful as a workload/context-volume metric.
    # It should NOT be interpreted as provider-billed tokens because
    # cache pricing may differ.

    processed_tokens = (
        direct_input_tokens
        + cache_read_tokens
        + cache_write_tokens
        + output_tokens
        + reasoning_tokens
    )

    # -----------------------------------------------------------------
    # Result
    # -----------------------------------------------------------------

    return {

        "file": str(path),

        # Timing
        "latency_seconds": round(
            latency_seconds,
            2
        ),

        # Cost
        "cost_usd": round(
            total_cost,
            6
        ),

        # LLM
        "llm_steps": llm_steps,

        # Tools
        "tool_calls": tool_calls,

        "read_calls": read_calls,
        "edit_calls": edit_calls,
        "bash_calls": bash_calls,
        "glob_calls": glob_calls,
        "other_tool_calls": other_tool_calls,

        # Tokens
        "processed_tokens": processed_tokens,

        "tokens": {

            "direct_input":
                direct_input_tokens,

            "cache_read":
                cache_read_tokens,

            "cache_write":
                cache_write_tokens,

            "output":
                output_tokens,

            "reasoning":
                reasoning_tokens
        },

        # Detailed tool breakdown
        "tool_breakdown":
            dict(tool_counts),

        # Useful for later execution analysis
        "files_read":
            files_read,

        "files_modified":
            files_modified,

        "bash_commands":
            bash_commands
    }


# ---------------------------------------------------------------------
# Human-readable summary
# ---------------------------------------------------------------------

def print_summary(result):

    print()
    print("=" * 70)
    print("OPENCODE EXECUTION METRICS")
    print("=" * 70)

    print(f"File              : {result['file']}")

    if result.get("status") == "FILE_NOT_FOUND":
        print("Status            : FILE NOT FOUND")
        return

    print()
    print("LLM EXECUTION")
    print("-" * 70)

    print(
        f"LLM Steps         : "
        f"{result['llm_steps']}"
    )

    print(
        f"Processed Tokens  : "
        f"{result['processed_tokens']:,}"
    )

    print(
        f"Output Tokens     : "
        f"{result['tokens']['output']:,}"
    )

    print(
        f"Reasoning Tokens  : "
        f"{result['tokens']['reasoning']:,}"
    )

    print()
    print("CACHE / CONTEXT")
    print("-" * 70)

    print(
        f"Direct Input      : "
        f"{result['tokens']['direct_input']:,}"
    )

    print(
        f"Cache Read        : "
        f"{result['tokens']['cache_read']:,}"
    )

    print(
        f"Cache Write       : "
        f"{result['tokens']['cache_write']:,}"
    )

    print()
    print("AGENT TOOL ACTIVITY")
    print("-" * 70)

    print(
        f"Total Tool Calls  : "
        f"{result['tool_calls']}"
    )

    print(
        f"Read Calls        : "
        f"{result['read_calls']}"
    )

    print(
        f"Edit Calls        : "
        f"{result['edit_calls']}"
    )

    print(
        f"Bash/Test Calls   : "
        f"{result['bash_calls']}"
    )

    print(
        f"Glob Calls        : "
        f"{result['glob_calls']}"
    )

    print(
        f"Other Tool Calls  : "
        f"{result['other_tool_calls']}"
    )

    print()
    print("COST / LATENCY")
    print("-" * 70)

    print(
        f"JSONL Latency     : "
        f"{result['latency_seconds']:.2f}s"
    )

    print(
        f"OpenCode Cost     : "
        f"${result['cost_usd']:.6f}"
    )

    # -------------------------------------------------------------
    # Files read
    # -------------------------------------------------------------

    if result["files_read"]:

        print()
        print("FILES / DIRECTORIES READ")
        print("-" * 70)

        for file_path in result["files_read"]:
            print(f"- {file_path}")

    # -------------------------------------------------------------
    # Files modified
    # -------------------------------------------------------------

    if result["files_modified"]:

        print()
        print("FILES MODIFIED")
        print("-" * 70)

        for file_path in result["files_modified"]:
            print(f"- {file_path}")

    # -------------------------------------------------------------
    # Bash commands
    # -------------------------------------------------------------

    if result["bash_commands"]:

        print()
        print("BASH / TEST COMMANDS")
        print("-" * 70)

        for command in result["bash_commands"]:
            print(f"- {command}")


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def main():

    if len(sys.argv) < 2:

        print(
            "Usage: python measure_metrics.py "
            "<path_to_jsonl> [another_jsonl ...]"
        )

        sys.exit(1)

    for arg in sys.argv[1:]:

        result = parse_jsonl(arg)

        print_summary(result)

        print()
        print("RAW JSON")
        print("-" * 70)

        print(
            json.dumps(
                result,
                indent=2
            )
        )


if __name__ == "__main__":
    main()