# cleanup
rm -rf .pytest_cache runs/* direct_solution.py design_first_solution.py design.md

opencode run --agent coordinator --format json "Strategy: DIRECT Task: task/simple_task.md" | python -u live_view.py runs/direct.jsonl

opencode run --agent coordinator --format json "Strategy: DESIGN_FIRST Task: task/simple_task.md" | python -u live_view.py runs/direct.jsonl

opencode run --agent code-quality-analyzer "Engineering Task: task/simple_task.md
Implementation A: design_first_solution.py Implementation B: direct_solution.py Output: runs/quality_comparison.md"