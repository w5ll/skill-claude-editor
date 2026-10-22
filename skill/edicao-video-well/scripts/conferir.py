"""Confere o vídeo renderizado antes de entregar.

Uso:
    python conferir.py --pasta saida/2026-10-22_tema --video saida/.../tema-v001.mp4 [--retranscrever]

Checa:
- abre e toca do começo ao fim; tamanho, quadros por segundo e duração batem com o pedido
- tem som; volume perto do alvo e pico abaixo de -1 dBTP
- nenhuma palavra cortada no meio numa emenda
- com --retranscrever: transcreve o resultado e compara com o texto esperado
  (pega fala engolida ou trecho sumido)
Gera conferencia.json e uma folha de quadros (.quadros.jpg) para olhar
enquadramento, rosto e legenda.
"""

from __future__ import annotations

import argparse
import difflib
import re
import subprocess
import unicodedata
from pathlib import Path

from comum import (dimensoes_exibidas, fluxo, fps_racional, ler_json, medir_volume, salvar_json, sondar,
                   tempo, trechos_no_quadro)


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


def folha_de_quadros(video: Path, duracao: float, destino: Path, n: int = 12):
    passo = duracao / (n + 1)
    filtro = f"fps=1/{passo:.4f},scale=-2:480,tile={min(n, 6)}x{(n + 5) // 6}:padding=6:color=0x16161f"
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{passo / 2:.3f}", "-i", str(video),
                    "-vf", filtro, "-frames:v", "1", "-q:v", "3", str(destino)], check=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--retranscrever", action="store_true")
    ap.add_argument("--modelo", default="small")
    a = ap.parse_args()

    registro_arq = a.video.with_suffix(".render.json")
    registro = ler_json(registro_arq) if registro_arq.exists() else {}
    cortes = ler_json(a.pasta / "cortes.json")
    insp = ler_json(a.pasta / "inspecao.json")["videos"][0]
    fps_alvo = fps_racional({"avg_frame_rate": registro.get("fps") or insp["fps"]})

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

    if not registro.get("amostra"):
        cortadas = palavras_cortadas(a.pasta, cortes, fps_alvo)
        check("nenhuma palavra cortada nas emendas", not cortadas,
              "; ".join(f"'{c['palavra']}' em {tempo(c['saida'])}" for c in cortadas) or "ok")

    texto_obtido = None
    if a.retranscrever and au is not None:
        from faster_whisper import WhisperModel
        from comum import carregar_mono
        modelo = WhisperModel(a.modelo, device="auto", compute_type="int8")
        segs, _ = modelo.transcribe(carregar_mono(a.video), language="pt", condition_on_previous_text=False)
        texto_obtido = " ".join(s.text.strip() for s in segs)
        esperado = " ".join(t["texto"] for t in cortes["trechos"])
        if registro.get("amostra"):
            check("fala da amostra transcrita", bool(texto_obtido.strip()), texto_obtido[:200])
        else:
            nota = difflib.SequenceMatcher(None, norm(esperado), norm(texto_obtido)).ratio()
            check("fala completa (retranscrição)", nota >= 0.85, f"{nota:.0%} igual ao esperado")

    quadros = a.video.with_suffix(".quadros.jpg")
    folha_de_quadros(a.video, dur, quadros)

    resultado = {"video": str(a.video), "checks": checks, "aprovado": all(c["ok"] for c in checks),
                 "quadros": str(quadros), "texto_retranscrito": texto_obtido}
    salvar_json(a.video.with_suffix(".conferencia.json"), resultado)
    for c in checks:
        print(f"  {'ok ' if c['ok'] else 'FALHOU'}  {c['item']}: {c['detalhe']}")
    print(f"\n{'APROVADO' if resultado['aprovado'] else 'COM PROBLEMA'}  · folha de quadros: {quadros}")


if __name__ == "__main__":
    main()
