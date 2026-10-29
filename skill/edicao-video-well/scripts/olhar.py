"""Olhar: marca os trechos em que a cabeça abaixa ou vira, o que parece leitura do roteiro.

Uso:
    python olhar.py medir --pasta saida/2026-10-22_tema [--formato 9:16]
    python olhar.py zoom  --pasta saida/2026-10-22_tema [--zoom 1.15]

medir  mede para onde a CABEÇA aponta 10 vezes por segundo (nariz em relação aos olhos e à boca),
       compara com o normal do próprio vídeo e grava olhar.json com os trechos de 1,2 s ou mais em
       que a cabeça fica abaixada ou virada para o lado. Grava também olhar-quadros.jpg: um quadro
       normal ao lado de um quadro de cada trecho marcado. Olhe a folha antes de aceitar: pensar
       olhando para baixo também é desvio.
zoom   escreve em camera.json um bloco de zoom (padrão 115%) sobre cada trecho marcado, para
       disfarçar. Pula o trecho que cruza um elemento 3D. Só rode com o "ok" do zoom no cartão.

Limite: o detector dá 5 pontos do rosto (olhos, nariz, boca). Dá para saber para onde a cabeça
aponta, não para onde os olhos olham. Leitura só com os olhos, cabeça parada, não é detectada.
Cortar o trecho é decisão a tomar no cortes.json, vendo as palavras que ele mostra.
"""

from __future__ import annotations

import argparse
import math
import subprocess
from pathlib import Path

import numpy as np

from comum import aviso, dimensoes_saida, erro, exigir, fps_racional, ler_json, salvar_json, tempo, trechos_no_quadro

PASSO = 0.1
MIN_DURACAO = 1.2        # menos que isso é só olhar de relance
JUNTA = 0.3              # desvios separados por até isso viram um só
LIMIAR_INCLINACAO = 0.07  # a partir da mediana do vídeo (cerca de 12 graus)
LIMIAR_GIRO = 0.25        # cerca de 15 graus
SIGMAS = 3.0
ZOOM_MAX = 1.3
BLOCO_MIN = 2.5          # a câmera não muda de novo antes disso (como em camera.py)
MARGEM_BLOCO = 0.2


def medidas_de_pose(m: dict) -> tuple[float, float]:
    """(inclinação, giro) de uma medida do rosto. Inclinação sobe com a cabeça para baixo."""
    meio = (m["olho_d_x"] + m["olho_e_x"]) / 2
    entre = abs(m["olho_e_x"] - m["olho_d_x"]) or 1e-6
    vert = (m["boca"] - m["olhos"]) or 1e-6
    return (m["nariz_y"] - m["olhos"]) / vert, (m["nariz_x"] - meio) / entre


