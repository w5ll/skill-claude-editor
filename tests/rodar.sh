#!/usr/bin/env bash
# Roda todos os testes, do mesmo jeito que os testes automáticos do GitHub.
# Uso: tests/rodar.sh [arquivo ou teste do unittest]   (sem argumento, roda tudo)
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
# o ffmpeg completo do Homebrew não substitui o do sistema: põe no caminho se existir
if [ -d /opt/homebrew/opt/ffmpeg-full/bin ]; then export PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH"; fi
python tests/ambiente.py || echo "aviso: ffmpeg incompleto, alguns testes vão pular (veja a instalação no README)"
if [ $# -gt 0 ]; then
  python -m unittest "$@"
else
  python -m unittest discover -s tests
fi
