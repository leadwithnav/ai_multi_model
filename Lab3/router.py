"""
Lab 3 Router & Routing Policy Engine

Separation of Responsibilities:
1. TaskClassifier -> Classifier LLM Agent: Answers "What kind of engineering task is this?"
   (Invokes LLM Classifier Agent via OpenCode, with fallback to heuristic keyword matching)
2. RoutingPolicy -> Answers "Which model should handle it based on Lab 2 benchmark evidence?"
3. Verifier -> Answers "Did the generated solution pass deterministic tests?"
"""

import os
import re
import json
import shutil
import subprocess
import yaml
from pathlib import Path

LAB3_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = LAB3_DIR.parent


class TaskClassifier:
    VALID_TASK_TYPES = ["implementation", "refactoring", "debugging", "testing"]

    @classmethod
    def classify_request(
        cls,
        request_text: str,
        classifier_agent: str = "claude-3-5-haiku",
        use_llm: bool = True
    ) -> str:
        """
        Classifies an incoming engineering task prompt using an LLM Agent into:
        - implementation
        - refactoring
        - debugging
        - testing

        CRITICAL ARCHITECTURAL DESIGN RULE:
        The LLM Classifier Agent determines WHAT KIND OF TASK it is.
        It does NOT select the model. The routing policy selects the model.
        """
        if use_llm:
            try:
                task_type = cls._classify_with_llm_agent(request_text, classifier_agent)
                if task_type in cls.VALID_TASK_TYPES:
                    print(f"[TaskClassifier Agent ({classifier_agent})] Classified task as: '{task_type}'")
                    return task_type
            except Exception as e:
                print(f"[TaskClassifier] LLM Classifier Agent fallback to heuristic due to: {e}")

        # Fallback to heuristic keyword matching
        task_type = cls._classify_with_heuristic(request_text)
        print(f"[TaskClassifier Heuristic] Classified task as: '{task_type}'")
        return task_type

    @classmethod
    def _classify_with_llm_agent(cls, request_text: str, classifier_agent: str) -> str:
        prompt = (
            "You are a software engineering task classifier agent.\n"
            "Classify the following engineering task request into EXACTLY ONE of these categories:\n"
            "- implementation\n"
            "- refactoring\n"
            "- debugging\n"
            "- testing\n\n"
            "Engineering Task Request:\n"
            "\"\"\"\n"
            f"{request_text}\n"
            "\"\"\"\n\n"
            "Respond with ONLY a JSON object containing the key 'task_type':\n"
            "{\"task_type\": \"<category>\"}\n"
            "Do not include any other text or markdown formatting."
        )

        opencode_bin = shutil.which("opencode") or shutil.which("opencode.cmd") or "opencode"
        cmd = [
            opencode_bin,
            "run",
            "--agent", classifier_agent,
            "--format", "json",
            prompt
        ]

        proc = subprocess.run(
            cmd,
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            timeout=60
        )

        raw_output = proc.stdout + "\n" + proc.stderr

        # Search for "task_type": "<value>" in JSONL output
        match = re.search(r'"task_type"\s*:\s*"([a-z_]+)"', raw_output, re.IGNORECASE)
        if match:
            candidate = match.group(1).lower()
            if candidate in cls.VALID_TASK_TYPES:
                return candidate

        # Secondary search for raw category keywords in output if JSON regex missed
        for valid in cls.VALID_TASK_TYPES:
            if f'"{valid}"' in raw_output.lower() or f"'{valid}'" in raw_output.lower():
                return valid

        raise ValueError("Could not parse valid task_type from LLM classifier output")

    @classmethod
    def _classify_with_heuristic(cls, request_text: str) -> str:
        text_lower = request_text.lower()

        if any(kw in text_lower for kw in ["refactor", "readability", "maintainability", "clean code"]):
            return "refactoring"
        elif any(kw in text_lower for kw in ["incident", "defect", "bug", "leak", "issue", "symptom", "inc-8821"]):
            return "debugging"
        elif any(kw in text_lower for kw in ["unit test", "test suite", "coverage", "mutation", "generate test"]):
            return "testing"
        elif any(kw in text_lower for kw in ["add support", "implement", "feature", "cancel_order", "endpoint"]):
            return "implementation"

        if "test" in text_lower:
            return "testing"
        if "fix" in text_lower:
            return "debugging"
        if "structure" in text_lower or "service" in text_lower:
            return "refactoring"

        return "implementation"


class RoutingPolicy:
    def __init__(self, policy_path: str = None):
        if policy_path is None:
            policy_path = Path(__file__).parent / "routing_policy.yaml"

        with open(policy_path, "r", encoding="utf-8") as f:
            self.data = yaml.safe_load(f)

        self.max_attempts = self.data.get("max_attempts", 2)
        self.policy = self.data.get("routing_policy", {})

    def select_model(self, task_type: str, strategy: str = "evidence") -> dict:
        """
        Selects primary and fallback models based on strategy:
        - 'evidence': Evidence-driven policy from Lab 2 benchmark.
        - 'cheapest': Always select cheapest model (claude-3-5-haiku).
        - 'strongest': Always select strongest model (claude-3-opus).
        """
        if strategy == "cheapest":
            return {
                "strategy": "cheapest",
                "task_type": task_type,
                "primary": "claude-3-5-haiku",
                "fallback": "claude-3-5-haiku",
                "max_attempts": self.max_attempts,
                "reason": "Strategy set to Cheapest Everywhere (claude-3-5-haiku)",
                "evidence": {}
            }
        elif strategy == "strongest":
            return {
                "strategy": "strongest",
                "task_type": task_type,
                "primary": "claude-3-opus",
                "fallback": "claude-3-opus",
                "max_attempts": self.max_attempts,
                "reason": "Strategy set to Strongest Everywhere (claude-3-opus)",
                "evidence": {}
            }

        # Evidence-Driven Routing
        task_policy = self.policy.get(task_type, {})
        primary = task_policy.get("primary", "claude-3-5-sonnet")
        fallback = task_policy.get("fallback", "claude-3-opus")
        evidence = task_policy.get("evidence", {})

        return {
            "strategy": "evidence",
            "task_type": task_type,
            "primary": primary,
            "fallback": fallback,
            "max_attempts": self.max_attempts,
            "reason": f"Selected from Lab 2 routing policy evidence for '{task_type}'",
            "evidence": evidence
        }
