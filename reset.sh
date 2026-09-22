#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_URL="https://github.com/leadwithnav/ai_multi_model.git"

GIT_TARGET="$LAB_DIR"
if [ -d "$LAB_DIR/../order-flow-service/.git" ]; then
    GIT_TARGET="$LAB_DIR/../order-flow-service"
elif [ -d "$LAB_DIR/order-flow-service/.git" ]; then
    GIT_TARGET="$LAB_DIR/order-flow-service"
elif [ -d "$LAB_DIR/../.git" ]; then
    GIT_TARGET="$LAB_DIR/.."
fi

if [ ! -d "$GIT_TARGET/.git" ]; then
    echo "Cloning repository from $REPO_URL..."
    git clone "$REPO_URL" "$LAB_DIR"
else
    cd "$GIT_TARGET"
    git remote set-url origin "$REPO_URL"
    git fetch origin
    git reset --hard HEAD
    git clean -fd
    cd "$LAB_DIR"
fi

GEN_TEST="$LAB_DIR/../order-flow-service/tests/test_inventory_generated.py"
if [ -f "$GEN_TEST" ]; then
    rm -f "$GEN_TEST"
fi

echo "Repository reset to baseline ($REPO_URL)."
