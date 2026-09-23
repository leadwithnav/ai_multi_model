#!/usr/bin/env bash

cd "$(dirname "$0")"

git restore --source=HEAD --staged --worktree ../order_flow_service/
git clean -fd ../order_flow_service/

echo "order_flow_service reset complete."
