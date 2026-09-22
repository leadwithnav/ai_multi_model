#!/usr/bin/env python3
"""
OpenCode JSONL Metrics Aggregator

Aggregates one complete `opencode run --format json` execution.

Reports:
- End-to-end latency from JSONL event timestamps
- Number of LLM steps
- Token usage
- Cache read/write tokens
- Effective input/context tokens
- Output/reasoning tokens
- Total cost reported by OpenCode
"""

import sys
import json


def parse_jsonl(stream, agent_name=None):
    llm_steps = 0

    direct_input_tokens = 0
    cache_read_tokens = 0
    cache_write_tokens = 0
    output_tokens = 0
    reasoning_tokens = 0

    total_cost = 0.0

    first_timestamp = None
    last_timestamp = None

    for line in stream:
        line = line.strip()

        if not line:
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        # ---------------------------------------------------------
        # Capture timestamps from ALL events for end-to-end latency
        # ---------------------------------------------------------
        timestamp = event.get("timestamp")

        if isinstance(timestamp, (int, float)):
            if first_timestamp is None:
                first_timestamp = timestamp

            last_timestamp = timestamp

        # ---------------------------------------------------------
        # Only step_finish contains LLM usage/cost information
        # ---------------------------------------------------------
        if event.get("type") != "step_finish":
            continue

        llm_steps += 1

        part = event.get("part", {})
        tokens = part.get("tokens", {}) or {}
        cache = tokens.get("cache", {}) or {}

        direct_input_tokens += tokens.get("input", 0) or 0
        output_tokens += tokens.get("output", 0) or 0
        reasoning_tokens += tokens.get("reasoning", 0) or 0

        cache_read_tokens += cache.get("read", 0) or 0
        cache_write_tokens += cache.get("write", 0) or 0

        # Use OpenCode's actual reported cost
        total_cost += part.get("cost", 0.0) or 0.0

    # ---------------------------------------------------------
    # End-to-end latency
    # OpenCode timestamps are milliseconds
    # ---------------------------------------------------------
    if first_timestamp is not None and last_timestamp is not None:
        latency_seconds = (last_timestamp - first_timestamp) / 1000.0
    else:
        latency_seconds = 0.0

    # ---------------------------------------------------------
    # Effective input/context processed
    #
    # direct input + cache reads + cache writes
    # ---------------------------------------------------------
    effective_input_tokens = (
        direct_input_tokens
        + cache_read_tokens
        + cache_write_tokens
    )

    # Generated tokens
    generated_tokens = output_tokens + reasoning_tokens

    # Useful overall workload-token number
    total_processed_tokens = (
        effective_input_tokens
        + generated_tokens
    )

    return {
        "agent": agent_name or "unknown",

        "llm_steps": llm_steps,

        "tokens": {
            "direct_input": direct_input_tokens,
            "cache_read": cache_read_tokens,
            "cache_write": cache_write_tokens,
            "effective_input": effective_input_tokens,

            "output": output_tokens,
            "reasoning": reasoning_tokens,

            "total_processed": total_processed_tokens
        },

        "latency_seconds": round(latency_seconds, 2),

        "cost_usd": round(total_cost, 6)
    }


def main():
    agent_name = sys.argv[1] if len(sys.argv) > 1 else None
    input_file = sys.argv[2] if len(sys.argv) > 2 else None

    if input_file:
        with open(input_file, "r", encoding="utf-8") as f:
            metrics = parse_jsonl(f, agent_name)
    else:
        metrics = parse_jsonl(sys.stdin, agent_name)

    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()