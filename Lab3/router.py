#!/usr/bin/env python3
"""
Lab 3 — Evidence-Driven Task Classification and Routing

Responsibilities:

1. TaskClassifier
   Classifies the engineering request as:
   implementation, refactoring, debugging, or testing.

2. RoutingPolicy
   Selects the primary and fallback models from routing_policy.yaml,
   which is populated from Lab 2 benchmark evidence.
"""

import json
import shutil
import subprocess
from pathlib import Path

import yaml


# ============================================================
# PATHS
# ============================================================

LAB3_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = LAB3_DIR.parent
SERVICE_ROOT = WORKSPACE_ROOT / "order_flow_service"


# ============================================================
# TASK CLASSIFIER
# ============================================================

class TaskClassifier:

    VALID_TASK_TYPES = [
        "implementation",
        "refactoring",
        "debugging",
        "testing",
    ]

    CLASSIFIER_AGENT = "task-classifier"

    @classmethod
    def classify_request(cls, request_text: str) -> str:
        """
        Classify the engineering request.

        The classifier only determines the task type.
        It does not perform the engineering task or select a model.
        """

        if not request_text.strip():
            raise ValueError(
                "Cannot classify an empty engineering request."
            )

        opencode_bin = (
            shutil.which("opencode")
            or shutil.which("opencode.cmd")
            or "opencode"
        )

        # ----------------------------------------------------
        # Prepare compact classification input
        # ----------------------------------------------------

        # Convert Markdown/multiline request into one line.
        compact_request = " ".join(
            request_text.split()
        )

        # The classifier does not need the entire engineering task.
        # This also avoids large/multiline CLI argument problems.
        compact_request = compact_request[:4000]

        classification_prompt = (
            "Classify this software engineering request. "
            "Return ONLY one of: "
            "implementation, refactoring, debugging, testing. "
            "If the request describes an existing defect, incident, "
            "failure, regression, or incorrect behavior, classify it "
            "as debugging. "
            "If it asks for new functionality, classify it as "
            "implementation. "
            "If it asks to improve code structure without changing "
            "behavior, classify it as refactoring. "
            "If it primarily asks to create or improve tests, "
            "classify it as testing. "
            "\n\nENGINEERING REQUEST:\n"
            f"{compact_request}"
        )

        cmd = [
            opencode_bin,
            "run",
            "--agent",
            cls.CLASSIFIER_AGENT,
            "--format",
            "json",
            classification_prompt,
        ]

        print(
            "[TaskClassifier] Starting OpenCode classifier..."
        )

        try:

            proc = subprocess.run(
                cmd,
                cwd=str(WORKSPACE_ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )

        except subprocess.TimeoutExpired as exc:

            raise RuntimeError(
                "Task classifier timed out after 60 seconds."
            ) from exc

        except Exception as exc:

            raise RuntimeError(
                f"Task classifier execution failed: {exc}"
            ) from exc

        print(
            "[TaskClassifier] OpenCode classifier finished."
        )

        if proc.returncode != 0:

            raise RuntimeError(
                "Task classifier OpenCode execution failed.\n"
                f"Return code: {proc.returncode}\n"
                f"stderr:\n{proc.stderr}"
            )

        classifier_text = cls._extract_text(
            proc.stdout
        )

        if not classifier_text:

            raise ValueError(
                "Task classifier returned no text.\n\n"
                f"Raw output:\n{proc.stdout}"
            )

        task_type = (
            classifier_text
            .strip()
            .lower()
            .replace('"', "")
            .replace("'", "")
            .strip()
        )

        if task_type not in cls.VALID_TASK_TYPES:

            raise ValueError(
                "Task classifier returned an invalid task type: "
                f"'{classifier_text}'.\n"
                "Expected exactly one of:\n"
                "implementation\n"
                "refactoring\n"
                "debugging\n"
                "testing"
            )

        print(
            f"[TaskClassifier] Result: {task_type}"
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
        Extract assistant text from:

            opencode run --format json

        Example:

        {
            "type": "text",
            "part": {
                "type": "text",
                "text": "debugging"
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

            part = (
                event.get("part", {})
                or {}
            )

            text = part.get("text")

            if text:
                text_parts.append(
                    text.strip()
                )

        return "\n".join(
            text_parts
        ).strip()


# ============================================================
# ROUTING POLICY
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

        policy_path = Path(policy_path)

        if not policy_path.exists():

            raise FileNotFoundError(
                "Routing policy not found: "
                f"{policy_path}"
            )

        with open(
            policy_path,
            "r",
            encoding="utf-8",
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

        if not self.policy:

            raise ValueError(
                "routing_policy.yaml does not contain "
                "a 'routing_policy' section."
            )

    # ========================================================
    # MODEL SELECTION
    # ========================================================

    def select_model(
        self,
        task_type: str
    ) -> dict:
        """
        Select the primary and fallback models using
        Lab 2 benchmark evidence stored in routing_policy.yaml.

        No cheapest/strongest comparison is performed here.
        """

        # ----------------------------------------------------
        # Validate task type
        # ----------------------------------------------------

        if (
            task_type
            not in TaskClassifier.VALID_TASK_TYPES
        ):

            raise ValueError(
                f"Unknown task type: '{task_type}'"
            )

        # ----------------------------------------------------
        # Get policy for this task type
        # ----------------------------------------------------

        task_policy = (
            self.policy.get(
                task_type
            )
        )

        if not task_policy:

            raise ValueError(
                "No routing policy configured for "
                f"task type '{task_type}'."
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
        # Validate primary
        # ----------------------------------------------------

        if (
            not primary
            or primary
            == "add_from_lab2_benchmarking"
        ):

            raise ValueError(
                f"Primary model for '{task_type}' "
                "has not been configured.\n\n"
                "Add the model selected from your "
                "Lab 2 benchmark results to "
                "routing_policy.yaml."
            )

        # ----------------------------------------------------
        # Validate fallback
        # ----------------------------------------------------

        if (
            not fallback
            or fallback
            == "add_from_lab2_benchmarking"
        ):

            raise ValueError(
                f"Fallback model for '{task_type}' "
                "has not been configured.\n\n"
                "Add the fallback model selected from "
                "your Lab 2 benchmark results to "
                "routing_policy.yaml."
            )

        # ----------------------------------------------------
        # Return evidence-based routing decision
        # ----------------------------------------------------

        return {

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
                    "Selected from routing_policy.yaml "
                    "using Lab 2 benchmark evidence "
                    f"for '{task_type}'."
                ),
        }