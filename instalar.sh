#!/usr/bin/env bash
# Prepara o computador para a skill welldit: Python, ffmpeg completo, ambiente da skill, bibliotecas e navegador.
# Uso: ./instalar.sh [--so-conferir] [--sim]
#   --so-conferir  não instala nada, só diz o que falta
#   --sim          não pergunta antes de instalar (para os testes automáticos)
# Pode rodar quantas vezes quiser: o que já está pronto fica como está.
# Nunca mexe em material-bruto/ nem em saida/. Os comandos e os erros técnicos ficam em instalacao.log.
# Compatível com o bash 3.2 do Mac.

cd "$(dirname "$0")" || exit 1
RAIZ=$(pwd)
LOG="$RAIZ/instalacao.log"
REQUISITOS="skill/welldit/scripts/requirements.txt"
SO_CONFERIR=0
SIM=0

for arg in "$@"; do
  case "$arg" in
    --so-conferir) SO_CONFERIR=1 ;;
    --sim) SIM=1 ;;
    -h|--help)
      echo "Uso: ./instalar.sh [--so-conferir] [--sim]"
      echo "  --so-conferir  só diz o que falta, sem instalar nada"
      echo "  --sim          instala sem perguntar"
      exit 0 ;;
    *) echo "Opção desconhecida: $arg. Use --help para ver as opções."; exit 2 ;;
  esac
done

FALTA=""      # lista do que falta (uma linha por item)
MUDOU=0       # 1 se este passo instalou ou criou algo
PASSO=0
TOTAL=7

dizer() { echo "$*"; }
passo() { PASSO=$((PASSO + 1)); echo; echo "[$PASSO/$TOTAL] $*"; }
pronto() { echo "      pronto: $*"; }
feito() { echo "      feito: $*"; MUDOU=1; }
falta() { echo "      falta: $*"; FALTA="$FALTA
- $*"; }

# roda um comando guardando tudo no registro; devolve o código de saída
quieto() {
  { echo; echo "\$ $*"; } >> "$LOG"
  "$@" >> "$LOG" 2>&1
}

parar() {
  echo
  echo "Não consegui terminar: $*"
  echo "Se quiser ajuda, mande o arquivo instalacao.log (está nesta pasta) para quem mantém o projeto."
  exit 1
}

# pergunta "s/n". Com --sim responde sim; sem terminal não dá para perguntar, então responde não.
perguntar() {
  [ "$SIM" = 1 ] && return 0
  [ -t 0 ] || return 1
  printf "      %s (s/n) " "$1"
  read -r resposta
  case "$resposta" in s|S|sim|Sim|SIM) return 0 ;; *) return 1 ;; esac
}

echo "Instalação do welldit"
echo "Isso prepara o computador para editar vídeos. Pode levar alguns minutos na primeira vez."
[ "$SO_CONFERIR" = 1 ] && echo "(Modo só conferir: nada será instalado.)"
{ echo "=== $(date) ==="; echo "pasta: $RAIZ"; } >> "$LOG"

# 1. Sistema --------------------------------------------------------------------------------------
passo "Conferindo o seu computador"
SISTEMA="outro"
case "$(uname -s)" in
  Darwin) SISTEMA="mac" ;;
  Linux) if command -v apt-get > /dev/null 2>&1; then SISTEMA="apt"; else SISTEMA="linux-outro"; fi ;;
esac
case "$SISTEMA" in
  mac) pronto "Mac" ;;
  apt)
    if grep -qi microsoft /proc/version 2> /dev/null; then pronto "Windows com Ubuntu (WSL)"; else pronto "Linux (Ubuntu ou Debian)"; fi ;;
  *)
    echo "      Este sistema ainda não é coberto pelo instalador."
    echo "      Veja a lista de ferramentas em skill/welldit/referencias/instalacao.md e instale à mão."
    exit 1 ;;
esac

# Homebrew (só no Mac). Não instalamos: ele pede a senha e baixa um script da internet.
BREW=""
if [ -n "${WELLDIT_BREW+x}" ]; then
  BREW="$WELLDIT_BREW"   # só para os testes: aponta para um Homebrew de mentira (ou vazio, para não ter nenhum)
elif [ "$SISTEMA" = "mac" ]; then
  for b in "$(command -v brew 2> /dev/null)" /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [ -n "$b" ] && [ -x "$b" ]; then BREW="$b"; break; fi
  done
fi

precisa_brew() {
  [ -n "$BREW" ] && return 0
  echo
  echo "Falta o instalador de programas do Mac (Homebrew). Eu não instalo ele sozinho."
  echo "Abra o site https://brew.sh, copie o comando que aparece lá, cole no Terminal e rode."
  echo "No fim ele mostra dois comandos em \"Next steps\": rode os dois. Depois rode ./instalar.sh de novo."
  exit 1
}

