#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$LAB_DIR/../order-flow-service"

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "ERROR: order-flow-service repository not found."
    exit 1
fi

cd "$REPO_DIR"

git reset --hard HEAD
git clean -fd

cd "$LAB_DIR"

mkdir -p artifacts/raw
mkdir -p artifacts/results

echo "Repository reset to baseline."
