#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Viam cloud builds may unpack source without a .git directory.
# Do not mistake a parent checkout for this module's source revision.
revision="source-archive"
if [ -e .git ]; then
  revision="$(git rev-parse HEAD 2>/dev/null || printf '%s' 'unknown')"
fi
printf '%s\n' "$revision" > viam_module/source_revision.txt
.venv-viam/bin/python -m PyInstaller --clean --noconfirm --onefile \
  --name upenn-mmwave --paths "$PWD" \
  --add-data 'configs:configs' --add-data 'viam_module/source_revision.txt:viam_module' \
  viam_module/main.py
dist/upenn-mmwave --self-test
tar -czf dist/upenn-mmwave.tar.gz meta.json dist/upenn-mmwave