# 2. Python ---------------------------------------------------------------------------------------
versao_ok() {  # o Python $1 serve? (3.10 a 3.13, com suporte a ambiente isolado)
  "$1" -c 'import sys, ensurepip, venv; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)' > /dev/null 2>&1
}

achar_python() {
  PY=""
  local candidatos="python3.12 python3.13 python3.11 python3.10 python3"
  local c caminho
  for c in $candidatos; do
    caminho=$(command -v "$c" 2> /dev/null)
    if [ -n "$caminho" ] && versao_ok "$caminho"; then PY="$caminho"; return 0; fi
  done
  if [ -n "$BREW" ]; then
    caminho="$("$BREW" --prefix python@3.12 2> /dev/null)/bin/python3.12"
    if [ -x "$caminho" ] && versao_ok "$caminho"; then PY="$caminho"; return 0; fi
  fi
  return 1
}

passo "Procurando o Python (versão 3.12, ou de 3.10 a 3.13)"
if achar_python; then
  pronto "Python $("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
elif [ "$SO_CONFERIR" = 1 ]; then
  falta "Python 3.12 (o 3.14 e o 3.9 do Mac não servem)"
else
  echo "      Não achei um Python que sirva. Preciso instalar o Python 3.12."
  echo "      Pode pedir a senha do computador."
  if perguntar "Posso instalar?"; then
    if [ "$SISTEMA" = "mac" ]; then
      precisa_brew
      quieto "$BREW" install python@3.12 || parar "a instalação do Python não deu certo."
    else
      quieto sudo apt-get update
      quieto sudo apt-get install -y python3 python3-venv python3-pip || parar "a instalação do Python não deu certo."
    fi
    achar_python || parar "instalei o Python, mas ele não ficou disponível. Feche e abra o Terminal e tente de novo."
    feito "Python instalado"
  else
    falta "Python 3.12"
  fi
fi

# 3. ffmpeg ---------------------------------------------------------------------------------------
FFMPEG_DIR=""
if [ "$SISTEMA" = "mac" ] && [ -n "$BREW" ]; then
  prefixo=$("$BREW" --prefix ffmpeg-full 2> /dev/null)
  if [ -n "$prefixo" ] && [ -d "$prefixo/bin" ]; then FFMPEG_DIR="$prefixo/bin"; fi
fi
# o ffmpeg-full não substitui o ffmpeg do sistema: ele vai na frente do caminho nesta rodada
if [ -n "$FFMPEG_DIR" ]; then export PATH="$FFMPEG_DIR:$PATH"; fi

filtros_que_faltam() {  # imprime os filtros que o ffmpeg do caminho não tem
  local lista f
  if ! command -v ffmpeg > /dev/null 2>&1 || ! command -v ffprobe > /dev/null 2>&1; then echo "ffmpeg"; return; fi
  lista=$(ffmpeg -hide_banner -filters 2> /dev/null | awk '{print $2}')
  for f in ass zscale afftdn; do
    echo "$lista" | grep -qx "$f" || echo "$f"
  done
}

passo "Procurando o ffmpeg completo (corta o vídeo, põe a legenda e acerta a cor)"
if [ -z "$(filtros_que_faltam)" ]; then
  pronto "ffmpeg completo"
elif [ "$SO_CONFERIR" = 1 ]; then
  falta "ffmpeg completo (o que existe aqui não tem legenda ou conversão de cor)"
else
  echo "      Não achei o ffmpeg completo. Preciso instalar. Pode pedir a senha do computador."
  if perguntar "Posso instalar?"; then
    if [ "$SISTEMA" = "mac" ]; then
      precisa_brew
      quieto "$BREW" install ffmpeg-full || parar "a instalação do ffmpeg não deu certo."
      prefixo=$("$BREW" --prefix ffmpeg-full 2> /dev/null)
      FFMPEG_DIR="$prefixo/bin"
      export PATH="$FFMPEG_DIR:$PATH"
    else
      quieto sudo apt-get update
      quieto sudo apt-get install -y ffmpeg || parar "a instalação do ffmpeg não deu certo."
    fi
    if [ -n "$(filtros_que_faltam)" ]; then
      parar "instalei o ffmpeg, mas ele ainda não tem a legenda ou a conversão de cor."
    fi
    feito "ffmpeg completo instalado"
  else
    falta "ffmpeg completo"
  fi
fi

# 4. Ambiente da skill ----------------------------------------------------------------------------
VENV_PY=".venv/bin/python"
passo "Preparando o ambiente da skill"
if [ -z "$PY" ]; then
  falta "ambiente da skill (depende do Python)"
elif [ -x "$VENV_PY" ] && versao_ok "$VENV_PY"; then
  pronto "ambiente já criado"
elif [ "$SO_CONFERIR" = 1 ]; then
  if [ -e .venv ]; then falta "ambiente da skill (o que existe usa um Python que não serve)"; else falta "ambiente da skill"; fi
