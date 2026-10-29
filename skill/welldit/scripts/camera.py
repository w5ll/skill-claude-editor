"""Zoom de ênfase: dá ritmo de corte de câmera num vídeo gravado com uma câmera só.

Uso:
    python camera.py planejar --pasta saida/2026-10-22_tema [--intensidade leve|normal|forte]
    python camera.py desligar --pasta saida/2026-10-22_tema

planejar  lê a fala já cortada e grava camera.json:
          - a cada frase o enquadramento alterna entre aberto (100%) e um pouco mais perto
            (112% no normal), como se fossem duas câmeras;
          - nas palavras fortes (negação como "nunca", "nenhum", "não"; números; "dobro",
            "metade") a câmera dá uma aproximação rápida (125%) e segura 0,6 s depois da palavra;
            a mesma palavra no máximo 2 vezes e nunca em duas ênfases seguidas;
          - frase longa (mais de 4,5 s) é dividida em duas; frase curta (menos de 1,2 s) junta
            com a seguinte; mudança a menos de 0,25 s de um corte vai para o corte;
          - nunca muda o zoom no meio de um elemento 3D (o elemento foi posicionado para
            aquele enquadramento): a troca espera o elemento sair; e nunca menos de 2,5 s
            depois da mudança anterior.
desligar  apaga camera.json (o vídeo sai com a câmera parada).

O zoom cresce em volta do rosto (rosto.json): o rosto fica no mesmo lugar da tela e só
aumenta, então nunca sai do quadro. Sem rosto.json, cresce em volta do centro, um pouco
acima do meio. Tudo é proposta: dá para apagar ou mudar blocos à mão no camera.json.
Depois de mudar a câmera, gere a legenda de novo (ela desvia do rosto já com o zoom).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from comum import erro, fps_racional, ler_json, salvar_json, tempo, trechos_no_quadro

INTENSIDADES = {
    # aberto, perto, aproximação de ênfase
    "leve": (1.0, 1.06, 1.15),
    "normal": (1.0, 1.12, 1.25),
    "forte": (1.0, 1.15, 1.30),
}
INTERVALO_MIN = 2.5     # segundos entre uma mudança e outra
FRASE_LONGA = 4.5
FRASE_CURTA = 1.2
SEGURA = 0.6            # a aproximação segura isso depois do fim da palavra
ENFASE_MIN = 4.0        # segundos entre duas aproximações
ENCOSTA_CORTE = 0.25

NEGACOES = {"nao", "nunca", "nem", "nada", "ninguem", "jamais", "nenhum", "nenhuma", "zero"}
NUMEROS = {"dois", "duas", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
           "treze", "catorze", "quatorze", "quinze", "vinte", "trinta", "quarenta", "cinquenta", "sessenta",
           "setenta", "oitenta", "noventa", "cem", "cento", "duzentos", "trezentos", "quinhentos", "mil",
           "milhao", "milhoes", "bilhao", "bilhoes", "dobro", "triplo", "metade"}


def normalizar(p: str) -> str:
    t = unicodedata.normalize("NFKD", p.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9%]+", "", t)


def eh_forte(p: str) -> bool:
    n = normalizar(p)
    if n in NEGACOES or n in NUMEROS:
        return True
    return bool(re.fullmatch(r"\d+%?", n)) and n not in {"1", "0"}


def frases(palavras: list[dict]) -> list[list[dict]]:
    grupos, atual = [], []
    for w in palavras:
        if atual and (w["i"] - atual[-1]["f"] > 0.35 or re.search(r"[.?!…]$", atual[-1]["p"])):
            grupos.append(atual)
            atual = []
        atual.append(w)
    if atual:
        grupos.append(atual)
    # longas viram duas (na maior pausa perto do meio)
    saida = []
    for g in grupos:
        if g[-1]["f"] - g[0]["i"] > FRASE_LONGA and len(g) >= 4:
            meio = (g[0]["i"] + g[-1]["f"]) / 2
            k = min(range(1, len(g)), key=lambda j: abs(g[j]["i"] - meio) - (g[j]["i"] - g[j - 1]["f"]) * 2)
            saida += [g[:k], g[k:]]
        else:
            saida.append(g)
    # curtas juntam com a seguinte
    juntas = []
    for g in saida:
        if juntas and juntas[-1][-1]["f"] - juntas[-1][0]["i"] < FRASE_CURTA:
            juntas[-1] = juntas[-1] + g
        else:
            juntas.append(g)
    return juntas


def janelas_ocupadas(pasta: Path) -> list[tuple[float, float]]:
    """Elementos 3D: a câmera não muda enquanto eles estão na tela."""
    arq = pasta / "elementos.json"
    if not arq.exists():
        return []
    return [(it["inicio"] - 0.05, it["inicio"] + it["duracao"] + 0.05) for it in ler_json(arq).get("itens", [])]


def planejar(pasta: Path, intensidade: str) -> dict:
    from legendas import palavras_no_corte
    insp = ler_json(pasta / "inspecao.json")["videos"][0]
    fps = fps_racional({"avg_frame_rate": insp["fps"]})
    cortes = ler_json(pasta / "cortes.json")
    palavras = palavras_no_corte(pasta, cortes, fps)
    trechos = trechos_no_quadro(cortes, fps)
    duracao = trechos[-1]["saida_fim"] if trechos else 0.0
    emendas = [t["saida_inicio"] for t in trechos[1:]]
    ocupado = janelas_ocupadas(pasta)
    aberto, perto, enfase = INTENSIDADES[intensidade]

    def livre(t: float) -> bool:
        return not any(a < t < b for a, b in ocupado)

    def encostar(t: float) -> float:
        prox = min(emendas, key=lambda e: abs(e - t), default=None)
        return prox if prox is not None and abs(prox - t) <= ENCOSTA_CORTE else t

    # 1. alternância por frase
    mudancas = [(0.0, aberto, "frase")]
    nivel = aberto
    for g in frases(palavras)[1:]:
        t = encostar(max(0.0, g[0]["i"] - 0.05))
        if not livre(t):
            # Elemento 3D na tela: a troca fica para quando ele sair, se a frase ainda continua.
            t = max(b for a, b in ocupado if a < t < b)
            if t > g[-1]["f"] - 1.0:
                continue
        if t - mudancas[-1][0] < INTERVALO_MIN - 1e-6:
            continue
        nivel = perto if nivel == aberto else aberto
        mudancas.append((t, nivel, "frase"))

    # 2. aproximações de ênfase
    blocos = []
    for k, (t, z, motivo) in enumerate(mudancas):
        fim = mudancas[k + 1][0] if k + 1 < len(mudancas) else duracao
        blocos.append({"inicio": round(t, 3), "fim": round(fim, 3), "zoom": z, "motivo": motivo})
    ultima_enfase = -99.0
    usadas: list[str] = []
    for w in palavras:
        if not eh_forte(w["p"]):
            continue
        n = normalizar(w["p"])
        # Variar: a mesma palavra no máximo 2 vezes no vídeo, e nunca duas ênfases seguidas nela.
        if usadas.count(n) >= 2 or (usadas and usadas[-1] == n):
            continue
        ini = max(0.0, w["i"] - 0.05)
        fim = min(duracao, w["f"] + SEGURA)
        if ini - ultima_enfase < ENFASE_MIN or fim - ini < 0.4:
            continue
        if not (livre(ini) and livre(fim)) or any(ini < a < fim or ini < b < fim for a, b in ocupado):
            continue
        # Mudança de frase colada na aproximação: as duas viram uma só (senão parece tremida).
        for b in blocos:
            if ini - 0.6 < b["inicio"] < ini and b["inicio"] > 0:
                ini = b["inicio"]
            if fim < b["inicio"] < fim + 0.6:
                fim = b["inicio"]
        if any(b["motivo"].startswith("ênfase") and b["fim"] > ini - 0.6 and b["inicio"] < fim + 0.6
               for b in blocos):
            continue
        novos = []
        for b in blocos:
            if b["fim"] <= ini or b["inicio"] >= fim:
                novos.append(b)
                continue
            if b["inicio"] < ini:
                novos.append({**b, "fim": round(ini, 3)})
            if b["fim"] > fim:
                novos.append({**b, "inicio": round(fim, 3)})
        novos.append({"inicio": round(ini, 3), "fim": round(fim, 3), "zoom": enfase,
                      "motivo": f"ênfase: {w['p'].strip('.,!?')}"})
        blocos = sorted(novos, key=lambda b: b["inicio"])
        ultima_enfase = ini
        usadas.append(n)
    return {"intensidade": intensidade, "duracao": round(duracao, 3), "blocos": blocos}


class Camera:
    """Zoom e ponto fixo em cada instante do vídeo cortado (antes da legenda e dos elementos)."""

    def __init__(self, dados: dict, largura: int, altura: int, rostos=None):
        self.blocos = sorted(dados.get("blocos", []), key=lambda b: b["inicio"])
        self.largura, self.altura = largura, altura
        self.rostos = rostos

    @classmethod
    def carregar(cls, pasta: Path, largura: int, altura: int) -> "Camera | None":
        arq = pasta / "camera.json"
        if not arq.exists():
            return None
        from rosto import Rostos
        return cls(ler_json(arq), largura, altura, Rostos.carregar(pasta, largura, altura))

    def zoom(self, t: float) -> float:
        for b in self.blocos:
            if b["inicio"] - 1e-6 <= t < b["fim"]:
                return float(b["zoom"])
        return 1.0

    def ancora(self, t: float) -> tuple[float, float]:
        """Ponto que não se mexe no zoom: o meio do rosto (ou um pouco acima do centro)."""
        r = self.rostos.em(t) if self.rostos else None
        if r is None:
            return self.largura / 2, self.altura * 0.40
        return r["cx"], (r["olhos"] + r["boca"]) / 2

    def transformar(self, t: float) -> tuple[float, float, float]:
        """(zoom, x0, y0): o ponto (x, y) do vídeo cortado aparece em ((x-x0)*zoom, (y-y0)*zoom)."""
        z = self.zoom(t)
        if z <= 1.0001:
            return 1.0, 0.0, 0.0
        ax, ay = self.ancora(t)
        x0 = min(max(ax * (1 - 1 / z), 0.0), self.largura * (1 - 1 / z))
        y0 = min(max(ay * (1 - 1 / z), 0.0), self.altura * (1 - 1 / z))
        return z, x0, y0

    def na_tela(self, caixa, t: float):
        z, x0, y0 = self.transformar(t)
        x1, y1, x2, y2 = caixa
        return ((x1 - x0) * z, (y1 - y0) * z, (x2 - x0) * z, (y2 - y0) * z)


def assinatura_camera(pasta: Path) -> str:
    partes = []
    for nome in ("camera.json", "rosto.json"):
        arq = pasta / nome
        partes.append(hashlib.sha1(arq.read_bytes()).hexdigest()[:12] if arq.exists() else "-")
    return "/".join(partes)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["planejar", "desligar"])
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--intensidade", choices=sorted(INTENSIDADES), default="normal")
    a = ap.parse_args()
    pasta = a.pasta.resolve()
    arq = pasta / "camera.json"
    if a.acao == "desligar":
        if arq.exists():
            arq.unlink()
        print("câmera parada (camera.json apagado). Gere a legenda de novo.")
        return
    if not (pasta / "cortes.json").exists():
        erro("rode propor_cortes.py antes")
    if not (pasta / "rosto.json").exists():
        print("atenção: sem rosto.json o zoom cresce em volta do centro. Rode rosto.py antes.")
    from comum import andamento, andamento_fim
    andamento(pasta, "planejando a câmera")
    dados = planejar(pasta, a.intensidade)
    salvar_json(arq, dados)
    enfases = [b for b in dados["blocos"] if b["motivo"].startswith("ênfase")]
    print(f"{len(dados['blocos'])} blocos de câmera · {len(enfases)} aproximações de ênfase")
    for b in dados["blocos"]:
        print(f"  {tempo(b['inicio'])}-{tempo(b['fim'])}  {b['zoom']:.0%}  {b['motivo']}")
    andamento_fim(pasta, "câmera planejada")
    print(f"ok  {arq}")


if __name__ == "__main__":
    main()
