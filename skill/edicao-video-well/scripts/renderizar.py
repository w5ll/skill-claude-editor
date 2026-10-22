"""Monta o vídeo editado a partir de cortes.json (e legendas.ass, se houver).

Uso:
    python renderizar.py --pasta saida/2026-10-22_tema --amostra 0 12     (amostra de 8 a 15 s)
    python renderizar.py --pasta saida/2026-10-22_tema                    (vídeo inteiro)
      [--formato original|9:16|4:5|1:1] [--sem-legenda] [--hdr sdr|manter]
      [--volume -14] [--sem-normalizar]

O que faz:
- Imagem: escolhe os quadros dos trechos numa passada só e mantém tamanho e
  quadros por segundo do original (taxa fixa). Nenhum filtro de cor.
- Som: corta com precisão de amostra, suaviza 8 ms em cada emenda (sem estalo) e
  iguala o volume da voz ao padrão das redes (-14 LUFS, pico até -1,5 dBTP).
- Legenda: queima legendas.ass com a fonte da marca.
- Nunca sobrescreve: cada saída ganha um número novo (v001, v002...).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from comum import (PASTA_FONTES, dimensoes_saida, erro, exigir, fps_racional, ler_json,
                   medir_volume, salvar_json, tempo, trechos_no_quadro)

TAXA = 48000
SUAVE = 0.008  # 8 ms de entrada e saída em cada emenda


def proximo_nome(pasta: Path, base: str) -> Path:
    n = 1
    while (pasta / f"{base}-v{n:03d}.mp4").exists():
        n += 1
    return pasta / f"{base}-v{n:03d}.mp4"


def decodificar(arquivo: str, canais: int) -> np.ndarray:
    bruto = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", arquivo, "-vn", "-map", "0:a:0",
         "-ac", str(canais), "-ar", str(TAXA), "-f", "f32le", "-"],
        check=True, capture_output=True).stdout
    return np.frombuffer(bruto, dtype=np.float32).reshape(-1, canais)


def montar_audio(trechos: list[dict], videos: dict, fps, canais: int, destino: Path) -> float:
    cache: dict[int, np.ndarray] = {}
    partes = []
    n_suave = int(SUAVE * TAXA)
    rampa = np.linspace(0, 1, n_suave, dtype=np.float32)[:, None]
    for t in trechos:
        if t["video"] not in cache:
            cache[t["video"]] = decodificar(videos[t["video"]], canais)
        som = cache[t["video"]]
        s0 = int(round(t["quadro_inicio"] / fps * TAXA))
        s1 = int(round(t["quadro_fim"] / fps * TAXA))
        pedaco = som[s0:s1].copy()
        falta = (s1 - s0) - len(pedaco)
        if falta > 0:  # o som acabou antes da imagem
            pedaco = np.vstack([pedaco, np.zeros((falta, canais), np.float32)])
        if len(pedaco) > 2 * n_suave:
            pedaco[:n_suave] *= rampa
            pedaco[-n_suave:] *= rampa[::-1]
        partes.append(pedaco)
    tudo = np.vstack(partes) if partes else np.zeros((0, canais), np.float32)
    pcm = (np.clip(tudo, -1, 1) * 32767).astype("<i2")
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(canais)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(pcm.tobytes())
    return len(tudo) / TAXA


def medir_loudnorm(wav: Path, alvo: float, pico: float) -> dict:
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-nostdin", "-i", str(wav), "-af",
         f"loudnorm=I={alvo}:TP={pico}:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True)
    texto = proc.stderr
    return json.loads(texto[texto.rfind("{"):texto.rfind("}") + 1])


def filtro_loudnorm(m: dict, alvo: float, pico: float) -> str:
    return (f"loudnorm=I={alvo}:TP={pico}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
            f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:"
            f"linear=true,aresample={TAXA}")


def blocos_por_video(trechos: list[dict]) -> list[list[dict]]:
    """Agrupa trechos seguidos do mesmo vídeo (cada grupo vira uma entrada do ffmpeg)."""
    grupos: list[list[dict]] = []
    for t in trechos:
        if grupos and grupos[-1][0]["video"] == t["video"] and t["quadro_inicio"] >= grupos[-1][-1]["quadro_fim"]:
            grupos[-1].append(t)
        else:
            grupos.append([t])
    return grupos


def caminho_filtro(p: Path) -> str:
    """Escapa um caminho para dentro de um filtro do ffmpeg."""
    return str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--amostra", nargs=2, type=float, metavar=("INICIO", "FIM"),
                    help="só um pedaço, em segundos do vídeo editado")
    ap.add_argument("--formato", default="original")
    ap.add_argument("--sem-legenda", action="store_true")
    ap.add_argument("--hdr", choices=["sdr", "manter"], help="obrigatório quando o original é HDR")
    ap.add_argument("--volume", type=float, default=-14.0, help="volume final em LUFS")
    ap.add_argument("--sem-normalizar", action="store_true", help="mantém o volume original")
    ap.add_argument("--nome", help="nome base do arquivo final (padrão: nome da pasta)")
    a = ap.parse_args()
    exigir("ffmpeg")

    pasta = a.pasta.resolve()
    insp = ler_json(pasta / "inspecao.json")["videos"]
    cortes = ler_json(pasta / "cortes.json")
    principal = insp[0]
    fps = fps_racional({"avg_frame_rate": principal["fps"]})
    largura, altura = dimensoes_saida(principal["largura"], principal["altura"], a.formato)
    hdr = any(v["hdr"] for v in insp)
    if hdr and not a.hdr:
        erro("o original é HDR: escolha --hdr sdr (converte para cor padrão) ou --hdr manter")
    if not hdr:
        a.hdr = None
    if a.hdr == "manter" and not all(v["hdr"] for v in insp):
        erro("--hdr manter só funciona quando todos os vídeos são HDR; use --hdr sdr")
    hdr_por_arquivo = {v["arquivo"]: v["cor"]["transferencia"] for v in insp if v["hdr"]}

    ass = pasta / "legendas.ass"
    usar_legenda = not a.sem_legenda
    if usar_legenda:
        if not ass.exists():
            erro("falta legendas.ass: rode legendas.py ou use --sem-legenda")
        estilo = ler_json(pasta / "legendas.json")["estilo"]
        if (estilo["largura"], estilo["altura"]) != (largura, altura):
            erro(f"a legenda foi feita para {estilo['largura']}x{estilo['altura']} e o vídeo sai "
                 f"{largura}x{altura}: rode legendas.py com o mesmo --formato")

    trechos = trechos_no_quadro(cortes, fps)
    if not trechos:
        erro("cortes.json não tem trechos")
    videos = {v["id"]: v["arquivo"] for v in cortes["videos"]}
    canais = 2 if any((v["audio"] or {}).get("canais", 1) >= 2 for v in insp) else 1
    duracao = trechos[-1]["saida_fim"]

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "voz.wav"
        dur_audio = montar_audio(trechos, videos, fps, canais, wav)

        filtro_audio = f"aresample={TAXA}"
        if not a.sem_normalizar:
            m = medir_loudnorm(wav, a.volume, -1.5)
            filtro_audio = filtro_loudnorm(m, a.volume, -1.5)

        cmd = ["ffmpeg", "-v", "error", "-stats", "-nostdin", "-y"]
        grafos, rotulos = [], []
        grupos = blocos_por_video(trechos)
        for n, grupo in enumerate(grupos):
            arquivo = videos[grupo[0]["video"]]
            cmd += ["-i", arquivo]
            cor = ""
            if a.hdr == "sdr" and arquivo in hdr_por_arquivo:
                # HDR do celular para cor padrão, antes de juntar com os outros vídeos.
                cor = (f"zscale=tin={hdr_por_arquivo[arquivo]}:pin=bt2020:min=bt2020nc:t=linear:npl=100,"
                       f"format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
                       f"zscale=t=bt709:m=bt709:r=tv,")
            formato_px = "yuv420p10le" if a.hdr == "manter" else "yuv420p"
            selecao = "+".join(f"between(n\\,{t['quadro_inicio']}\\,{t['quadro_fim'] - 1})" for t in grupo)
            grafos.append(
                f"[{n}:v:0]{cor}fps={fps.numerator}/{fps.denominator},"
                f"scale={largura}:{altura}:force_original_aspect_ratio=increase,crop={largura}:{altura},setsar=1,format={formato_px},"
                f"select='{selecao}',setpts=N/({fps.numerator}/{fps.denominator})/TB[v{n}]")
            rotulos.append(f"[v{n}]")
        cmd += ["-i", str(wav)]
        idx_audio = len(grupos)
        cadeia = "".join(rotulos) + f"concat=n={len(grupos)}:v=1:a=0[vc]" if len(grupos) > 1 else None
        if cadeia:
            grafos.append(cadeia)
            atual = "[vc]"
        else:
            atual = "[v0]"

        if usar_legenda:
            grafos.append(f"{atual}ass=filename='{caminho_filtro(ass)}':fontsdir='{caminho_filtro(PASTA_FONTES)}'[vl]")
            atual = "[vl]"
        grafos.append(f"[{idx_audio}:a]{filtro_audio}[ac]")

        cmd += ["-filter_complex", ";".join(grafos), "-map", atual, "-map", "[ac]"]
        if a.amostra:
            ini, fim = a.amostra
            fim = min(fim, duracao)
            if fim <= ini:
                erro("amostra vazia")
            cmd += ["-ss", f"{ini:.3f}", "-t", f"{fim - ini:.3f}"]
        if a.hdr == "manter":
            cmd += ["-c:v", "libx265", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p10le", "-tag:v", "hvc1",
                    "-color_primaries", "bt2020", "-color_trc", principal["cor"]["transferencia"],
                    "-colorspace", "bt2020nc"]
        else:
            cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-profile:v", "high", "-pix_fmt", "yuv420p",
                    "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]
        cmd += ["-r", f"{fps.numerator}/{fps.denominator}", "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart"]

        base = "amostra" if a.amostra else (a.nome or pasta.name)
        destino = proximo_nome(pasta, base)
        cmd.append(str(destino))
        print(f"renderizando {destino.name} ({largura}x{altura}, {tempo(duracao if not a.amostra else a.amostra[1] - a.amostra[0])})...")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            destino.unlink(missing_ok=True)  # não deixa arquivo pela metade
            erro("o ffmpeg falhou:\n" + proc.stderr[-2000:])

    registro = {
        "arquivo": str(destino), "amostra": a.amostra, "formato": a.formato, "largura": largura, "altura": altura,
        "fps": f"{fps.numerator}/{fps.denominator}", "legenda": usar_legenda, "hdr": a.hdr,
        "volume_alvo": None if a.sem_normalizar else a.volume,
        "duracao_esperada": round((a.amostra[1] - a.amostra[0]) if a.amostra else duracao, 3),
        "duracao_audio_montado": round(dur_audio, 3),
        "trechos": len(trechos),
    }
    salvar_json(destino.with_suffix(".render.json"), registro)
    vol = medir_volume(destino)
    print(f"ok  {destino}  · volume {vol['volume_lufs']} LUFS · pico {vol['pico_dbtp']} dBTP")


if __name__ == "__main__":
    main()
