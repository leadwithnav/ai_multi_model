#!/usr/bin/env python3
"""
Lab 9 - Workflow Orchestration Metrics Aggregator

Parses OpenCode JSONL logs and aggregates execution metrics for:
- ALL_LOW Strategy
- ALL_HIGH Strategy
- TIERED Strategy

Metrics tracked:
- LLM Steps
- Wall-Clock Latency (seconds)
- Total Cost (USD)
- Token Usage (Input, Output, Reasoning, Cache)
- Tool Calls
"""

import json
import sys
from pathlib import Path

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

def main():
    if len(sys.argv) < 2:
        print("Usage: python measure_metrics.py [strategy/agent] <jsonl_file>")
        sys.exit(1)

    jsonl_path = sys.argv[-1]
    for arg in sys.argv[1:]:
        if arg.endswith(".jsonl") or Path(arg).exists():
            jsonl_path = arg
            break

    m = parse_jsonl(jsonl_path)
    print(json.dumps(m, indent=2))

if __name__ == "__main__":
    main()