else
  if [ -e .venv ]; then
    echo "      O ambiente que existe usa um Python que não serve. Vou guardar ele com outro nome e criar um novo."
    perguntar "Posso?" || { falta "ambiente da skill"; PY=""; }
    if [ -n "$PY" ]; then
      destino=".venv-antigo"
      [ -e "$destino" ] && destino=".venv-antigo-$(date +%Y%m%d-%H%M%S)"
      mv .venv "$destino" || parar "não consegui guardar o ambiente antigo."
      echo "      O antigo ficou em $destino. Pode apagar depois, se quiser."
    fi
  fi
  if [ -n "$PY" ]; then
    quieto "$PY" -m venv .venv || parar "não consegui criar o ambiente da skill."
    feito "ambiente criado"
  fi
fi

# caminho do ffmpeg-full dentro do ambiente (só no Mac), uma vez só
if [ -n "$FFMPEG_DIR" ] && [ -f .venv/bin/activate ] && [ "$SO_CONFERIR" = 0 ]; then
  if ! grep -q "ffmpeg-full" .venv/bin/activate; then
    echo "export PATH=\"$FFMPEG_DIR:\$PATH\"" >> .venv/bin/activate
    feito "o ffmpeg completo foi ligado ao ambiente da skill"
  fi
fi

# 5. Bibliotecas ----------------------------------------------------------------------------------
passo "Instalando as bibliotecas de transcrição, rosto e desenho"
if [ ! -x "$VENV_PY" ]; then
  falta "bibliotecas (dependem do ambiente da skill)"
elif "$VENV_PY" -c 'import faster_whisper, numpy, fontTools, playwright, cv2' > /dev/null 2>&1; then
  pronto "bibliotecas já instaladas"
elif [ "$SO_CONFERIR" = 1 ]; then
  falta "bibliotecas de transcrição, rosto e desenho"
else
  echo "      Isso baixa alguns programas e leva alguns minutos."
  quieto "$VENV_PY" -m pip install -r "$REQUISITOS" || parar "não consegui instalar as bibliotecas (conferiu a internet?)."
  feito "bibliotecas instaladas"
fi

# 6. Navegador dos elementos 3D -------------------------------------------------------------------
passo "Preparando o navegador que desenha os elementos 3D"
navegador_ok() {
  "$VENV_PY" - > /dev/null 2>&1 << 'PYEOF'
import os
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    exe = p.chromium.executable_path
    raise SystemExit(0 if exe and os.path.exists(exe) else 1)
PYEOF
}
if [ ! -x "$VENV_PY" ] || ! "$VENV_PY" -c 'import playwright' > /dev/null 2>&1; then
  falta "navegador dos elementos 3D (depende das bibliotecas)"
elif navegador_ok; then
  pronto "navegador já instalado"
elif [ "$SO_CONFERIR" = 1 ]; then
  falta "navegador dos elementos 3D"
else
  echo "      Baixando o navegador. No Linux isso pode pedir a senha do computador."
  if [ "$SISTEMA" = "mac" ]; then
    quieto "$VENV_PY" -m playwright install chromium || parar "não consegui baixar o navegador."
  else
    quieto "$VENV_PY" -m playwright install --with-deps chromium || parar "não consegui baixar o navegador."
  fi
  feito "navegador instalado"
fi

# 7. Conferência final ----------------------------------------------------------------------------
passo "Conferindo se tudo funciona junto"
if [ -z "$FALTA" ] && [ -x "$VENV_PY" ]; then
  if quieto "$VENV_PY" tests/ambiente.py; then
    quebrados=""
    for s in skill/welldit/scripts/*.py; do
      "$VENV_PY" "$s" --help > /dev/null 2>&1 || quebrados="$quebrados $(basename "$s")"
    done
    if [ -z "$quebrados" ]; then
      pronto "todos os programas da skill respondem"
    else
      echo "      Alguns programas da skill não abriram:$quebrados" >> "$LOG"
      falta "alguns programas da skill não abriram (veja o instalacao.log)"
    fi
  else
    falta "o ffmpeg não passou na conferência final"
  fi
else
  pronto "(conferência final só depois que tudo estiver instalado)"
fi

echo
if [ -n "$FALTA" ]; then
  echo "Ainda falta:$FALTA"
  if [ "$SO_CONFERIR" = 1 ]; then
    echo "Rode ./instalar.sh (sem --so-conferir) para instalar."
  else
    echo "Rode ./instalar.sh de novo depois de resolver, ou mande o instalacao.log para quem mantém o projeto."
  fi
  exit 1
fi
if [ "$MUDOU" = 0 ]; then
  echo "Tudo já estava pronto. Nada foi alterado."
else
  echo "Tudo pronto!"
fi
echo
echo "Próximo passo: abra esta pasta no VS Code (menu Arquivo, Abrir Pasta) e abra o Claude Code."
echo "Na primeira transcrição de um vídeo, a skill baixa o modelo de transcrição (cerca de 1,6 GB). Só essa vez."
exit 0
