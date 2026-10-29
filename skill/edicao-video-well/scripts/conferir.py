"""Confere o vídeo renderizado antes de entregar.

Uso:
    python conferir.py --pasta saida/2026-10-22_tema --video saida/.../tema-v001.mp4 [--retranscrever]
        [--pausa-max 0.7] [--pausas-ok 12.3 40.1]

Checa:
- abre e toca do começo ao fim; tamanho, quadros por segundo e duração batem com o pedido
- tem som; volume perto do alvo e pico abaixo de -1 dBTP
- nenhuma palavra cortada no meio numa emenda
- nenhum estalo nas emendas (salto brusco na onda bem no ponto do corte)
- nenhum trecho repetido (a mesma fala tocando duas vezes depois de mexer no corte)
- nenhum silêncio morto: pausa sem fala maior que --pausa-max (0,7 s). Pausa de efeito
  que fica de propósito: passe o segundo dela em --pausas-ok
- nenhum quadro preto (fora da tela cheia dos elementos, que é escura de propósito)
- volume parecido entre os trechos: um trecho mais de 4 dB fora do resto, ou dois
  vizinhos com mais de 6 dB de diferença, falha e diz quanto ganho pôr no cortes.json
- com música: a música ficou abaixo da voz
- com --retranscrever: transcreve o resultado e compara com o texto esperado
  (pega fala engolida ou trecho sumido)
Gera conferencia.json, uma folha de quadros (.quadros.jpg) para olhar enquadramento,
rosto e legenda, e folhas de emendas (.emendasNN.jpg): em cada linha, os 2 últimos
quadros do trecho que sai e os 2 primeiros do que entra, para ver pulo de imagem.
"""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import unicodedata
from pathlib import Path

import numpy as np

from comum import (carregar_mono, dimensoes_exibidas, envelope_db, fluxo, fps_racional, ler_json, medir_volume,
                   salvar_json, sondar, tempo, trechos_no_quadro)

TAXA = 48000
EMENDAS_POR_FOLHA = 8


def norm(t: str) -> list[str]:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", t).split()


def palavras_cortadas(pasta: Path, cortes: dict, fps) -> list[dict]:
    achados = []
    trechos = trechos_no_quadro(cortes, fps)
    for v in cortes["videos"]:
        palavras = ler_json(pasta / "transcricoes" / f"{Path(v['arquivo']).stem}.json")["palavras"]
        for t in (x for x in trechos if x["video"] == v["id"]):
            for borda, nome in ((t["inicio_exato"], "início"), (t["fim_exato"], "fim")):
                for w in palavras:
                    # palavra atravessa a borda com mais de 40 ms de cada lado
                    if w["i"] + 0.04 < borda < w["f"] - 0.04:
                        achados.append({"video": v["id"], "tempo": round(borda, 3), "borda": nome,
                                        "palavra": w["p"], "saida": round(t["saida_inicio"] if nome == "início"
                                                                          else t["saida_fim"], 3)})
    return achados


def repeticoes(cortes: dict, fps) -> list[str]:
    """Trecho que toca de novo um pedaço do anterior (mesmo vídeo e tempo, ou mesmas palavras)."""
    achados = []
    trechos = trechos_no_quadro(cortes, fps)
    for k in range(1, len(trechos)):
        a, b = trechos[k - 1], trechos[k]
        if a["video"] == b["video"] and b["inicio_exato"] < a["fim_exato"] - 0.05 and b["fim_exato"] > a["inicio_exato"]:
            achados.append(f"trechos {k - 1} e {k} usam o mesmo pedaço do vídeo ({tempo(b['saida_inicio'])})")
            continue
        fa, fb = norm(a.get("texto", "")), norm(b.get("texto", ""))
        if len(fa) >= 3 and len(fb) >= 3 and fa[-3:] == fb[:3]:
            achados.append(f"o trecho {k} começa com as mesmas 3 palavras que o {k - 1} termina "
                           f"(\"{' '.join(fb[:3])}\", {tempo(b['saida_inicio'])})")
    return achados


def silencios(pasta: Path, cortes: dict, fps, limite: float, aceitas: list[float], janela) -> list[dict]:
    """Buracos sem fala no vídeo final, pelas palavras no tempo do corte (funciona com música por baixo)."""
    from legendas import palavras_no_corte
    palavras = palavras_no_corte(pasta, cortes, fps)
    if not palavras:
        return []
    ini, fim = janela
    achados = []
    marcas = [(ini, palavras[0]["i"], "começo")] if palavras[0]["i"] - ini > 0.6 else []
    for w0, w1 in zip(palavras, palavras[1:]):
        if w1["i"] - w0["f"] >= limite:
            marcas.append((w0["f"], w1["i"], "meio"))
    if fim - palavras[-1]["f"] > 1.0:
        marcas.append((palavras[-1]["f"], fim, "fim"))
    for a, b, onde in marcas:
        if b <= ini or a >= fim:
            continue
        if any(a - 0.3 <= t <= b + 0.3 for t in aceitas):
            continue
        achados.append({"inicio": round(a, 2), "fim": round(b, 2), "onde": onde})
    return achados


