"""Onde está o rosto do Well em cada momento do vídeo cortado.

Uso:
    python rosto.py --pasta saida/2026-10-22_tema [--formato 9:16]

Lê cortes.json, procura o rosto 10 vezes por segundo em cada trecho que fica e grava
rosto.json (posição dos olhos, da boca e o tamanho do rosto, já no enquadramento final).
A legenda, os elementos 3D e o zoom usam isso para não cobrir nem cortar o rosto.

Detector: YuNet do OpenCV (assets/modelos, licença MIT). O caminho do rosto é
suavizado como no editonny:
  1. mediana de 5 medidas seguidas (uma detecção errada não mexe em nada);
  2. rosto perdido (mão na frente, virou de lado): segura a última posição boa; depois
     de 0,3 s perdido, só volta a confiar quando 2 das 3 medidas seguintes acham o rosto;
  3. zona morta: o alvo só muda se o centro andar mais de 3% da largura ou o tamanho
     mudar mais de 12% (tremida pequena não mexe o quadro);
  4. cada mudança de alvo vira um movimento suave de 0,5 s;
  5. cada trecho começa do zero (o caminho de uma tomada não vaza para a outra).

Rode de novo sempre que o cortes.json mudar (os outros scripts avisam).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import numpy as np

from comum import (PASTA_SKILL, aviso, dimensoes_saida, erro, exigir, fps_racional, ler_json, salvar_json,
                   tempo, trechos_no_quadro)

MODELO = PASTA_SKILL / "assets" / "modelos" / "face_detection_yunet_2023mar.onnx"
PASSO = 0.1               # 10 medidas por segundo
LARGURA_ANALISE = 360     # o rosto é procurado numa cópia pequena do vídeo (mais rápido)
CONFIANCA = 0.6
ZONA_MORTA_CENTRO = 0.03
ZONA_MORTA_TAMANHO = 0.12
MOVIMENTO = 0.5           # segundos de cada movimento suave
PERDA_LONGA = 0.3


def assinatura(cortes: dict, fps, largura: int, altura: int) -> str:
    trechos = trechos_no_quadro(cortes, fps)
    videos = {v["id"]: v["arquivo"] for v in cortes["videos"]}
    chave = [[videos[t["video"]], t["quadro_inicio"], t["quadro_fim"]] for t in trechos] + [largura, altura]
    return hashlib.sha1(json.dumps(chave).encode()).hexdigest()[:16]


def detector(largura: int, altura: int):
    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
    try:
        import cv2
    except ImportError:
        erro("opencv não está instalado. Rode: pip install -r scripts/requirements.txt")
    if not MODELO.exists():
        erro(f"falta o modelo de rosto em {MODELO}")
    return cv2.FaceDetectorYN.create(str(MODELO), "", (largura, altura), CONFIANCA, 0.3, 50)


def medir_video(arquivo: str, largura: int, altura: int, pasta=None) -> list:
    """Uma medida a cada 0,1 s do arquivo inteiro, já no enquadramento final (frações)."""
    k = max(1, round(largura / LARGURA_ANALISE))
    w, h = largura // k, altura // k
    w, h = w - w % 2, h - h % 2
    det = detector(w, h)
    filtro = f"fps=10,scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},format=bgr24"
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-i", arquivo, "-an", "-vf", filtro,
                             "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    tam = w * h * 3
    medidas = []
    try:
        duracao = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                        arquivo], capture_output=True, text=True).stdout.strip() or 0)
    except ValueError:
        duracao = 0.0
    while True:
        bruto = proc.stdout.read(tam)
        if len(bruto) < tam:
            break
        quadro = np.frombuffer(bruto, np.uint8).reshape(h, w, 3)
        if pasta is not None and duracao:
            from comum import andamento
            andamento(pasta, "procurando o rosto", len(medidas) * PASSO / duracao, Path(arquivo).name, forcar=False)
        _, faces = det.detect(quadro)
        if faces is None or len(faces) == 0:
            medidas.append(None)
            continue
        f = max(faces, key=lambda r: r[2] * r[3])
        x, y, fw, fh = (float(v) for v in f[:4])
        olhos_y = (f[5] + f[7]) / 2
        boca_y = (f[11] + f[13]) / 2
        medidas.append({"cx": (x + fw / 2) / w, "cy": (y + fh / 2) / h, "w": fw / w, "h": fh / h,
                        "olhos": float(olhos_y) / h, "boca": float(boca_y) / h, "conf": round(float(f[14]), 2)})
    proc.wait()
    return medidas


CAMPOS = ("cx", "cy", "w", "h", "olhos", "boca")


def suavizar(amostras: list) -> list:
    """Caminho estável do rosto num trecho (lista de dicionários ou None, um a cada 0,1 s)."""
    n = len(amostras)
    # 1. mediana de 5
    med = []
    for k in range(n):
        if amostras[k] is None:
            med.append(None)
            continue
        janela = [a for a in amostras[max(0, k - 2):k + 3] if a is not None]
        med.append({c: float(np.median([a[c] for a in janela])) for c in CAMPOS})
    # 2. segura quando perde; depois de perda longa, exige 2 de 3
    firme = []
    ultimo, perdido = None, 0
    for k in range(n):
        a = med[k]
        if a is None:
            perdido += 1
            firme.append(ultimo)
            continue
        if ultimo is not None and perdido * PASSO >= PERDA_LONGA:
            seguintes = sum(1 for b in med[k:k + 3] if b is not None)
            if seguintes < 2:
                perdido += 1
                firme.append(ultimo)
                continue
        ultimo, perdido = a, 0
        firme.append(a)
    # Antes da primeira detecção: usa a primeira posição boa.
    primeiro = next((a for a in firme if a is not None), None)
    if primeiro is None:
        return []
    firme = [a if a is not None else primeiro for a in firme]
    # 3. zona morta: alvos
    alvos = [dict(firme[0])]
    trocas = [0]
    for k in range(1, n):
        alvo = alvos[-1]
        a = firme[k]
        anda = math.hypot(a["cx"] - alvo["cx"], (a["cy"] - alvo["cy"]) * 0.5625) > ZONA_MORTA_CENTRO
        cresce = abs(a["w"] - alvo["w"]) / max(alvo["w"], 1e-6) > ZONA_MORTA_TAMANHO
        if anda or cresce:
            alvos.append(dict(a))
            trocas.append(k)
    # 4. movimento suave de 0,5 s centrado em cada troca
    caminho = [dict(alvos[0]) for _ in range(n)]
    meio = MOVIMENTO / PASSO / 2
    for j in range(1, len(alvos)):
        k0 = trocas[j]
        de, para = alvos[j - 1], alvos[j]
        for k in range(n):
            if k < k0 - meio:
                continue
            u = min(1.0, max(0.0, (k - (k0 - meio)) / (2 * meio)))
            s = 0.5 - 0.5 * math.cos(math.pi * u)
            caminho[k] = {c: caminho[k][c] + (para[c] - de[c]) * s for c in CAMPOS}
    return caminho


def medir(pasta: Path, formato: str) -> dict:
    exigir("ffmpeg")
    insp = ler_json(pasta / "inspecao.json")["videos"]
    cortes = ler_json(pasta / "cortes.json")
    fps = fps_racional({"avg_frame_rate": insp[0]["fps"]})
    largura, altura = dimensoes_saida(insp[0]["largura"], insp[0]["altura"], formato)
    trechos = trechos_no_quadro(cortes, fps)
    videos = {v["id"]: v["arquivo"] for v in cortes["videos"]}
    medidas = {}
    for vid in sorted({t["video"] for t in trechos}):
        print(f"  procurando o rosto em {Path(videos[vid]).name}...")
        medidas[vid] = medir_video(videos[vid], largura, altura, pasta)

    saida = []
    for n, t in enumerate(trechos):
        dur = t["saida_fim"] - t["saida_inicio"]
        passos = max(1, int(math.ceil(dur / PASSO)))
        brutas, tempos = [], []
        for k in range(passos + 1):
            ts = t["inicio_exato"] + min(k * PASSO, dur)
            idx = int(round(ts / PASSO))
            m = medidas[t["video"]]
            brutas.append(m[idx] if 0 <= idx < len(m) else None)
            tempos.append(round(t["saida_inicio"] + min(k * PASSO, dur), 3))
        caminho = suavizar(brutas)
        achou = sum(1 for b in brutas if b is not None)
        pontos = [[tempos[k]] + [round(caminho[k][c], 4) for c in CAMPOS] + [int(brutas[k] is not None)]
                  for k in range(len(caminho))]
        saida.append({"trecho": n, "inicio": round(t["saida_inicio"], 3), "fim": round(t["saida_fim"], 3),
                      "achou": round(achou / len(brutas), 2), "pontos": pontos})
    return {"versao": 1, "assinatura": assinatura(cortes, fps, largura, altura), "formato": formato,
            "largura": largura, "altura": altura, "passo": PASSO, "campos": ["t", *CAMPOS, "achou"],
            "trechos": saida}


class Rostos:
    """Consulta o rosto no vídeo cortado. Coordenadas em pixels do enquadramento final, antes do zoom."""

    def __init__(self, dados: dict):
        self.dados = dados
        self.largura, self.altura = dados["largura"], dados["altura"]
        self.trechos = dados["trechos"]

    @classmethod
    def carregar(cls, pasta: Path, largura: int | None = None, altura: int | None = None,
                 exigir_atual: bool = True) -> "Rostos | None":
        arq = pasta / "rosto.json"
        if not arq.exists():
            return None
        dados = ler_json(arq)
        if exigir_atual:
            insp = ler_json(pasta / "inspecao.json")["videos"]
            fps = fps_racional({"avg_frame_rate": insp[0]["fps"]})
            w = largura or dados["largura"]
            h = altura or dados["altura"]
            if dados.get("assinatura") != assinatura(ler_json(pasta / "cortes.json"), fps, w, h):
                erro("rosto.json é de outro corte ou outro formato: rode rosto.py de novo")
        return cls(dados)

    def _ponto(self, p) -> dict:
        _, cx, cy, w, h, olhos, boca, achou = p
        return {"cx": cx * self.largura, "cy": cy * self.altura, "w": w * self.largura, "h": h * self.altura,
                "olhos": olhos * self.altura, "boca": boca * self.altura, "achou": bool(achou)}

    def em(self, t: float) -> dict | None:
        for tr in self.trechos:
            if tr["inicio"] - 1e-6 <= t < tr["fim"] + 1e-6 and tr["pontos"]:
                pts = tr["pontos"]
                k = min(len(pts) - 1, max(0, int(round((t - tr["inicio"]) / self.dados["passo"]))))
                return self._ponto(pts[k])
        return None

    def amostras(self, t0: float, t1: float) -> list[tuple[float, dict]]:
        saida = []
        for tr in self.trechos:
            if tr["fim"] <= t0 or tr["inicio"] >= t1:
                continue
            for p in tr["pontos"]:
                if t0 - 0.05 <= p[0] <= t1 + 0.05:
                    saida.append((p[0], self._ponto(p)))
        return saida


def zona_protegida(r: dict) -> tuple[float, float, float, float]:
    """Retângulo que nada pode cobrir: da testa ao queixo, com folga dos lados."""
    return (r["cx"] - r["w"] * 0.62, r["cy"] - r["h"] * 0.62, r["cx"] + r["w"] * 0.62, r["cy"] + r["h"] * 0.60)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--formato", default="original", help="o mesmo que vai no renderizar.py")
    a = ap.parse_args()
    pasta = a.pasta.resolve()
    if not (pasta / "cortes.json").exists():
        erro("rode propor_cortes.py antes")
    from comum import andamento, andamento_fim
    andamento(pasta, "procurando o rosto", 0.0)
    dados = medir(pasta, a.formato)
    salvar_json(pasta / "rosto.json", dados)
    sem = [tr for tr in dados["trechos"] if tr["achou"] < 0.3]
    for tr in dados["trechos"]:
        if tr["pontos"]:
            p = tr["pontos"][len(tr["pontos"]) // 2]
            print(f"  trecho {tr['trecho']:>2} {tempo(tr['inicio'])}-{tempo(tr['fim'])}: rosto em "
                  f"{tr['achou']:.0%} das medidas · centro {p[1]:.0%} x {p[2]:.0%} · largura {p[3]:.0%}")
        else:
            print(f"  trecho {tr['trecho']:>2} {tempo(tr['inicio'])}-{tempo(tr['fim'])}: rosto não encontrado")
    if sem:
        aviso(f"atenção: {len(sem)} trecho(s) quase sem rosto; ali a legenda e o zoom ficam na posição padrão")
    andamento_fim(pasta, "rosto encontrado")
    print(f"ok  {pasta / 'rosto.json'}")


if __name__ == "__main__":
    main()
