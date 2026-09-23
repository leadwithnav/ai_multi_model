#!/usr/bin/env python3
"""
Lab 6 - Intelligent Failure Recovery

Flow:

Request
  ↓
Classifier
  ↓
Initial Routing Policy
  ↓
Model + Reasoning
  ↓
Coding Agent
  ↓
Deterministic Acceptance Test
  ↓
PASS → Done

FAIL
  ↓
Diagnostician
  ↓
Failure Category
  ↓
Deterministic Recovery Policy
  ↓
Retry Same Configuration
OR
Escalate Model
OR
Stop
  ↓
Verify Once More

Maximum coding attempts: 2
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import yaml

from run_router import (
    route_request,
    opencode_binary,
    extract_text_from_jsonl,
)


# ============================================================
# PATHS
# ============================================================

LAB_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = LAB_DIR.parent

SERVICE_ROOT = (
    WORKSPACE_ROOT
    / "order_flow_service"
)

ACCEPTANCE_TEST_ROOT = (
    LAB_DIR
    / "acceptance_tests"
)

RECOVERY_POLICY_FILE = (
    LAB_DIR
    / "config"
    / "recovery_policy.yaml"
)

RUNS_DIR = LAB_DIR / "runs"


# ============================================================
# ACCEPTANCE TEST MAPPING
# ============================================================

TEST_MAP = {
    "request_01":
        "test_request_01.py",

    "request_02":
        "test_request_02.py",

    "request_03":
        "test_request_03.py",
}


# ============================================================
# UTILITIES
# ============================================================

def save_json(path, data):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_recovery_policy():

    if not RECOVERY_POLICY_FILE.exists():

        raise FileNotFoundError(
            "Recovery policy not found:\n"
            f"{RECOVERY_POLICY_FILE}"
        )

    with open(
        RECOVERY_POLICY_FILE,
        "r",
        encoding="utf-8",
    ) as f:

        return yaml.safe_load(f)


def clean_json_text(text):

    text = text.strip()

    if text.startswith("```"):

        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        text = "\n".join(
            lines
        ).strip()

    return text


# ============================================================
# PREFLIGHT CHECK
# ============================================================

def preflight_check(request_name):

    print()
    print("=" * 60)
    print("PREFLIGHT CHECK")
    print("=" * 60)

    if not SERVICE_ROOT.exists():

        raise FileNotFoundError(
            "order_flow_service not found:\n"
            f"{SERVICE_ROOT}"
        )

    if not ACCEPTANCE_TEST_ROOT.exists():

        raise FileNotFoundError(
            "Acceptance-test directory not found:\n"
            f"{ACCEPTANCE_TEST_ROOT}"
        )

    test_filename = TEST_MAP.get(
        request_name
    )

    if not test_filename:

        raise RuntimeError(
            "No acceptance test mapped for "
            f"{request_name}"
        )

    test_file = (
        ACCEPTANCE_TEST_ROOT
        / test_filename
    )

    if not test_file.exists():

        raise FileNotFoundError(
            "Acceptance test not found:\n"
            f"{test_file}"
        )

    print(
        f"Service root    : {SERVICE_ROOT}"
    )

    print(
        f"Acceptance test : {test_file}"
    )

    print("Preflight       : OK")


# ============================================================
# CODING AGENT
# ============================================================

def execute_coding_agent(
    agent_name,
    prompt,
    request_name,
    attempt_number,
):

    print()
    print("=" * 60)
    print(
        f"CODING ATTEMPT {attempt_number}"
    )
    print("=" * 60)

    print(
        f"Agent : {agent_name}"
    )

    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    jsonl_path = (
        RUNS_DIR
        / (
            f"{request_name}"
            f"_attempt{attempt_number}"
            f"_{agent_name}.jsonl"
        )
    )

    command = [
        opencode_binary(),
        "run",
        "--agent",
        agent_name,
        "--format",
        "json",
        prompt,
    ]

    start = time.perf_counter()

    try:

        result = subprocess.run(
            command,
            cwd=LAB_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )

    except subprocess.TimeoutExpired:

        elapsed = (
            time.perf_counter()
            - start
        )

        print(
            f"MODEL TIMEOUT after "
            f"{elapsed:.2f}s"
        )

        return {
            "status":
                "MODEL_TIMEOUT",

            "agent":
                agent_name,

            "wall_clock_seconds":
                round(
                    elapsed,
                    2,
                ),

            "jsonl_file":
                str(jsonl_path),
        }

    elapsed = (
        time.perf_counter()
        - start
    )

    jsonl_path.write_text(
        result.stdout or "",
        encoding="utf-8",
    )

    if result.returncode != 0:

        print(
            "Operational model error."
        )

        if result.stderr:

            print()
            print("Model stderr:")
            print("-" * 60)
            print(
                result.stderr[-3000:]
            )
            print("-" * 60)

        return {
            "status":
                "MODEL_ERROR",

            "agent":
                agent_name,

            "wall_clock_seconds":
                round(
                    elapsed,
                    2,
                ),

            "jsonl_file":
                str(jsonl_path),

            "stderr":
                (
                    result.stderr
                    or ""
                )[-3000:],
        }

    print(
        f"Completed : {elapsed:.2f}s"
    )

    print(
        f"Telemetry : {jsonl_path}"
    )

    # --------------------------------------------------------
    # Extract and show the model's human-readable response.
    # --------------------------------------------------------

    response_text = (
        extract_text_from_jsonl(
            result.stdout or ""
        )
    )

    if response_text:

        print()
        print("Agent response:")
        print("-" * 60)
        print(response_text)
        print("-" * 60)

    return {
        "status":
            "COMPLETED",

        "agent":
            agent_name,

        "wall_clock_seconds":
            round(
                elapsed,
                2,
            ),

        "jsonl_file":
            str(jsonl_path),

        "response_text":
            response_text,
    }


# ============================================================
# DETERMINISTIC VERIFICATION
# ============================================================

def verify(request_name):

    print()
    print("=" * 60)
    print("DETERMINISTIC VERIFICATION")
    print("=" * 60)

    test_filename = (
        TEST_MAP.get(
            request_name
        )
    )

    if not test_filename:

        raise RuntimeError(
            "No acceptance test mapped "
            f"for {request_name}"
        )

    test_file = (
        ACCEPTANCE_TEST_ROOT
        / test_filename
    )

    if not test_file.exists():

        raise FileNotFoundError(
            "Acceptance test not found:\n"
            f"{test_file}"
        )

    if not SERVICE_ROOT.exists():

        raise FileNotFoundError(
            "Service root not found:\n"
            f"{SERVICE_ROOT}"
        )

    print(
        f"Test    : {test_file}"
    )

    print(
        f"Service : {SERVICE_ROOT}"
    )

    env = os.environ.copy()

    env[
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD"
    ] = "1"

    command = [
        sys.executable,
        "-m",
        "pytest",
        str(test_file),
        "-q",
        "-p",
        "pytest_asyncio.plugin",
        "--tb=short",
    ]

    print()
    print(
        "Running : "
        + " ".join(
            str(x)
            for x in command
        )
    )

    try:

        result = subprocess.run(
            command,
            cwd=SERVICE_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            env=env,
        )

    except subprocess.TimeoutExpired:

        print()
        print(
            "RESULT : VERIFICATION ERROR"
        )

        print(
            "Reason : acceptance test "
            "timed out"
        )

        return {
            "status":
                "VERIFICATION_ERROR",

            "reason":
                "TIMEOUT",

            "output":
                "Acceptance test timed out.",
        }

    output = (
        (result.stdout or "")
        + "\n"
        + (result.stderr or "")
    ).strip()

    print()
    print(
        "Pytest exit code : "
        f"{result.returncode}"
    )

    # --------------------------------------------------------
    # pytest exit code 0
    #
    # Acceptance tests passed.
    # --------------------------------------------------------

    if result.returncode == 0:

        print("RESULT : PASS")

        if output:

            print()
            print("Pytest output:")
            print("-" * 60)
            print(
                output[-5000:]
            )
            print("-" * 60)

        return {
            "status":
                "PASSED",

            "exit_code":
                result.returncode,

            "output":
                output[-5000:],
        }

    # --------------------------------------------------------
    # pytest exit code 1
    #
    # Tests executed successfully, but the implementation
    # failed the quality bar.
    #
    # This IS a coding-quality failure.
    # Send it to the diagnostician.
    # --------------------------------------------------------

    if result.returncode == 1:

        print("RESULT : FAIL")

        print()
        print(
            "Acceptance test failure:"
        )
        print("-" * 60)
        print(
            output[-5000:]
        )
        print("-" * 60)

        return {
            "status":
                "FAILED",

            "exit_code":
                result.returncode,

            "output":
                output[-5000:],
        }

    # --------------------------------------------------------
    # Any other pytest exit code
    #
    # pytest/test infrastructure itself failed.
    #
    # Do NOT send this to quality recovery.
    # --------------------------------------------------------

    print(
        "RESULT : VERIFICATION ERROR"
    )

    print()
    print(
        "Pytest infrastructure error:"
    )
    print("-" * 60)
    print(
        output[-5000:]
    )
    print("-" * 60)

    return {
        "status":
            "VERIFICATION_ERROR",

        "exit_code":
            result.returncode,

        "reason":
            "PYTEST_ERROR",

        "output":
            output[-5000:],
    }


# ============================================================
# DIAGNOSTICIAN
# ============================================================

def diagnose_failure(
    request_name,
    request_text,
    verification_output,
):

    print()
    print("=" * 60)
    print("FAILURE DIAGNOSIS")
    print("=" * 60)

    prompt = f"""
