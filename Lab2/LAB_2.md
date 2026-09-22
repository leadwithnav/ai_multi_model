# Lab 2 — Benchmark Models Across Engineering Tasks

## Objective

In this lab, you will answer the fundamental multi-model engineering question:

> **"Does the model that performs well for implementation also perform well for refactoring, debugging, and testing?"**

You will benchmark multiple AI models across four realistic engineering workloads on the `order_flow_service` repository:
1. **Feature Implementation** (`benchmark/implementation/TASK.md`)
2. **Refactoring** (`benchmark/refactoring/TASK.md`)
3. **Debugging** (`benchmark/debugging/TASK.md`)
4. **Test Generation** (`benchmark/testing/TASK.md`)

---

## Benchmark Execution Loop

For each **Task** and each **Model**, follow this standard 6-step loop:

```text
PREDICT ──► RUN MODEL ──► EVALUATE ──► MEASURE ──► RESET ──► REPEAT
```

### Step 1: Set Up Environment
Ensure your AWS Bedrock profile is active:
```powershell
# PowerShell
$env:AWS_PROFILE="order-flow-course"
$env:AWS_REGION="us-east-1"
```
```bash
# Bash
export AWS_PROFILE=order-flow-course
export AWS_REGION=us-east-1
```

### Step 2: Run OpenCode Model Command
Run the target agent against the specific task file, capturing JSON events for metric analysis:

#### PowerShell
```powershell
opencode run --agent claude-3-5-sonnet --format json "$(Get-Content benchmark/implementation/TASK.md -Raw)" > run_events.jsonl
python metrics_helper.py claude-3-5-sonnet run_events.jsonl
```

#### Bash
```bash
opencode run --agent claude-3-5-sonnet --format json "$(cat benchmark/implementation/TASK.md)" > run_events.jsonl
python metrics_helper.py claude-3-5-sonnet run_events.jsonl
```

### Step 3: Run Deterministic Instructor Evaluation

Depending on the task being evaluated, run the corresponding instructor test suite:

- **Task 1 (Implementation)**:
  ```bash
  pytest instructor_tests/test_implementation_acceptance.py -v
  ```
- **Task 2 (Refactoring)**:
  ```bash
  pytest instructor_tests/test_refactoring_regression.py -v
  ```
- **Task 3 (Debugging)**:
  ```bash
  pytest instructor_tests/test_debugging_acceptance.py -v
  ```
- **Task 4 (Testing)**:
  ```bash
  python instructor_tests/testing_eval/evaluator.py
  ```

### Step 4: Record Results
Record whether the model met the **Quality Bar** (100% test pass rate for Tasks 1-3, or >= 80% mutation score for Task 4), along with **End-to-End Latency**, **Cost**, and **LLM Steps**.

### Step 5: Reset Repository
Reset the repository to a clean baseline before running the next model:
```powershell
.\reset.ps1   # Windows
```
```bash
./reset.sh    # Linux/macOS
```

---

## Benchmark Metrics Table

Record your observations across 3 runs per Model × Task combination:

| Task | Model | Pass Rate | Avg Cost / Task | Avg Latency | Avg LLM Steps | Meets Quality Bar |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Implementation** | `claude-3-5-haiku` | /3 | | | | |
| **Implementation** | `claude-3-5-sonnet` | /3 | | | | |
| **Implementation** | `claude-3-opus` | /3 | | | | |
| **Refactoring** | `claude-3-5-haiku` | /3 | | | | |
| **Refactoring** | `claude-3-5-sonnet` | /3 | | | | |
| **Refactoring** | `claude-3-opus` | /3 | | | | |
| **Debugging** | `claude-3-5-haiku` | /3 | | | | |
| **Debugging** | `claude-3-5-sonnet` | /3 | | | | |
| **Debugging** | `claude-3-opus` | /3 | | | | |
| **Testing** | `claude-3-5-haiku` | /3 | | | | |
| **Testing** | `claude-3-5-sonnet` | /3 | | | | |
| **Testing** | `claude-3-opus` | /3 | | | | |

---

## Workload Capability Matrix

Based on empirical evidence, select the optimal model for each engineering workload:

| Engineering Workload | Models Meeting Quality Bar | Selected Model | Selection Rationale (Cost / Latency / Evidence) |
| :--- | :--- | :--- | :--- |
| **Feature Implementation** | | | |
| **Refactoring** | | | |
| **Debugging** | | | |
| **Test Generation** | | | |

---

## Core Takeaway

> **"Do not choose the most capable model for every workload. Choose the least expensive model that reliably meets the quality bar for that specific engineering task."**
