#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
"$PYTHON_BIN" -m venv .venv-viam
.venv-viam/bin/python -m pip install -r requirements.txt