ORIGINAL ENGINEERING REQUEST

{request_text}


ACCEPTANCE TEST FAILURE

{verification_output}


The current order_flow_service repository contains
the failed coding attempt.

Inspect the implementation if needed.

Classify WHY the solution failed.

Return only the JSON required by your
diagnostician instructions.
""".strip()

    jsonl_path = (
        RUNS_DIR
        / f"{request_name}_diagnostician.jsonl"
    )

    command = [
        opencode_binary(),
        "run",
        "--agent",
        "diagnostician",
        "--format",
        "json",
        prompt,
    ]

    start = time.perf_counter()

    try:

        result = subprocess.run(
            command,
            cwd=LAB_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

    except subprocess.TimeoutExpired as exc:

        raise RuntimeError(
            "Diagnostician timed out."
        ) from exc

    elapsed = (
        time.perf_counter()
        - start
    )

    jsonl_path.write_text(
        result.stdout or "",
        encoding="utf-8",
    )

    if result.returncode != 0:

        raise RuntimeError(
            "Diagnostician failed.\n\n"
            + (result.stderr or "")
        )

    response_text = (
        extract_text_from_jsonl(
            result.stdout
        )
    )

    response_text = (
        clean_json_text(
            response_text
        )
    )

    try:

        diagnosis = json.loads(
            response_text
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "Diagnostician did not return "
            "valid JSON.\n\n"
            f"Received:\n{response_text}"
        ) from exc

    allowed_categories = {
        "SYNTAX_ERROR",
        "INCOMPLETE_FIX",
        "WRONG_APPROACH",
        "TEST_INFRASTRUCTURE_ISSUE",
    }

    category = diagnosis.get(
        "failure_category"
    )

    if category not in allowed_categories:

        raise RuntimeError(
            "Invalid failure category: "
            f"{category}"
        )

    diagnosis[
        "wall_clock_seconds"
    ] = round(
        elapsed,
        2,
    )

    diagnosis[
        "jsonl_file"
    ] = str(
        jsonl_path
    )

    save_json(
        RUNS_DIR
        / f"{request_name}_diagnosis.json",
        diagnosis,
    )

    print(
        f"Category : {category}"
    )

    print(
        "Reason   : "
        f"{diagnosis.get('reason', '')}"
    )

    return diagnosis


# ============================================================
# DETERMINISTIC RECOVERY POLICY
# ============================================================

def choose_recovery(
    diagnosis,
    initial_route,
    policy,
):

    category = diagnosis[
        "failure_category"
    ]

    try:

        rule = (
            policy["recovery_policy"]
            [category]
        )

    except KeyError as exc:

        raise RuntimeError(
            "No recovery policy for "
            f"{category}"
        ) from exc

    action = rule["action"]

    print()
    print("=" * 60)
    print("RECOVERY DECISION")
    print("=" * 60)

    print(
        f"Failure Category : {category}"
    )

    print(
        f"Policy Action    : {action}"
    )

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    if action == "stop":

        return {
            "action":
                "stop",

            "reason":
                rule.get(
                    "reason",
                    "human_review",
                ),
        }

    # --------------------------------------------------------
    # SAME MODEL + SAME REASONING
    # --------------------------------------------------------

    if action == "retry_same_configuration":

        recovery = {
            "action":
                action,

            "model":
                initial_route["model"],

            "reasoning":
                initial_route["reasoning"],

            "agent":
                initial_route["agent"],

            "prompt_mode":
                rule.get(
                    "prompt_mode",
                    "targeted",
                ),
        }

        print(
            "Recovery Agent   : "
            f"{recovery['agent']}"
        )

        return recovery

    # --------------------------------------------------------
    # ESCALATE MODEL
    #
    # Keep reasoning effort unchanged.
    # --------------------------------------------------------

    if action == "escalate_model":

        escalation_model = (
            initial_route.get(
                "escalation_model"
            )
        )

        if not escalation_model:

            raise RuntimeError(
                "Recovery requires model "
                "escalation, but the initial "
                "route has no escalation_model."
            )

        reasoning = (
            initial_route["reasoning"]
        )

        recovery_agent = (
            f"{escalation_model}-"
            f"{reasoning}"
        )

        recovery = {
            "action":
                action,

            "model":
                escalation_model,

            "reasoning":
                reasoning,

            "agent":
                recovery_agent,

            "prompt_mode":
                rule.get(
                    "prompt_mode",
                    "targeted",
                ),
        }

        print(
            "Recovery Agent   : "
            f"{recovery_agent}"
        )

        return recovery

    raise RuntimeError(
        "Unsupported recovery action: "
        f"{action}"
    )


# ============================================================
# RECOVERY HANDOFF PROMPT
# ============================================================

def build_recovery_prompt(
    request_text,
    verification_output,
    diagnosis,
    recovery,
):

    prompt_mode = recovery.get(
        "prompt_mode",
        "targeted",
    )

    if prompt_mode == "syntax_strict":

        instruction = """
