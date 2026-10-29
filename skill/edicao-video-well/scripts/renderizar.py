"""Monta o vídeo editado a partir de cortes.json (e legendas.ass, se houver).

Uso:
    python renderizar.py --pasta saida/2026-10-22_tema --amostra 0 12     (amostra de 8 a 15 s)
    python renderizar.py --pasta saida/2026-10-22_tema                    (vídeo inteiro)
      [--formato original|9:16|4:5|1:1, com @1080 para reduzir] [--sem-legenda] [--hdr sdr|manter]
      [--ruido nao|leve|forte] [--volume -14] [--sem-normalizar] [--sem-elementos] [--sem-som]

O que faz:
- Imagem: escolhe os quadros dos trechos numa passada só e mantém tamanho e
  quadros por segundo do original (taxa fixa). Nenhum filtro de cor.
- Câmera: se existir camera.json (camera.py), aplica o zoom de ênfase em volta do
  rosto, antes da legenda e dos elementos (eles não crescem junto).
- Som: corta com precisão de amostra, suaviza 8 ms em cada emenda (sem estalo),
  aplica o ganho de cada trecho ("ganho_db" no cortes.json, se houver), tira o
  chiado com --ruido, mistura música e efeitos de som.json (som.py) e iguala o
  volume ao padrão das redes (-14 LUFS, pico até -1,5 dBTP).
- Legenda: queima legendas.ass com a fonte da marca.
- Nunca sobrescreve: cada saída ganha um número novo (v001, v002...).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
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


def montar_audio(trechos: list[dict], videos: dict, fps, canais: int, ruido: str) -> tuple[np.ndarray, list]:
    from ruido import decodificar, limpar
    cache: dict[int, np.ndarray] = {}
    tratamento = []
    partes = []
    n_suave = int(SUAVE * TAXA)
    rampa = np.linspace(0, 1, n_suave, dtype=np.float32)[:, None]
    for t in trechos:
        if t["video"] not in cache:
            som = decodificar(videos[t["video"]], canais)
            if ruido != "nao":
                som, feito = limpar(videos[t["video"]], som, ruido)
                tratamento.append({"video": t["video"], **feito})
            cache[t["video"]] = som
        som = cache[t["video"]]
        s0 = int(round(t["quadro_inicio"] / fps * TAXA))
        s1 = int(round(t["quadro_fim"] / fps * TAXA))
        pedaco = som[s0:s1].copy()
        falta = (s1 - s0) - len(pedaco)
        if falta > 0:  # o som acabou antes da imagem
            pedaco = np.vstack([pedaco, np.zeros((falta, canais), np.float32)])
        if t.get("ganho_db"):
            pedaco *= np.float32(10 ** (float(t["ganho_db"]) / 20))
        if len(pedaco) > 2 * n_suave:
            pedaco[:n_suave] *= rampa
            pedaco[-n_suave:] *= rampa[::-1]
        partes.append(pedaco)
    tudo = np.vstack(partes) if partes else np.zeros((0, canais), np.float32)
    return tudo, tratamento


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


def grafo_base(grupos, videos, fps, largura, altura, hdr, hdr_por_arquivo) -> tuple[list[str], list[str], str]:
    """Entradas e filtros que montam a imagem cortada (sem legenda e sem elementos)."""
    entradas, grafos, rotulos = [], [], []
    for n, grupo in enumerate(grupos):
        arquivo = videos[grupo[0]["video"]]
        entradas += ["-i", arquivo]
        cor = ""
        if hdr == "sdr" and arquivo in hdr_por_arquivo:
            # HDR do celular para cor padrão, antes de juntar com os outros vídeos.
            cor = (f"zscale=tin={hdr_por_arquivo[arquivo]}:pin=bt2020:min=bt2020nc:t=linear:npl=100,"
                   f"format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
                   f"zscale=t=bt709:m=bt709:r=tv,")
        formato_px = "yuv420p10le" if hdr == "manter" else "yuv420p"
        selecao = "+".join(f"between(n\\,{t['quadro_inicio']}\\,{t['quadro_fim'] - 1})" for t in grupo)
        grafos.append(
            f"[{n}:v:0]{cor}fps={fps.numerator}/{fps.denominator},"
            f"scale={largura}:{altura}:force_original_aspect_ratio=increase,crop={largura}:{altura},setsar=1,"
            f"format={formato_px},select='{selecao}',setpts=N/({fps.numerator}/{fps.denominator})/TB[v{n}]")
        rotulos.append(f"[v{n}]")
    if len(grupos) > 1:
        grafos.append("".join(rotulos) + f"concat=n={len(grupos)}:v=1:a=0[vc]")
        return entradas, grafos, "[vc]"
    return entradas, grafos, "[v0]"


def grafo_camadas(atual: str, primeiro_elemento: int, elementos: list, ass: Path | None) -> tuple[list[str], str]:
    grafos = []
    for k, el in enumerate(elementos):
        grafos.append(f"[{primeiro_elemento + k}:v]format=rgba,setpts=PTS-STARTPTS+{el['inicio']:.3f}/TB[e{k}]")
        grafos.append(f"{atual}[e{k}]overlay=x={el['x']}:y={el['y']}:eof_action=pass:format=auto[ve{k}]")
        atual = f"[ve{k}]"
    if elementos:
        grafos.append(f"{atual}format=yuv420p[vf]")
        atual = "[vf]"
    if ass is not None:
        grafos.append(f"{atual}ass=filename='{caminho_filtro(ass)}':fontsdir='{caminho_filtro(PASTA_FONTES)}'[vl]")
        atual = "[vl]"
    return grafos, atual


def codificacao(hdr, principal, fps) -> list[str]:
    if hdr == "manter":
        cmd = ["-c:v", "libx265", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p10le", "-tag:v", "hvc1",
               "-color_primaries", "bt2020", "-color_trc", principal["cor"]["transferencia"],
               "-colorspace", "bt2020nc"]
    else:
        cmd = ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-profile:v", "high", "-pix_fmt", "yuv420p",
               "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]
    return cmd + ["-r", f"{fps.numerator}/{fps.denominator}", "-c:a", "aac", "-b:a", "192k",
                  "-movflags", "+faststart"]


def aplicar_camera(cmd_base: list, cmd_final: list, camera, largura: int, altura: int, fps, tmp: Path) -> str:
    """Primeiro ffmpeg solta os quadros cortados, aqui cada quadro ganha o zoom, o segundo
    ffmpeg põe elementos e legenda e grava. Devolve o erro, se houver."""
    import cv2
    err_a, err_b = open(tmp / "erro_a.txt", "w+"), open(tmp / "erro_b.txt", "w+")
    pa = subprocess.Popen(cmd_base, stdout=subprocess.PIPE, stderr=err_a)
    pb = subprocess.Popen(cmd_final, stdin=subprocess.PIPE, stderr=err_b)
    tam_y = largura * altura
    tam = tam_y * 3 // 2
    cw, ch = largura // 2, altura // 2
    n = 0
    try:
        while True:
            bruto = pa.stdout.read(tam)
            if len(bruto) < tam:
                break
            z, x0, y0 = camera.transformar(n * fps.denominator / fps.numerator)
            if z > 1.0001:
                q = np.frombuffer(bruto, np.uint8)
                y = q[:tam_y].reshape(altura, largura)
                u = q[tam_y:tam_y + cw * ch].reshape(ch, cw)
                v = q[tam_y + cw * ch:].reshape(ch, cw)
                m = np.float32([[z, 0, -x0 * z], [0, z, -y0 * z]])
                mc = np.float32([[z, 0, -x0 * z / 2], [0, z, -y0 * z / 2]])
                opc = dict(flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                bruto = b"".join([cv2.warpAffine(y, m, (largura, altura), **opc).tobytes(),
                                  cv2.warpAffine(u, mc, (cw, ch), **opc).tobytes(),
                                  cv2.warpAffine(v, mc, (cw, ch), **opc).tobytes()])
            try:
                pb.stdin.write(bruto)
            except BrokenPipeError:  # a amostra terminou antes do fim do vídeo
                break
            n += 1
    finally:
        try:
            pb.stdin.close()
        except BrokenPipeError:
            pass
        pa.stdout.close()
        if pa.poll() is None:
            pa.terminate()
        pa.wait()
        pb.wait()
    erro_txt = ""
    if pb.returncode != 0:
        err_b.seek(0)
        erro_txt = err_b.read()[-2000:]
    elif pa.returncode not in (0, -15) and n == 0:
        err_a.seek(0)
        erro_txt = err_a.read()[-2000:]
    err_a.close()
    err_b.close()
    return erro_txt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--amostra", nargs=2, type=float, metavar=("INICIO", "FIM"),
                    help="só um pedaço, em segundos do vídeo editado")
    ap.add_argument("--formato", default="original")
    ap.add_argument("--sem-legenda", action="store_true")
    ap.add_argument("--hdr", choices=["sdr", "manter"], help="obrigatório quando o original é HDR")
    ap.add_argument("--ruido", choices=["nao", "leve", "forte"], default="nao", help="redução de ruído da voz")
    ap.add_argument("--volume", type=float, default=-14.0, help="volume final em LUFS")
    ap.add_argument("--sem-normalizar", action="store_true", help="mantém o volume original")
    ap.add_argument("--sem-elementos", action="store_true", help="ignora elementos.json")
    ap.add_argument("--sem-som", action="store_true", help="ignora som.json (sem música e sem efeitos)")
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

    from camera import Camera, assinatura_camera
    camera = Camera.carregar(pasta, largura, altura)
    if camera is not None and a.hdr == "manter":
        erro("o zoom de ênfase não funciona com --hdr manter; use --hdr sdr ou rode camera.py desligar")

    ass = pasta / "legendas.ass"
    usar_legenda = not a.sem_legenda
    if usar_legenda:
        if not ass.exists():
            erro("falta legendas.ass: rode legendas.py ou use --sem-legenda")
        estilo = ler_json(pasta / "legendas.json")["estilo"]
        if (estilo["largura"], estilo["altura"]) != (largura, altura):
            erro(f"a legenda foi feita para {estilo['largura']}x{estilo['altura']} e o vídeo sai "
                 f"{largura}x{altura}: rode legendas.py com o mesmo --formato")
        if estilo.get("posicao") == "auto" and estilo.get("camera") != assinatura_camera(pasta):
            erro("a câmera ou o rosto mudaram depois da legenda: rode legendas.py --reaproveitar")

    trechos = trechos_no_quadro(cortes, fps)
    if not trechos:
        erro("cortes.json não tem trechos")
    videos = {v["id"]: v["arquivo"] for v in cortes["videos"]}
    canais = 2 if any((v["audio"] or {}).get("canais", 1) >= 2 for v in insp) else 1
    duracao = trechos[-1]["saida_fim"]

    with tempfile.TemporaryDirectory() as tmp_txt:
        tmp = Path(tmp_txt)
        print("montando o som...")
        voz, tratamento = montar_audio(trechos, videos, fps, canais, a.ruido)
        dur_audio = len(voz) / TAXA
        mistura = {}
        plano_som = pasta / "som.json"
        if plano_som.exists() and not a.sem_som:
            from som import mixar
            voz, mistura = mixar(voz, ler_json(plano_som))
        from ruido import salvar_wav
        wav = tmp / "voz.wav"
        salvar_wav(voz, wav)

        filtro_audio = f"aresample={TAXA}"
        if not a.sem_normalizar:
            m = medir_loudnorm(wav, a.volume, -1.5)
            filtro_audio = filtro_loudnorm(m, a.volume, -1.5)

        elementos = []
        if not a.sem_elementos and (pasta / "elementos.json").exists():
            if a.hdr == "manter":
                erro("elementos 3D não funcionam com --hdr manter; use --hdr sdr ou --sem-elementos")
            from elementos import desenhar
            elementos = desenhar(pasta, largura, altura, fps)

        log = ["-v", os.environ.get("FFLOG", "error"), "-nostdin", "-y"]
        grupos = blocos_por_video(trechos)
        entradas, grafos_base, rot_base = grafo_base(grupos, videos, fps, largura, altura, a.hdr, hdr_por_arquivo)
        corte = []
        if a.amostra:
            ini, fim = a.amostra
            fim = min(fim, duracao)
            if fim <= ini:
                erro("amostra vazia")
            corte = ["-ss", f"{ini:.3f}", "-t", f"{fim - ini:.3f}"]
        base = "amostra" if a.amostra else (a.nome or pasta.name)
        destino = proximo_nome(pasta, base)
        elem_in = []
        for el in elementos:
            elem_in += ["-thread_queue_size", "64", "-i", el["video"]]
        print(f"renderizando {destino.name} ({largura}x{altura}, "
              f"{tempo(duracao if not a.amostra else a.amostra[1] - a.amostra[0])})...")

        if camera is None:
            idx_audio = len(grupos)
            g_camadas, atual = grafo_camadas(rot_base, idx_audio + 1, elementos, ass if usar_legenda else None)
            grafos = grafos_base + g_camadas + [f"[{idx_audio}:a]{filtro_audio}[ac]"]
            cmd = (["ffmpeg"] + log + entradas + ["-i", str(wav)] + elem_in +
                   ["-filter_complex", ";".join(grafos), "-map", atual, "-map", "[ac]"] + corte +
                   codificacao(a.hdr, principal, fps) + [str(destino)])
            proc = subprocess.run(cmd, capture_output=True, text=True)
            falha = proc.stderr[-2000:] if proc.returncode != 0 else ""
        else:
            cmd_base = (["ffmpeg"] + log + entradas + ["-filter_complex", ";".join(grafos_base), "-map", rot_base,
                        "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"])
            g_camadas, atual = grafo_camadas("[0:v]", 2, elementos, ass if usar_legenda else None)
            grafos = g_camadas + [f"[1:a]{filtro_audio}[ac]"]
            if not g_camadas:
                grafos = ["[0:v]null[vq]"] + grafos
                atual = "[vq]"
            cmd_final = (["ffmpeg"] + log + ["-f", "rawvideo", "-pix_fmt", "yuv420p", "-s", f"{largura}x{altura}",
                         "-framerate", f"{fps.numerator}/{fps.denominator}", "-i", "-", "-i", str(wav)] + elem_in +
                         ["-filter_complex", ";".join(grafos), "-map", atual, "-map", "[ac]"] + corte +
                         codificacao(a.hdr, principal, fps) + [str(destino)])
            falha = aplicar_camera(cmd_base, cmd_final, camera, largura, altura, fps, tmp)
        if falha:
            destino.unlink(missing_ok=True)  # não deixa arquivo pela metade
            erro("o ffmpeg falhou:\n" + falha)

    registro = {
        "arquivo": str(destino), "amostra": a.amostra, "formato": a.formato, "largura": largura, "altura": altura,
        "fps": f"{fps.numerator}/{fps.denominator}", "legenda": usar_legenda, "hdr": a.hdr,
        "elementos": [{"elemento": e["elemento"], "inicio": e["inicio"], "duracao": e["duracao"],
                       "modo": e["modo"], "posicao": e.get("posicao_usada", e.get("posicao")),
                       "escala": e.get("escala_usada", 1.0)} for e in elementos],
        "camera": None if camera is None else {"blocos": len(camera.blocos),
                                               "enfases": sum(1 for b in camera.blocos
                                                              if str(b.get("motivo", "")).startswith("ênfase"))},
        "ruido": {"modo": a.ruido, "por_video": tratamento},
        "som": mistura or None,
        "volume_alvo": None if a.sem_normalizar else a.volume,
        "duracao_esperada": round((a.amostra[1] - a.amostra[0]) if a.amostra else duracao, 3),
        "duracao_audio_montado": round(dur_audio, 3),
        "trechos": len(trechos),
        "emendas": [round(t["saida_inicio"], 4) for t in trechos[1:]],
    }
    salvar_json(destino.with_suffix(".render.json"), registro)
    vol = medir_volume(destino)
    print(f"ok  {destino}  · volume {vol['volume_lufs']} LUFS · pico {vol['pico_dbtp']} dBTP")


if __name__ == "__main__":
    main()
