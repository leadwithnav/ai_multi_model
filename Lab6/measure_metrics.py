#!/usr/bin/env python3
"""
Lab 6 - OpenCode Workflow Metrics

Reads OpenCode JSONL files and reports:

- LLM steps
- direct input tokens
- cache read tokens
- cache write tokens
- output tokens
- reasoning tokens
- OpenCode event-span latency
- OpenCode-reported cost

Examples:

Single file:

    python measure_metrics.py \
        runs/request_01_attempt1_terra-low.jsonl


Whole workflow:

    python measure_metrics.py \
        runs/request_01_classifier.jsonl \
        runs/request_01_attempt1_terra-low.jsonl \
        runs/request_01_diagnostician.jsonl \
        runs/request_01_attempt2_terra-low.jsonl
"""

import json
import sys
from pathlib import Path


# ============================================================
# PARSE ONE JSONL FILE
# ============================================================

def parse_jsonl(path):

    llm_steps = 0

    direct_input_tokens = 0
    cache_read_tokens = 0
    cache_write_tokens = 0

    output_tokens = 0
    reasoning_tokens = 0

    total_cost = 0.0

    first_timestamp = None
    last_timestamp = None

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as stream:

        for line in stream:

            line = line.strip()

            if not line:
                continue

            try:
                event = json.loads(line)

            except json.JSONDecodeError:
                continue

            # ------------------------------------------------
            # Event-span latency
            # ------------------------------------------------

            timestamp = event.get(
                "timestamp"
            )

            if isinstance(
                timestamp,
                (int, float)
            ):

                if first_timestamp is None:
                    first_timestamp = (
                        timestamp
                    )

                last_timestamp = timestamp

            # ------------------------------------------------
            # Usage exists on step_finish
            # ------------------------------------------------

            if (
                event.get("type")
                != "step_finish"
            ):
                continue

            llm_steps += 1

            part = (
                event.get(
                    "part",
                    {}
                )
                or {}
            )

            tokens = (
                part.get(
                    "tokens",
                    {}
                )
                or {}
            )

            cache = (
                tokens.get(
                    "cache",
                    {}
                )
                or {}
            )

            direct_input_tokens += (
                tokens.get(
                    "input",
                    0
                )
                or 0
            )

            output_tokens += (
                tokens.get(
                    "output",
                    0
                )
                or 0
            )

            reasoning_tokens += (
                tokens.get(
                    "reasoning",
                    0
                )
                or 0
            )

            cache_read_tokens += (
                cache.get(
                    "read",
                    0
                )
                or 0
            )

            cache_write_tokens += (
                cache.get(
                    "write",
                    0
                )
                or 0
            )

            total_cost += (
                part.get(
                    "cost",
                    0.0
                )
                or 0.0
            )

    # --------------------------------------------------------
    # OpenCode event-span latency
    # --------------------------------------------------------

    if (
        first_timestamp is not None
        and last_timestamp is not None
    ):

        event_latency = (
            last_timestamp
            - first_timestamp
        ) / 1000.0

    else:

        event_latency = 0.0

    effective_input = (
        direct_input_tokens
        + cache_read_tokens
        + cache_write_tokens
    )

    generated_tokens = (
        output_tokens
        + reasoning_tokens
    )

    return {

        "file":
            Path(path).name,

        "llm_steps":
            llm_steps,

        "tokens": {

            "direct_input":
                direct_input_tokens,

            "cache_read":
                cache_read_tokens,

            "cache_write":
                cache_write_tokens,

            "effective_input":
                effective_input,

            "output":
                output_tokens,

            "reasoning":
                reasoning_tokens,

            "generated":
                generated_tokens,
        },

        "event_latency_seconds":
            round(
                event_latency,
                2
            ),

        "cost_usd":
            round(
                total_cost,
                6
            ),
    }


# ============================================================
# AGGREGATE
# ============================================================

def aggregate(results):

    return {

        "files":
            len(results),

        "llm_steps":
            sum(
                r["llm_steps"]
                for r in results
            ),

        "tokens": {

            "direct_input":
                sum(
                    r["tokens"]
                    ["direct_input"]
                    for r in results
                ),

            "cache_read":
                sum(
                    r["tokens"]
                    ["cache_read"]
                    for r in results
                ),

            "cache_write":
                sum(
                    r["tokens"]
                    ["cache_write"]
                    for r in results
                ),

            "effective_input":
                sum(
                    r["tokens"]
                    ["effective_input"]
                    for r in results
                ),

            "output":
                sum(
                    r["tokens"]
                    ["output"]
                    for r in results
                ),

            "reasoning":
                sum(
                    r["tokens"]
                    ["reasoning"]
                    for r in results
                ),

            "generated":
                sum(
                    r["tokens"]
                    ["generated"]
                    for r in results
                ),
        },

        # Do not call this wall-clock latency.
        # These are summed OpenCode event spans.
        "summed_event_latency_seconds":
            round(
                sum(
                    r[
                        "event_latency_seconds"
                    ]
                    for r in results
                ),
                2
            ),

        "cost_usd":
            round(
                sum(
                    r["cost_usd"]
                    for r in results
                ),
                6
            ),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) < 2:

        print(
            "Usage:\n"
            "  python measure_metrics.py "
            "<jsonl> [jsonl ...]"
        )

        sys.exit(1)

    results = []

    for filename in sys.argv[1:]:

        path = Path(filename)

        if not path.exists():

            print(
                f"WARNING: skipping "
                f"missing file: {path}",
                file=sys.stderr,
            )

            continue

        metrics = parse_jsonl(
            path
        )

        results.append(
            metrics
        )

    if not results:

        print(
            "No valid JSONL files found.",
            file=sys.stderr,
        )

        sys.exit(1)

    report = {

        "runs":
            results,

        "workflow_total":
            aggregate(results),
    }

    print(
        json.dumps(
            report,
            indent=2
        )
    )


if __name__ == "__main__":
    main()