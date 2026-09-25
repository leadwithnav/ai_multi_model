rm -f runs/* prompts/tuned_prompt.md

opencode run --agent coordinator --format json "Strategy: BASELINE
Task: task/complex_task.md" | python -u live_view.py runs/baseline.jsonl

opencode run --agent coordinator --format json \
"Strategy: TUNED Task: task/complex_task.md" | python -u live_view.py runs/tuned.jsonl

opencode run --agent run-analyzer \
"Task: task/complex_task.md
Baseline Run: runs/baseline.jsonl
Baseline Code: runs/baseline_solution.py
Optimized Run: runs/tuned.jsonl
Optimized Code: runs/tuned_solution.py"