def mediana_movel(valores: list, janela: int = 5) -> list:
    saida = []
    for k in range(len(valores)):
        v = [x for x in valores[max(0, k - janela // 2):k + janela // 2 + 1] if x is not None]
        saida.append(float(np.median(v)) if v and valores[k] is not None else None)
    return saida


def analisar(serie: list[tuple[float, dict | None]]) -> dict:
    """Marca os desvios de uma série (tempo no vídeo cortado, medida ou None) a cada 0,1 s."""
    pares = [medidas_de_pose(m) if m else None for _, m in serie]
    incl = mediana_movel([p[0] if p else None for p in pares])
    giro = mediana_movel([p[1] if p else None for p in pares])
    validos_i = [x for x in incl if x is not None]
    validos_g = [x for x in giro if x is not None]
    if len(validos_i) < 20:
        return {"normal": None, "limiares": None, "desvios": []}
    base_i, base_g = float(np.median(validos_i)), float(np.median(validos_g))
    sigma = 1.4826 * float(np.median([abs(x - base_i) for x in validos_i]))
    lim_i = max(LIMIAR_INCLINACAO, SIGMAS * sigma)

    marcas = []     # (tipo, razão entre o desvio e o limiar) ou None
    for ci, cg in zip(incl, giro):
        if ci is None:
            marcas.append(None)
        elif ci - base_i > lim_i:
            marcas.append(("baixo", (ci - base_i) / lim_i))
        elif abs(cg - base_g) > LIMIAR_GIRO:
            marcas.append(("lado", abs(cg - base_g) / LIMIAR_GIRO))
        else:
            marcas.append(None)

    corridas = []   # [tipo, k0, k1, [razões]]
    for k, m in enumerate(marcas):
        if m is None:
            continue
        if corridas and corridas[-1][0] == m[0] and (k - corridas[-1][2]) * PASSO <= JUNTA + PASSO + 1e-9:
            corridas[-1][2] = k
            corridas[-1][3].append(m[1])
        else:
            corridas.append([m[0], k, k, [m[1]]])
    desvios = []
    for tipo, k0, k1, razoes in corridas:
        ini, fim = serie[k0][0], serie[k1][0] + PASSO
        if fim - ini < MIN_DURACAO - 1e-9:
            continue
        forca = float(np.mean(razoes))
        desvios.append({"inicio": round(ini, 2), "fim": round(fim, 2), "tipo": tipo,
                        "intensidade": "leve" if forca < 1.5 else ("média" if forca < 2.5 else "forte")})
    # a medida mais parecida com o normal serve de quadro de referência na folha
    ref = min((k for k in range(len(incl)) if incl[k] is not None),
              key=lambda k: abs(incl[k] - base_i) + abs(giro[k] - base_g))
    return {"normal": {"inclinacao": round(base_i, 3), "giro": round(base_g, 3), "tempo_referencia": serie[ref][0]},
            "limiares": {"inclinacao": round(lim_i, 3), "giro": LIMIAR_GIRO}, "desvios": desvios}


def serie_do_corte(pasta: Path, formato: str):
    """Medidas do rosto a cada 0,1 s ao longo do vídeo cortado (com o nariz)."""
    from rosto import medir_video
    exigir("ffmpeg")
    insp = ler_json(pasta / "inspecao.json")["videos"]
    cortes = ler_json(pasta / "cortes.json")
    fps = fps_racional({"avg_frame_rate": insp[0]["fps"]})
    largura, altura = dimensoes_saida(insp[0]["largura"], insp[0]["altura"], formato)
    trechos = trechos_no_quadro(cortes, fps)
    videos = {v["id"]: v["arquivo"] for v in cortes["videos"]}
    medidas = {}
    for vid in sorted({t["video"] for t in trechos}):
        print(f"  medindo a cabeça em {Path(videos[vid]).name}...")
        medidas[vid] = medir_video(videos[vid], largura, altura, pasta)
    serie = []
    for t in trechos:
        dur = t["saida_fim"] - t["saida_inicio"]
        for k in range(max(1, int(math.ceil(dur / PASSO)))):
            ts = t["inicio_exato"] + k * PASSO
            idx = int(round(ts / PASSO))
            m = medidas[t["video"]]
            serie.append((round(t["saida_inicio"] + k * PASSO, 3), m[idx] if 0 <= idx < len(m) else None))
    return serie, trechos, videos


def fonte(trechos: list[dict], t: float) -> tuple[int, float]:
    """(vídeo, segundo no arquivo original) do instante t do vídeo cortado."""
    for tr in trechos:
        if tr["saida_inicio"] - 1e-6 <= t < tr["saida_fim"] + 1e-6:
            return tr["video"], tr["inicio_exato"] + (t - tr["saida_inicio"])
    tr = trechos[-1]
    return tr["video"], tr["fim_exato"]


def quadro(arquivo: str, segundo: float, altura: int = 360):
    import cv2
    bruto = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{segundo:.3f}", "-i", arquivo,
                            "-frames:v", "1", "-vf", f"scale=-2:{altura}", "-f", "image2pipe", "-vcodec", "png", "-"],
                           capture_output=True).stdout
    if not bruto:
        return None
    return cv2.imdecode(np.frombuffer(bruto, np.uint8), cv2.IMREAD_COLOR)


def folha(pasta: Path, dados: dict, trechos: list[dict], videos: dict, maximo: int = 8) -> Path | None:
    import cv2
    if not dados["desvios"]:
        return None
    vid, seg = fonte(trechos, dados["normal"]["tempo_referencia"])
    normal = quadro(videos[vid], seg)
    if normal is None:
        return None
    linhas = []
    for d in dados["desvios"][:maximo]:
        vid, seg = fonte(trechos, (d["inicio"] + d["fim"]) / 2)
        q = quadro(videos[vid], seg)
        if q is None:
            continue
        a, b = normal.copy(), q.copy()
        cv2.putText(a, "normal", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        cv2.putText(b, f"{d['tipo']} {tempo(d['inicio'])}-{tempo(d['fim'])}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.9, (80, 80, 255), 2)
        linhas.append(np.hstack([a, b]))
    if not linhas:
        return None
    destino = pasta / "olhar-quadros.jpg"
    cv2.imwrite(str(destino), np.vstack(linhas))
    return destino


# ---------- zoom para disfarçar ----------

def sobrepor(blocos: list[dict], ini: float, fim: float, zoom: float, motivo: str) -> list[dict]:
    """Coloca um bloco por cima dos que existem, cortando os vizinhos (como camera.py faz com a ênfase)."""
    novos = []
    for b in blocos:
        if b["fim"] <= ini or b["inicio"] >= fim:
            novos.append(b)
            continue
        if b["inicio"] < ini:
            novos.append({**b, "fim": round(ini, 3)})
        if b["fim"] > fim:
            novos.append({**b, "inicio": round(fim, 3)})
    novos.append({"inicio": round(ini, 3), "fim": round(fim, 3), "zoom": zoom, "motivo": motivo})
    return sorted(novos, key=lambda b: b["inicio"])


def aplicar_zoom(blocos: list[dict], desvios: list[dict], ocupado: list[tuple[float, float]], duracao: float,
                 zoom: float) -> tuple[list[dict], list[dict], list[dict]]:
    """Devolve (blocos novos, desvios usados, desvios pulados por causa de elemento 3D)."""
    usados, pulados = [], []
    for d in desvios:
        ini = max(0.0, d["inicio"] - MARGEM_BLOCO)
        fim = min(duracao, d["fim"] + MARGEM_BLOCO)
        if fim - ini < BLOCO_MIN:
            ini = max(0.0, (ini + fim) / 2 - BLOCO_MIN / 2)
            fim = min(duracao, ini + BLOCO_MIN)
        if any(a < fim and b > ini for a, b in ocupado):
            pulados.append(d)
            continue
        blocos = sobrepor(blocos, ini, fim, zoom, f"disfarçar leitura ({d['tipo']})")
        usados.append(d)
    return blocos, usados, pulados


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["medir", "zoom"])
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--formato", default="original", help="o mesmo que vai no renderizar.py")
    ap.add_argument("--zoom", type=float, default=1.15)
    a = ap.parse_args()
    pasta = a.pasta.resolve()
    if not (pasta / "cortes.json").exists():
        erro("rode propor_cortes.py antes")
    from comum import andamento, andamento_fim

    if a.acao == "medir":
        andamento(pasta, "olhando para onde a cabeça aponta", 0.0)
        serie, trechos, videos = serie_do_corte(pasta, a.formato)
        dados = analisar(serie)
        if dados["normal"] is None:
            erro("o rosto aparece em poucos momentos: não dá para medir o olhar neste vídeo")
        from legendas import palavras_no_corte
        cortes = ler_json(pasta / "cortes.json")
        insp = ler_json(pasta / "inspecao.json")["videos"][0]
        palavras = palavras_no_corte(pasta, cortes, fps_racional({"avg_frame_rate": insp["fps"]}))
        for d in dados["desvios"]:
            d["texto"] = " ".join(w["p"] for w in palavras if d["inicio"] - 0.05 <= (w["i"] + w["f"]) / 2 <= d["fim"] + 0.05)
        dados["versao"] = 1
        arq = folha(pasta, dados, trechos, videos)
        salvar_json(pasta / "olhar.json", dados)
        andamento_fim(pasta, "olhar medido")
        if not dados["desvios"]:
            print("nenhum trecho com a cabeça abaixada ou virada por 1,2 s ou mais")
        for d in dados["desvios"]:
            onde = "abaixada" if d["tipo"] == "baixo" else "virada para o lado"
            print(f"  {tempo(d['inicio'])}-{tempo(d['fim'])}  cabeça {onde} ({d['intensidade']}): {d['texto']}")
        if arq:
            print(f"folha de quadros: {arq}")
        print(f"ok  {pasta / 'olhar.json'}")
        return

    arq = pasta / "olhar.json"
    if not arq.exists():
        erro("rode olhar.py medir antes")
    if not 1.0 < a.zoom <= ZOOM_MAX:
        erro(f"o zoom vai de 1,01 a {ZOOM_MAX}")
    dados = ler_json(arq)
    cortes = ler_json(pasta / "cortes.json")
    duracao = cortes.get("duracao_final") or sum(t["fim"] - t["inicio"] for t in cortes["trechos"])
    camera = ler_json(pasta / "camera.json") if (pasta / "camera.json").exists() else {"intensidade": "disfarce",
                                                                                       "duracao": duracao, "blocos": []}
    from camera import janelas_ocupadas
    blocos, usados, pulados = aplicar_zoom(camera["blocos"], dados["desvios"], janelas_ocupadas(pasta), duracao, a.zoom)
    camera["blocos"] = blocos
    salvar_json(pasta / "camera.json", camera)
    for d in usados:
        print(f"  zoom {a.zoom:.0%} em {tempo(d['inicio'])}-{tempo(d['fim'])}")
    for d in pulados:
        aviso(f"  pulei {tempo(d['inicio'])}-{tempo(d['fim'])}: tem elemento 3D na tela (a câmera não muda nesse momento)")
    print("Gere a legenda de novo (legendas.py --reaproveitar): ela desvia do rosto já com o zoom.")
    print(f"ok  {pasta / 'camera.json'}")


if __name__ == "__main__":
    main()