def som_48k(video: Path) -> np.ndarray:
    bruto = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(video), "-vn", "-ac", "1", "-ar",
                            str(TAXA), "-f", "f32le", "-"], capture_output=True).stdout
    return np.frombuffer(bruto, np.float32)


def estalos(som: np.ndarray, emendas: list[float]) -> list[float]:
    achados = []
    d = np.abs(np.diff(som))
    for t in emendas:
        c = int(t * TAXA)
        perto = d[max(0, c - 96):c + 96]                 # 2 ms de cada lado
        volta = np.concatenate([d[max(0, c - 2400):max(0, c - 240)], d[c + 240:c + 2400]])
        if perto.size == 0 or volta.size == 0:
            continue
        salto, normal = float(perto.max()), float(np.median(volta)) + 1e-4
        if salto > 0.05 and salto / normal > 12:
            achados.append(round(t, 3))
    return achados


def niveis_dos_trechos(som16: np.ndarray, limites: list[tuple[float, float]]) -> list[float | None]:
    from fala import medir_fala
    env = envelope_db(som16)
    m = medir_fala(env)
    niveis = []
    for a, b in limites:
        pedaco = env[int(a * 100):int(b * 100)]
        fala = pedaco[pedaco > m["limiar_db"]]
        if fala.size < 20:  # menos de 0,2 s de fala: não dá para comparar
            niveis.append(None)
            continue
        niveis.append(float(10 * np.log10(np.mean(10 ** (fala / 10)))))
    return niveis


def quadros_pretos(video: Path, telas: list[tuple[float, float]]) -> list[tuple[float, float]]:
    proc = subprocess.run(["ffmpeg", "-v", "info", "-nostdin", "-i", str(video), "-an", "-vf",
                           "blackdetect=d=0.1:pix_th=0.08", "-f", "null", "-"], capture_output=True, text=True)
    achados = []
    for m in re.finditer(r"black_start:([\d.]+) black_end:([\d.]+)", proc.stderr):
        a, b = float(m.group(1)), float(m.group(2))
        if not any(a < tb + 0.1 and b > ta - 0.1 for ta, tb in telas):
            achados.append((round(a, 2), round(b, 2)))
    return achados


def folha_de_quadros(video: Path, duracao: float, destino: Path, n: int = 12):
    passo = duracao / (n + 1)
    filtro = f"fps=1/{passo:.4f},scale=-2:480,tile={min(n, 6)}x{(n + 5) // 6}:padding=6:color=0x16161f"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{passo / 2:.3f}", "-i", str(video),
                    "-vf", filtro, "-frames:v", "1", "-q:v", "3", str(destino)], check=False)


