# ============================================================
# LAB 9: WORKFLOW ORCHESTRATION STRATEGIES
# ============================================================

# ------------------------------------------------------------
# SCENARIO 1: SIMPLE TASK (task/simple_task.md)
# ------------------------------------------------------------

# Run with ALL_LOW strategy
opencode run --agent coordinator --format json "Strategy: ALL_LOW
Read the engineering requirement from task/simple_task.md and execute the configured workflow." | tee runs/all_low.jsonl
rm -rf solution.py test_solution.py design.md .pytest_cache

# Run with ALL_HIGH strategy
opencode run --agent coordinator --format json "Strategy: ALL_HIGH
Read the engineering requirement from task/simple_task.md and execute the configured workflow." | tee runs/all_high.jsonl
rm -rf solution.py test_solution.py design.md .pytest_cache

# Run with TIERED strategy
opencode run --agent coordinator --format json "Strategy: TIERED
Read the engineering requirement from task/simple_task.md and execute the configured workflow." | tee runs/tiered.jsonl
rm -rf solution.py test_solution.py design.md .pytest_cache

# ------------------------------------------------------------
# SCENARIO 2: COMPLEX TASK (task/complex_task.md)
# ------------------------------------------------------------

# Run with ALL_LOW strategy
opencode run --agent coordinator --format json "Strategy: ALL_LOW
Read the engineering requirement from task/complex_task.md and execute the configured workflow." | tee runs/all_low.jsonl
rm -rf solution.py test_solution.py design.md .pytest_cache

# Run with ALL_HIGH strategy
opencode run --agent coordinator --format json "Strategy: ALL_HIGH
Read the engineering requirement from task/complex_task.md and execute the configured workflow." | tee runs/all_high.jsonl
rm -rf solution.py test_solution.py design.md .pytest_cache

# Run with TIERED strategy
opencode run --agent coordinator --format json "Strategy: TIERED
Read the engineering requirement from task/complex_task.md and execute the configured workflow." | tee runs/tiered.jsonl
rm -rf solution.py test_solution.py design.md .pytest_cache

# ------------------------------------------------------------
# RUN ANALYZER AGENT
# ------------------------------------------------------------

# Run Analyzer agent to produce comparison.md
opencode run --agent runs-analyzer "analyze"