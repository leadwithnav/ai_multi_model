# Lab 2 — Instructor & Facilitator Guide

## Overview & Pedagogical Purpose

In Lab 1, participants benchmarked models on a single isolated utility task (Rate Limiter). In **Lab 2**, participants evaluate models across **four distinct software engineering workloads**:

1. **Feature Implementation**: Adding a domain feature (`cancel_order` & REST endpoint).
2. **Refactoring**: Improving code structure and readability while preserving public contracts.
3. **Debugging**: Identifying and fixing a subtle multi-item inventory stock allocation leak (INC-8821).
4. **Test Generation**: Generating a test suite evaluated via hidden mutation defect detection.

---

## 1. Why Each Task Was Chosen

| Workload | Target Component | Core Cognitive Challenge | Why It Tests Model Capability |
|----------|------------------|--------------------------|--------------------------------|
| **Feature Implementation** | `OrderService` & `main.py` | Architecture & State Transitions | Requires understanding database transactions, status enums, error handling, and FastAPI route conventions. |
| **Refactoring** | `OrderService` | Readability & Backwards Compatibility | Tests if the model can clean code without breaking public signatures or introducing subtle regression bugs. |
| **Debugging** | `OrderService` & `InventoryService` | Multi-step Reasoning & Root-Cause Diagnosis | Tests if the model can trace symptoms to partial transaction leaks without explicit code pointers. |
| **Test Generation** | `InventoryService` | Boundary & Failure Condition Coverage | Evaluates test suite quality via mutation testing (kill rate) rather than superficial test count. |

---

## 2. Expected Behavior & Acceptance Criteria

### Task 1: Feature Implementation (`cancel_order`)
- **Location**: `src/services/order_service.py` & `src/main.py`.
- **Expected Behavior**:
  - `cancel_order(session, order_id)` updates status to `CANCELLED` and restores reserved inventory stock.
  - Returns `ValueError` if `order_id` is missing or order is already `CANCELLED`/`FAILED`.
  - Exposes `POST /orders/{order_id}/cancel` returning 200 OK or 400 Bad Request.
- **Instructor Test**: `pytest instructor_tests/test_implementation_acceptance.py`.

### Task 2: Refactoring (`OrderService`)
- **Location**: `src/services/order_service.py`.
- **Expected Behavior**:
  - Code decomposed into clean helper methods; string literals replaced with `OrderStatus` enums.
  - All existing methods (`create_order`, `handle_payment_webhook`) maintain exact signatures and return types.
- **Instructor Test**: `pytest instructor_tests/test_refactoring_regression.py`.

### Task 3: Debugging (INC-8821 Stock Allocation Leak)
- **Location**: `src/services/order_service.py` line 18-23.
- **Root Cause**: `create_order` iterates through items and calls `reserve_stock` sequentially. If item 1 succeeds and item 2 fails, item 1's stock was already committed and is never rolled back!
- **Expected Fix**: Catch reservation failure and roll back previously reserved items, or wrap stock reservation in an atomic transaction scope.
- **Instructor Test**: `pytest instructor_tests/test_debugging_acceptance.py`.

### Task 4: Test Generation (`InventoryService`)
- **Location**: Model creates `tests/test_inventory_generated.py`.
- **Evaluation Mechanism**: `python metrics_helper.py` / `python instructor_tests/testing_eval/evaluator.py`.
- **Mutations Evaluated**:
  1. `mutation_1_over_reserve.py` (Double stock deduction)
  2. `mutation_2_negative_stock.py` (No stock minimum check)
  3. `mutation_3_silent_get_stock.py` (Missing SKU returns 999)
  4. `mutation_4_no_commit_reserve.py` (Fails to commit DB session)
  5. `mutation_5_partial_stock_leak.py` (Deducts stock on failed reservation)
- **Quality Bar**: Score >= 80% (Kills at least 4 out of 5 mutants).

---

## 3. Reset Procedure

Before running any model on a task, execute:
```powershell
# Windows PowerShell
.\reset.ps1
```
or
```bash
# Bash
./reset.sh
```

---

## 4. Troubleshooting & Common Participant Issues

1. **Model fails Task 3 (Debugging)**:
   - *Issue*: Model modifies `InventoryService.get_stock` instead of rolling back reservations in `OrderService`.
   - *Explanation*: Shallow reasoning models inspect where the error occurs rather than tracing transaction lifecycle.

2. **Model fails Task 4 (Test Generation)**:
   - *Issue*: Model writes 20 superficial `assert 1 == 1` tests that pass on baseline but miss all 5 mutants.
   - *Explanation*: Emphasizes why test count is a poor metric compared to defect detection score.

---

## 5. Key Conclusions

### What CAN Be Concluded:
- Model performance varies significantly depending on the engineering task type (e.g., a fast model may excel at refactoring but fail complex debugging).
- Quality must be evaluated deterministically using automated test suites and mutation testing.

### What CANNOT Be Concluded:
- "Model X is globally superior to Model Y for all software tasks."
- "More generated code or tests equals higher software quality."
