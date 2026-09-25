rm -rf runs/* 

opencode run --agent vertical-run-analyzer \
"Task: task/simple_task.md
Run: runs/simple_vertical.jsonl
Luna: runs/simple_luna_solution.py
Terra: runs/simple_terra_solution.py
Sol: runs/simple_sol_solution.py"