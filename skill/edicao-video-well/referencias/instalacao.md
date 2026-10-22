# Instalação

Precisa, no computador onde o Claude Code roda:

| Ferramenta | Para quê | Como instalar |
| --- | --- | --- |
| Python 3.10 ou mais novo | rodar os scripts | já vem no Mac recente; ou `brew install python` |
| ffmpeg e ffprobe | ler, cortar e montar o vídeo | Mac: `brew install ffmpeg` · Linux: `apt install ffmpeg` |
| faster-whisper, numpy, fonttools, playwright | transcrição local, medida da legenda, desenho dos elementos 3D | `pip install -r scripts/requirements.txt` |
| Chromium do Playwright | desenhar os elementos 3D | `python -m playwright install chromium` (ou usa o Google Chrome instalado) |

O ffmpeg precisa ter `libass` (legenda) e `zimg` (conversão de HDR). O do Homebrew e o do Ubuntu já vêm com os dois. Confira com:

```bash
ffmpeg -hide_banner -filters | grep -E " (ass|zscale) "
```

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
