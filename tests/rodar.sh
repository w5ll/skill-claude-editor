#!/usr/bin/env bash
# Roda todos os testes, do mesmo jeito que os testes automáticos do GitHub.
# Uso: tests/rodar.sh [arquivo ou teste do unittest]   (sem argumento, roda tudo)
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi
# o ffmpeg completo do Homebrew não substitui o do sistema: põe no caminho se existir
if command -v brew > /dev/null 2>&1 && [ -d "$(brew --prefix ffmpeg-full 2> /dev/null)/bin" ]; then export PATH="$(brew --prefix ffmpeg-full)/bin:$PATH"; fi
python tests/ambiente.py || echo "aviso: ffmpeg incompleto, alguns testes vão pular (veja a instalação no README)"
if [ $# -gt 0 ]; then
  python -m unittest "$@"
else
  python -m unittest discover -s tests
fi