def folhas_de_emendas(video: Path, emendas: list[float], fps, total_quadros: int) -> list[str]:
    """Para cada emenda: os 2 últimos quadros do trecho que sai e os 2 primeiros do que entra."""
    folhas = []
    linhas = []
    for t in emendas:
        j = int(round(t * fps))
        if 2 <= j <= total_quadros - 2:
            linhas.append((t, [j - 2, j - 1, j, j + 1]))
    for k in range(0, len(linhas), EMENDAS_POR_FOLHA):
        grupo = linhas[k:k + EMENDAS_POR_FOLHA]
        quadros = [q for _, qs in grupo for q in qs]
        sel = "+".join(f"eq(n\\,{q})" for q in quadros)
        destino = video.with_name(f"{video.stem}.emendas{k // EMENDAS_POR_FOLHA + 1:02d}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(video), "-an", "-vf",
                        f"select='{sel}',scale=-2:300,tile=4x{len(grupo)}:padding=4:margin=4:color=0x16161f",
                        "-fps_mode", "passthrough", "-frames:v", "1", "-q:v", "3", str(destino)], check=False)
        if destino.exists():
            folhas.append({"arquivo": str(destino), "emendas": [round(t, 2) for t, _ in grupo]})
    return folhas


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--retranscrever", action="store_true")
    ap.add_argument("--modelo", default="small")
    ap.add_argument("--pausa-max", type=float, default=0.7, help="silêncio sem fala acima disso falha")
    ap.add_argument("--pausas-ok", nargs="*", type=float, default=[],
                    help="segundos (no vídeo editado) de pausas de efeito que ficam de propósito")
    a = ap.parse_args()

    from comum import andamento, andamento_fim
    andamento(a.pasta, "conferindo", detalhe=a.video.name)
    registro_arq = a.video.with_suffix(".render.json")
    registro = ler_json(registro_arq) if registro_arq.exists() else {}
    cortes = ler_json(a.pasta / "cortes.json")
    insp = ler_json(a.pasta / "inspecao.json")["videos"][0]
    fps_alvo = fps_racional({"avg_frame_rate": registro.get("fps") or insp["fps"]})
    amostra = registro.get("amostra")
    desloc = amostra[0] if amostra else 0.0

    checks = []

    def check(nome, ok, detalhe):
        checks.append({"item": nome, "ok": bool(ok), "detalhe": detalhe})

    tocou = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(a.video), "-f", "null", "-"],
                           capture_output=True, text=True)
    check("abre e toca até o fim", tocou.returncode == 0 and not tocou.stderr.strip(),
          tocou.stderr.strip()[:300] or "sem erro de leitura")

    info = sondar(a.video)
    v, au = fluxo(info, "video"), fluxo(info, "audio")
    dur = float(info["format"]["duration"])
    w, h = dimensoes_exibidas(v)
    fps = fps_racional(v)
    if registro:
        check("tamanho", (w, h) == (registro["largura"], registro["altura"]), f"{w}x{h}")
        esperado = registro["duracao_esperada"]
        check("duração", abs(dur - esperado) < 0.15, f"{tempo(dur)} (esperado {tempo(esperado)})")
    check("quadros por segundo", abs(float(fps) - float(fps_alvo)) < 0.01, f"{float(fps):.3f}")
    check("tem som", au is not None, au.get("codec_name") if au else "sem faixa de áudio")

    if au is not None:
        vol = medir_volume(a.video)
        alvo = registro.get("volume_alvo")
        if alvo is not None and vol["volume_lufs"] is not None:
            check("volume da voz", abs(vol["volume_lufs"] - alvo) <= 1.0, f"{vol['volume_lufs']} LUFS (alvo {alvo})")
        if vol["pico_dbtp"] is not None:
            check("pico sem distorcer", vol["pico_dbtp"] <= -1.0, f"{vol['pico_dbtp']} dBTP (limite -1)")

    trechos = trechos_no_quadro(cortes, fps_alvo)
    emendas_tot = registro.get("emendas") or [round(t["saida_inicio"], 4) for t in trechos[1:]]
    emendas = [t - desloc for t in emendas_tot if 0.05 < t - desloc < dur - 0.05]

    if not amostra:
        cortadas = palavras_cortadas(a.pasta, cortes, fps_alvo)
        check("nenhuma palavra cortada nas emendas", not cortadas,
              "; ".join(f"'{c['palavra']}' em {tempo(c['saida'])}" for c in cortadas) or "ok")
        reps = repeticoes(cortes, fps_alvo)
        check("nenhum trecho repetido", not reps, "; ".join(reps) or "ok")

    sil = silencios(a.pasta, cortes, fps_alvo, a.pausa_max, a.pausas_ok, (desloc, desloc + dur))
    check(f"nenhum silêncio morto (acima de {a.pausa_max:.1f} s)", not sil,
          "; ".join(f"{tempo(s['inicio'])} a {tempo(s['fim'])} ({s['fim'] - s['inicio']:.1f} s"
                    f"{', no ' + s['onde'] if s['onde'] != 'meio' else ''}): tirar ou, se for de efeito, "
                    f"--pausas-ok {s['inicio']:.1f}" for s in sil) or "ok")

    nivel_info = []
    if au is not None:
        som = som_48k(a.video)
        est = estalos(som, emendas)
        check("nenhum estalo nas emendas", not est, ", ".join(tempo(t + desloc) for t in est) or "ok")
        if not amostra and len(trechos) > 1:
            som16 = carregar_mono(a.video)
            limites = [(t["saida_inicio"], t["saida_fim"]) for t in trechos]
            niveis = niveis_dos_trechos(som16, limites)
            validos = [(n, x, t["saida_fim"] - t["saida_inicio"]) for n, (x, t) in enumerate(zip(niveis, trechos))
                       if x is not None]
            if len(validos) >= 2:
                ordem = sorted(validos, key=lambda z: z[1])
                pesos = np.cumsum([z[2] for z in ordem])
                ref = ordem[int(np.searchsorted(pesos, pesos[-1] / 2))][1]
                problemas = []
                for n, x, _ in validos:
                    if abs(x - ref) > 4:
                        problemas.append((n, x))
                for (n0, x0, _), (n1, x1, _) in zip(validos, validos[1:]):
                    if n1 == n0 + 1 and abs(x1 - x0) > 6:
                        pior = n0 if abs(x0 - ref) > abs(x1 - ref) else n1
                        if pior not in [p[0] for p in problemas]:
                            problemas.append((pior, x0 if pior == n0 else x1))
                for n, x in sorted(problemas):
                    atual = float(cortes["trechos"][n].get("ganho_db", 0)) if n < len(cortes["trechos"]) else 0.0
                    sugere = round((atual + ref - x) * 2) / 2
                    nivel_info.append(f"trecho {n} ({tempo(trechos[n]['saida_inicio'])}) "
                                      f"{abs(x - ref):.1f} dB {'mais baixo' if x < ref else 'mais alto'}: "
                                      f"ponha \"ganho_db\": {sugere} nesse trecho do cortes.json")
                check("volume parecido entre os trechos", not nivel_info, "; ".join(nivel_info) or
                      f"todos a menos de 4 dB do nível médio")

    telas = [(e["inicio"] - desloc, e["inicio"] + e["duracao"] - desloc) for e in registro.get("elementos") or []
             if e.get("modo") == "tela"]
    pretos = quadros_pretos(a.video, telas)
    check("nenhum quadro preto", not pretos, ", ".join(f"{tempo(x + desloc)} a {tempo(y + desloc)}"
                                                       for x, y in pretos) or "ok")

    mus = (registro.get("som") or {}).get("musica")
    if mus:
        abaixo = mus.get("abaixo_da_voz_na_fala_db")
        check("música abaixo da voz", abaixo is not None and abaixo >= 15,
              f"{abaixo} dB abaixo enquanto ele fala · {mus.get('abaixo_da_voz_nas_pausas_db')} dB nas pausas")

    texto_obtido = None
    if a.retranscrever and au is not None:
        from faster_whisper import WhisperModel
        modelo = WhisperModel(a.modelo, device="auto", compute_type="int8")
        segs, _ = modelo.transcribe(carregar_mono(a.video), language="pt", condition_on_previous_text=False)
        texto_obtido = " ".join(s.text.strip() for s in segs)
        esperado = " ".join(t["texto"] for t in cortes["trechos"])
        if amostra:
            check("fala da amostra transcrita", bool(texto_obtido.strip()), texto_obtido[:200])
        else:
            nota = difflib.SequenceMatcher(None, norm(esperado), norm(texto_obtido)).ratio()
            check("fala completa (retranscrição)", nota >= 0.85, f"{nota:.0%} igual ao esperado")

    quadros = a.video.with_suffix(".quadros.jpg")
    folha_de_quadros(a.video, dur, quadros)
    folhas = folhas_de_emendas(a.video, emendas, fps, int(round(dur * float(fps))))

    # Um quadro no meio de cada elemento 3D: conferir se não cobre o rosto nem a legenda.
    quadros_elementos = []
    for n, el in enumerate(registro.get("elementos") or []):
        t = el["inicio"] + el["duracao"] * 0.6 - desloc
        if 0 <= t < dur:
            destino = a.video.with_name(f"{a.video.stem}.elemento{n:02d}.jpg")
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{t:.3f}", "-i", str(a.video),
                            "-frames:v", "1", "-vf", "scale=-2:720", "-q:v", "3", str(destino)], check=False)
            if destino.exists():
                quadros_elementos.append(str(destino))

    resultado = {"video": str(a.video), "checks": checks, "aprovado": all(c["ok"] for c in checks),
                 "quadros": str(quadros), "folhas_de_emendas": folhas, "quadros_elementos": quadros_elementos,
                 "texto_retranscrito": texto_obtido}
    salvar_json(a.video.with_suffix(".conferencia.json"), resultado)
    andamento_fim(a.pasta, "conferido", a.video.name)
    for c in checks:
        print(f"  {'ok ' if c['ok'] else 'FALHOU'}  {c['item']}: {c['detalhe']}")
    for f in folhas:
        print(f"  olhar emendas ({', '.join(tempo(t + desloc) for t in f['emendas'])}): {f['arquivo']}")
    for q in quadros_elementos:
        print(f"  olhar elemento 3D: {q}")
    print(f"\n{'APROVADO' if resultado['aprovado'] else 'COM PROBLEMA'}  · folha de quadros: {quadros}")


if __name__ == "__main__":
    main()
