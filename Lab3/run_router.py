#!/usr/bin/env python3

"""
Lab 3 — Benchmark-Derived Model Router

Flow:
1. Read engineering request.
2. task-classifier determines task_type.
3. routing_policy.yaml maps task_type to an agent.
4. Run selected OpenCode agent.
5. Stream raw JSONL telemetry live into runs/.
6. Save final routing/execution result.

No fallback.
No acceptance testing.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml


# ============================================================
# CONFIGURATION
# ============================================================

LAB_DIR = Path(__file__).resolve().parent

WORKSPACE_ROOT = LAB_DIR.parent

SERVICE_ROOT = (
    WORKSPACE_ROOT
    / "order_flow_service"
)

RUNS_DIR = (
    LAB_DIR
    / "runs"
)

POLICY_FILE = (
    LAB_DIR
    / "config"
    / "routing_policy.yaml"
)

CLASSIFIER_AGENT = "task-classifier"

CLASSIFIER_TIMEOUT = 120
AGENT_TIMEOUT = 300


# ============================================================
# OPENCODE EXECUTABLE
# ============================================================

def opencode_binary():

    if os.name == "nt":
        return "opencode.cmd"

    return "opencode"


# ============================================================
# SAVE RAW JSONL
# ============================================================

def save_jsonl(
    request_name,
    role,
    stdout,
):

    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        RUNS_DIR
        / f"{request_name}_{role}.jsonl"
    )

    path.write_text(
        stdout or "",
        encoding="utf-8",
    )

    return path


# ============================================================
# EXTRACT TEXT FROM OPENCODE JSONL
# ============================================================

def parse_opencode_output(stdout):

    text_parts = []

    for line in stdout.splitlines():

        line = line.strip()

        if not line:
            continue

        try:
            event = json.loads(line)

        except json.JSONDecodeError:
            continue

        part = event.get(
            "part",
            {},
        )

        if part.get("type") == "text":

            text = part.get("text")

            if text:
                text_parts.append(text)

    return "\n".join(
        text_parts
    ).strip()


# ============================================================
# EXTRACT ERROR FROM OPENCODE JSONL
# ============================================================

def extract_opencode_error(stdout):

    if not stdout:
        return None

    for line in stdout.splitlines():

        line = line.strip()

        if not line:
            continue

        try:
            event = json.loads(line)

        except json.JSONDecodeError:
            continue

        if event.get("type") != "error":
            continue

        error = event.get(
            "error",
            {},
        )

        data = error.get(
            "data",
            {},
        )

        message = data.get(
            "message"
        )

        reference = data.get(
            "ref"
        )

        if message and reference:

            return (
                f"{message} "
                f"(reference: {reference})"
            )

        if message:
            return message

        return str(error)

    return None


# ============================================================
# VALIDATE ENVIRONMENT
# ============================================================

def validate_environment():

    if not SERVICE_ROOT.exists():

        raise FileNotFoundError(
            "Service workspace not found:\n"
            f"{SERVICE_ROOT}"
        )

    agents_dir = (
        SERVICE_ROOT
        / ".opencode"
        / "agent"
    )

    if not agents_dir.exists():

        raise FileNotFoundError(
            "OpenCode agent directory not found:\n"
            f"{agents_dir}"
        )

    if not POLICY_FILE.exists():

        raise FileNotFoundError(
            "Routing policy not found:\n"
            f"{POLICY_FILE}"
        )


# ============================================================
# STEP 1 — CLASSIFY TASK
# ============================================================

def classify_task(
    request_text,
    request_name,
):

    print()
    print("=" * 60)
    print("1. TASK CLASSIFICATION")
    print("=" * 60)

    print(
        f"Workspace : {SERVICE_ROOT}"
    )

    print(
        f"Agent     : {CLASSIFIER_AGENT}"
    )

    # Compact request only for classification.
    compact_request = " ".join(
        request_text.split()
    )

    command = [
        opencode_binary(),
        "run",
        "--agent",
        CLASSIFIER_AGENT,
        "--format",
        "json",
        compact_request,
    ]

    try:

        result = subprocess.run(
            command,
            cwd=SERVICE_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CLASSIFIER_TIMEOUT,
        )

    except subprocess.TimeoutExpired:

        raise RuntimeError(
            "Task classifier timed out."
        )

    # Save classifier telemetry.
    classifier_path = save_jsonl(
        request_name,
        "classifier",
        result.stdout,
    )

    if result.returncode != 0:

        error_message = (
            extract_opencode_error(
                result.stdout
            )
        )

        details = (
            error_message
            or result.stderr[-2000:]
            or result.stdout[-2000:]
            or "Unknown OpenCode error"
        )

        raise RuntimeError(
            "Task classifier failed.\n\n"
            + details
        )

    response = parse_opencode_output(
        result.stdout
    )

    # Remove Markdown fences.
    response = (
        response
        .replace("```json", "")
        .replace("```JSON", "")
        .replace("```", "")
        .strip()
    )

    try:

        classification = json.loads(
            response
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "Task classifier did not return valid JSON."
            "\n\nClassifier response:\n"
            + response
        ) from exc

    task_type = classification.get(
        "task_type"
    )

    allowed_task_types = {
        "implementation",
        "refactoring",
        "debugging",
        "testing",
    }

    if task_type not in allowed_task_types:

        raise RuntimeError(
            "Invalid task_type returned "
            f"by classifier: {task_type}"
        )

    print()
    print(
        f"Task Type : {task_type}"
    )

    signals = classification.get(
        "signals",
        [],
    )

    if signals:

        print()
        print("Signals:")

        for signal in signals:

            print(
                f"  - {signal}"
            )

    print()
    print(
        f"Classifier telemetry: "
        f"{classifier_path}"
    )

    return classification


# ============================================================
# STEP 2 — LOAD ROUTING POLICY
# ============================================================

def load_policy():

    with POLICY_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:

        policy = yaml.safe_load(f)

    if not isinstance(
        policy,
        dict,
    ):

        raise RuntimeError(
            "routing_policy.yaml is empty or invalid."
        )

    return policy


# ============================================================
# STEP 3 — SELECT AGENT
# ============================================================

def select_agent(
    classification,
    policy,
):

    task_type = classification[
        "task_type"
    ]

    try:

        agent = (
            policy["routing_policy"]
                  [task_type]
                  ["primary"]
        )

    except KeyError as exc:

        raise RuntimeError(
            "Routing policy is missing "
            f"a mapping for: {exc}"
        ) from exc

    return agent


# ============================================================
# STREAM READER
# ============================================================

def stream_reader(
    stream,
    output_queue,
    stream_name,
):
    """
    Read stdout/stderr without blocking the main thread.

    Each line is placed into a queue so that the main thread
    can enforce the overall wall-clock timeout.
    """

    try:

        for line in iter(
            stream.readline,
            "",
        ):

            output_queue.put(
                (
                    stream_name,
                    line,
                )
            )

    finally:

        stream.close()

        output_queue.put(
            (
                stream_name,
                None,
            )
        )


# ============================================================
# DISPLAY LIVE EVENT
# ============================================================

def display_live_event(line):

    try:

        event = json.loads(
            line
        )

    except json.JSONDecodeError:

        return

    event_type = event.get(
        "type"
    )

    part = event.get(
        "part",
        {},
    )

    # --------------------------------------------------------
    # Agent text
    # --------------------------------------------------------

    if event_type == "text":

        text = part.get(
            "text"
        )

        if text:

            print()
            print(text)
            print()

        return

    # --------------------------------------------------------
    # Tool activity
    # --------------------------------------------------------

    if event_type in {
        "tool_use",
        "tool",
    }:

        tool_name = (
            part.get("tool")
            or part.get("name")
        )

        if tool_name:

            print(
                f"[tool] {tool_name}"
            )

        return

    # --------------------------------------------------------
    # Step completion
    # --------------------------------------------------------

    if event_type == "step_finish":

        tokens = part.get(
            "tokens",
            {},
        )

        total_tokens = tokens.get(
            "total",
            0,
        )

        cost = part.get(
            "cost",
            0,
        )

        print(
            "[step] "
            f"tokens={total_tokens} "
            f"cost=${cost:.6f}"
        )

        return

    # --------------------------------------------------------
    # Error
    # --------------------------------------------------------

    if event_type == "error":

        error = event.get(
            "error",
            {},
        )

        data = error.get(
            "data",
            {},
        )

        message = (
            data.get("message")
            or str(error)
        )

        print(
            f"[error] {message}"
        )


# ============================================================
# TERMINATE PROCESS
# ============================================================

def terminate_process(process):

    if process.poll() is not None:
        return

    try:

        process.terminate()

        process.wait(
            timeout=5
        )

    except subprocess.TimeoutExpired:

        process.kill()

        process.wait()


# ============================================================
# STEP 4 — RUN SELECTED AGENT WITH LIVE STREAMING
# ============================================================

def execute_agent(
    agent,
    request_text,
    request_name,
):

    print()
    print("=" * 60)
    print("3. AGENT EXECUTION")
    print("=" * 60)

    print(
        f"Agent     : {agent}"
    )

    print(
        f"Workspace : {SERVICE_ROOT}"
    )

    command = [
        opencode_binary(),
        "run",
        "--agent",
        agent,
        "--format",
        "json",
        request_text,
    ]

    # --------------------------------------------------------
    # Create telemetry file BEFORE OpenCode starts
    # --------------------------------------------------------

    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    jsonl_path = (
        RUNS_DIR
        / f"{request_name}_primary.jsonl"
    )

    print(
        f"Telemetry : {jsonl_path}"
    )

    print()
    print(
        "OpenCode running..."
    )
    print()

    # --------------------------------------------------------
    # Start timer
    # --------------------------------------------------------

    start = time.perf_counter()

    # --------------------------------------------------------
    # Start OpenCode
    # --------------------------------------------------------

    process = subprocess.Popen(
        command,
        cwd=SERVICE_ROOT,

        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,

        text=True,
        encoding="utf-8",
        errors="replace",

        bufsize=1,
    )

    # --------------------------------------------------------
    # Queue used by stdout/stderr reader threads
    # --------------------------------------------------------

    output_queue = queue.Queue()

    stdout_thread = threading.Thread(
        target=stream_reader,
        args=(
            process.stdout,
            output_queue,
            "stdout",
        ),
        daemon=True,
    )

    stderr_thread = threading.Thread(
        target=stream_reader,
        args=(
            process.stderr,
            output_queue,
            "stderr",
        ),
        daemon=True,
    )

    stdout_thread.start()
    stderr_thread.start()

    stdout_finished = False
    stderr_finished = False

    stderr_lines = []

    timed_out = False

    # --------------------------------------------------------
    # Stream telemetry to disk
    # --------------------------------------------------------

    with jsonl_path.open(
        "w",
        encoding="utf-8",
        buffering=1,
    ) as telemetry_file:

        while True:

            elapsed = (
                time.perf_counter()
                - start
            )

            # ------------------------------------------------
            # TRUE WALL-CLOCK TIMEOUT
            # ------------------------------------------------

            if elapsed >= AGENT_TIMEOUT:

                timed_out = True

                print()
                print(
                    f"[timeout] Agent exceeded "
                    f"{AGENT_TIMEOUT} seconds."
                )

                terminate_process(
                    process
                )

                break

            # ------------------------------------------------
            # Read next available output
            # ------------------------------------------------

            try:

                stream_name, line = (
                    output_queue.get(
                        timeout=0.2
                    )
                )

            except queue.Empty:

                # Process exited and both streams drained.
                if (
                    process.poll()
                    is not None
                    and stdout_finished
                    and stderr_finished
                ):
                    break

                continue

            # ------------------------------------------------
            # Stream completed
            # ------------------------------------------------

            if line is None:

                if stream_name == "stdout":
                    stdout_finished = True

                elif stream_name == "stderr":
                    stderr_finished = True

                if (
                    process.poll()
                    is not None
                    and stdout_finished
                    and stderr_finished
                ):
                    break

                continue

            # ------------------------------------------------
            # STDOUT = OpenCode JSONL telemetry
            # ------------------------------------------------

            if stream_name == "stdout":

                telemetry_file.write(
                    line
                )

                # Make event visible on disk immediately.
                telemetry_file.flush()

                display_live_event(
                    line
                )

            # ------------------------------------------------
            # STDERR
            # ------------------------------------------------

            elif stream_name == "stderr":

                stderr_lines.append(
                    line
                )

    # --------------------------------------------------------
    # Wait for reader threads briefly
    # --------------------------------------------------------

    stdout_thread.join(
        timeout=1
    )

    stderr_thread.join(
        timeout=1
    )

    elapsed = (
        time.perf_counter()
        - start
    )

    # --------------------------------------------------------
    # Timeout
    # --------------------------------------------------------

    if timed_out:

        print()
        print("=" * 60)
        print(
            "Execution Status: TIMEOUT"
        )
        print("=" * 60)

        print(
            f"Wall Time       : "
            f"{elapsed:.2f}s"
        )

        print(
            f"Telemetry       : "
            f"{jsonl_path}"
        )

        return {
            "status":
                "TIMEOUT",

            "wall_seconds":
                elapsed,

            "jsonl_path":
                str(jsonl_path),
        }

    # --------------------------------------------------------
    # Obtain return code
    # --------------------------------------------------------

    return_code = (
        process.wait()
    )

    # --------------------------------------------------------
    # Model / OpenCode failure
    # --------------------------------------------------------

    if return_code != 0:

        print()
        print("=" * 60)
        print(
            "Execution Status: MODEL_ERROR"
        )
        print("=" * 60)

        print(
            f"Return Code     : "
            f"{return_code}"
        )

        stderr = "".join(
            stderr_lines
        )

        if stderr:

            print()
            print("STDERR:")
            print(
                stderr[-5000:]
            )

        print(
            f"Telemetry       : "
            f"{jsonl_path}"
        )

        return {
            "status":
                "MODEL_ERROR",

            "wall_seconds":
                elapsed,

            "jsonl_path":
                str(jsonl_path),
        }

    # --------------------------------------------------------
    # Success
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print(
        "Execution Status: COMPLETED"
    )
    print("=" * 60)

    print(
        f"Wall Time       : "
        f"{elapsed:.2f}s"
    )

    print(
        f"Telemetry       : "
        f"{jsonl_path}"
    )

    return {
        "status":
            "COMPLETED",

        "wall_seconds":
            elapsed,

        "jsonl_path":
            str(jsonl_path),
    }


# ============================================================
# SAVE FINAL RESULT
# ============================================================

def save_result(
    request_name,
    classification,
    agent,
    execution,
):

    result = {

        "request":
            request_name,

        "classification":
            classification,

        "selected_agent":
            agent,

        "workspace":
            str(SERVICE_ROOT),

        "execution":
            execution,
    }

    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        RUNS_DIR
        / f"{request_name}_result.json"
    )

    path.write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    return path


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) != 2:

        print()
        print("Usage:")

        print(
            "python run_router.py "
            "tasks/request_01.md"
        )

        sys.exit(1)

    # --------------------------------------------------------
    # Validate environment
    # --------------------------------------------------------

    validate_environment()

    # --------------------------------------------------------
    # Read engineering request
    # --------------------------------------------------------

    request_path = Path(
        sys.argv[1]
    ).resolve()

    if not request_path.exists():

        raise FileNotFoundError(
            request_path
        )

    request_name = (
        request_path.stem
    )

    request_text = (
        request_path.read_text(
            encoding="utf-8"
        )
    )

    # --------------------------------------------------------
    # Header
    # --------------------------------------------------------

    print()
    print("=" * 60)

    print(
        "LAB 3 — BENCHMARK-DERIVED MODEL ROUTER"
    )

    print("=" * 60)

    print()
    print(
        f"Request   : {request_name}"
    )

    print(
        f"Lab       : {LAB_DIR}"
    )

    print(
        f"Workspace : {SERVICE_ROOT}"
    )

    print(
        "Agents    : "
        f"{SERVICE_ROOT / '.opencode' / 'agent'}"
    )

    # ========================================================
    # 1. CLASSIFY
    # ========================================================

    classification = classify_task(
        request_text,
        request_name,
    )

    # ========================================================
    # 2. ROUTE
    # ========================================================

    policy = load_policy()

    agent = select_agent(
        classification,
        policy,
    )

    print()
    print("=" * 60)
    print("2. ROUTING DECISION")
    print("=" * 60)

    print(
        f"Task Type : "
        f"{classification['task_type']}"
    )

    print(
        f"Agent     : {agent}"
    )

    # ========================================================
    # 3. EXECUTE
    # ========================================================

    execution = execute_agent(
        agent,
        request_text,
        request_name,
    )

    # ========================================================
    # 4. SAVE RESULT
    # ========================================================

    result_path = save_result(
        request_name,
        classification,
        agent,
        execution,
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    print("=" * 60)
    print("FINAL RESULT")
    print("=" * 60)

    print(
        f"Status    : "
        f"{execution['status']}"
    )

    print(
        f"Agent     : "
        f"{agent}"
    )

    print(
        f"Workspace : "
        f"{SERVICE_ROOT}"
    )

    print()
    print(
        "Result artifact:"
    )

    print(
        result_path
    )

    print()
    print(
        "Run metrics with:"
    )

    print(
        "python metrics_helper.py "
        f"runs/{request_name}_primary.jsonl"
    )

    if execution["status"] == "COMPLETED":
        sys.exit(0)

    sys.exit(2)


if __name__ == "__main__":
    main()