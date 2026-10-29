# Instalação

Precisa, no computador onde o Claude Code roda:

| Ferramenta | Para quê | Como instalar |
| --- | --- | --- |
| Python 3.12 (de 3.10 a 3.13) | rodar os scripts | Mac: `brew install python@3.12`. O 3.14 ainda não funciona com o faster-whisper; o `python3` padrão do Mac (3.9) é velho demais |
| ffmpeg e ffprobe completos | ler, cortar e montar o vídeo | Mac: `brew install ffmpeg-full` (o `ffmpeg` simples do Homebrew vem sem legenda e sem conversão de HDR) · Linux: `apt install ffmpeg` |
| faster-whisper, numpy, fonttools, playwright, opencv | transcrição local, medida da legenda, desenho dos elementos 3D, detecção do rosto e zoom | `pip install -r scripts/requirements.txt` |
| Chromium do Playwright | desenhar os elementos 3D | `python -m playwright install chromium` (ou usa o Google Chrome instalado) |

O ffmpeg precisa ter `libass` (legenda), `zimg` (conversão de HDR) e o filtro de ruído `afftdn`. O `ffmpeg-full` do Homebrew e o do Ubuntu vêm com tudo. O `ffmpeg-full` não substitui o comando `ffmpeg` do sistema: ponha o caminho dele no ambiente (`echo 'export PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH"' >> .venv/bin/activate`). O passo a passo completo está no README do projeto, em "Instalar no seu Mac, com o VS Code". Confira com:

```bash
ffmpeg -hide_banner -filters | grep -E " (ass|zscale|afftdn|asendcmd) "
```

As músicas e os efeitos sonoros (cerca de 8 MB) e o detector de rosto já vêm dentro da skill. Nada é baixado na hora.

## Modelo de transcrição

Na primeira transcrição o modelo é baixado da internet e fica guardado:

- `large-v3-turbo` (padrão): cerca de 1,6 GB, melhor qualidade.
- `small`: cerca de 500 MB, bem mais rápido, bom para teste.

Depois disso nada sai do computador.

## Ambiente isolado (recomendado)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r skill/edicao-video-well/scripts/requirements.txt
python -m playwright install chromium
```

## Onde rodar

A skill foi feita para o Claude Code (no computador do Well ou numa sessão na nuvem com os vídeos acessíveis). No Claude.ai pelo navegador o limite de envio de arquivo e a falta do ffmpeg costumam impedir a edição de vídeo.
