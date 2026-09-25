# Run with ALL_LOW strategy
opencode run --agent coordinator --format json "Strategy: ALL_LOW
Read the engineering requirement from task/complex_task.md and execute the configured workflow." | python -u live_view.py runs/all_low.jsonl

# Cleanup
rm -rf solution.py test_solution.py design.md .pytest_cache

# Run with ALL_HIGH strategy
opencode run --agent coordinator --format json "Strategy: ALL_HIGH
Read the engineering requirement from task/complex_task.md and execute the configured workflow." | python -u live_view.py runs/all_high.jsonl


# Cleanup
rm -rf solution.py test_solution.py design.md .pytest_cache

# Run with TIERED strategy
opencode run --agent coordinator --format json "Strategy: TIERED
Read the engineering requirement from task/complex_task.md and execute the configured workflow." | python -u live_view.py runs/tiered.jsonl

# Cleanup
rm -rf solution.py test_solution.py design.md .pytest_cache

# Run Analyzer agent to analyze the results
opencode run --agent runs-analyzer "analyze"

