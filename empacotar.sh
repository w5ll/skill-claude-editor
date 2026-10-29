#!/usr/bin/env bash
# Gera dist/welldit.skill (zip da pasta da skill).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
rm -f dist/welldit.skill
cd skill
zip -rq ../dist/welldit.skill welldit -x '*/__pycache__/*' '*.pyc' '*/.gitkeep'
cd ..
echo "ok  dist/welldit.skill ($(du -h dist/welldit.skill | cut -f1))"
