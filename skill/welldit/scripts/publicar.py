"""Pacote de publicação: capa, conferência dos limites do Instagram, texto do post e a pasta pronta para postar.

Uso:
    python publicar.py capa-opcoes --pasta saida/... --video saida/.../tema-v001.mp4
    python publicar.py capa --pasta saida/... --video ...mp4 (--opcao 2 | --segundo 8.5) --titulo "Você perde *5 clientes* por mês"
    python publicar.py texto --pasta saida/... --arquivo saida/.../texto-do-post.md
    python publicar.py conferir --pasta saida/... --video ...mp4 [--texto ...md] [--capa capa-v001.jpg]
    python publicar.py pacote --pasta saida/... --video ...mp4 --capa capa-v001.jpg --texto texto-do-post.md [--mesmo-assim]

capa-opcoes  escolhe 4 quadros do vídeo pronto para capa (rosto grande, centrado, nítido, boca fechada)
             e grava capa-opcoes.jpg com eles numerados.
capa         renderiza um quadro limpo (sem legenda nem elementos) e põe o título por cima, fora do rosto
             e dentro do corte 3:4 da grade do perfil. Grava capa-vNNN.jpg e capa-grade-vNNN.jpg.
texto        confere o texto do post (tamanho, hashtags, números que a pessoa não falou).
conferir     confere o vídeo, a legenda nas margens, o texto e o título contra assets/instagram.json.
pacote       confere tudo e monta publicacao-<nome>/ com o vídeo, a capa, o texto, a legenda e o resultado.

Os limites do Instagram ficam em assets/instagram.json (com data e fontes): confira na ajuda oficial.
Nada é publicado e nada sai do computador.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from comum import (PASTA_SKILL, arquivo_da_fonte, aviso, carregar_marca, definir_perfil, erro, nome_do_perfil, exigir, fluxo, fps_racional, ler_json, salvar_json, sondar, tempo,
                   trechos_no_quadro)

ARQ_LIMITES = PASTA_SKILL / "assets" / "instagram.json"
OK, AVISO, FALHOU = "ok", "aviso", "FALHOU"
PASSO_CAPA = 0.5
DISTANCIA_EMENDA = 0.3
SEPARACAO_CAPAS = 3.0
ALTURA_MAXIMA_TITULO = 560      # px em 1080x1920
FOLGA_ROSTO_TITULO = 40


def limites() -> dict:
    return ler_json(ARQ_LIMITES)


def marcas(item) -> str:
    return {OK: "✅", AVISO: "⚠️", FALHOU: "❌"}[item]


# ---------- conferência: vídeo ----------

def conferir_numeros(duracao: float, mb: float, largura: int, altura: int, fps: float, tem_audio: bool,
                     codec_v: str, codec_a: str | None, lim: dict) -> list[tuple[str, str]]:
    r = []
    d = lim["duracao_s"]
    if duracao > d["falha_acima"]:
        r.append((FALHOU, f"duração de {duracao:.0f} s passa do maior limite conhecido ({d['falha_acima']} s)"))
    elif duracao > d["aviso_acima"]:
        r.append((AVISO, f"duração de {duracao:.0f} s: acima de {d['aviso_acima']} s, que depende da conta e da versão do app"))
    else:
        r.append((OK, f"duração de {duracao:.0f} s"))
    a = lim["arquivo_mb"]
    if mb > a["falha_acima"]:
        r.append((FALHOU, f"arquivo de {mb:.0f} MB passa de {a['falha_acima']} MB"))
    elif mb > a["aviso_acima"]:
        r.append((AVISO, f"arquivo de {mb:.0f} MB: grande demais para subir pelo celular com folga"))
    else:
        r.append((OK, f"arquivo de {mb:.1f} MB"))
    p = lim["proporcao"]
    alvo = p["largura"] / p["altura"]
    if abs(largura / altura - alvo) / alvo > p["tolerancia"]:
        r.append((FALHOU, f"proporção {largura}x{altura} não é {p['largura']}:{p['altura']}: o Reels ficaria com faixas ou cortado"))
    else:
        r.append((OK, f"proporção {p['largura']}:{p['altura']} ({largura}x{altura})"))
    w = lim["largura_px"]
    if largura < w["falha_abaixo"]:
        r.append((FALHOU, f"largura de {largura} px: abaixo do mínimo de {w['falha_abaixo']} px"))
    elif largura < w["aviso_abaixo"]:
        r.append((AVISO, f"largura de {largura} px: o ideal é {w['aviso_abaixo']} px"))
    f = lim["quadros_por_segundo"]
    if not f["minimo"] <= fps <= f["maximo"]:
        r.append((AVISO, f"{fps:.1f} quadros por segundo, fora de {f['minimo']} a {f['maximo']}"))
    else:
        r.append((OK, f"{fps:.0f} quadros por segundo"))
    if not tem_audio:
        r.append((FALHOU, "o vídeo não tem som"))
    elif codec_a not in lim["codecs"]["audio"]:
        r.append((AVISO, f"áudio em {codec_a}: o esperado é {', '.join(lim['codecs']['audio'])}"))
    if codec_v not in lim["codecs"]["video"]:
        r.append((AVISO, f"vídeo em {codec_v}: o esperado é {', '.join(lim['codecs']['video'])}"))
    return r


def conferir_arquivo(video: Path, lim: dict) -> list[tuple[str, str]]:
    exigir("ffprobe")
    info = sondar(video)
    v, a = fluxo(info, "video"), fluxo(info, "audio")
    if v is None:
        return [(FALHOU, "o arquivo não tem imagem")]
    from comum import dimensoes_exibidas
    largura, altura = dimensoes_exibidas(v)
    fps = float(fps_racional(v))
    duracao = float(info["format"].get("duration") or v.get("duration") or 0)
    mb = video.stat().st_size / 1e6
    return conferir_numeros(duracao, mb, largura, altura, fps, a is not None, v.get("codec_name", "?"),
                            a.get("codec_name") if a else None, lim)


# ---------- conferência: legenda nas margens ----------

def caixa_legenda(b: dict, estilo: dict) -> tuple[float, float]:
    """(topo, base) do bloco de legenda, em pixels do vídeo."""
    from legendas import caixa_texto
    altura = estilo["altura"]
    alto = caixa_texto(estilo)
    if b.get("y") is not None:
        return b["y"] - alto, b["y"]
    pos = estilo.get("posicao", "auto")
    if pos == "meio":
        return altura / 2 - alto / 2, altura / 2 + alto / 2
    if pos == "alto":
        return altura * 0.16, altura * 0.16 + alto
    base = altura * (1 - 0.24)
    return base - alto, base


def conferir_legenda(blocos: list[dict], estilo: dict, lim: dict) -> list[tuple[str, str]]:
    from legendas import LARGURA_UTIL
    m = lim["margens_em_1080x1920"]
    sx, sy = estilo["largura"] / 1080, estilo["altura"] / 1920
    ruins = []
    for b in blocos:
        topo, base = caixa_legenda(b, estilo)
        if topo < m["topo"] * sy:
            ruins.append((b["inicio"], b["texto"], "sob o topo da tela"))
        elif base > estilo["altura"] - m["base"] * sy:
            ruins.append((b["inicio"], b["texto"], "sob a legenda do post e os botões de baixo"))
    saida = []
    folga_lado = estilo["largura"] * (1 - LARGURA_UTIL) / 2
    if folga_lado < m["direita"] * sx:
        saida.append((AVISO, f"o texto da legenda pode chegar a {folga_lado:.0f} px da borda; os botões da direita ocupam {m['direita'] * sx:.0f} px"))
    if ruins:
        onde = ", ".join(f"{tempo(t)} (\"{txt}\", {motivo})" for t, txt, motivo in ruins[:3])
        saida.append((FALHOU, f"{len(ruins)} bloco(s) de legenda fora da área segura: {onde}"))
    else:
        saida.append((OK, "legenda dentro das margens de segurança"))
    return saida


# ---------- conferência: texto e números ----------

def numeros_do_texto(texto: str) -> set[str]:
    texto = re.sub(r"(?<!\w)#\w+", " ", texto)
    saida = set()
    for n in re.findall(r"\d+(?:[.,]\d+)*", texto):
        saida.add(valor_numerico(n))
    return saida


def valor_numerico(n: str) -> str:
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", n):      # 1.000 = mil
        return n.replace(".", "")
    return n.replace(",", ".")


def numeros_falados(palavras: list[dict]) -> set[str]:
    from elementos import NUMEROS, normalizar
    saida = set()
    for w in palavras:
        n = normalizar(w["p"])
        if n.isdigit():
            saida.add(str(int(n)))
        elif n in NUMEROS:
            saida.add(str(NUMEROS[n]))
    for w in palavras:        # "1.500", "2,5" e "50%" escritos como a transcrição entregou
        for n in re.findall(r"\d+(?:[.,]\d+)*", w["p"]):
            saida.add(valor_numerico(n))
    return saida


def nao_falados(texto: str, falados: set[str]) -> list[str]:
    return sorted(n for n in numeros_do_texto(texto) if n not in falados)


def conferir_texto(texto: str, falados: set[str] | None, lim: dict) -> list[tuple[str, str]]:
    t = lim["texto_do_post"]
    if not texto.strip():
        return [(FALHOU, "o texto do post está vazio")]
    r = []
    n = len(texto)
    r.append((FALHOU, f"texto de {n} caracteres: passa de {t['caracteres_falha_acima']}") if n > t["caracteres_falha_acima"]
             else (OK, f"texto de {n} de {t['caracteres_falha_acima']} caracteres"))
    h = len(re.findall(r"(?<!\w)#\w+", texto))
    if h > t["hashtags_falha_acima"]:
        r.append((FALHOU, f"{h} hashtags: passa de {t['hashtags_falha_acima']}"))
    elif h > t["hashtags_aviso_acima"]:
        r.append((AVISO, f"{h} hashtags: o Instagram recomenda até {t['hashtags_aviso_acima']}"))
    else:
        r.append((OK, f"{h} hashtag(s)"))
    if falados is not None:
        fora = nao_falados(texto, falados)
        if fora:
            r.append((AVISO, f"número(s) no texto que a pessoa não falou no vídeo: {', '.join(fora)}. Confirme com ela"))
    return r


def conferir_titulo(titulo: str, falados: set[str] | None, lim: dict) -> list[tuple[str, str]]:
    t = lim["titulo_da_capa"]
    palavras = len(re.sub(r"\*", "", titulo).split())
    if palavras == 0:
        return [(FALHOU, "o título da capa está vazio")]
    if palavras > t["palavras_falha_acima"]:
        r = [(FALHOU, f"título com {palavras} palavras: não cabe legível na capa (máximo {t['palavras_falha_acima']})")]
    elif palavras > t["palavras_aviso_acima"]:
        r = [(AVISO, f"título com {palavras} palavras: títulos curtos (até {t['palavras_aviso_acima']}) leem melhor no perfil")]
    else:
        r = [(OK, f"título com {palavras} palavras")]
    if falados is not None:
        fora = nao_falados(titulo, falados)
        if fora:
            r.append((AVISO, f"número(s) no título que a pessoa não falou no vídeo: {', '.join(fora)}. Confirme com ela"))
    return r


# ---------- capa: escolha do quadro ----------

def nota_geometrica(r: dict | None, largura: int, em_pausa: bool) -> float | None:
    """Nota de 0 a 0,70 (o resto, 0,30, é a nitidez). None quando não há rosto."""
    if r is None or not r.get("achou"):
        return None
    tam = r["w"] / largura
    dist = 0.0 if 0.25 <= tam <= 0.60 else (0.25 - tam if tam < 0.25 else tam - 0.60)
    pontos_tam = max(0.0, 1 - dist / 0.25)
    pontos_centro = max(0.0, 1 - abs(r["cx"] / largura - 0.5) / 0.25)
    return 0.35 * pontos_tam + 0.25 * pontos_centro + (0.10 if em_pausa else 0.0)


def candidatos_geometricos(rostos, duracao: float, emendas: list[float], palavras: list[dict], largura: int,
                           passo: float = PASSO_CAPA) -> list[dict]:
    saida = []
    t = DISTANCIA_EMENDA
    while t <= duracao - DISTANCIA_EMENDA:
        if not any(abs(t - e) < DISTANCIA_EMENDA for e in emendas):
            r = rostos.em(t)
            em_pausa = not any(w["i"] <= t <= w["f"] for w in palavras)
            nota = nota_geometrica(r, largura, em_pausa)
            if nota is not None:
                saida.append({"t": round(t, 2), "geo": nota, "rosto": r, "pausa": em_pausa})
        t += passo
    return saida


def escolher(cands: list[dict], chave: str, n: int = 4, separacao: float = SEPARACAO_CAPAS) -> list[dict]:
    """Os n melhores, pelo menos `separacao` segundos distantes uns dos outros."""
    saida = []
    for c in sorted(cands, key=lambda c: -c[chave]):
        if all(abs(c["t"] - s["t"]) >= separacao for s in saida):
            saida.append(c)
        if len(saida) == n:
            break
    return saida


def nitidez(quadro_bgr, rosto: dict) -> float:
    import cv2
    h, w = quadro_bgr.shape[:2]
    x0, x1 = int(max(0, rosto["cx"] - rosto["w"] / 2)), int(min(w, rosto["cx"] + rosto["w"] / 2))
    y0, y1 = int(max(0, rosto["cy"] - rosto["h"] / 2)), int(min(h, rosto["cy"] + rosto["h"] / 2))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return 0.0
    cinza = cv2.cvtColor(quadro_bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(cinza, cv2.CV_64F).var())


def extrair_quadro(video: Path | str, segundo: float, destino: Path | None = None):
    """Um quadro do vídeo. Devolve a imagem (BGR) e, se pedido, grava em `destino`."""
    import cv2
    bruto = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", f"{segundo:.3f}", "-i", str(video),
                            "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    if not bruto:
        return None
    img = cv2.imdecode(np.frombuffer(bruto, np.uint8), cv2.IMREAD_COLOR)
    if destino is not None and img is not None:
        cv2.imwrite(str(destino), img)
    return img


# ---------- capa: onde vai o título ----------

def zona_titulo(rosto: dict | None, largura: int, altura: int, lim: dict) -> tuple[float, float] | None:
    """(topo, base) da faixa onde o título pode ficar: fora do rosto, na grade 3:4 e nas margens."""
    sx, sy = largura / 1080, altura / 1920
    corte = max(0.0, (altura - largura * 4 / 3) / 2)
    topo = max(lim["margens_em_1080x1920"]["topo"] * sy, corte + 60 * sy)
    base = altura - max(lim["margens_em_1080x1920"]["base"] * sy, corte + 60 * sy)
    minimo = lim["titulo_da_capa"]["altura_minima_px"] * sy
    maximo = ALTURA_MAXIMA_TITULO * sy
    if rosto is None:
        return (topo, min(base, topo + maximo)) if base - topo >= minimo else None
    from rosto import zona_protegida
    _, zy0, _, zy1 = zona_protegida(rosto)
    folga = FOLGA_ROSTO_TITULO * sy
    opcoes = []
    abaixo = (zy1 + folga, min(base, zy1 + folga + maximo))
    acima = (max(topo, zy0 - folga - maximo), zy0 - folga)
    for y0, y1 in (abaixo, acima):
        y0 = max(y0, topo)
        if y1 - y0 >= minimo:
            opcoes.append((y0, y1))
    return max(opcoes, key=lambda z: z[1] - z[0]) if opcoes else None


def proximo_numero(pasta: Path, prefixo: str, ext: str) -> int:
    n = 1
    while (pasta / f"{prefixo}-v{n:03d}{ext}").exists():
        n += 1
    return n


# ---------- comandos ----------

def carregar_trabalho(pasta: Path):
    from rosto import Rostos
    from legendas import palavras_no_corte
    if not (pasta / "rosto.json").exists():
        erro("rode rosto.py antes (a capa usa o rosto)")
    insp = ler_json(pasta / "inspecao.json")["videos"]
    cortes = ler_json(pasta / "cortes.json")
    fps = fps_racional({"avg_frame_rate": insp[0]["fps"]})
    rostos = Rostos.carregar(pasta)
    palavras = palavras_no_corte(pasta, cortes, fps)
    trechos = trechos_no_quadro(cortes, fps)
    return rostos, palavras, trechos


def comando_capa_opcoes(pasta: Path, video: Path):
    import cv2
    from comum import andamento, andamento_fim
    andamento(pasta, "escolhendo quadros para a capa", 0.0)
    rostos, palavras, trechos = carregar_trabalho(pasta)
    duracao = trechos[-1]["saida_fim"]
    emendas = [t["saida_inicio"] for t in trechos[1:]]
    cands = candidatos_geometricos(rostos, duracao, emendas, palavras, rostos.largura)
    if not cands:
        erro("não achei nenhum quadro com rosto longe das emendas")
    previas = escolher(cands, "geo", n=12, separacao=1.5)
    quadros = {}
    for k, c in enumerate(previas):
        img = extrair_quadro(video, c["t"])
        if img is None or img.shape[1] != rostos.largura or img.shape[0] != rostos.altura:
            erro(f"o vídeo não tem o tamanho do rosto.json ({rostos.largura}x{rostos.altura}): use o mesmo --formato")
        quadros[c["t"]] = img
        c["nitidez"] = nitidez(img, c["rosto"])
        andamento(pasta, "escolhendo quadros para a capa", (k + 1) / len(previas))
    maior = max(c["nitidez"] for c in previas) or 1.0
    for c in previas:
        c["nota"] = round(c["geo"] + 0.30 * c["nitidez"] / maior, 3)
    top = escolher(previas, "nota", n=4)
    linhas = []
    for n, c in enumerate(top, 1):
        img = cv2.resize(quadros[c["t"]], (360, int(360 * rostos.altura / rostos.largura)))
        cv2.putText(img, str(n), (14, 54), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (255, 255, 255), 4)
        cv2.putText(img, tempo(c["t"]), (14, img.shape[0] - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        linhas.append(img)
    folha = pasta / "capa-opcoes.jpg"
    cv2.imwrite(str(folha), np.hstack(linhas))
    salvar_json(pasta / "capa-opcoes.json", {"video": str(video), "opcoes": [
        {"opcao": n, "segundo": c["t"], "nota": c["nota"], "nitidez": round(c["nitidez"], 1), "boca_fechada": c["pausa"]}
        for n, c in enumerate(top, 1)]})
    andamento_fim(pasta, "quadros da capa escolhidos")
    for n, c in enumerate(top, 1):
        print(f"  opção {n}: {tempo(c['t'])}  nota {c['nota']:.2f}{'  boca fechada' if c['pausa'] else ''}")
    print(f"ok  {folha}")


def renderizar_quadro_limpo(pasta: Path, video: Path, segundo: float, tmp: Path) -> Path:
    """Um quadro do vídeo sem legenda, sem elementos e sem som, no mesmo formato do vídeo pronto."""
    reg = video.with_suffix(".render.json")
    if not reg.exists():
        erro(f"falta {reg.name}: a capa precisa saber o formato e a cor do vídeo pronto")
    r = ler_json(reg)
    if r.get("hdr") == "manter":
        erro("a capa não funciona com --hdr manter: renderize o vídeo com --hdr sdr")
    antes = set(pasta.glob("amostra-v*.mp4"))
    cmd = [sys.executable, str(Path(__file__).with_name("renderizar.py")), "--pasta", str(pasta),
           "--amostra", f"{segundo:.3f}", f"{segundo + 0.6:.3f}", "--formato", r.get("formato", "original"),
           "--sem-legenda", "--sem-elementos", "--sem-som", "--sem-normalizar", "--perfil", nome_do_perfil(pasta)]
    if r.get("hdr"):
        cmd += ["--hdr", r["hdr"]]
    print("renderizando um quadro limpo (sem legenda nem elementos)...")
    p = subprocess.run(cmd, capture_output=True, text=True)
    novos = set(pasta.glob("amostra-v*.mp4")) - antes
    if p.returncode != 0 or not novos:
        erro("não consegui renderizar o quadro limpo:\n" + (p.stderr or p.stdout)[-800:])
    amostra = sorted(novos)[-1]
    destino = tmp / "base.png"
    img = extrair_quadro(amostra, 0.2, destino)
    for arq in novos:                  # são amostras que este comando acabou de criar
        arq.unlink(missing_ok=True)
        arq.with_suffix(".render.json").unlink(missing_ok=True)
    if img is None:
        erro("não consegui tirar o quadro da amostra")
    return destino


def desenhar_capa(base: Path, titulo: str, largura: int, altura: int, zona: tuple[float, float],
                  marca: dict | None = None) -> bytes:
    """A capa pronta (JPEG), nas cores e na fonte do perfil de marca (o padrão, se não vier um)."""
    import cv2
    from elementos import abrir_navegador
    marca = marca or carregar_marca()
    cores = marca["cores"]
    jpg = cv2.imencode(".jpg", cv2.imread(str(base)), [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()
    cfg = {"largura": largura, "altura": altura, "titulo": titulo, "y0": round(zona[0]), "y1": round(zona[1]),
           "margem_x": round(largura * 0.08), "fundo": "data:image/jpeg;base64," + base64.b64encode(jpg).decode(),
           "cores": {"texto": cores["texto"], "destaque": cores["destaque"], "escuro": cores["fundo_profundo"]},
           "fonte": {"familia": marca["legenda"]["fonte"], "url": arquivo_da_fonte(marca).as_uri()}}
    molde = (PASTA_SKILL / "templates" / "capa.html").resolve().as_uri()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        nav = abrir_navegador(pw)
        pagina = nav.new_page(viewport={"width": largura, "height": altura}, device_scale_factor=1)
        pagina.goto(molde)
        resultado = pagina.evaluate("cfg => montar(cfg)", cfg)
        if not resultado["cabe"]:
            nav.close()
            erro("o título não cabe na faixa livre, mesmo pequeno: encurte o título ou escolha outro quadro")
        png = pagina.screenshot(type="jpeg", quality=92, clip={"x": 0, "y": 0, "width": largura, "height": altura})
        nav.close()
    print(f"  letra de {resultado['tamanho']} px")
    return png


def grade_do_perfil(capa: Path, destino: Path):
    """A capa com o corte 3:4 marcado, ao lado do corte (como aparece na grade do perfil)."""
    import cv2
    img = cv2.imread(str(capa))
    h, w = img.shape[:2]
    corte = max(0, (h - round(w * 4 / 3)) // 2)
    marcada = img.copy()
    escura = (img * 0.35).astype(np.uint8)
    marcada[:corte], marcada[h - corte:] = escura[:corte], escura[h - corte:]
    cv2.rectangle(marcada, (0, corte), (w - 1, h - corte - 1), (255, 255, 255), 3)
    perfil = img[corte:h - corte]
    alvo = 960
    a = cv2.resize(marcada, (round(w * alvo / h), alvo))
    b = cv2.resize(perfil, (round(perfil.shape[1] * (alvo * 0.75) / perfil.shape[0]), round(alvo * 0.75)))
    fundo = np.full((alvo, b.shape[1] + 30, 3), 22, np.uint8)
    fundo[(alvo - b.shape[0]) // 2:(alvo - b.shape[0]) // 2 + b.shape[0], 15:15 + b.shape[1]] = b
    cv2.imwrite(str(destino), np.hstack([a, fundo]))


def comando_capa(pasta: Path, video: Path, opcao: int | None, segundo: float | None, titulo: str):
    from comum import andamento, andamento_fim
    from rosto import Rostos
    lim = limites()
    if opcao is not None:
        arq = pasta / "capa-opcoes.json"
        if not arq.exists():
            erro("rode publicar.py capa-opcoes antes, ou use --segundo")
        ops = {o["opcao"]: o for o in ler_json(arq)["opcoes"]}
        if opcao not in ops:
            erro(f"a opção vai de 1 a {len(ops)}")
        segundo = ops[opcao]["segundo"]
    if segundo is None:
        erro("diga o quadro: --opcao N ou --segundo S")
    _, palavras, _ = carregar_trabalho(pasta)
    for nivel, texto in conferir_titulo(titulo, numeros_falados(palavras), lim):
        print(f"  {marcas(nivel)} {texto}")
        if nivel == FALHOU:
            erro("corrija o título")
    rostos = Rostos.carregar(pasta)
    zona = zona_titulo(rostos.em(segundo), rostos.largura, rostos.altura, lim)
    if zona is None:
        erro("não há faixa livre de 260 px fora do rosto neste quadro: escolha outro quadro")
    andamento(pasta, "montando a capa", 0.3)
    with tempfile.TemporaryDirectory() as tmp_txt:
        base = renderizar_quadro_limpo(pasta, video, segundo, Path(tmp_txt))
        andamento(pasta, "montando a capa", 0.8)
        jpg = desenhar_capa(base, titulo, rostos.largura, rostos.altura, zona, carregar_marca(pasta=pasta))
    n = proximo_numero(pasta, "capa", ".jpg")
    capa, grade = pasta / f"capa-v{n:03d}.jpg", pasta / f"capa-grade-v{n:03d}.jpg"
    capa.write_bytes(jpg)
    grade_do_perfil(capa, grade)
    andamento_fim(pasta, "capa pronta")
    print(f"ok  {capa}  {grade}")


def achar(pasta: Path, caminho: Path) -> Path:
    """O arquivo como foi dado, ou dentro da pasta do trabalho."""
    if caminho.is_absolute() or caminho.exists():
        return caminho.resolve()
    return (pasta / caminho).resolve()


def ler_texto(arq: Path) -> str:
    if not arq.exists():
        erro(f"não achei {arq}")
    return arq.read_text(encoding="utf-8").strip()


def conferir_tudo(pasta: Path, video: Path, texto: Path | None, capa: Path | None) -> list[tuple[str, str, str]]:
    lim = limites()
    saida = [("Vídeo", n, t) for n, t in conferir_arquivo(video, lim)]
    leg = pasta / "legendas.json"
    reg = video.with_suffix(".render.json")
    if leg.exists() and reg.exists() and ler_json(reg).get("legenda"):
        d = ler_json(leg)
        saida += [("Legenda", n, t) for n, t in conferir_legenda(d["blocos"], d["estilo"], lim)]
    falados = None
    try:
        _, palavras, _ = carregar_trabalho(pasta)
        falados = numeros_falados(palavras)
    except SystemExit:
        pass
    if texto is not None:
        saida += [("Texto do post", n, t) for n, t in conferir_texto(ler_texto(texto), falados, lim)]
    else:
        saida.append(("Texto do post", AVISO, "ainda não há texto do post"))
    if capa is not None:
        saida.append(("Capa", OK if capa.exists() else FALHOU, f"{capa.name}" if capa.exists() else f"não achei {capa}"))
    else:
        saida.append(("Capa", AVISO, "ainda não há capa"))
    return saida


def mostrar(itens: list[tuple[str, str, str]]):
    grupo = None
    for g, nivel, texto in itens:
        if g != grupo:
            print(f"\n{g}")
            grupo = g
        print(f"  {marcas(nivel)} {texto}")
    print()


def comando_conferir(pasta: Path, video: Path, texto: Path | None, capa: Path | None) -> list:
    lim = limites()
    print(f"Limites do Instagram conferidos em {lim['conferido_em']} (assets/instagram.json): confirme na ajuda oficial.")
    itens = conferir_tudo(pasta, video, texto, capa)
    mostrar(itens)
    salvar_json(pasta / "publicacao.json", {"video": str(video), "conferido_em": lim["conferido_em"],
                                            "itens": [{"grupo": g, "nivel": n, "texto": t} for g, n, t in itens]})
    return itens


def comando_pacote(pasta: Path, video: Path, texto: Path, capa: Path, mesmo_assim: bool):
    itens = comando_conferir(pasta, video, texto, capa)
    falhas = [t for _, n, t in itens if n == FALHOU]
    if falhas and not mesmo_assim:
        erro(f"{len(falhas)} item(ns) falharam: corrija ou use --mesmo-assim se for de propósito", 1)
    destino = pasta / f"publicacao-{video.stem}"
    n = 2
    while destino.exists():
        destino = pasta / f"publicacao-{video.stem}-{n}"
        n += 1
    destino.mkdir()
    try:
        os.link(video, destino / video.name)
    except OSError:
        shutil.copy2(video, destino / video.name)
    shutil.copy2(capa, destino / "capa.jpg")
    (destino / "texto-do-post.txt").write_text(ler_texto(texto) + "\n", encoding="utf-8")
    if (pasta / "legendas.srt").exists():
        shutil.copy2(pasta / "legendas.srt", destino / "legenda.srt")
    lim = limites()
    linhas = ["# Conferência da publicação", "",
              f"Limites do Instagram conferidos em {lim['conferido_em']}. Confirme na ajuda oficial antes de postar.", ""]
    grupo = None
    for g, nivel, t in itens:
        if g != grupo:
            linhas += ["", f"## {g}", ""]
            grupo = g
        linhas.append(f"- {marcas(nivel)} {t}")
    (destino / "conferencia.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"ok  {destino}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["capa-opcoes", "capa", "texto", "conferir", "pacote"])
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--video", type=Path)
    ap.add_argument("--opcao", type=int)
    ap.add_argument("--segundo", type=float)
    ap.add_argument("--titulo")
    ap.add_argument("--arquivo", type=Path, help="texto: o texto do post")
    ap.add_argument("--texto", type=Path)
    ap.add_argument("--capa", type=Path)
    ap.add_argument("--mesmo-assim", action="store_true")
    ap.add_argument("--perfil", help="perfil de marca (padrão: o da pasta do trabalho)")
    a = ap.parse_args()
    definir_perfil(a.perfil)
    pasta = a.pasta.resolve()
    if a.acao == "texto":
        if not a.arquivo:
            erro("informe --arquivo com o texto do post")
        falados = None
        try:
            falados = numeros_falados(carregar_trabalho(pasta)[1])
        except SystemExit:
            aviso("sem rosto.json não dá para conferir os números com a fala")
        itens = conferir_texto(ler_texto(achar(pasta, a.arquivo)), falados, limites())
        mostrar([("Texto do post", n, t) for n, t in itens])
        sys.exit(1 if any(n == FALHOU for n, _ in itens) else 0)
    if not a.video:
        erro("informe --video com o MP4 pronto")
    video = a.video.resolve()
    if not video.exists():
        erro(f"não achei {video}")
    exigir("ffmpeg")
    if a.acao == "capa-opcoes":
        comando_capa_opcoes(pasta, video)
    elif a.acao == "capa":
        if not a.titulo:
            erro("informe o título: --titulo \"Frase com *destaque*\"")
        comando_capa(pasta, video, a.opcao, a.segundo, a.titulo)
    elif a.acao == "conferir":
        itens = comando_conferir(pasta, video, achar(pasta, a.texto) if a.texto else None,
                                 achar(pasta, a.capa) if a.capa else None)
        sys.exit(1 if any(n == FALHOU for _, n, _ in itens) else 0)
    else:
        if not (a.texto and a.capa):
            erro("o pacote precisa de --texto e --capa")
        comando_pacote(pasta, video, achar(pasta, a.texto), achar(pasta, a.capa), a.mesmo_assim)


if __name__ == "__main__":
    main()
