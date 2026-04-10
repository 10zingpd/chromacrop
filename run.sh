#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Install deps if needed
"$SCRIPT_DIR/setup.sh"

# Run the module using the venv's Python
exec "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/main.py" "$@"
