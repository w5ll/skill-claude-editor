"""Transcreve a fala de cada vídeo, palavra por palavra, no próprio computador.

Uso:
    python transcrever.py VIDEO [VIDEO ...] --pasta saida/2026-10-22_tema
        [--modelo large-v3-turbo] [--idioma pt] [--termos "nomes que aparecem neste vídeo"] [--refazer]
    python transcrever.py VIDEO --pasta saida/... --trecho 165 178
        (transcreve de novo só esse pedaço, sem termos, e troca as palavras dele)

--termos: só nomes e palavras difíceis que aparecem NESTE vídeo (tirados do roteiro).
Termo que não aparece na fala atrapalha: quando o Whisper não entende um trecho, ele
costuma "inventar" palavras da lista ("OAB, OAB, OAB"). Na dúvida, não passe termos.

Trecho com som de fala que o Whisper não reconheceu não é descartado: vai para
"sem_transcricao" no arquivo, e o propor_cortes.py manda conferir em vez de cortar.

Grava transcricoes/<nome-do-video>.json com o tempo de início e fim de cada palavra.
O modelo é baixado uma única vez (cerca de 1,6 GB no large-v3-turbo; use --modelo small
para um teste rápido). Nada é enviado para fora do computador.

A transcrição serve para achar erros, repetições e montar a legenda. Os pontos de
corte em si vêm da medição do áudio (propor_cortes.py), que é mais precisa.
"""

from __future__ import annotations

import argparse
import re
import time
import unicodedata
from pathlib import Path

from comum import TAXA_ANALISE, carregar_mono, envelope_db, erro, ler_json, salvar_json
from fala import ajustar_palavras, medir_fala, regioes_sem_palavra

# Frases que o Whisper costuma inventar no silêncio.
ALUCINACOES = (
    "legendas pela comunidade amara org",
    "obrigado por assistir",
    "inscreva se no canal",
    "legenda adriana zanotto",
)


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", t).strip()


def assinatura(arquivo: Path) -> str:
    st = arquivo.stat()
    return f"{st.st_size}-{int(st.st_mtime)}"


def eco_dos_termos(seg, termos: set[str]) -> bool:
    """Segmento inventado: só repete termos da lista ou a mesma palavra várias vezes."""
    palavras = [normalizar(w.word) for w in (seg.words or []) if normalizar(w.word)]
    if not palavras:
        return False
    prob = sum(float(w.probability) for w in seg.words) / len(seg.words)
    if termos and all(p in termos for p in palavras) and (len(palavras) >= 2 or prob < 0.6):
        return True
    return len(palavras) >= 3 and len(set(palavras)) == 1


def _palavras(segmentos, deslocamento: float = 0.0, termos: set[str] | None = None) -> list[dict]:
    palavras = []
    for seg in segmentos:
        if any(a in normalizar(seg.text) for a in ALUCINACOES):
            continue
        if eco_dos_termos(seg, termos or set()):
            continue
        for w in seg.words or []:
            texto = w.word.strip()
            if not texto:
                continue
            palavras.append({
                "p": texto,
                "i": round(float(w.start) + deslocamento, 3),
                "f": round(float(w.end) + deslocamento, 3),
                "conf": round(float(w.probability), 3),
            })
    return palavras


def transcrever(arquivo: Path, modelo, idioma: str | None, termos: str) -> dict:
    audio = carregar_mono(arquivo)
    opcoes = dict(
        language=idioma,
        word_timestamps=True,
        condition_on_previous_text=False,  # evita repetir frases inventadas
        initial_prompt=termos or None,
        beam_size=5,
        vad_filter=False,  # os tempos ficam fiéis ao original
    )
    lista_termos = {normalizar(t) for t in re.split(r"[,;]", termos or "") if normalizar(t)}
    segmentos, info = modelo.transcribe(audio, **opcoes)
    palavras = _palavras(segmentos, termos=lista_termos)

    # Encaixa as palavras na fala medida no áudio.
    regioes = medir_fala(envelope_db(audio))["regioes"]
    palavras = ajustar_palavras(palavras, regioes)

    # O Whisper costuma pular frases repetidas (acha que é eco). Cada trecho de fala
    # que ficou sem palavra é transcrito de novo, sozinho.
    # Sem os termos: com eles, o Whisper inventa palavras da lista onde não entendeu.
    recuperadas = 0
    opcoes["language"] = info.language
    opcoes["initial_prompt"] = None
    for a, b in regioes_sem_palavra(palavras, regioes):
        ini, fim = max(0.0, a - 0.15), b + 0.15
        pedaco = audio[int(ini * TAXA_ANALISE):int(fim * TAXA_ANALISE)]
        segs, _ = modelo.transcribe(pedaco, **opcoes)
        novas = [w for w in _palavras(segs, ini, lista_termos) if w["f"] > a and w["i"] < b]
        for w in novas:
            w["recuperada"] = True
        palavras += novas
        recuperadas += len(novas)
    if recuperadas:
        palavras.sort(key=lambda w: w["i"])
        palavras = ajustar_palavras(palavras, regioes)

    sem = [[round(a, 2), round(b, 2)] for a, b in regioes_sem_palavra(palavras, regioes, minimo=0.6)]
    return {
        "arquivo": str(arquivo.resolve()),
        "sem_transcricao": sem,
        "idioma": info.language,
        "certeza_idioma": round(float(info.language_probability), 3),
        "texto": " ".join(p["p"] for p in palavras),
        "palavras_recuperadas": recuperadas,
        "palavras": palavras,
    }


