#!/usr/bin/env bash
# Reset order_flow_service working directory to HEAD
git restore --source=HEAD --staged --worktree ../order_flow_service/
git clean -fd ../order_flow_service/
echo "Working directory order_flow_service reset to HEAD."
