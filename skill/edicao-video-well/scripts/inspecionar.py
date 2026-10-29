"""Inspeciona os vídeos brutos antes de propor a edição.

Uso:
    python inspecionar.py VIDEO [VIDEO ...] --pasta saida/2026-10-22_tema

Grava inspecao.json e três quadros por vídeo (10%, 50% e 90%) em quadros/,
para conferir rosto, enquadramento e se já existe texto na tela.
Não altera os originais.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from comum import (dimensoes_exibidas, eh_hdr, erro, exigir,
                   fluxo, fps_racional, medir_volume, rotacao, salvar_json, sondar, tempo)


def inspecionar(arquivo: Path, pasta_quadros: Path) -> dict:
    if not arquivo.exists():
        erro(f"arquivo não encontrado: {arquivo}")
    info = sondar(arquivo)
    video, audio = fluxo(info, "video"), fluxo(info, "audio")
    if video is None:
        erro(f"{arquivo.name} não tem imagem")
    duracao = float(info["format"].get("duration") or video.get("duration") or 0)
    largura, altura = dimensoes_exibidas(video)
    fps = fps_racional(video)
    nominal = fps_racional({"avg_frame_rate": video.get("r_frame_rate", "0/0")})
    pendencias = []

    dados = {
        "arquivo": str(arquivo.resolve()),
        "nome": arquivo.name,
        "duracao": round(duracao, 3),
        "largura": largura,
        "altura": altura,
        "orientacao": "vertical" if altura > largura else ("horizontal" if largura > altura else "quadrado"),
        "rotacao": rotacao(video),
        "fps": f"{fps.numerator}/{fps.denominator}",
        "fps_aprox": round(float(fps), 3),
        "taxa_variavel": abs(float(fps) - float(nominal)) > 0.05,
        "codec_video": video.get("codec_name"),
        "formato_pixel": video.get("pix_fmt"),
        "cor": {
            "primarias": video.get("color_primaries"),
            "transferencia": video.get("color_transfer"),
            "matriz": video.get("color_space"),
            "faixa": video.get("color_range"),
        },
        "hdr": eh_hdr(video),
        "audio": None,
    }
    if dados["hdr"]:
        pendencias.append("vídeo em HDR (padrão do iPhone): decidir se converte para cor padrão ou mantém HDR")
    if dados["taxa_variavel"]:
        pendencias.append("taxa de quadros variável (comum em celular): a saída sai em taxa fixa")

    if audio is None:
        pendencias.append("sem áudio")
    else:
        from ruido import medir, medir_eco, medir_estouro
        vol = medir_volume(arquivo)
        ruido = medir(arquivo)
        estouro = medir_estouro(arquivo)
        eco = medir_eco(arquivo)
        dados["audio"] = {
            "codec": audio.get("codec_name"),
            "canais": audio.get("channels"),
            "taxa": int(audio.get("sample_rate", 0)),
            "faixas_de_audio": sum(1 for s in info["streams"] if s.get("codec_type") == "audio"),
            "volume_lufs": vol["volume_lufs"],
            "pico_dbtp": vol["pico_dbtp"],
            "ruido": ruido,
            "estouro": estouro,
            "eco": eco,
        }
        if estouro["estouro"] == "certo":
            pendencias.append("áudio estourado (distorcido) em " + ", ".join(tempo(t) for t in estouro["momentos"][:5])
                              + ": não dá para recuperar, só regravando a frase")
        elif estouro["estouro"] == "possível":
            pendencias.append("talvez estourado em " + ", ".join(tempo(t) for t in estouro["momentos"][:5])
                              + ": ouvir esses pontos")
        if ruido["sugestao"] != "nao":
            pendencias.append(f"ruído de fundo {ruido['diferenca_db']} dB abaixo da voz: sugiro redução de ruído "
                              f"{ruido['sugestao']}")
        if eco["eco"] in ("sim", "pouco"):
            pendencias.append(f"a sala tem {'eco' if eco['eco'] == 'sim' else 'um pouco de eco'} (o som leva "
                              f"cerca de {eco['reverberacao_s']} s para morrer): não dá para tirar na edição; "
                              "vale gravar num lugar com mais pano ou móvel")
        if dados["audio"]["faixas_de_audio"] > 1:
            pendencias.append("mais de uma faixa de áudio: confirmar qual usar (a skill usa a primeira)")

    # Quadros para olhar: rosto, enquadramento, texto já existente na tela.
    pasta_quadros.mkdir(parents=True, exist_ok=True)
    quadros = []
    for pct in (10, 50, 90):
        t = duracao * pct / 100
        destino = pasta_quadros / f"{arquivo.stem}_{pct:02d}.jpg"
        subprocess.run([
            "ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{t:.3f}", "-i", str(arquivo),
            "-frames:v", "1", "-vf", "scale=-2:720", "-q:v", "3", str(destino),
        ], check=False)
        if destino.exists():
            quadros.append(str(destino))
    dados["quadros"] = quadros
    dados["pendencias"] = pendencias
    return dados


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("videos", nargs="+", type=Path)
    ap.add_argument("--pasta", type=Path, required=True, help="pasta do trabalho (saida/AAAA-MM-DD_tema)")
    a = ap.parse_args()
    exigir("ffmpeg")

    resultado = {"videos": [inspecionar(v, a.pasta / "quadros") for v in a.videos]}
    salvar_json(a.pasta / "inspecao.json", resultado)

    for v in resultado["videos"]:
        au = v["audio"] or {}
        print(f"{v['nome']}: {tempo(v['duracao'])} · {v['largura']}x{v['altura']} {v['orientacao']} · "
              f"{v['fps_aprox']} quadros/s{' (variável)' if v['taxa_variavel'] else ''} · "
              f"{'HDR' if v['hdr'] else 'cor padrão'} · volume {au.get('volume_lufs')} LUFS · "
              f"ruído {(au.get('ruido') or {}).get('diferenca_db')} dB abaixo da voz")
        for p in v["pendencias"]:
            print(f"  atenção: {p}")
    print(f"ok  {a.pasta / 'inspecao.json'}")


if __name__ == "__main__":
    main()
