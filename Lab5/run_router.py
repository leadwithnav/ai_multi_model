#!/usr/bin/env python3

"""
Lab 4 — Adaptive Model + Reasoning Router

Flow:

1. Read one engineering request.
2. Ask the classifier LLM for:
      - task_type
      - complexity
3. Python routing policy selects:
      - primary model
      - fallback model
      - reasoning effort
4. Run primary OpenCode coding agent.
5. Run deterministic acceptance test.
6. If acceptance test FAILS:
      - reset repository
      - run fallback model on the ORIGINAL request
      - verify again
7. Save raw OpenCode JSONL for metrics_helper.py.

Important:
- LLM makes semantic judgments.
- Python owns routing policy.
- Python/pytest owns verification.
- Fallback is ONLY for quality failure in this lab.
- Timeout/provider/model errors do NOT trigger fallback.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml


# ============================================================
# PATHS
# ============================================================

LAB_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = LAB_DIR.parent

SERVICE_ROOT = WORKSPACE_ROOT / "order_flow_service"


ACCEPTANCE_TEST_ROOT = (
    LAB_DIR
    / "acceptance_tests"
)

POLICY_FILE = (
    LAB_DIR
    / "config"
    / "routing_policy.yaml"
)

ARTIFACTS_DIR = (
    LAB_DIR
    / "runs"
)

RESET_SCRIPT = (
    LAB_DIR
    / "reset.sh"
)

CLASSIFIER_AGENT = "classifier"


# Map each request to its deterministic acceptance test.
TEST_MAP = {
    "request_01": "test_request_01.py",
    "request_02": "test_request_02.py",
    "request_03": "test_request_03.py",
}


# ============================================================
# OPENCODE EXECUTABLE
# ============================================================

def opencode_binary():
    """
    Windows installations commonly expose opencode.cmd.
    """

    if os.name == "nt":
        return "opencode.cmd"

    return "opencode"


# ============================================================
# OPENCODE JSONL PARSING
# ============================================================

def parse_opencode_output(stdout: str):
    """
    Extract final text from OpenCode JSONL.

    We deliberately do NOT calculate metrics here.

    Students will use metrics_helper.py separately.
    """

    text_parts = []

    for line in stdout.splitlines():

        line = line.strip()

        if not line:
            continue

        try:
            event = json.loads(line)

        except json.JSONDecodeError:
            continue

        part = event.get("part", {})

        if part.get("type") == "text":

            text = part.get("text")

            if text:
                text_parts.append(text)

    return "\n".join(text_parts).strip()


# ============================================================
# SAVE RAW OPENCODE JSONL
# ============================================================

def save_jsonl(
    request_name: str,
    role: str,
    stdout: str,
):
    """
    Save the untouched OpenCode --format json output.

    Example:

    artifacts/request_03_primary.jsonl
    artifacts/request_03_fallback.jsonl

    metrics_helper.py can process these later.
    """

    ARTIFACTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        ARTIFACTS_DIR
        / f"{request_name}_{role}.jsonl"
    )

    path.write_text(
        stdout,
        encoding="utf-8",
    )

    return path


# ============================================================
# STEP 1 — CLASSIFIER
# ============================================================

def classify_request(
    request_text: str,
    request_name: str,
):
    """
    LLM makes TWO semantic judgments:

    task_type:
        implementation
        debugging
        refactoring
        testing

    complexity:
        low
        medium
        high
    """

    print()
    print("=" * 60)
    print("1. CLASSIFICATION")
    print("=" * 60)


    # Compact only for classifier input.
    # Coding model still receives original full request.

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
            cwd=LAB_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )

    except subprocess.TimeoutExpired:

        raise RuntimeError(
            "Classifier timed out."
        )


    # Optional: save classifier telemetry too.
    classifier_path = save_jsonl(
        request_name,
        "classifier",
        result.stdout,
    )


    if result.returncode != 0:

        raise RuntimeError(
            "Classifier failed.\n\n"
            + result.stderr[-2000:]
        )


    response = parse_opencode_output(
        result.stdout
    )


    # Tolerate accidental Markdown fences.

    response = (
        response
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )


    try:

        classification = json.loads(
            response
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "Classifier did not return valid JSON."
            "\n\nClassifier response:\n"
            + response
        ) from exc


    # --------------------------------------------------------
    # Validate classifier output
    # --------------------------------------------------------

    allowed_task_types = {
        "implementation",
        "debugging",
        "refactoring",
        "testing",
    }

    allowed_complexities = {
        "low",
        "medium",
        "high",
    }


    task_type = classification.get(
        "task_type"
    )

    complexity = classification.get(
        "complexity"
    )


    if task_type not in allowed_task_types:

        raise RuntimeError(
            f"Classifier returned invalid "
            f"task_type: {task_type}"
        )


    if complexity not in allowed_complexities:

        raise RuntimeError(
            f"Classifier returned invalid "
            f"complexity: {complexity}"
        )


    print(
        f"Task Type  : {task_type}"
    )

    print(
        f"Complexity : {complexity}"
    )


    signals = classification.get(
        "signals",
        [],
    )


    if signals:

        print("\nSignals:")

        for signal in signals:
            print(f"  - {signal}")


    print(
        f"\nClassifier telemetry:"
        f"\n{classifier_path}"
    )


    return classification


# ============================================================
# STEP 2 — LOAD ROUTING POLICY
# ============================================================

def load_policy():

    if not POLICY_FILE.exists():

        raise FileNotFoundError(
            f"Routing policy not found:\n"
            f"{POLICY_FILE}"
        )


    with POLICY_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:

        return yaml.safe_load(f)


# ============================================================
# STEP 3 — ROUTING DECISION
# ============================================================

def select_route(
    classification: dict,
    policy: dict,
):
    """
    LLM does NOT choose models.

    Python deterministically maps:

        task_type
            ↓
        primary model
        fallback model

    and

        complexity
            ↓
        reasoning effort
    """

    task_type = (
        classification["task_type"]
    )

    complexity = (
        classification["complexity"]
    )


    try:

        model_policy = (
            policy["model_policy"]
                  [task_type]
        )

        primary_model = (
            model_policy["primary"]
        )

        fallback_model = (
            model_policy["fallback"]
        )

        reasoning_effort = (
            policy["reasoning_policy"]
                  [complexity]
        )

    except KeyError as exc:

        raise RuntimeError(
            "Routing policy is missing "
            f"a required mapping: {exc}"
        ) from exc


    primary_agent = (
        f"{primary_model}-"
        f"{reasoning_effort}"
    )

    fallback_agent = (
        f"{fallback_model}-"
        f"{reasoning_effort}"
    )


    return {

        "primary": {
            "model":
                primary_model,

            "reasoning_effort":
                reasoning_effort,

            "agent":
                primary_agent,
        },

        "fallback": {
            "model":
                fallback_model,

            "reasoning_effort":
                reasoning_effort,

            "agent":
                fallback_agent,
        },
    }


# ============================================================
# STEP 4 — RUN OPENCODE CODING AGENT
# ============================================================

def execute_agent(
    config: dict,
    request_text: str,
    request_name: str,
    role: str,
):
    """
    Run one coding agent.

    role:
        primary
        fallback

    Raw OpenCode JSONL is written to artifacts/.
    """

    print()
    print("=" * 60)
    print(
        f"{role.upper()} EXECUTION"
    )
    print("=" * 60)

    print(
        f"Model     : {config['model']}"
    )

    print(
        "Reasoning : "
        f"{config['reasoning_effort']}"
    )

    print(
        f"Agent     : {config['agent']}"
    )


    command = [
        opencode_binary(),
        "run",
        "--agent",
        config["agent"],
        "--format",
        "json",
        request_text,
    ]


    start = time.perf_counter()


    try:

        result = subprocess.run(
            command,
            cwd=LAB_DIR,
            capture_output=True,
            text=True,
            timeout=300,
        )


    except subprocess.TimeoutExpired as exc:

        elapsed = (
            time.perf_counter()
            - start
        )


        stdout = exc.stdout or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode(
                errors="replace"
            )


        jsonl_path = save_jsonl(
            request_name,
            role,
            stdout,
        )


        print(
            "\nExecution Status: TIMEOUT"
        )

        print(
            f"Wall Time       : "
            f"{elapsed:.2f}s"
        )

        print(
            f"Telemetry       : "
            f"{jsonl_path}"
        )


        return {
            "status": "TIMEOUT",
            "jsonl_path":
                str(jsonl_path),
            "wall_seconds":
                elapsed,
        }


    elapsed = (
        time.perf_counter()
        - start
    )


    jsonl_path = save_jsonl(
        request_name,
        role,
        result.stdout,
    )


    if result.returncode != 0:

        print(
            "\nExecution Status: MODEL_ERROR"
        )

        print(
            result.stderr[-1500:]
        )


        return {
            "status":
                "MODEL_ERROR",

            "jsonl_path":
                str(jsonl_path),

            "wall_seconds":
                elapsed,
        }


    print(
        "\nExecution Status: COMPLETED"
    )

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

        "jsonl_path":
            str(jsonl_path),

        "wall_seconds":
            elapsed,
    }


# ============================================================
# STEP 5 — DETERMINISTIC ACCEPTANCE TEST
# ============================================================

def verify(
    request_name: str,
):
    """
    Run the acceptance test for this request.

    Exit code:
        0 -> PASS
        1 -> QUALITY FAILURE
        anything else -> verification/infrastructure problem
    """

    print()
    print("=" * 60)
    print("ACCEPTANCE TEST")
    print("=" * 60)


    test_filename = TEST_MAP.get(
        request_name
    )


    if not test_filename:

        raise RuntimeError(
            f"No acceptance test configured "
            f"for {request_name}"
        )


    test_file = (
        ACCEPTANCE_TEST_ROOT
        / test_filename
    )


    if not test_file.exists():

        raise FileNotFoundError(
            f"Acceptance test not found:\n"
            f"{test_file}"
        )


    env = os.environ.copy()

    # Keep globally installed pytest plugins
    # from contaminating the lab.
    env[
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD"
    ] = "1"


    command = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-q",
        "--tb=short",
        "-p",
        "pytest_asyncio.plugin",
    ]


    try:

        result = subprocess.run(
            command,
            cwd=SERVICE_ROOT,
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
        )


    except subprocess.TimeoutExpired:

        print(
            "Verification: ERROR"
        )

        print(
            "Acceptance tests timed out."
        )


        return {
            "status":
                "VERIFICATION_ERROR",

            "passed":
                None,

            "output":
                "Acceptance tests timed out.",
        }


    output = (
        result.stdout
        + "\n"
        + result.stderr
    ).strip()


    # --------------------------------------------------------
    # PASS
    # --------------------------------------------------------

    if result.returncode == 0:

        print("Verification: PASSED")

        print()

        print(
            result.stdout[-1500:]
        )


        return {
            "status":
                "PASSED",

            "passed":
                True,

            "output":
                output[-2000:],
        }


    # --------------------------------------------------------
    # QUALITY FAILURE
    # --------------------------------------------------------

    if result.returncode == 1:

        print("Verification: FAILED")

        print()

        print(
            output[-2000:]
        )


        return {
            "status":
                "FAILED",

            "passed":
                False,

            "output":
                output[-2000:],
        }


    # --------------------------------------------------------
    # INFRASTRUCTURE / PYTEST ERROR
    # --------------------------------------------------------

    print(
        "Verification: ERROR"
    )

    print()

    print(
        output[-2000:]
    )


    return {
        "status":
            "VERIFICATION_ERROR",

        "passed":
            None,

        "output":
            output[-2000:],
    }


# ============================================================
# RESET BEFORE FALLBACK
# ============================================================

def reset_repository():
    """
    Lab 4 does not teach context handoff yet.

    Therefore fallback receives:
        - original repository
        - original engineering request

    Context/state handoff can be introduced in a later lab.
    """

    print()
    print("Resetting repository before fallback...")


    if not RESET_SCRIPT.exists():

        raise FileNotFoundError(
            f"reset.sh not found:\n"
            f"{RESET_SCRIPT}"
        )


    result = subprocess.run(
        [
            "bash",
            str(RESET_SCRIPT),
        ],
        cwd=LAB_DIR,
        capture_output=True,
        text=True,
    )


    if result.returncode != 0:

        raise RuntimeError(
            "Repository reset failed:\n"
            + result.stderr
        )


    print(
        result.stdout.strip()
    )


# ============================================================
# SAVE RESULT SUMMARY
# ============================================================

def save_result(
    request_name,
    classification,
    route,
    primary,
    primary_verification,
    fallback,
    fallback_verification,
):
    """
    Save routing/verification information.

    Cost/token metrics remain in the raw JSONL
    and are inspected using metrics_helper.py.
    """

    result = {

        "request":
            request_name,

        "classification":
            classification,

        "route":
            route,

        "primary": {
            "execution":
                primary,

            "verification":
                primary_verification,
        },

        "fallback_used":
            fallback is not None,

        "fallback": (
            {
                "execution":
                    fallback,

                "verification":
                    fallback_verification,
            }
            if fallback
            else None
        ),
    }


    ARTIFACTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    path = (
        ARTIFACTS_DIR
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

        print(
            "\nUsage:"
        )

        print(
            "python run_router.py "
            "tasks/request_01.md"
        )

        sys.exit(1)


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


    if request_name not in TEST_MAP:

        raise RuntimeError(
            f"No acceptance test mapped "
            f"for {request_name}"
        )


    request_text = (
        request_path.read_text(
            encoding="utf-8"
        )
    )


    print()
    print("=" * 60)
    print(
        "LAB 4 — ADAPTIVE MODEL + REASONING ROUTING"
    )
    print("=" * 60)

    print(
        f"\nRequest: {request_name}"
    )


    # ========================================================
    # 1. CLASSIFY
    # ========================================================

    classification = classify_request(
        request_text,
        request_name,
    )


    # ========================================================
    # 2. APPLY ROUTING POLICY
    # ========================================================

    policy = load_policy()


    route = select_route(
        classification,
        policy,
    )


    print()
    print("=" * 60)
    print("2. ROUTING DECISION")
    print("=" * 60)


    print(
        "Primary Model  : "
        f"{route['primary']['model']}"
    )

    print(
        "Fallback Model : "
        f"{route['fallback']['model']}"
    )

    print(
        "Reasoning      : "
        f"{route['primary']['reasoning_effort']}"
    )


    # ========================================================
    # 3. PRIMARY EXECUTION
    # ========================================================

    primary = execute_agent(
        route["primary"],
        request_text,
        request_name,
        "primary",
    )


    # Operational failure.
    #
    # Do NOT fallback here.
    # Retry/timeout/provider failover belongs to Lab 5.

    if primary["status"] != "COMPLETED":

        print()
        print("=" * 60)
        print("FINAL RESULT")
        print("=" * 60)

        print(
            "Primary model did not complete "
            "successfully."
        )

        print(
            "No quality fallback attempted."
        )

        print(
            "\nOperational resilience "
            "is covered in Lab 5."
        )

        sys.exit(2)


    # ========================================================
    # 4. VERIFY PRIMARY
    # ========================================================

    primary_verification = verify(
        request_name
    )


    fallback = None
    fallback_verification = None


    # ========================================================
    # 5. QUALITY FALLBACK
    # ========================================================

    if (
        primary_verification["status"]
        == "FAILED"
    ):

        print()
        print("=" * 60)
        print("QUALITY FALLBACK")
        print("=" * 60)

        print(
            "Primary model did not meet "
            "the quality bar."
        )

        print(
            "Activating fallback model."
        )


        # ----------------------------------------------------
        # No handoff in this lab.
        #
        # Restore baseline and give fallback the same
        # original request.
        # ----------------------------------------------------

        reset_repository()


        fallback = execute_agent(
            route["fallback"],
            request_text,
            request_name,
            "fallback",
        )


        if fallback["status"] == "COMPLETED":

            fallback_verification = verify(
                request_name
            )


        else:

            print()
            print(
                "Fallback model encountered "
                "an operational error."
            )


    # ========================================================
    # 6. FINAL STATUS
    # ========================================================

    if fallback is None:

        completed = (
            primary_verification["status"]
            == "PASSED"
        )

    else:

        completed = bool(
            fallback_verification
            and
            fallback_verification["status"]
            == "PASSED"
        )


    # ========================================================
    # 7. SAVE SUMMARY
    # ========================================================

    result_path = save_result(
        request_name,
        classification,
        route,
        primary,
        primary_verification,
        fallback,
        fallback_verification,
    )


    # ========================================================
    # 8. STUDENT OUTPUT
    # ========================================================

    print()
    print("=" * 60)
    print("FINAL RESULT")
    print("=" * 60)


    print(
        "Completed     : "
        f"{'YES' if completed else 'NO'}"
    )

    print(
        "Fallback Used : "
        f"{'YES' if fallback else 'NO'}"
    )


    print(
        f"\nResult artifact:\n"
        f"{result_path}"
    )


    print()
    print("=" * 60)
    print("METRICS")
    print("=" * 60)


    print(
        "\nRun metrics for the primary:"
    )

    print(
        "python metrics_helper.py "
        f"artifacts/{request_name}_primary.jsonl"
    )


    if fallback:

        print(
            "\nRun metrics for the fallback:"
        )

        print(
            "python metrics_helper.py "
            f"artifacts/{request_name}_fallback.jsonl"
        )


    print()

    if completed:
        sys.exit(0)

    sys.exit(1)


if __name__ == "__main__":
    main()