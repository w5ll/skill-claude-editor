#!/usr/bin/env bash
# Gera dist/edicao-video-well.skill (zip da pasta da skill).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
rm -f dist/edicao-video-well.skill
cd skill
zip -rq ../dist/edicao-video-well.skill edicao-video-well -x '*/__pycache__/*' '*.pyc' '*/.gitkeep'
cd ..
echo "ok  dist/edicao-video-well.skill ($(du -h dist/edicao-video-well.skill | cut -f1))"
