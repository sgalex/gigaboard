#!/bin/bash
# GigaBoard Development Scripts

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "🚀 Starting GigaBoard Backend..."
cd "$SCRIPT_DIR/apps/backend"
"$SCRIPT_DIR/.venv/bin/python" run_dev.py
