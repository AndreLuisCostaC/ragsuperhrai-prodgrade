#!/bin/bash
# Clean all build artifacts
# Usage: ./clean.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🧹 Cleaning build artifacts..."

rm -rf "$PROJECT_ROOT/packages/layer1"
rm -rf "$PROJECT_ROOT/packages/layer2"
rm -rf "$PROJECT_ROOT/packages/layer3"
rm -rf "$PROJECT_ROOT/dist"

mkdir -p "$PROJECT_ROOT/packages/layer1"
mkdir -p "$PROJECT_ROOT/packages/layer2"
mkdir -p "$PROJECT_ROOT/packages/layer3"

echo "✅ Clean complete!"