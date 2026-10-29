"""Elementos 3D que entram no vídeo quando o Well fala a palavra certa.

Uso:
    python elementos.py sugerir --pasta saida/2026-10-22_tema [--modo sobreposto|tela] [--intervalo 6]
    python elementos.py desenhar --pasta saida/2026-10-22_tema

sugerir  lê a fala já cortada e propõe elementos em elementos.json: "WhatsApp" chama a
         mensagem, "cinco minutos" chama o relógio, "funil" o funil, e assim por diante.
         O elemento entra um pouquinho antes da palavra (até 0,15 s), como num corte bem feito.
desenhar gera os quadros de cada elemento (fundo transparente) em elementos/. O
         renderizar.py chama isso sozinho quando falta algum.

Elementos (os mesmos do carrossel): esfera, anel, cubo, cristal, mensagem, funil, relogio,
grafico, alvo, cadeado, lupa, furo.

Modos:
- sobreposto: o elemento flutua sobre o vídeo, com um rótulo opcional. O rosto do Well
  continua na tela. Posição "auto" (padrão): com rosto.json, procura o primeiro lugar que
  não cobre o rosto (topo, topo menor, esquerda, direita, cada vez menor), já com o zoom
  da câmera. Também aceita topo, esquerda, direita ou meio fixos.
- tela: por 1 a 3 s a tela vira o fundo escuro da marca com o elemento e um título curto,
  como um slide do carrossel no meio do vídeo. A voz continua por baixo.

Tudo é proposta: Claude revisa elementos.json (tira, troca, muda o tempo ou o texto) e
confere nos quadros que o elemento não cobre o rosto.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from comum import PASTA_SKILL, aviso, erro, fps_racional, ler_json, salvar_json, tempo

ELEMENTOS = ["esfera", "anel", "cubo", "cristal", "mensagem", "funil", "relogio", "grafico",
             "alvo", "cadeado", "lupa", "furo"]

# Começo de palavra (sem acento) -> elemento. A primeira regra que bate vale.
GATILHOS = [
    ("whatsapp", "mensagem"), ("zap", "mensagem"), ("mensage", "mensagem"), ("respond", "mensagem"),
    ("respost", "mensagem"), ("convers", "mensagem"), ("atendiment", "mensagem"), ("direct", "mensagem"),
    ("minuto", "relogio"), ("hora", "relogio"), ("segundo", "relogio"), ("demor", "relogio"),
    ("prazo", "relogio"), ("tempo", "relogio"), ("rapid", "relogio"),
    ("funil", "funil"), ("etapa", "funil"), ("jornada", "funil"), ("lead", "funil"), ("contato", "funil"),
    ("result", "grafico"), ("cresc", "grafico"), ("faturament", "grafico"), ("dobr", "grafico"),
    ("aument", "grafico"), ("escal", "grafico"), ("contrato", "grafico"),
    ("publico", "alvo"), ("alvo", "alvo"), ("foco", "alvo"), ("nicho", "alvo"), ("qualificad", "alvo"),
    ("oab", "cadeado"), ("etica", "cadeado"), ("regra", "cadeado"), ("segur", "cadeado"),
    ("sigilo", "cadeado"), ("proteg", "cadeado"),
    ("analis", "lupa"), ("descobr", "lupa"), ("procur", "lupa"), ("diagnost", "lupa"), ("investig", "lupa"),
    ("perd", "furo"), ("furo", "furo"), ("vazament", "furo"), ("buraco", "furo"), ("escap", "furo"),
    ("desperdic", "furo"), ("jogando fora", "furo"),
    # Assuntos gerais (gestão, planejamento, rotina), não só marketing jurídico.
    ("objetiv", "alvo"), ("estrateg", "alvo"), ("proposit", "alvo"), ("sonho", "alvo"),
    ("planej", "grafico"), ("lancament", "grafico"), ("caixa", "grafico"), ("lucro", "grafico"),
    ("venda", "grafico"), ("vender", "grafico"), ("faturar", "grafico"), ("meta", "alvo"),
    ("rotina", "relogio"), ("agenda", "relogio"), ("horario", "relogio"), ("cedo", "relogio"),
    ("problema", "furo"), ("erro", "furo"), ("prejuiz", "furo"),
    ("decis", "lupa"), ("enxerg", "lupa"), ("entend", "lupa"), ("clareza", "lupa"),
    ("disciplin", "cadeado"), ("metodo", "cadeado"), ("metodic", "cadeado"), ("rigor", "cadeado"),
]
# Palavras que só contam inteiras (o começo delas pega outras: "meta" x "metade").
INTEIRAS = {"meta", "metas", "erro", "erros", "cedo"}

NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
           "sete": 7, "oito": 8, "nove": 9, "dez": 10, "quinze": 15, "vinte": 20, "trinta": 30,
           "quarenta": 40, "cinquenta": 50, "sessenta": 60, "cem": 100, "mil": 1000}
UNIDADES = {"minuto": "minutos", "minutos": "minutos", "hora": "horas", "horas": "horas",
            "segundo": "segundos", "segundos": "segundos", "dia": "dias", "dias": "dias",
            "por": "%", "reais": "reais", "leads": "leads", "clientes": "clientes", "contratos": "contratos"}

ANTECIPA = 0.12      # o elemento entra um pouco antes da palavra
DURACAO = 2.0        # tempo na tela (sobreposto)
DURACAO_TELA = 1.8


def normalizar(p: str) -> str:
    t = unicodedata.normalize("NFKD", p.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", t)


def rotulo_numero(palavras: list[dict], k: int) -> str | None:
    """'cinco minutos' -> '*5 minutos*' (vira texto do elemento)."""
    n = normalizar(palavras[k]["p"])
    valor = int(n) if n.isdigit() else NUMEROS.get(n)
    if valor is None or k + 1 >= len(palavras):
        return None
    un = normalizar(palavras[k + 1]["p"])
    if un in UNIDADES:
        unidade = UNIDADES[un]
        return f"*{valor}%*" if unidade == "%" else f"*{valor} {unidade}*"
    return None


def sugerir(palavras: list[dict], duracao_video: float, modo: str, intervalo: float) -> list[dict]:
    itens = []
    ultimo = -999.0
    norm = [normalizar(w["p"]) for w in palavras]
    for k, w in enumerate(palavras):
        if w["i"] - ultimo < intervalo:
            continue
        elemento, gatilho, texto = None, w["p"], None
        rot = rotulo_numero(palavras, k)
        if not rot and k > 0 and norm[k] in UNIDADES:  # "minutos" logo depois de "cinco"
            rot = rotulo_numero(palavras, k - 1)
            if rot:
                k, w = k - 1, palavras[k - 1]
        if rot:
            elemento = "relogio" if any(u in rot for u in ("minuto", "hora", "segundo", "dia")) else "grafico"
            gatilho, texto = f"{w['p']} {palavras[k + 1]['p']}", rot
        else:
            for prefixo, el in GATILHOS:
                if " " in prefixo:
                    junto = norm[k] + (norm[k + 1] if k + 1 < len(norm) else "")
                    if junto.startswith(prefixo.replace(" ", "")):
                        elemento = el
                        break
                elif (norm[k] in (prefixo, prefixo + "s") if prefixo in INTEIRAS else norm[k].startswith(prefixo)):
                    elemento = el
                    break
        if not elemento:
            continue
        dur = DURACAO_TELA if modo == "tela" else DURACAO
        inicio = max(0.0, w["i"] - ANTECIPA)
        if inicio + dur > duracao_video:
            dur = duracao_video - inicio
        if dur < 1.0:
            continue
        itens.append({"elemento": elemento, "inicio": round(inicio, 3), "duracao": round(dur, 2),
                      "modo": modo, "posicao": "auto", "texto": texto or "",
                      "gatilho": gatilho.strip(".,!?"), "fala_em": round(w["i"], 3)})
        ultimo = w["i"]
    return itens


# ---------- desenho dos quadros ----------

def tamanho_quadro(item: dict, largura: int, altura: int) -> tuple[int, int]:
    if item["modo"] == "tela":
        return largura, altura
    lado = round(largura * 0.40 * float(item.get("escala_usada", item.get("escala", 1.0))))
    h = round(lado * 1.32) if item.get("texto") else lado
    return lado - lado % 2, h - h % 2


def posicao_quadro(item: dict, largura: int, altura: int) -> tuple[int, int]:
    if item["modo"] == "tela":
        return 0, 0
    w, h = tamanho_quadro(item, largura, altura)
    pos = item.get("posicao_usada", item.get("posicao", "topo"))
    if pos == "esquerda":
        return round(largura * 0.04), round(altura * 0.12)
    if pos == "direita":
        return largura - w - round(largura * 0.04), round(altura * 0.12)
    if pos == "meio":
        return (largura - w) // 2, (altura - h) // 2 - round(altura * 0.05)
    return (largura - w) // 2, round(altura * 0.07)


# Ordem de tentativa da posição automática: (posição, escala).
TENTATIVAS = [("topo", 1.0), ("topo", 0.8), ("esquerda", 0.8), ("direita", 0.8),
              ("esquerda", 0.65), ("direita", 0.65), ("topo", 0.65), ("esquerda", 0.5), ("direita", 0.5)]


def resolver_posicao(item: dict, largura: int, altura: int, rostos, camera) -> str | None:
    """Escolhe onde o elemento entra sem cobrir o rosto. Devolve um aviso, se não achou lugar."""
    item.pop("posicao_usada", None)
    item.pop("escala_usada", None)
    if item["modo"] == "tela" or item.get("posicao", "auto") != "auto":
        return None
    if rostos is None:
        item["posicao_usada"], item["escala_usada"] = "topo", float(item.get("escala", 1.0))
        return None
    from rosto import zona_protegida
    zonas = []
    for t, r in rostos.amostras(item["inicio"], item["inicio"] + item["duracao"]):
        z = zona_protegida(r)
        zonas.append(camera.na_tela(z, t) if camera else z)
    if not zonas:
        item["posicao_usada"], item["escala_usada"] = "topo", 1.0
        return None
    melhor = None
    for pos, esc in TENTATIVAS:
        teste = {**item, "posicao_usada": pos, "escala_usada": esc}
        w, h = tamanho_quadro(teste, largura, altura)
        x, y = posicao_quadro(teste, largura, altura)
        # O desenho ocupa só o miolo do quadro (sobra transparente em volta).
        bx0, by0, bx1, by1 = x + w * 0.12, y + h * 0.08, x + w * 0.88, y + h * 0.92
        cobre = 0.0
        for zx0, zy0, zx1, zy1 in zonas:
            ix = max(0.0, min(bx1, zx1) - max(bx0, zx0))
            iy = max(0.0, min(by1, zy1) - max(by0, zy0))
            cobre = max(cobre, ix * iy)
        if cobre <= 0:
            item["posicao_usada"], item["escala_usada"] = pos, esc
            return None
        if melhor is None or cobre < melhor[0]:
            melhor = (cobre, pos, esc)
    item["posicao_usada"], item["escala_usada"] = melhor[1], melhor[2]
    return (f"o {item['elemento']} em {item['inicio']:.1f} s encosta no rosto em qualquer posição: "
            "use o modo tela ou tire o elemento")


def pasta_do_item(pasta: Path, n: int, item: dict, largura: int, altura: int, fps) -> Path:
    chave = json.dumps([item["elemento"], item["modo"], item.get("texto", ""), item["duracao"],
                        item.get("escala_usada", item.get("escala", 1.0)),
                        largura, altura, str(fps), ler_json(PASTA_SKILL / "marca.json")["cores"]], sort_keys=True)
    return pasta / "elementos" / f"{n:02d}_{item['elemento']}_{hashlib.sha1(chave.encode()).hexdigest()[:8]}"


def abrir_navegador(p):
    """Chromium do Playwright; se não estiver instalado, tenta o Chrome do computador."""
    tentativas = [{}]
    if os.environ.get("NAVEGADOR_CHROMIUM"):
        tentativas.insert(0, {"executable_path": os.environ["NAVEGADOR_CHROMIUM"]})
    for caminho in sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"), reverse=True):
        tentativas.append({"executable_path": caminho})
    tentativas.append({"channel": "chrome"})
    ultimo_erro = None
    for opcoes in tentativas:
        try:
            return p.chromium.launch(**opcoes)
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
    erro(f"não consegui abrir o navegador para desenhar os elementos ({ultimo_erro}). "
         "Rode: python -m playwright install chromium")


def desenhar(pasta: Path, largura: int, altura: int, fps) -> list[dict]:
    """Gera os quadros que faltam. Devolve os itens com 'quadros' e 'x','y'."""
    arq = pasta / "elementos.json"
    if not arq.exists():
        return []
    dados = ler_json(arq)
    itens = dados.get("itens", [])
    marca = ler_json(PASTA_SKILL / "marca.json")
    molde = (PASTA_SKILL / "templates" / "elementos.html").resolve().as_uri()
    from camera import Camera
    from rosto import Rostos
    rostos = Rostos.carregar(pasta, largura, altura)
    camera = Camera.carregar(pasta, largura, altura)
    pendentes = []
    for n, item in enumerate(itens):
        if item["elemento"] not in ELEMENTOS:
            erro(f"elemento desconhecido: {item['elemento']} (use {', '.join(ELEMENTOS)})")
        aviso_pos = resolver_posicao(item, largura, altura, rostos, camera)
        if aviso_pos:
            aviso(f"atenção: {aviso_pos}")
        destino = pasta_do_item(pasta, n, item, largura, altura, fps)
        total = max(1, math.ceil(item["duracao"] * float(fps)))
        item["quadros"] = str(destino)
        item["video"] = str(destino / "elemento.mov")
        item["x"], item["y"] = posicao_quadro(item, largura, altura)
        if not (destino / "elemento.mov").exists():
            pendentes.append((item, destino, total))
    if pendentes:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            erro("playwright não está instalado. Rode: pip install -r scripts/requirements.txt")
        with sync_playwright() as p:
            nav = abrir_navegador(p)
            for item, destino, total in pendentes:
                w, h = tamanho_quadro(item, largura, altura)
                if destino.exists():
                    shutil.rmtree(destino)
                destino.mkdir(parents=True)
                pagina = nav.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
                pagina.goto(molde)
                pagina.evaluate("document.fonts.ready")
                pagina.evaluate("cfg => montar(cfg)", {
                    "elemento": item["elemento"], "modo": item["modo"], "largura": w, "altura": h,
                    "duracao": item["duracao"], "texto": item.get("texto", ""), "cores": marca["cores"],
                    "arroba": marca.get("arroba", "")})
                pagina.evaluate("document.fonts.ready")
                for q in range(total):
                    from comum import andamento
                    andamento(pasta, "desenhando os elementos 3D", q / total, item["elemento"], forcar=False)
                    pagina.evaluate(f"desenhar({q / float(fps)})")
                    pagina.screenshot(path=str(destino / f"{q + 1:04d}.png"), omit_background=True,
                                      clip={"x": 0, "y": 0, "width": w, "height": h})
                pagina.close()
                # Junta os quadros num vídeo curto com transparência e formato único (o navegador
                # salva PNG ora com, ora sem transparência, e o ffmpeg se perde nessa troca).
                subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-framerate",
                                f"{fps.numerator}/{fps.denominator}", "-i", str(destino / "%04d.png"),
                                "-vf", "format=rgba", "-c:v", "png", "-pix_fmt", "rgba",
                                str(destino / "elemento.mov")], check=True)
                for png in destino.glob("*.png"):
                    png.unlink()
                print(f"  desenhado {destino.name} ({total} quadros)")
            nav.close()
    return itens


def palavras_saida(pasta: Path) -> list[dict]:
    from legendas import palavras_no_corte
    insp = ler_json(pasta / "inspecao.json")["videos"][0]
    return palavras_no_corte(pasta, ler_json(pasta / "cortes.json"), fps_racional({"avg_frame_rate": insp["fps"]}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["sugerir", "desenhar"])
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--modo", choices=["sobreposto", "tela"], default="sobreposto")
    ap.add_argument("--intervalo", type=float, default=6.0, help="segundos mínimos entre um elemento e outro")
    ap.add_argument("--formato", default="original")
    a = ap.parse_args()
    pasta = a.pasta.resolve()

    if a.acao == "sugerir":
        if not (pasta / "cortes.json").exists():
            erro("rode propor_cortes.py antes")
        palavras = palavras_saida(pasta)
        if not palavras:
            erro("não há fala no corte")
        cortes = ler_json(pasta / "cortes.json")
        itens = sugerir(palavras, cortes["duracao_final"], a.modo, a.intervalo)
        destino = pasta / "elementos.json"
        if destino.exists():
            aviso("elementos.json já existia: a versão anterior foi guardada em elementos.anterior.json")
            shutil.copy(destino, pasta / "elementos.anterior.json")
        salvar_json(destino, {"itens": itens})
        from comum import andamento_fim
        andamento_fim(pasta, "elementos sugeridos")
        print(f"{len(itens)} elementos sugeridos")
        for n, it in enumerate(itens):
            print(f"  {n:>2}  {tempo(it['inicio'])}  {it['elemento']:<9} quando fala \"{it['gatilho']}\""
                  f"{'  texto: ' + it['texto'] if it['texto'] else ''}")
        print(f"ok  {destino}")
    else:
        from comum import dimensoes_saida
        insp = ler_json(pasta / "inspecao.json")["videos"][0]
        largura, altura = dimensoes_saida(insp["largura"], insp["altura"], a.formato)
        itens = desenhar(pasta, largura, altura, fps_racional({"avg_frame_rate": insp["fps"]}))
        for n, it in enumerate(itens):
            lugar = "tela cheia" if it["modo"] == "tela" else (
                f"{it.get('posicao_usada', it.get('posicao'))}, tamanho {float(it.get('escala_usada', 1.0)):.0%}")
            print(f"  {n:>2}  {tempo(it['inicio'])}  {it['elemento']:<9} {lugar}")
        print(f"ok  {len(itens)} elementos prontos em {pasta / 'elementos'}")


if __name__ == "__main__":
    main()
