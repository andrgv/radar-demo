#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
git rev-parse HEAD > viam_module/source_revision.txt
.venv-viam/bin/python -m PyInstaller --clean --noconfirm --onefile \
  --name upenn-mmwave --paths "$PWD" \
  --add-data 'configs:configs' --add-data 'viam_module/source_revision.txt:viam_module' \
  viam_module/main.py
dist/upenn-mmwave --self-test
tar -czf dist/upenn-mmwave.tar.gz meta.json dist/upenn-mmwave
