#!/usr/bin/env python3

import sys
import json
from pathlib import Path


def separator():
    print("\n" + "=" * 72, flush=True)


def short_separator():
    print("-" * 72, flush=True)


def get_role(agent_name):
    """Convert agent name into a readable role."""

    name = agent_name.lower()

    if "architect" in name:
        return "ARCHITECT"

    if "builder" in name:
        return "BUILDER"

    if "qa" in name:
        return "QA"

    return "SUBAGENT"


def get_tier(agent_name):
    """Extract LOW / MID / HIGH from agent name."""

    name = agent_name.lower()

    if name.startswith("high-"):
        return "HIGH"

    if name.startswith("mid-"):
        return "MID"

    if name.startswith("low-"):
        return "LOW"

    return "UNKNOWN"


def display_task_event(event):
    """
    Display subagent delegation using the actual OpenCode
    JSON structure.
    """

    part = event.get("part", {})

    if part.get("tool") != "task":
        return

    state = part.get("state", {})
    status = state.get("status", "unknown")

    input_data = state.get("input", {})

    agent = input_data.get("subagent_type", "unknown")
    prompt = input_data.get("prompt", "")
    description = input_data.get("description", "")

    role = get_role(agent)
    tier = get_tier(agent)

    metadata = state.get("metadata", {})
    model_data = metadata.get("model", {})

    provider = model_data.get("providerID", "")
    model = model_data.get("modelID", "")

    timing = state.get("time", {})
    start = timing.get("start")
    end = timing.get("end")

    duration = None

    if start is not None and end is not None:
        duration = (end - start) / 1000.0

    # ---------------------------------------------------------
    # HEADER
    # ---------------------------------------------------------

    separator()

    print(f"{role} — {tier}", flush=True)

    short_separator()

    print(f"Agent       : {agent}", flush=True)

    if description:
        print(f"Task        : {description}", flush=True)

    if model:
        print(f"Model       : {model}", flush=True)

    if provider:
        print(f"Provider    : {provider}", flush=True)

    print(f"Status      : {status.upper()}", flush=True)

    if duration is not None:
        print(f"Duration    : {duration:.2f}s", flush=True)

    # ---------------------------------------------------------
    # PROMPT
    # ---------------------------------------------------------

    if prompt:

        print()
        print("PROMPT SENT TO AGENT")
        short_separator()

        print(prompt.strip(), flush=True)

    # ---------------------------------------------------------
    # RESULT
    # ---------------------------------------------------------

    output = state.get("output")

    if output:

        print()
        print("AGENT RESPONSE")
        short_separator()

        # Remove OpenCode task wrapper if desired.
        # For now preserve complete response.
        print(str(output).strip(), flush=True)

    # ---------------------------------------------------------
    # ERROR
    # ---------------------------------------------------------

    error = state.get("error")

    if error:

        print()
        print("ERROR")
        short_separator()

        print(str(error).strip(), flush=True)

    separator()


def display_todo_event(event):
    """
    Optional high-level coordinator progress.

    We don't print every todo detail; just current active work.
    """

    part = event.get("part", {})

    if part.get("tool") != "todowrite":
        return

    state = part.get("state", {})

    input_data = state.get("input", {})
    todos = input_data.get("todos", [])

    for todo in todos:

        if todo.get("status") == "in_progress":

            content = todo.get("content")

            if content:
                print(
                    f"\n[COORDINATOR] {content}",
                    flush=True
                )

            break


def display_text_event(event):
    """
    Display normal assistant/coordinator text when present.
    """

    if event.get("type") != "text":
        return

    part = event.get("part", {})

    text = part.get("text")

    if text:

        print()
        print("[COORDINATOR]")
        print(text.strip(), flush=True)


def process_event(event):

    event_type = event.get("type")

    # ---------------------------------------------------------
    # SUBAGENT CALL
    # ---------------------------------------------------------

    if event_type == "tool_use":

        part = event.get("part", {})

        tool = part.get("tool")

        if tool == "task":
            display_task_event(event)
            return

        if tool == "todowrite":
            display_todo_event(event)
            return

        # Hide noisy tools:
        #
        # read
        # edit
        # write
        # bash
        # grep
        # glob
        #
        return

    # ---------------------------------------------------------
    # COORDINATOR TEXT
    # ---------------------------------------------------------

    if event_type == "text":
        display_text_event(event)
        return

    # ---------------------------------------------------------
    # Hide step_start / step_finish from console.
    #
    # They remain in JSONL for measure_metrics.py.
    # ---------------------------------------------------------

    return


def main():

    if len(sys.argv) != 2:

        print(
            "Usage: python live_view.py <output.jsonl>",
            file=sys.stderr
        )

        return 1

    output_path = Path(sys.argv[1])

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    separator()

    print("OPENCODE MULTI-AGENT WORKFLOW")

    short_separator()

    print(f"Raw JSONL : {output_path}")
    print("Live View : ENABLED")

    separator()

    event_count = 0

    try:

        with output_path.open(
            "w",
            encoding="utf-8",
            newline="\n"
        ) as output_file:

            for raw_line in sys.stdin:

                # -------------------------------------------------
                # ALWAYS save original JSONL first.
                #
                # measure_metrics.py gets the exact raw OpenCode
                # events.
                # -------------------------------------------------

                output_file.write(raw_line)
                output_file.flush()

                line = raw_line.strip()

                if not line:
                    continue

                try:

                    event = json.loads(line)

                except json.JSONDecodeError:

                    # Ignore non-JSON output.
                    # Never terminate the pipeline.
                    continue

                event_count += 1

                try:

                    process_event(event)

                except Exception as exc:

                    # Display problems must NEVER terminate capture.
                    print(
                        f"[VIEW ERROR] {exc}",
                        file=sys.stderr,
                        flush=True
                    )

    except KeyboardInterrupt:

        print(
            "\nWorkflow interrupted.",
            file=sys.stderr,
            flush=True
        )

        return 130

    except Exception as exc:

        print(
            f"\n[CAPTURE ERROR] {exc}",
            file=sys.stderr,
            flush=True
        )

        # Keep consuming input to avoid EPIPE upstream.
        try:
            for _ in sys.stdin:
                pass
        except Exception:
            pass

        return 1

    separator()

    print("WORKFLOW CAPTURE COMPLETE")

    short_separator()

    print(f"Events captured : {event_count}")
    print(f"JSONL saved     : {output_path}")

    separator()

    return 0


if __name__ == "__main__":
    sys.exit(main())