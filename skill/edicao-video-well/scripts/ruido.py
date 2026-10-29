"""Mede o ruído de fundo da gravação e tira o chiado da voz.

Uso:
    python ruido.py medir VIDEO [VIDEO ...]
    python ruido.py testar VIDEO --modo leve|forte --saida teste.wav   (ouvir antes e depois)

Como mede: separa fala e pausa no áudio (mesma medida dos cortes), tira 60 ms das
pontas de cada pausa e compara o nível das pausas com o da fala.

- 30 dB ou mais de diferença: gravação limpa, não precisa tratar.
- entre 20 e 30 dB: chiado perceptível, sugere "leve".
- abaixo de 20 dB: ruído forte, sugere "forte".

Como trata (ideia do editonny, que comparou vários métodos):
    corta o grave abaixo de 80 Hz e passa o filtro de ruído do ffmpeg (afftdn) com uma
    amostra do próprio ruído, tirada das pausas da gravação (até 2 s).
- leve: redução de 10 dB. forte: 20 dB.
- O piso do filtro fica 3 dB acima do ruído medido (o padrão do ffmpeg anularia a amostra).
- Com menos de 0,3 s de pausa, usa as janelas mais silenciosas; aí o "forte" vira "leve".
- Se nem as janelas mais silenciosas ficam longe da fala, não mexe (tratar estragaria a voz).

O filtro atrasa o som em alguns milissegundos; o atraso é medido uma vez e
descontado, então a voz continua no mesmo instante da imagem.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np

from comum import TAXA_ANALISE, carregar_mono, envelope_db, erro, exigir
from fala import PASSO, medir_fala

TAXA = 48000
REDUCAO = {"leve": 10, "forte": 20}
PONTA = 0.06            # tira isso das pontas de cada pausa (respiração, fim de palavra)
AMOSTRA_MAX = 2.0       # segundos de ruído usados como amostra
PAUSA_MINIMA = 0.3      # abaixo disso usa as janelas mais silenciosas
LIMPO_DB = 30.0
LEVE_DB = 20.0


def pausas(regioes: list, duracao: float) -> list[tuple[float, float]]:
    """Intervalos sem fala, já sem as pontas."""
    saida, anterior = [], 0.0
    for a, b in regioes + [[duracao, duracao]]:
        ini, fim = anterior + PONTA, a - PONTA
        if fim - ini >= 0.05:
            saida.append((ini, fim))
        anterior = b
    return saida


def _nivel_db(pedacos: list[np.ndarray]) -> float | None:
    junto = np.concatenate(pedacos) if pedacos else np.zeros(0)
    if junto.size == 0:
        return None
    return float(10 * np.log10(max(np.mean(junto.astype(np.float64) ** 2), 1e-12)))


def medir(arquivo) -> dict:
    """Nível de fala e de ruído (dB) e a sugestão de tratamento."""
    audio = carregar_mono(arquivo)
    duracao = len(audio) / TAXA_ANALISE
    env = envelope_db(audio)
    regioes = medir_fala(env)["regioes"]
    p = pausas(regioes, duracao)
    total_pausa = sum(b - a for a, b in p)
    fala = _nivel_db([audio[int(a * TAXA_ANALISE):int(b * TAXA_ANALISE)] for a, b in regioes])
    if total_pausa >= PAUSA_MINIMA:
        ruido = _nivel_db([audio[int(a * TAXA_ANALISE):int(b * TAXA_ANALISE)] for a, b in p])
        base = "pausas"
    else:
        # Quase sem pausa: as janelas de 50 ms mais silenciosas (pegam os vales do ruído,
        # então o valor sai um pouco baixo e o piso sobe 3 dB a mais).
        n = int(0.05 * TAXA_ANALISE)
        janelas = [audio[k:k + n] for k in range(0, len(audio) - n, n)]
        niveis = sorted(janelas, key=lambda j: float(np.mean(j.astype(np.float64) ** 2)))
        quantas = max(1, min(int(AMOSTRA_MAX / 0.05), len(niveis) // 10))
        ruido = _nivel_db(niveis[:quantas])
        base = "janelas silenciosas"
    if fala is None or ruido is None:
        return {"fala_db": fala, "ruido_db": ruido, "diferenca_db": None, "sugestao": "nao", "base": base,
                "pausa_s": round(float(total_pausa), 2)}
    dif = fala - ruido
    if dif >= LIMPO_DB:
        sugestao = "nao"
    elif dif >= LEVE_DB:
        sugestao = "leve"
    else:
        sugestao = "forte"
    return {"fala_db": round(fala, 1), "ruido_db": round(ruido, 1), "diferenca_db": round(dif, 1),
            "sugestao": sugestao, "base": base, "pausa_s": round(float(total_pausa), 2)}


def medir_estouro(arquivo) -> dict:
    """Áudio estourado: topo da onda achatado (várias amostras seguidas no teto).

    Lê na taxa original, canal por canal (reamostrar alisa o achatamento e esconde o
    problema). Limitador forte também deixa a onda perto do teto, por isso só três ou
    mais amostras idênticas seguidas contam, e o resultado é "certo", "possível" ou "não".
    """
    info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                           "stream=sample_rate,channels", "-of", "csv=p=0", str(arquivo)],
                          capture_output=True, text=True).stdout.strip().split(",")
    if len(info) < 2 or not info[0]:
        return {"estouro": "não", "momentos": []}
    taxa, canais = int(info[0]), int(info[1])
    bruto = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(arquivo), "-vn", "-map", "0:a:0",
                            "-f", "f32le", "-"], check=True, capture_output=True).stdout
    som = np.frombuffer(bruto, dtype=np.float32).reshape(-1, canais)
    pico = float(np.max(np.abs(som))) if som.size else 0.0
    if pico < 0.89:  # mais de 1 dB abaixo do máximo: não encostou no teto
        return {"estouro": "não", "pico": round(pico, 3), "momentos": []}
    eventos = []
    for c in range(canais):
        x = som[:, c]
        perto = np.abs(x) >= 0.98 * pico
        iguais = np.concatenate([[False], np.isclose(x[1:], x[:-1], atol=1e-6)])
        plato = perto & iguais
        m = np.concatenate([[False], plato, [False]])
        d = np.diff(m.astype(np.int8))
        inicios, fins = np.where(d == 1)[0], np.where(d == -1)[0]
        for a, b in zip(inicios, fins):
            if b - a >= 2:  # 3 amostras ou mais no mesmo valor
                eventos.append(a / taxa)
    eventos.sort()
    agrupados = []
    for t in eventos:
        if not agrupados or t - agrupados[-1][-1] > 0.25:
            agrupados.append([t])
        else:
            agrupados[-1].append(t)
    acima = int(np.sum(np.abs(som) > 1.0))
    if len(agrupados) >= 5 or acima > 10:
        nivel = "certo"
    elif agrupados:
        nivel = "possível"
    else:
        nivel = "não"
    return {"estouro": nivel, "pico": round(pico, 3), "vezes": len(agrupados),
            "momentos": [round(float(g[0]), 2) for g in agrupados[:8]]}


def medir_eco(arquivo) -> dict:
    """Eco da sala: quanto tempo o som leva para morrer no fim de cada frase.

    Em cada fim de fala seguido de pausa (0,3 s ou mais), parte do ponto mais forte dos
    últimos 300 ms e mede quanto tempo o nível leva para cair 20 dB (ou chegar perto do
    ruído de fundo). Com a velocidade da queda estima o tempo de reverberação (o tempo
    para cair 60 dB). Fala em sala seca dá perto de 0,6 s nessa conta (a própria sílaba
    demora a sumir); a partir de 0,85 s já tem eco; acima de 1,2 s o eco é forte.
    É uma estimativa: serve de aviso, não de prova.
    """
    audio = carregar_mono(arquivo)
    env = envelope_db(audio)
    m = medir_fala(env)
    regioes = m["regioes"]
    tempos = []
    for (a, b), (c, _) in zip(regioes, regioes[1:] + [[1e9, 1e9]]):
        if c - b < 0.3:
            continue
        k0, k1 = max(0, int((b - 0.3) / PASSO)), min(len(env), int(b / PASSO) + 40)
        trecho = env[k0:k1]
        if len(trecho) < 35:
            continue
        pico = int(np.argmax(trecho[:30]))
        topo = float(trecho[pico])
        alvo = max(topo - 20, m["ruido_db"] + 3)
        if topo - alvo < 8:
            continue
        abaixo = np.where(trecho[pico:] <= alvo)[0]
        if len(abaixo):
            tempos.append(abaixo[0] * PASSO * 60 / (topo - alvo))
    if len(tempos) < 4:
        return {"eco": "sem medida", "reverberacao_s": None, "medidas": len(tempos)}
    rt = float(np.median(tempos))
    return {"eco": "sim" if rt > 1.2 else ("pouco" if rt > 0.85 else "não"),
            "reverberacao_s": round(rt, 2), "medidas": len(tempos)}


def decodificar(arquivo: str, canais: int) -> np.ndarray:
    bruto = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", str(arquivo), "-vn", "-map", "0:a:0",
         "-ac", str(canais), "-ar", str(TAXA), "-f", "f32le", "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(bruto, dtype=np.float32).reshape(-1, canais)


def _filtrar(som: np.ndarray, filtro: str) -> np.ndarray:
    canais = som.shape[1]
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-f", "f32le", "-ar", str(TAXA), "-ac", str(canais), "-i", "-",
         "-af", filtro, "-f", "f32le", "-ar", str(TAXA), "-ac", str(canais), "-"],
        input=np.ascontiguousarray(som, dtype=np.float32).tobytes(), capture_output=True)
    if proc.returncode != 0:
        erro("o filtro de ruído falhou: " + proc.stderr.decode(errors="replace")[-500:])
    return np.frombuffer(proc.stdout, dtype=np.float32).reshape(-1, canais)


@lru_cache(maxsize=None)
def atraso_do_filtro() -> int:
    """Quantas amostras o afftdn atrasa o som (medido com um estalo, uma vez por ffmpeg)."""
    som = np.zeros((TAXA, 1), np.float32)
    som[TAXA // 2, 0] = 0.8
    saida = _filtrar(som, "afftdn=nr=10:nf=-60")
    return max(0, int(np.argmax(np.abs(saida[:, 0]))) - TAXA // 2)


def amostra_de_ruido(som: np.ndarray, pausas_s: list[tuple[float, float]]) -> np.ndarray:
    """Junta as pausas mais longas (até 2 s), com 5 ms de transição entre elas."""
    pedacos, total = [], 0
    limite = int(AMOSTRA_MAX * TAXA)
    for a, b in sorted(pausas_s, key=lambda x: x[1] - x[0], reverse=True):
        p = som[int(a * TAXA):int(b * TAXA)]
        if len(p) < int(0.04 * TAXA):
            continue
        pedacos.append(p[:limite - total])
        total += len(pedacos[-1])
        if total >= limite:
            break
    if not pedacos:
        return np.zeros((0, som.shape[1]), np.float32)
    n = int(0.005 * TAXA)
    saida = pedacos[0]
    for p in pedacos[1:]:
        if len(saida) > n and len(p) > n:
            r = np.linspace(0, 1, n, dtype=np.float32)[:, None]
            saida = np.vstack([saida[:-n], saida[-n:] * (1 - r) + p[:n] * r, p[n:]])
        else:
            saida = np.vstack([saida, p])
    return saida


def limpar(arquivo: str, som: np.ndarray, modo: str) -> tuple[np.ndarray, dict]:
    """Devolve o som sem chiado (mesmo tamanho, mesmo instante) e o que foi feito."""
    if modo not in REDUCAO:
        return som, {"modo": "nao"}
    exigir("ffmpeg")
    m = medir(arquivo)
    if m["diferenca_db"] is None or m["diferenca_db"] < 6:
        return som, {"modo": "nao", "motivo": "o ruído está quase no nível da voz; tratar estragaria a fala", **m}
    feito = modo
    if m["base"] != "pausas" and modo == "forte":
        feito = "leve"
    duracao = len(som) / TAXA
    audio16 = carregar_mono(arquivo)
    regioes = medir_fala(envelope_db(audio16))["regioes"]
    if m["base"] == "pausas":
        trechos = pausas(regioes, duracao)
    else:
        env = envelope_db(audio16)
        ordem = np.argsort(env)[:max(1, int(AMOSTRA_MAX / PASSO))]
        trechos = [(k * PASSO, k * PASSO + 0.05) for k in sorted(ordem)]
    clip = amostra_de_ruido(som, trechos)
    if len(clip) < int(0.05 * TAXA):
        return som, {"modo": "nao", "motivo": "não achei ruído limpo para usar de amostra", **m}
    piso = float(np.clip(m["ruido_db"] + 3.0 + (3.0 if m["base"] != "pausas" else 0.0), -80, -20))
    atraso = atraso_do_filtro()
    fim_clip = len(clip) / TAXA
    filtro = (f"asendcmd=c='0.0 afftdn@dn sn start\\; {max(0.01, fim_clip - 0.01):.3f} afftdn@dn sn stop',"
              f"highpass=f=80:p=2,afftdn@dn=nr={REDUCAO[feito]}:nf={piso:.1f}")
    entrada = np.vstack([clip, som, np.zeros((atraso, som.shape[1]), np.float32)])
    saida = _filtrar(entrada, filtro)
    inicio = len(clip) + atraso
    limpo = saida[inicio:inicio + len(som)]
    if len(limpo) < len(som):
        limpo = np.vstack([limpo, np.zeros((len(som) - len(limpo), som.shape[1]), np.float32)])
    return np.ascontiguousarray(limpo), {"modo": feito, "reducao_db": REDUCAO[feito], "piso_db": round(piso, 1),
                                         "amostra_s": round(fim_clip, 2), "atraso_amostras": atraso, **m}


def salvar_wav(som: np.ndarray, destino: Path):
    pcm = (np.clip(som, -1, 1) * 32767).astype("<i2")
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(som.shape[1])
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["medir", "testar"])
    ap.add_argument("videos", nargs="+", type=Path)
    ap.add_argument("--modo", choices=["leve", "forte"], default="leve")
    ap.add_argument("--saida", type=Path, help="wav de teste (só com testar)")
    a = ap.parse_args()
    for v in a.videos:
        if not v.exists():
            erro(f"arquivo não encontrado: {v}")
        if a.acao == "medir":
            m = medir(v)
            nomes = {"nao": "limpo, não precisa", "leve": "leve", "forte": "forte"}
            print(f"{v.name}: voz {m['fala_db']} dB · ruído {m['ruido_db']} dB · diferença {m['diferenca_db']} dB "
                  f"→ sugestão: {nomes[m['sugestao']]}  (medido em {m['base']}, {m['pausa_s']} s de pausa)")
        else:
            som = decodificar(str(v), 1)
            limpo, feito = limpar(str(v), som, a.modo)
            destino = a.saida or v.with_name(f"{v.stem}.ruido-{a.modo}.wav")
            salvar_wav(np.hstack([som, limpo]) if som.shape[1] == 1 else limpo, destino)
            print(f"{v.name}: {feito}")
            print(f"ok  {destino}  (canal esquerdo: original · direito: tratado)")
    sys.exit(0)


if __name__ == "__main__":
    main()
