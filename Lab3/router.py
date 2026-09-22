"""
Lab 3 — Task Classification and Routing Policy

Responsibilities:

1. TaskClassifier
   Answers:
       "What kind of engineering task is this?"

   Uses the dedicated OpenCode agent:
       task-classifier

   Possible outputs:
       implementation
       refactoring
       debugging
       testing


2. RoutingPolicy
   Answers:
       "Which model should handle this task?"

   For evidence strategy, the decision comes from:
       routing_policy.yaml

   The policy was created using Lab 2 benchmark results.
"""

import json
import shutil
import subprocess
from pathlib import Path

import yaml


# ============================================================
# Paths
# ============================================================

LAB3_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = LAB3_DIR.parent

SERVICE_ROOT = WORKSPACE_ROOT / "order_flow_service"


# ============================================================
# Task Classifier
# ============================================================

class TaskClassifier:

    VALID_TASK_TYPES = [
        "implementation",
        "refactoring",
        "debugging",
        "testing"
    ]

    CLASSIFIER_AGENT = "task-classifier"

    @classmethod
    def classify_request(
        cls,
        request_text: str
    ) -> str:
        """
        Ask the dedicated OpenCode task-classifier agent
        to classify the engineering request.

        The classifier only answers:

            implementation
            refactoring
            debugging
            testing

        It does NOT select the coding model.
        """

        opencode_bin = (
            shutil.which("opencode")
            or shutil.which("opencode.cmd")
            or "opencode"
        )

        cmd = [
            opencode_bin,
            "run",
            "--agent",
            cls.CLASSIFIER_AGENT,
            "--format",
            "json"
        ]

        try:

            proc = subprocess.run(
                cmd,

                # Run from application repository
                cwd=str(SERVICE_ROOT),

                # Send complete request through stdin
                input=request_text,

                capture_output=True,
                text=True,
                timeout=60
            )

        except subprocess.TimeoutExpired:

            raise RuntimeError(
                "Task classifier timed out."
            )

        except Exception as exc:

            raise RuntimeError(
                f"Task classifier execution failed: {exc}"
            )

        # ----------------------------------------------------
        # Check OpenCode execution
        # ----------------------------------------------------

        if proc.returncode != 0:

            raise RuntimeError(
                "Task classifier OpenCode execution failed.\n"
                f"{proc.stderr}"
            )

        # ----------------------------------------------------
        # Extract text returned by classifier from JSONL
        # ----------------------------------------------------

        classifier_text = cls._extract_text(
            proc.stdout
        )

        if not classifier_text:

            raise ValueError(
                "Task classifier returned no text."
            )

        # ----------------------------------------------------
        # Normalize result
        # ----------------------------------------------------

        task_type = (
            classifier_text
            .strip()
            .lower()
        )

        # Remove accidental quotes
        task_type = (
            task_type
            .replace('"', '')
            .replace("'", "")
            .strip()
        )

        # ----------------------------------------------------
        # Validate result
        # ----------------------------------------------------

        if task_type not in cls.VALID_TASK_TYPES:

            raise ValueError(
                "Task classifier returned an invalid "
                f"task type: '{classifier_text}'.\n"
                "Expected one of: "
                f"{cls.VALID_TASK_TYPES}"
            )

        print(
            f"[TaskClassifier] "
            f"Classified task as: "
            f"'{task_type}'"
        )

        return task_type

    # ========================================================
    # Extract assistant text from OpenCode JSONL
    # ========================================================

    @staticmethod
    def _extract_text(
        raw_jsonl: str
    ) -> str:
        """
        Extract text events from:

            opencode run --format json

        Example event:

        {
            "type": "text",
            "part": {
                "type": "text",
                "text": "implementation"
            }
        }
        """

        text_parts = []

        for line in raw_jsonl.splitlines():

            line = line.strip()

            if not line:
                continue

            try:

                event = json.loads(line)

            except json.JSONDecodeError:

                continue

            if event.get("type") != "text":
                continue

            part = event.get(
                "part",
                {}
            ) or {}

            text = part.get("text")

            if text:

                text_parts.append(
                    text.strip()
                )

        return "\n".join(
            text_parts
        ).strip()


