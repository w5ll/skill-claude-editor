"""Medição de fala e silêncio no áudio, e ajuste das palavras do Whisper a ela."""

from __future__ import annotations

import numpy as np

PASSO = 0.01           # o envelope tem um valor a cada 10 ms
ALCANCE = 0.12         # quanto a borda pode avançar sobre som fraco
JUNTA_INTERNA = 0.12   # buracos menores que isso são parte da mesma fala
FALA_MINIMA = 0.06     # estalos mais curtos que isso viram silêncio


def ilhas(mascara: np.ndarray) -> list[tuple[int, int]]:
    """Trechos contínuos onde a máscara é verdadeira, em índices do envelope."""
    m = np.concatenate([[False], mascara, [False]])
    d = np.diff(m.astype(int))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def medir_fala(env: np.ndarray) -> dict:
    ruido = float(np.percentile(env, 10))
    fala = float(np.percentile(env, 95))
    limiar = ruido + 0.4 * (fala - ruido)
    limiar = min(max(limiar, ruido + 6), fala - 12)
    fraco = ruido + 4  # som fraco que ainda pode ser consoante

    brutas = [(a, b) for a, b in ilhas(env > limiar)]
    juntas: list[list[int]] = []
    for a, b in brutas:
        if juntas and (a - juntas[-1][1]) * PASSO < JUNTA_INTERNA:
            juntas[-1][1] = b
        else:
            juntas.append([a, b])
    regioes = []
    alcance = int(ALCANCE / PASSO)
    for a, b in juntas:
        if (b - a) * PASSO < FALA_MINIMA:
            continue
        ia = a
        while ia > 0 and a - ia < alcance and env[ia - 1] > fraco:
            ia -= 1
        fb = b
        while fb < len(env) and fb - b < alcance and env[fb] > fraco:
            fb += 1
        regioes.append([ia * PASSO, fb * PASSO])
    return {"ruido_db": round(ruido, 1), "fala_db": round(fala, 1), "limiar_db": round(limiar, 1),
            "regioes": regioes}



def regiao_de(t: float, regioes: list) -> int | None:
    for k, (a, b) in enumerate(regioes):
        if a - 0.02 <= t <= b + 0.02:
            return k
    return None


def ajustar_palavras(palavras: list[dict], regioes: list) -> list[dict]:
    """Encaixa as palavras na fala medida.

    O Whisper erra as bordas: estica a primeira palavra sobre o silêncio inicial e
    às vezes faz uma palavra atravessar uma pausa inteira. Aqui a palavra que
    começa no silêncio passa a começar na fala seguinte, e a que atravessa uma
    pausa fica presa à fala da palavra vizinha colada nela.
    """
    if not regioes:
        return palavras
    saida = []
    for n, w in enumerate(palavras):
        i, f = w["i"], w["f"]
        ri, rf = regiao_de(i, regioes), regiao_de(f, regioes)
        if ri is None:  # começa no silêncio: puxa para a próxima fala
            prox = next((a for a, b in regioes if a >= i), None)
            if prox is not None and prox < f:
                i, ri = prox, regiao_de(prox, regioes)
        if rf is None:  # termina no silêncio: recua para o fim da fala anterior
            ant = next((b for a, b in reversed(regioes) if b <= f), None)
            if ant is not None and ant > i:
                f, rf = ant, regiao_de(ant, regioes)
        if ri is not None and rf is not None and ri != rf:
            seguinte = palavras[n + 1] if n + 1 < len(palavras) else None
            if seguinte is not None and abs(seguinte["i"] - w["f"]) < 0.03:
                i = max(i, regioes[rf][0])           # fica com a fala de depois
            else:
                f = min(f, regioes[ri][1])           # fica com a fala de antes
        saida.append({**w, "i": round(i, 3), "f": round(max(f, i + 0.04), 3)})
    return saida


def regioes_sem_palavra(palavras: list[dict], regioes: list, minimo: float = 0.35) -> list:
    return [[a, b] for a, b in regioes
            if b - a >= minimo and not any(w["f"] > a + 0.03 and w["i"] < b - 0.03 for w in palavras)]
