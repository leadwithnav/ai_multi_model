```bash
#!/usr/bin/env bash
set -euo pipefail

# Directory containing this script = repository root
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Only this folder will be reset
SERVICE_DIR="order_flow_service"

cd "$REPO_DIR"

echo "Resetting only: $SERVICE_DIR"

# Verify that we are in the Git repository
if [ ! -d ".git" ]; then
    echo "ERROR: $REPO_DIR is not a Git repository."
    exit 1
fi

# Verify the target folder exists
if [ ! -d "$SERVICE_DIR" ]; then
    echo "ERROR: $SERVICE_DIR does not exist."
    exit 1
fi

# Restore tracked files ONLY inside order_flow_service
git restore --source=HEAD --staged --worktree "$SERVICE_DIR/"

# Remove untracked files/directories ONLY inside order_flow_service
git clean -fd "$SERVICE_DIR/"

echo ""
echo "Reset complete."
echo "Only $SERVICE_DIR was reset."
echo "All other lab files were left unchanged."
```
