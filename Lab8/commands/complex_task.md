cd Lab7 

# cleanup
rm -rf .pytest_cache runs/* prompt/tuned.md solution.py test_solution.py

opencode run --agent coordinator --format json "Strategy: DIRECT Task: task/complex_task.md" | python -u live_view.py runs/direct.jsonl

opencode run --agent coordinator --format json "Strategy: DESIGN_FIRST Task: task/complex_task.md" | python -u live_view.py runs/direct.jsonl

opencode run --agent code-quality-analyzer "Engineering Task: task/complex_task.md
Implementation A: design_first_solution.py Implementation B: direct_solution.py Output: runs/quality_comparison.md"