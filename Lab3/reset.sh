#!/usr/bin/env bash

cd "$(dirname "$0")"

git restore --source=HEAD --staged --worktree ../order_flow_service/
git clean -fd ../order_flow_service/

# Remove generated test file if created
if [ -f "../order_flow_service/tests/test_inventory_generated.py" ]; then
    rm -f "../order_flow_service/tests/test_inventory_generated.py"
fi

echo "order_flow_service reset complete."