Repair the implementation.

The previous attempt contains a syntax or
code-structure error.

Correct that error and make sure modified
Python files compile successfully before
finishing.

Preserve correct parts of the previous attempt.
""".strip()

    else:

        instruction = """
Repair the current implementation based on
the diagnosis below.

Preserve correct parts of the previous attempt.

Do not simply repeat the same failed mechanism.

Specifically address the failure identified
by the diagnostician.
""".strip()

    return f"""
ORIGINAL ENGINEERING REQUEST

{request_text}


PREVIOUS ATTEMPT

A coding model already attempted this request.

The current order_flow_service repository
contains that attempt.


ACCEPTANCE TEST FAILURE

{verification_output}


FAILURE CATEGORY

{diagnosis["failure_category"]}


DIAGNOSIS

{diagnosis.get("reason", "")}


RECOVERY INSTRUCTION

{instruction}


Do not modify acceptance tests.
Do not modify unrelated functionality.
Preserve existing public interfaces.
""".strip()


# ============================================================
# MAIN WORKFLOW
# ============================================================

def main():

    if len(sys.argv) != 2:

        print(
            "Usage:\n"
            "  python run_recovery.py "
            "tasks/request_01.md"
        )

        sys.exit(1)

    RUNS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # 1. CLASSIFY + ROUTE
    # --------------------------------------------------------

    routed = route_request(
        sys.argv[1]
    )

    request_name = (
        routed["request_name"]
    )

    request_text = (
        routed["request_text"]
    )

    classification = (
        routed["classification"]
    )

    initial_route = (
        routed["route"]
    )

    # --------------------------------------------------------
    # 2. PREFLIGHT CHECK
    #
    # Check paths before spending another model call.
    # This does NOT run the acceptance test.
    # --------------------------------------------------------

    preflight_check(
        request_name
    )

    # --------------------------------------------------------
    # 3. ATTEMPT 1
    # --------------------------------------------------------

    attempt1 = (
        execute_coding_agent(
            agent_name=
                initial_route["agent"],

            prompt=
                request_text,

            request_name=
                request_name,

            attempt_number=1,
        )
    )

    # --------------------------------------------------------
    # Model/provider failed operationally.
    #
    # Do NOT quality-recover.
    # Operational retry/failover belongs to the
    # resilience lab.
    # --------------------------------------------------------

    if (
        attempt1["status"]
        != "COMPLETED"
    ):

        final_result = {
            "final_status":
                "OPERATIONAL_MODEL_FAILURE",

            "classification":
                classification,

            "initial_route":
                initial_route,

            "attempt1":
                attempt1,
        }

        save_json(
            RUNS_DIR
            / f"{request_name}_result.json",
            final_result,
        )

        print()
        print(
            "STOP: model/provider "
            "execution failed."
        )

        print(
            "Operational retry/failover "
            "belongs to the resilience lab."
        )

        return

    # --------------------------------------------------------
    # 4. VERIFY ATTEMPT 1
    # --------------------------------------------------------

    verification1 = verify(
        request_name
    )

    # --------------------------------------------------------
    # PASS FIRST TRY
    # --------------------------------------------------------

    if (
        verification1["status"]
        == "PASSED"
    ):

        final_result = {
            "final_status":
                "PASSED_FIRST_TRY",

            "classification":
                classification,

            "initial_route":
                initial_route,

            "attempt1":
                attempt1,

            "verification1":
                verification1,
        }

        save_json(
            RUNS_DIR
            / f"{request_name}_result.json",
            final_result,
        )

        print()
        print("=" * 60)
        print("FINAL RESULT")
        print("=" * 60)

        print(
            "Status : PASSED_FIRST_TRY"
        )

        return

    # --------------------------------------------------------
    # pytest/test infrastructure itself failed.
    #
    # Do NOT diagnose this as a coding-quality failure.
    # --------------------------------------------------------

    if (
        verification1["status"]
        == "VERIFICATION_ERROR"
    ):

        final_result = {
            "final_status":
                "VERIFICATION_ERROR",

            "classification":
                classification,

            "initial_route":
                initial_route,

            "attempt1":
                attempt1,

            "verification1":
                verification1,
        }

        save_json(
            RUNS_DIR
            / f"{request_name}_result.json",
            final_result,
        )

        print()
        print("=" * 60)
        print("WORKFLOW STOPPED")
        print("=" * 60)

        print(
            "Acceptance-test infrastructure "
            "failed."
        )

        print(
            "This is NOT being treated as a "
            "coding-quality failure."
        )

        print(
            "Fix the pytest/test-environment "
            "problem and rerun the experiment."
        )

        return

    # --------------------------------------------------------
    # 5. DIAGNOSE QUALITY FAILURE
    # --------------------------------------------------------

    diagnosis = diagnose_failure(
        request_name,
        request_text,
        verification1["output"],
    )

    # --------------------------------------------------------
    # 6. APPLY RECOVERY POLICY
    # --------------------------------------------------------

    recovery_policy = (
        load_recovery_policy()
    )

    recovery = choose_recovery(
        diagnosis,
        initial_route,
        recovery_policy,
    )

    # --------------------------------------------------------
    # 7. HUMAN STOP
    # --------------------------------------------------------

    if recovery["action"] == "stop":

        final_result = {
            "final_status":
                "HALTED_FOR_HUMAN_REVIEW",

            "classification":
                classification,

            "initial_route":
                initial_route,

            "attempt1":
                attempt1,

            "verification1":
                verification1,

            "diagnosis":
                diagnosis,

            "recovery":
                recovery,
        }

        save_json(
            RUNS_DIR
            / f"{request_name}_result.json",
            final_result,
        )

        print()
        print("=" * 60)
        print("FINAL RESULT")
        print("=" * 60)

        print(
            "Status : "
            "HUMAN REVIEW REQUIRED"
        )

        return

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # NO RESET HERE.
    #
    # Attempt 2 sees Attempt 1's implementation.
    #
    # This is deliberate context handoff.
    # --------------------------------------------------------

    recovery_prompt = (
        build_recovery_prompt(
            request_text,
            verification1["output"],
            diagnosis,
            recovery,
        )
    )

    # --------------------------------------------------------
    # 8. ATTEMPT 2
    # --------------------------------------------------------

    attempt2 = (
        execute_coding_agent(
            agent_name=
                recovery["agent"],

            prompt=
                recovery_prompt,

            request_name=
                request_name,

            attempt_number=2,
        )
    )

    if (
        attempt2["status"]
        != "COMPLETED"
    ):

        final_status = (
            "RECOVERY_MODEL_FAILURE"
        )

        verification2 = None

    else:

        # ----------------------------------------------------
        # 9. VERIFY ATTEMPT 2
        # ----------------------------------------------------

        verification2 = verify(
            request_name
        )

        if (
            verification2["status"]
            == "PASSED"
        ):

            final_status = (
                "PASSED_AFTER_RECOVERY"
            )

        elif (
            verification2["status"]
            == "FAILED"
        ):

            final_status = (
                "FAILED_AFTER_RECOVERY"
            )

        else:

            final_status = (
                "VERIFICATION_ERROR"
            )

    # --------------------------------------------------------
    # 10. FINAL RESULT
    # --------------------------------------------------------

    final_result = {
        "final_status":
            final_status,

        "classification":
            classification,

        "initial_route":
            initial_route,

        "attempt1":
            attempt1,

        "verification1":
            verification1,

        "diagnosis":
            diagnosis,

        "recovery":
            recovery,

        "attempt2":
            attempt2,

        "verification2":
            verification2,
    }

    result_path = (
        RUNS_DIR
        / f"{request_name}_result.json"
    )

    save_json(
        result_path,
        final_result,
    )

    print()
    print("=" * 60)
    print("FINAL RESULT")
    print("=" * 60)

    print(
        f"Status : {final_status}"
    )

    print(
        f"Result : {result_path}"
    )


if __name__ == "__main__":
    main()