def retranscrever_trecho(video: Path, pasta: Path, nome_modelo: str, idioma: str, ini: float, fim: float):
    from faster_whisper import WhisperModel
    destino = pasta / "transcricoes" / f"{video.stem}.json"
    if not destino.exists():
        erro("transcreva o vídeo inteiro antes")
    dados = ler_json(destino)
    audio = carregar_mono(video)
    a0, b0 = max(0.0, ini), min(len(audio) / TAXA_ANALISE, fim)
    print(f"carregando o modelo {nome_modelo}...")
    modelo = WhisperModel(nome_modelo, device="auto", compute_type="int8")
    pedaco = audio[int(a0 * TAXA_ANALISE):int(b0 * TAXA_ANALISE)]
    segs, _ = modelo.transcribe(pedaco, language=None if idioma == "auto" else idioma, word_timestamps=True,
                                condition_on_previous_text=False, initial_prompt=None, beam_size=5, vad_filter=False)
    novas = [w for w in _palavras(segs, a0) if w["i"] >= a0 - 0.05 and w["f"] <= b0 + 0.05]
    regioes = medir_fala(envelope_db(audio))["regioes"]
    novas = ajustar_palavras(novas, regioes)
    for w in novas:
        w["retranscrita"] = True
    fora = [w for w in dados["palavras"] if not (a0 <= (w["i"] + w["f"]) / 2 <= b0)]
    dados["palavras"] = sorted(fora + novas, key=lambda w: w["i"])
    dados["texto"] = " ".join(w["p"] for w in dados["palavras"])
    dados["sem_transcricao"] = [[round(x, 2), round(y, 2)]
                                for x, y in regioes_sem_palavra(dados["palavras"], regioes, minimo=0.6)]
    salvar_json(destino, dados)
    print(f"ok  {destino}  (trecho {a0:.1f}-{b0:.1f} s: {len(novas)} palavras)")
    print("    " + " ".join(w["p"] for w in novas))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("videos", nargs="+", type=Path)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--modelo", default="large-v3-turbo")
    ap.add_argument("--idioma", default="pt", help="pt por padrão; use auto para detectar")
    ap.add_argument("--termos", default="", help="nomes próprios e termos que aparecem na fala")
    ap.add_argument("--refazer", action="store_true", help="ignora a transcrição já salva")
    ap.add_argument("--trecho", nargs=2, type=float, metavar=("INICIO", "FIM"),
                    help="transcreve de novo só esse pedaço (segundos do vídeo bruto), sem termos")
    a = ap.parse_args()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        erro("faster-whisper não está instalado. Rode: pip install -r scripts/requirements.txt")

    if a.trecho:
        if len(a.videos) != 1:
            erro("--trecho funciona com um vídeo por vez")
        retranscrever_trecho(a.videos[0], a.pasta, a.modelo, a.idioma, *a.trecho)
        return

    modelo = None
    for video in a.videos:
        if not video.exists():
            erro(f"arquivo não encontrado: {video}")
        destino = a.pasta / "transcricoes" / f"{video.stem}.json"
        if destino.exists() and not a.refazer:
            salvo = ler_json(destino)
            if salvo.get("assinatura") == assinatura(video) and salvo.get("termos", "") == a.termos:
                print(f"já transcrito  {destino}")
                continue
        if modelo is None:
            print(f"carregando o modelo {a.modelo} (a primeira vez baixa da internet)...")
            modelo = WhisperModel(a.modelo, device="auto", compute_type="int8")
        t0 = time.time()
        dados = transcrever(video, modelo, None if a.idioma == "auto" else a.idioma, a.termos)
        dados["assinatura"] = assinatura(video)
        dados["termos"] = a.termos
        dados["modelo"] = a.modelo
        salvar_json(destino, dados)
        print(f"ok  {destino}  ({len(dados['palavras'])} palavras em {time.time() - t0:.0f} s)")
        print(f"    {dados['texto'][:300]}{'...' if len(dados['texto']) > 300 else ''}")


if __name__ == "__main__":
    main()
