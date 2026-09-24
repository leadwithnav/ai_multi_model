#!/usr/bin/env python3
"""
Lab 8 - Context Handoff Metrics Aggregator

Parses OpenCode JSONL logs and aggregates execution metrics for:
- Cold Retry Branch (3 Trials)
- Context-Aware Retry Branch (3 Trials)

Metrics tracked:
- Pass Rate
- Mean Wall-Clock Latency (seconds)
- Mean Direct Input Tokens
- Mean Cache Read / Write Tokens
- Mean Output Tokens
- Mean Total Processed Tokens
- Mean Cost (USD)
- Tool Call breakdown
"""

import json
import sys
from pathlib import Path
from collections import Counter


def parse_jsonl(path):
    path = Path(path)
    if not path.exists():
        return {
            "file": str(path),
            "status": "FILE_NOT_FOUND",
            "latency_seconds": 0.0,
            "cost_usd": 0.0,
            "llm_steps": 0,
            "tool_calls": 0,
            "tokens": {
                "direct_input": 0,
                "cache_read": 0,
                "cache_write": 0,
                "output": 0,
                "reasoning": 0
            },
            "processed_tokens": 0
        }

    llm_steps = 0
    direct_input = 0
    cache_read = 0
    cache_write = 0
    output_tokens = 0
    reasoning_tokens = 0
    total_cost = 0.0
    tool_calls = 0
    first_ts = None
    last_ts = None

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            ts = event.get("timestamp")
            if isinstance(ts, (int, float)):
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            event_type = event.get("type")
            part = event.get("part", {}) or {}

            if event_type == "step_finish":
                llm_steps += 1
                tokens = part.get("tokens", {}) or {}
                cache = tokens.get("cache", {}) or {}

                direct_input += tokens.get("input", 0) or 0
                output_tokens += tokens.get("output", 0) or 0
                reasoning_tokens += tokens.get("reasoning", 0) or 0
                cache_read += cache.get("read", 0) or 0
                cache_write += cache.get("write", 0) or 0
                total_cost += part.get("cost", 0.0) or 0.0

            elif event_type == "tool_use":
                tool_calls += 1

    latency = (last_ts - first_ts) / 1000.0 if (first_ts and last_ts) else 0.0
    processed = direct_input + cache_read + cache_write + output_tokens + reasoning_tokens

    return {
        "file": str(path),
        "status": "OK",
        "latency_seconds": round(latency, 2),
        "cost_usd": round(total_cost, 6),
        "llm_steps": llm_steps,
        "tool_calls": tool_calls,
        "processed_tokens": processed,
        "tokens": {
            "direct_input": direct_input,
            "cache_read": cache_read,
            "cache_write": cache_write,
            "output": output_tokens,
            "reasoning": reasoning_tokens
        }
    }


def aggregate_branch_trials(trial_results):
    """
    Given a list of trial result dicts (with 'test_status', 'wall_latency', 'jsonl_metrics'),
    computes average metrics across trials.
    """
    count = len(trial_results)
    if count == 0:
        return {}

    passed_count = sum(1 for t in trial_results if t.get("test_status") == "PASS")
    pass_rate = (passed_count / count) * 100.0

    mean_wall_latency = sum(t.get("wall_latency", 0.0) for t in trial_results) / count
    mean_cost = sum(t.get("metrics", {}).get("cost_usd", 0.0) for t in trial_results) / count
    mean_input_tokens = sum(t.get("metrics", {}).get("tokens", {}).get("direct_input", 0) for t in trial_results) / count
    mean_output_tokens = sum(t.get("metrics", {}).get("tokens", {}).get("output", 0) for t in trial_results) / count
    mean_processed_tokens = sum(t.get("metrics", {}).get("processed_tokens", 0) for t in trial_results) / count

    return {
        "trials_count": count,
        "pass_rate_pct": round(pass_rate, 1),
        "passed_trials": passed_count,
        "mean_wall_latency_s": round(mean_wall_latency, 2),
        "mean_cost_usd": round(mean_cost, 6),
        "mean_input_tokens": round(mean_input_tokens, 1),
        "mean_output_tokens": round(mean_output_tokens, 1),
        "mean_processed_tokens": round(mean_processed_tokens, 1),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python measure_metrics.py <jsonl_file1> [jsonl_file2 ...]")
        sys.exit(1)

    for path_str in sys.argv[1:]:
        m = parse_jsonl(path_str)
        print(json.dumps(m, indent=2))


if __name__ == "__main__":
    main()