# ============================================================
# Routing Policy
# ============================================================

class RoutingPolicy:

    def __init__(
        self,
        policy_path: str = None
    ):

        if policy_path is None:

            policy_path = (
                LAB3_DIR
                / "routing_policy.yaml"
            )

        with open(
            policy_path,
            "r",
            encoding="utf-8"
        ) as file:

            self.data = (
                yaml.safe_load(file)
                or {}
            )

        self.max_attempts = (
            self.data.get(
                "max_attempts",
                2
            )
        )

        self.policy = (
            self.data.get(
                "routing_policy",
                {}
            )
        )

    # ========================================================
    # Model Selection
    # ========================================================

    def select_model(
        self,
        task_type: str,
        strategy: str = "evidence"
    ) -> dict:
        """
        Select coding model based on routing strategy.

        Strategies:

        cheapest
            Always use Haiku.

        strongest
            Always use Opus.

        evidence
            Use routing_policy.yaml populated
            from Lab 2 benchmark results.
        """

        # ----------------------------------------------------
        # Cheapest Everywhere
        # ----------------------------------------------------

        if strategy == "cheapest":

            return {

                "strategy":
                    "cheapest",

                "task_type":
                    task_type,

                "primary":
                    "claude-3-5-haiku",

                "fallback":
                    None,

                "max_attempts":
                    1,

                "reason":
                    (
                        "Cheapest Everywhere baseline: "
                        "use Haiku for every task."
                    )
            }

        # ----------------------------------------------------
        # Highest-Capability Everywhere
        # ----------------------------------------------------

        if strategy == "strongest":

            return {

                "strategy":
                    "strongest",

                "task_type":
                    task_type,

                "primary":
                    "claude-3-opus",

                "fallback":
                    None,

                "max_attempts":
                    1,

                "reason":
                    (
                        "Highest-Capability Everywhere "
                        "baseline: use Opus for every task."
                    )
            }

        # ----------------------------------------------------
        # Validate strategy
        # ----------------------------------------------------

        if strategy != "evidence":

            raise ValueError(
                f"Unknown routing strategy: "
                f"'{strategy}'"
            )

        # ====================================================
        # Evidence-Driven Routing
        # ====================================================

        task_policy = (
            self.policy.get(
                task_type
            )
        )

        if not task_policy:

            raise ValueError(
                f"No routing policy configured "
                f"for task type '{task_type}'."
            )

        primary = (
            task_policy.get(
                "primary"
            )
        )

        fallback = (
            task_policy.get(
                "fallback"
            )
        )

        # ----------------------------------------------------
        # Make sure students populated Lab 2 results
        # ----------------------------------------------------

        if (
            not primary
            or primary
            == "add_from_lab2_benchmarking"
        ):

            raise ValueError(
                f"Primary model for "
                f"'{task_type}' has not been "
                f"configured.\n"
                f"Add the model selected from "
                f"your Lab 2 benchmark results "
                f"to routing_policy.yaml."
            )

        if (
            not fallback
            or fallback
            == "add_from_lab2_benchmarking"
        ):

            raise ValueError(
                f"Fallback model for "
                f"'{task_type}' has not been "
                f"configured.\n"
                f"Add the fallback selected from "
                f"your Lab 2 benchmark results "
                f"to routing_policy.yaml."
            )

        return {

            "strategy":
                "evidence",

            "task_type":
                task_type,

            "primary":
                primary,

            "fallback":
                fallback,

            "max_attempts":
                self.max_attempts,

            "reason":
                (
                    "Selected from the routing "
                    "policy created using Lab 2 "
                    f"benchmark evidence for "
                    f"'{task_type}'."
                )
        }