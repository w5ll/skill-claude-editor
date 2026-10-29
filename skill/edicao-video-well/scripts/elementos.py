"""Elementos 3D que entram no vídeo quando o Well fala a palavra certa.

Uso:
    python elementos.py sugerir --pasta saida/2026-10-22_tema [--modo sobreposto|tela] [--intervalo 6]
    python elementos.py desenhar --pasta saida/2026-10-22_tema
    python elementos.py validar --pasta saida/2026-10-22_tema            (ou --arquivo desenho.svg --animacao girar)
    python elementos.py previa --pasta saida/2026-10-22_tema [--formato original@1080]
    python elementos.py promover NOME --pasta saida/2026-10-22_tema [--palavras "bussol,rumo"]

sugerir  lê a fala já cortada e propõe elementos em elementos.json: "WhatsApp" chama a
         mensagem, "cinco minutos" chama o relógio, "funil" o funil, e assim por diante.
         O elemento entra um pouquinho antes da palavra (até 0,15 s), como num corte bem feito.
desenhar gera os quadros de cada elemento (fundo transparente) em elementos/. O
         renderizar.py chama isso sozinho quando falta algum.
validar  confere os elementos gerados (desenho e animação) e diz, em português, o que está errado.
previa   desenha cada elemento do elementos.json (prontos e gerados) e monta elementos-previa.jpg:
         em 3 instantes, sobre o fundo da marca e sobre o próprio vídeo. É a imagem do cartão.
promover guarda um elemento gerado e aprovado no catálogo (templates/gerados/), para o sugerir
         achar pela palavra nos próximos vídeos.

Elementos gerados: o item do elementos.json tem "elemento": "gerado:nome", "svg" (o desenho, em
elementos-gerados/nome.svg) e "animacao". Veja referencias/elementos-3d.md.

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
import atexit
import base64
import glob
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

from comum import PASTA_SKILL, aviso, erro, fps_racional, ler_json, salvar_json, tempo, trechos_no_quadro

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

# ---------- elementos gerados ----------
PASTA_GERADOS = PASTA_SKILL / "templates" / "gerados"
GRADIENTES = ["met", "met2", "lado", "brilho", "esf", "vidro", "buraco", "sombra"]
IDS_RESERVADOS = set(GRADIENTES) | {"recorte-reflexo"}
CORES_SOLIDAS = {"#16161f", "#0a0a12", "#eaefef", "#ffffff"}
TAGS_FORMA = {"path", "circle", "ellipse", "rect", "line", "polyline", "polygon"}
TAGS_DESENHO = TAGS_FORMA | {"g"}
MAX_FORMAS = 12
MARGEM = 30
# animação -> (parte que se mexe, o que faz)
ANIMACOES = {
    "girar": ("gira", "gira em volta do centro da parte (com \"parar\": true vai de -25° a 0° e para)"),
    "subir": ("sobe", "sobe 40 unidades e volta, devagar"),
    "balancar": ("balanca", "inclina de -6° a 6°, como barco na onda"),
    "tracar": ("traco", "o traço se desenha do começo ao fim em 1 s e fica"),
    "encaixar": ("encaixa", "a parte desce 60 unidades e encaixa com um pequeno quique"),
    "pulsar": ("pulsa", "cresce 8% e volta, a cada 0,8 s"),
    "brilhar": ("reflexo", "o reflexo passa de lado a lado uma vez"),
    "aparecer": (None, "as partes com class=\"passo\" aparecem uma a uma, a cada 0,15 s"),
}
ATRIBUTOS_GEOMETRIA = {"d", "cx", "cy", "r", "rx", "ry", "x", "y", "width", "height", "x1", "y1", "x2", "y2", "points"}
ATRIBUTOS = ATRIBUTOS_GEOMETRIA | {"id", "class", "transform", "opacity", "fill", "fill-opacity", "stroke",
                                   "stroke-width", "stroke-opacity", "stroke-linecap", "stroke-linejoin",
                                   "stroke-dasharray"}
TAGS_PROIBIDAS = {
    "script": "script não é permitido: o desenho não pode rodar código",
    "text": "texto dentro do desenho não é permitido (<text>): o rótulo vai no campo texto do item",
    "tspan": "texto dentro do desenho não é permitido (<tspan>): o rótulo vai no campo texto do item",
    "image": "imagem dentro do desenho não é permitida (<image>)",
    "use": "<use> não é permitido: repita a forma",
    "foreignObject": "<foreignObject> não é permitido",
    "style": "<style> não é permitido: use os atributos de cada forma",
    "svg": "escreva só o miolo do desenho, sem a tag <svg> em volta",
    "defs": "não defina gradientes nem recortes: use os da marca (url(#met), url(#lado)...)",
}

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


def carregar_catalogo() -> list[dict]:
    """Elementos gerados que o Well aprovou (templates/gerados/catalogo.json)."""
    arq = PASTA_GERADOS / "catalogo.json"
    if not arq.exists():
        return []
    entradas = []
    for e in ler_json(arq).get("elementos", []):
        if not (PASTA_GERADOS / e.get("svg", "")).is_file():
            aviso(f"catálogo: o desenho de {e.get('nome')} não está em templates/gerados/: ignorei")
            continue
        e["_stems"] = [normalizar(p) for p in e.get("palavras", []) if normalizar(p)]
        entradas.append(e)
    return entradas


def sugerir(palavras: list[dict], duracao_video: float, modo: str, intervalo: float,
            catalogo: list[dict] | None = None) -> list[dict]:
    itens = []
    ultimo = -999.0
    norm = [normalizar(w["p"]) for w in palavras]
    for k, w in enumerate(palavras):
        if w["i"] - ultimo < intervalo:
            continue
        elemento, gatilho, texto, entrada = None, w["p"], None, None
        rot = rotulo_numero(palavras, k)
        if not rot and k > 0 and norm[k] in UNIDADES:  # "minutos" logo depois de "cinco"
            rot = rotulo_numero(palavras, k - 1)
            if rot:
                k, w = k - 1, palavras[k - 1]
        if rot:
            elemento = "relogio" if any(u in rot for u in ("minuto", "hora", "segundo", "dia")) else "grafico"
            gatilho, texto = f"{w['p']} {palavras[k + 1]['p']}", rot
        else:
            for ent in catalogo or []:      # o catálogo de gerados aprovados vale primeiro: é mais específico
                if any(norm[k].startswith(st) for st in ent["_stems"]):
                    elemento, entrada = f"gerado:{ent['nome']}", ent
                    break
            for prefixo, el in ([] if entrada else GATILHOS):
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
        item = {"elemento": elemento, "inicio": round(inicio, 3), "duracao": round(dur, 2),
                "modo": modo, "posicao": "auto", "texto": texto or "",
                "gatilho": gatilho.strip(".,!?"), "fala_em": round(w["i"], 3)}
        if entrada:
            item = {"elemento": elemento, "svg": f"elementos-gerados/{entrada['nome']}.svg",
                    "animacao": entrada["animacao"], **({"parar": True} if entrada.get("parar") else {}),
                    "ideia": entrada.get("ideia", ""), **{k: v for k, v in item.items() if k != "elemento"}}
        itens.append(item)
        ultimo = w["i"]
    return itens


# ---------- desenho dos quadros ----------

def tamanho_quadro(item: dict, largura: int, altura: int) -> tuple[int, int]:
    if item["modo"] == "tela":
        return largura, altura
    if item.get("caixa_usada"):      # cena em painel: o tamanho vem do conteúdo (cenas.resolver_caixa)
        return item["caixa_usada"][2], item["caixa_usada"][3]
    lado = round(largura * 0.40 * float(item.get("escala_usada", item.get("escala", 1.0))))
    h = round(lado * 1.32) if item.get("texto") else lado
    return lado - lado % 2, h - h % 2


def posicao_quadro(item: dict, largura: int, altura: int) -> tuple[int, int]:
    if item["modo"] == "tela":
        return 0, 0
    if item.get("caixa_usada"):
        return item["caixa_usada"][0], item["caixa_usada"][1]
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
    item.pop("caixa_usada", None)
    if eh_cena(item):
        from cenas import resolver_caixa
        return resolver_caixa(item, largura, altura, rostos, camera)
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


def pasta_do_item(pasta: Path, n: int, item: dict, largura: int, altura: int, fps, svg: str | None = None) -> Path:
    partes = [item["elemento"], item["modo"], item.get("texto", ""), item["duracao"],
              item.get("escala_usada", item.get("escala", 1.0)),
              largura, altura, str(fps), ler_json(PASTA_SKILL / "marca.json")["cores"]]
    if svg is not None:     # elemento gerado: o desenho e a animação entram na chave (os 12 prontos não mudam)
        partes += [hashlib.sha1(svg.encode()).hexdigest(), item.get("animacao"), bool(item.get("parar"))]
    if eh_cena(item):       # cena: o conteúdo, o tempo (a sincronia depende do início) e o tamanho do painel
        partes += [item.get("cena"), item["inicio"], (item.get("caixa_usada") or [0, 0, 0, 0])[2:]]
    chave = json.dumps(partes, sort_keys=True)
    nome = item["elemento"].replace(":", "-")
    return pasta / "elementos" / f"{n:02d}_{nome}_{hashlib.sha1(chave.encode()).hexdigest()[:8]}"


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



# ---------- validação dos elementos gerados ----------

def eh_gerado(item: dict) -> bool:
    return str(item.get("elemento", "")).startswith("gerado:")


def eh_cena(item: dict) -> bool:
    return str(item.get("elemento", "")).startswith("cena:")


def _sem_ns(nome: str) -> str:
    return nome.rsplit("}", 1)[-1]


def _numero(v: str) -> float | None:
    try:
        return float(v.strip())
    except ValueError:
        return None


def _pintura_ok(v: str) -> bool:
    v = v.strip()
    if v == "none":
        return True
    m = re.fullmatch(r"url\(#([\w-]+)\)", v)
    if m:
        return m.group(1) in GRADIENTES
    c = v.lower()
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        c = "#" + "".join(ch * 2 for ch in c[1:])
    return c in CORES_SOLIDAS


def _problema_do_valor(nome: str, v: str) -> str | None:
    """Devolve o que está errado no valor de um atributo, ou None."""
    if re.search(r"https?:|javascript:|data:|file:|\.\./|\.(png|jpe?g|gif|svg|css)\b", v, re.I):
        return f'{nome}="{v}" aponta para fora do desenho: referência a arquivo ou endereço não é permitida'
    if nome in ("fill", "stroke"):
        if not _pintura_ok(v):
            return (f'{nome}="{v}" não é permitido: use none, um gradiente da marca ({", ".join("url(#" + g + ")" for g in GRADIENTES)}) '
                    f'ou as cores {", ".join(sorted(CORES_SOLIDAS))}')
    elif "url(" in v:
        return f'{nome}="{v}": url(...) só vale em fill e stroke'
    elif nome in ATRIBUTOS_GEOMETRIA - {"d", "points"}:
        if _numero(v) is None:
            return f'{nome}="{v}" deveria ser um número'
    elif nome == "d":
        if not re.fullmatch(r"[MmLlHhVvCcSsQqTtAaZz0-9eE.,+\-\s]*", v):
            return f'o caminho d="{v[:40]}..." tem caracteres que não são de desenho'
    elif nome == "points":
        if not re.fullmatch(r"[0-9eE.,+\-\s]*", v):
            return f'points="{v[:40]}" deveria ter só números'
    elif nome == "transform":
        if not re.fullmatch(r"(\s*(translate|rotate|scale|skewX|skewY|matrix)\(\s*[-+0-9.eE, ]*\)\s*)+", v):
            return f'transform="{v}" não é permitido: use translate, rotate, scale, skewX, skewY ou matrix com números'
    elif nome in ("opacity", "fill-opacity", "stroke-opacity"):
        n = _numero(v)
        if n is None or not 0 <= n <= 1:
            return f'{nome}="{v}" deveria ser um número entre 0 e 1'
    elif nome == "stroke-width":
        n = _numero(v)
        if n is None or not 0 < n <= 40:
            return f'stroke-width="{v}" deveria ser um número entre 0 e 40'
    elif nome == "stroke-linecap":
        if v not in ("butt", "round", "square"):
            return f'stroke-linecap="{v}" deveria ser butt, round ou square'
    elif nome == "stroke-linejoin":
        if v not in ("miter", "round", "bevel"):
            return f'stroke-linejoin="{v}" deveria ser miter, round ou bevel'
    elif nome == "stroke-dasharray":
        if not re.fullmatch(r"[0-9.,\s]+", v):
            return f'stroke-dasharray="{v}" deveria ter só números'
    elif nome == "class":
        if set(v.split()) - {"passo"}:
            return f'class="{v}": a única classe permitida é "passo"'
    elif nome == "id":
        if not re.fullmatch(r"[A-Za-z][\w-]*", v):
            return f'id="{v}" deveria ser uma palavra sem espaço nem acento'
        if v in IDS_RESERVADOS:
            return f'id="{v}" é reservado pela marca (gradientes): escolha outro nome'
    return None


def validar_svg(texto: str, animacao: str | None = None, parar: bool = False) -> tuple[list[str], list[str]]:
    """Confere o desenho de um elemento gerado. Devolve (erros, avisos), em português."""
    erros: list[str] = []
    avisos: list[str] = []
    if re.search(r"<!(?!--)", texto) or "<?" in texto:
        erros.append("o desenho tem DOCTYPE, CDATA ou instrução de processamento: use só as tags de desenho")
    for tag in dict.fromkeys(re.findall(r"<\s*([A-Za-z][\w:-]*)", texto)):
        if tag in TAGS_PROIBIDAS:
            erros.append(TAGS_PROIBIDAS[tag])
        elif tag not in TAGS_DESENHO:
            erros.append(f"<{tag}> não é permitido: use só {', '.join(sorted(TAGS_DESENHO))}")
    if re.search(r"\bhref\s*=|xlink:", texto, re.I):
        erros.append("href não é permitido: o desenho não pode apontar para outro arquivo ou endereço")
    if re.search(r"\bon\w+\s*=", texto, re.I):
        erros.append("atributo de evento (onclick, onload...) não é permitido: o desenho não roda código")
    if re.search(r"\bstyle\s*=", texto, re.I):
        erros.append("o atributo style não é permitido: use fill, stroke e opacity em cada forma")
    try:
        raiz = ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{texto}</svg>')
    except ET.ParseError as e:
        erros.append(f"o arquivo não é um desenho válido (XML): {e}")
        return list(dict.fromkeys(erros)), avisos
    formas, ids, passos, tem_sombra = 0, {}, 0, False
    for el in raiz.iter():
        if el is raiz:
            continue
        tag = _sem_ns(el.tag)
        if tag not in TAGS_DESENHO:
            continue            # já reportada acima
        if (el.text or "").strip():
            erros.append(f"texto solto dentro de <{tag}>: o desenho não pode ter texto")
        if tag in TAGS_FORMA:
            formas += 1
        for nome_ns, valor in el.attrib.items():
            nome = _sem_ns(nome_ns)
            if nome.lower().startswith("on") or nome in ("href", "style"):
                continue        # já reportado acima
            if nome not in ATRIBUTOS:
                erros.append(f'atributo não permitido em <{tag}>: {nome}="{valor[:30]}"')
                continue
            problema = _problema_do_valor(nome, valor)
            if problema:
                erros.append(problema)
        if el.get("fill") == "url(#sombra)":
            tem_sombra = True
        if "passo" in (el.get("class") or "").split():
            passos += 1
        if el.get("id"):
            if el.get("id") in ids:
                erros.append(f'id="{el.get("id")}" aparece mais de uma vez')
            ids[el.get("id")] = el
    if formas == 0:
        erros.append("o desenho não tem nenhuma forma")
    if formas > MAX_FORMAS:
        erros.append(f"o desenho tem {formas} formas e o máximo é {MAX_FORMAS}: simplifique")
    if formas and not tem_sombra:
        avisos.append('sem sombra no chão: falta <ellipse cx="200" cy="368" rx="120" ry="18" fill="url(#sombra)"/>')
    if animacao is None:
        erros.append("faltou dizer a animação (campo animacao)")
    elif animacao not in ANIMACOES:
        erros.append(f'animação desconhecida: "{animacao}" (use {", ".join(ANIMACOES)})')
    else:
        parte = ANIMACOES[animacao][0]
        if animacao == "aparecer":
            if passos == 0:
                erros.append('a animação "aparecer" precisa de partes com class="passo"')
            elif passos == 1:
                avisos.append('só uma parte com class="passo": "aparecer" serve para várias, uma a uma')
        elif parte not in ids:
            erros.append(f'a animação "{animacao}" precisa de uma parte com id="{parte}" no desenho')
        elif animacao == "tracar":
            tr = ids[parte]
            if _sem_ns(tr.tag) != "path" or tr.get("stroke") in (None, "none"):
                erros.append('para "tracar", o id="traco" deve estar num <path> com stroke (o traço que se desenha)')
        if parar and animacao != "girar":
            erros.append('"parar": true só vale com a animação "girar"')
    return list(dict.fromkeys(erros)), avisos


def ler_svg(pasta: Path, item: dict) -> str:
    """Lê o desenho de um elemento gerado. Só aceita arquivo dentro da pasta do trabalho ou do catálogo."""
    if not item.get("svg"):
        erro(f"o elemento {item['elemento']} não tem o campo svg (o arquivo do desenho)")
    arq = (pasta / item["svg"]).resolve()
    permitidas = (pasta.resolve(), PASTA_GERADOS.resolve())
    if not any(arq.is_relative_to(d) for d in permitidas):
        erro(f"o desenho {item['svg']} está fora da pasta do trabalho: guarde em elementos-gerados/")
    if not arq.exists():
        erro(f"não achei o desenho {item['svg']} do elemento {item['elemento']}")
    return arq.read_text(encoding="utf-8")


JS_CAIXA = """() => {
  const svg = document.querySelector('#elemento svg'), r0 = svg.getBoundingClientRect(), k = 400 / r0.width;
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  svg.querySelectorAll('path,circle,ellipse,rect,line,polyline,polygon').forEach(f => {
    if (f.closest('defs') || (f.getAttribute('fill') || '') === 'url(#sombra)') return;
    const r = f.getBoundingClientRect(); if (!r.width && !r.height) return;
    const st = f.getAttribute('stroke'), sw = st && st !== 'none' ? ((+f.getAttribute('stroke-width') || 1) / 2) : 0;
    x0 = Math.min(x0, (r.left - r0.left) * k - sw); y0 = Math.min(y0, (r.top - r0.top) * k - sw);
    x1 = Math.max(x1, (r.right - r0.left) * k + sw); y1 = Math.max(y1, (r.bottom - r0.top) * k + sw);
  });
  return [x0, y0, x1, y1];
}"""


def cfg_pagina(item: dict, w: int, h: int, svg: str | None, marca: dict) -> dict:
    cfg = {"elemento": item["elemento"], "modo": item["modo"], "largura": w, "altura": h,
           "duracao": item["duracao"], "texto": item.get("texto", ""), "cores": marca["cores"],
           "arroba": marca.get("arroba", "")}
    if svg is not None:
        cfg.update(svg=svg, animacao=item.get("animacao"), parar=bool(item.get("parar")))
    return cfg


def problema_de_margem(pagina) -> str | None:
    """Com o desenho já montado na página, confere se cabe na caixa com a margem de 30."""
    x0, y0, x1, y1 = pagina.evaluate(JS_CAIXA)
    lim0, lim1 = MARGEM - 1.5, 400 - MARGEM + 1.5
    if x0 < lim0 or y0 < lim0 or x1 > lim1 or y1 > lim1:
        return (f"o desenho passa da margem de {MARGEM}: ocupa de {x0:.0f} a {x1:.0f} na horizontal e de "
                f"{y0:.0f} a {y1:.0f} na vertical, e precisa ficar entre {MARGEM} e {400 - MARGEM} "
                f"(a sombra do chão não conta)")
    return None


def medir_margem(nav, svg: str, item: dict, marca: dict) -> str | None:
    molde = (PASTA_SKILL / "templates" / "elementos.html").resolve().as_uri()
    pagina = nav.new_page(viewport={"width": 432, "height": 432}, device_scale_factor=1)
    try:
        pagina.goto(molde)
        pagina.evaluate("document.fonts.ready")
        pagina.evaluate("cfg => montar(cfg)", cfg_pagina({**item, "modo": "sobreposto", "texto": ""}, 432, 432, svg, marca))
        return problema_de_margem(pagina)
    finally:
        pagina.close()


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
    svgs: dict[int, str] = {}
    for n, item in enumerate(itens):
        if eh_gerado(item):
            svgs[n] = ler_svg(pasta, item)
            erros, _ = validar_svg(svgs[n], item.get("animacao"), bool(item.get("parar")))
            if erros:
                erro(f"o desenho de {item['elemento']} não passou na validação (rode elementos.py validar): "
                     + "; ".join(erros))
        elif eh_cena(item):
            from cenas import TIPOS
            if item["elemento"].split(":", 1)[1] not in TIPOS:
                erro(f"cena desconhecida: {item['elemento']} (use {', '.join('cena:' + t for t in TIPOS)})")
        elif item["elemento"] not in ELEMENTOS:
            erro(f"elemento desconhecido: {item['elemento']} (use {', '.join(ELEMENTOS)}, gerado:nome ou cena:tipo)")
        aviso_pos = resolver_posicao(item, largura, altura, rostos, camera)
        if aviso_pos:
            aviso(f"atenção: {aviso_pos}")
        destino = pasta_do_item(pasta, n, item, largura, altura, fps, svgs.get(n))
        total = max(1, math.ceil(item["duracao"] * float(fps)))
        item["quadros"] = str(destino)
        item["video"] = str(destino / "elemento.mov")
        item["x"], item["y"] = posicao_quadro(item, largura, altura)
        if not (destino / "elemento.mov").exists():
            pendentes.append((n, item, destino, total))
    if pendentes:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            erro("playwright não está instalado. Rode: pip install -r scripts/requirements.txt")
        with sync_playwright() as p:
            nav = abrir_navegador(p)
            for n, item, destino, total in pendentes:
                w, h = tamanho_quadro(item, largura, altura)
                if destino.exists():
                    shutil.rmtree(destino)
                pagina = nav.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
                if eh_cena(item):
                    from cenas import cfg_da_cena
                    pagina.goto((PASTA_SKILL / "templates" / "cenas.html").resolve().as_uri())
                    pagina.evaluate("document.fonts.ready")
                    resultado = pagina.evaluate("cfg => montar(cfg)", cfg_da_cena(item, w, h, marca))
                    if resultado.get("estoura"):
                        erro(f"o texto da {item['elemento']} em {item['inicio']:.1f} s não cabe no painel: encurte os textos")
                else:
                    pagina.goto(molde)
                    pagina.evaluate("document.fonts.ready")
                    pagina.evaluate("cfg => montar(cfg)", cfg_pagina(item, w, h, svgs.get(n), marca))
                pagina.evaluate("document.fonts.ready")
                if n in svgs:
                    problema = problema_de_margem(pagina)
                    if problema:
                        erro(f"o desenho de {item['elemento']}: {problema}")
                destino.mkdir(parents=True)
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



# ---------- validar, prévia e promover ----------

def validar_itens(pasta: Path | None, arquivo: Path | None, animacao: str | None, parar: bool) -> int:
    """Valida os elementos gerados do elementos.json (ou um arquivo avulso). Devolve quantos têm erro."""
    marca = ler_json(PASTA_SKILL / "marca.json")
    alvos: list[tuple[str, str, dict]] = []
    if arquivo:
        item = {"elemento": f"gerado:{arquivo.stem}", "animacao": animacao, "parar": parar, "modo": "sobreposto",
                "duracao": 2.0}
        alvos.append((arquivo.name, arquivo.read_text(encoding="utf-8"), item))
    else:
        arq = pasta / "elementos.json"
        if not arq.exists():
            erro("não há elementos.json: rode elementos.py sugerir antes")
        for item in ler_json(arq).get("itens", []):
            if eh_gerado(item):
                alvos.append((item["elemento"], ler_svg(pasta, item), item))
    if not alvos:
        print("nenhum elemento gerado para validar (os 12 prontos não precisam)")
        return 0
    ruins = 0
    medidas = []
    for nome, svg, item in alvos:
        erros, avisos = validar_svg(svg, item.get("animacao"), bool(item.get("parar")))
        medidas.append((nome, svg, item, erros, avisos))
    ok_estaticos = [m for m in medidas if not m[3]]
    margens: dict[str, str | None] = {}
    if ok_estaticos:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            nav = abrir_navegador(pw)
            for nome, svg, item, _, _ in ok_estaticos:
                margens[nome] = medir_margem(nav, svg, item, marca)
            nav.close()
    for nome, svg, item, erros, avisos in medidas:
        if margens.get(nome):
            erros = erros + [margens[nome]]
        if erros:
            ruins += 1
            print(f"FALHOU  {nome}")
            for e in erros:
                print(f"          {e}")
        else:
            print(f"ok      {nome}  (animação {item.get('animacao')})")
        for a in avisos:
            print(f"          aviso: {a}")
    return ruins


def quadro_do_video(pasta: Path, cortes: dict, insp: list, fps, largura: int, altura: int, te: float,
                    destino: Path) -> bool:
    """Um quadro do vídeo no instante te do vídeo editado (já no tamanho da saída, reduzido a 432 de largura)."""
    for tr in trechos_no_quadro(cortes, fps):
        if tr["saida_inicio"] <= te < tr["saida_fim"] + 1e-6:
            v = insp[tr["video"]]
            orig = tr["inicio_exato"] + (te - tr["saida_inicio"])
            cor = ""
            if v.get("hdr"):
                cor = (f"zscale=tin={v['cor']['transferencia']}:pin=bt2020:min=bt2020nc:t=linear:npl=100,"
                       "format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,")
            filtro = (f"{cor}scale={largura}:{altura}:force_original_aspect_ratio=increase,"
                      f"crop={largura}:{altura},scale=432:-2")
            r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{orig:.3f}", "-i", v["arquivo"],
                                "-frames:v", "1", "-vf", filtro, "-q:v", "3", str(destino)])
            return r.returncode == 0 and destino.exists()
    return False


def previa(pasta: Path, largura: int, altura: int, fps) -> Path:
    """Folha elementos-previa.jpg: cada elemento aos 0,2 s, 0,6 s e 1,4 s, sobre o fundo da marca e sobre o vídeo."""
    arq = pasta / "elementos.json"
    if not arq.exists():
        erro("não há elementos.json: rode elementos.py sugerir antes")
    itens = [i for i in ler_json(arq).get("itens", []) if not eh_cena(i)]   # cenas: cenas.py previa
    if not itens:
        erro("o elementos.json está vazio (as cenas têm a prévia em cenas.py previa)")
    marca = ler_json(PASTA_SKILL / "marca.json")
    cores = marca["cores"]
    cortes = ler_json(pasta / "cortes.json")
    insp = ler_json(pasta / "inspecao.json")["videos"]
    from camera import Camera
    from rosto import Rostos
    rostos = Rostos.carregar(pasta, largura, altura)
    camera = Camera.carregar(pasta, largura, altura)
    molde = (PASTA_SKILL / "templates" / "elementos.html").resolve().as_uri()
    fonte = (PASTA_SKILL / "assets" / "fontes" / "Sora-ExtraBold.ttf").resolve().as_uri()
    tmp = pasta / "previa-tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    atexit.register(shutil.rmtree, tmp, True)      # some mesmo se algo der errado no meio
    linhas = []
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        nav = abrir_navegador(pw)
        for n, item in enumerate(itens):
            svg = None
            if eh_gerado(item):
                svg = ler_svg(pasta, item)
                erros, _ = validar_svg(svg, item.get("animacao"), bool(item.get("parar")))
                if erros:
                    erro(f"o desenho de {item['elemento']} não passou na validação: " + "; ".join(erros))
            elif item["elemento"] not in ELEMENTOS:
                erro(f"elemento desconhecido: {item['elemento']}")
            aviso_pos = resolver_posicao(item, largura, altura, rostos, camera)
            if aviso_pos:
                aviso(f"atenção: {aviso_pos}")
            w, h = tamanho_quadro(item, largura, altura)
            x, y = posicao_quadro(item, largura, altura)
            instantes = sorted({round(min(t, max(0.3, item["duracao"] - 0.4)), 2) for t in (0.2, 0.6, 1.4)})
            pagina = nav.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            pagina.goto(molde)
            pagina.evaluate("document.fonts.ready")
            pagina.evaluate("cfg => montar(cfg)", cfg_pagina(item, w, h, svg, marca))
            pagina.evaluate("document.fonts.ready")
            celulas = []
            for k, t in enumerate(instantes):
                pagina.evaluate(f"desenhar({t})")
                png = pagina.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": w, "height": h})
                jpg = tmp / f"q{n}_{k}.jpg"
                tem_quadro = quadro_do_video(pasta, cortes, insp, fps, largura, altura, item["inicio"] + t, jpg)
                celulas.append({"t": t, "png": base64.b64encode(png).decode(),
                                "jpg": base64.b64encode(jpg.read_bytes()).decode() if tem_quadro else None})
            pagina.close()
            linhas.append({"n": n, "item": item, "w": w, "h": h, "x": x, "y": y, "celulas": celulas})
        nav.close()

    def esc(t: str) -> str:
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    corpo = []
    for ln in linhas:
        it = ln["item"]
        novo = eh_gerado(it)
        nome = it["elemento"].split(":", 1)[-1]
        info = [f'<div class="nome">{esc(nome)}{" <span class=novo>novo</span>" if novo else ""}</div>',
                f'<div class="tempo">{tempo(it["inicio"])} no vídeo · {it["duracao"]:.1f} s</div>']
        if it.get("ideia"):
            info.append(f'<div class="ideia">{esc(it["ideia"])}</div>')
        info.append(f'<div class="peq">fala: “{esc(it.get("gatilho", ""))}”</div>')
        if novo:
            info.append(f'<div class="peq">animação: {esc(it.get("animacao", ""))}</div>')
        if it.get("texto"):
            info.append(f'<div class="peq">rótulo: {esc(it["texto"])}</div>')
        escuras = "".join(f'<div class="cel escura"><img src="data:image/png;base64,{c["png"]}"><span>{c["t"]:.1f} s</span></div>'
                          for c in ln["celulas"])
        quadros = "".join(
            '<div class="cel quadro"' + (f' style="background-image:url(data:image/jpeg;base64,{c["jpg"]})"' if c["jpg"] else "") + '>'
            f'<img class="el" style="left:{ln["x"] / largura * 100:.2f}%;top:{ln["y"] / altura * 100:.2f}%;'
            f'width:{ln["w"] / largura * 100:.2f}%;height:{ln["h"] / altura * 100:.2f}%" src="data:image/png;base64,{c["png"]}">'
            f'<span>{c["t"]:.1f} s</span></div>' for c in ln["celulas"])
        corpo.append(f'<div class="linha"><div class="info">{"".join(info)}</div>{escuras}{quadros}</div>')
    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><style>
@font-face {{ font-family: "Sora ExtraBold"; src: url("{fonte}"); }}
body {{ margin: 0; padding: 24px; background: {cores['fundo_profundo']}; color: {cores['texto']};
        font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; width: max-content; }}
h1 {{ font: 22px "Sora ExtraBold"; margin: 0 0 4px; }}
.sub {{ color: {cores['rotulo']}; font-size: 14px; margin-bottom: 18px; }}
.linha {{ display: flex; gap: 10px; align-items: center; margin-bottom: 14px; padding-bottom: 14px;
          border-bottom: 1px solid #ffffff1a; }}
.info {{ width: 290px; flex: none; }}
.nome {{ font: 24px "Sora ExtraBold"; }}
.novo {{ font: 12px -apple-system, Arial; background: {cores['destaque']}; color: {cores['fundo_profundo']};
         padding: 2px 8px; border-radius: 9px; vertical-align: middle; font-weight: 700; }}
.tempo {{ margin: 4px 0; color: {cores['destaque']}; font-size: 15px; }}
.ideia {{ font-size: 16px; margin: 4px 0; }}
.peq {{ font-size: 13px; color: {cores['rotulo']}; margin-top: 2px; }}
.cel {{ position: relative; flex: none; overflow: hidden; border-radius: 10px; }}
.cel span {{ position: absolute; left: 6px; bottom: 4px; font-size: 12px; color: #fff; text-shadow: 0 1px 3px #000; }}
.escura {{ width: 270px; height: 384px; background: radial-gradient(120% 80% at 50% 30%, {cores['fundo']}, {cores['fundo_profundo']});
           display: flex; align-items: center; justify-content: center; }}
.escura img {{ max-width: 100%; max-height: 100%; }}
.quadro {{ width: 216px; height: 384px; background: #333 center/cover; }}
.quadro .el {{ position: absolute; }}
</style></head><body>
<h1>Prévia dos elementos 3D</h1>
<div class="sub">Cada elemento aos 0,2 s, 0,6 s e 1,4 s: à esquerda sobre o fundo da marca, à direita sobre o próprio vídeo. Tempos no vídeo editado.</div>
{"".join(corpo)}</body></html>"""
    pagina_html = pasta / "previa-tmp" / "previa.html"
    pagina_html.write_text(html, encoding="utf-8")
    saida = pasta / "elementos-previa.jpg"
    with sync_playwright() as pw:
        nav = abrir_navegador(pw)
        pg = nav.new_page(viewport={"width": 1900, "height": 600}, device_scale_factor=1)
        pg.goto(pagina_html.resolve().as_uri())
        pg.evaluate("document.fonts.ready")
        pg.screenshot(path=str(saida), type="jpeg", quality=92, full_page=True)
        nav.close()
    shutil.rmtree(tmp, ignore_errors=True)
    return saida


def promover(pasta: Path, nome: str, palavras: list[str] | None) -> dict:
    """Guarda um elemento gerado e aprovado no catálogo (templates/gerados/)."""
    if not re.fullmatch(r"[a-z][a-z0-9-]*", nome):
        erro("o nome do elemento deve ter só letras minúsculas sem acento, números e hífen (ex.: bussola)")
    arq = pasta / "elementos.json"
    if not arq.exists():
        erro("não há elementos.json nessa pasta")
    item = next((i for i in ler_json(arq).get("itens", []) if i.get("elemento") == f"gerado:{nome}"), None)
    if not item:
        erro(f"não há elemento gerado:{nome} no elementos.json")
    svg = ler_svg(pasta, item)
    erros, _ = validar_svg(svg, item.get("animacao"), bool(item.get("parar")))
    if erros:
        erro("o desenho não passou na validação: " + "; ".join(erros))
    if not palavras:
        palavras = []
        for w in re.findall(r"\w+", item.get("gatilho", "")):
            n = normalizar(w)
            if len(n) >= 4:
                palavras.append(n[:max(4, len(n) - 2)])
    palavras = [normalizar(p) for p in palavras if normalizar(p)]
    if not palavras:
        erro("diga as palavras que chamam o elemento: --palavras \"bussol,rumo\" (começo da palavra, sem acento)")
    for p in palavras:
        for prefixo, pronto in GATILHOS:
            if " " not in prefixo and (p.startswith(prefixo) or prefixo.startswith(p)):
                aviso(f'a palavra "{p}" também chama o elemento pronto {pronto}: no catálogo, o gerado vale primeiro')
                break
    som = ler_json(PASTA_SKILL / "assets" / "sons" / "sons.json").get("por_animacao", {}).get(item.get("animacao"))
    PASTA_GERADOS.mkdir(parents=True, exist_ok=True)
    (PASTA_GERADOS / f"{nome}.svg").write_text(svg, encoding="utf-8")
    caminho = PASTA_GERADOS / "catalogo.json"
    cat = ler_json(caminho) if caminho.exists() else {"elementos": []}
    entrada = {"nome": nome, "svg": f"{nome}.svg", "animacao": item["animacao"],
               **({"parar": True} if item.get("parar") else {}), "ideia": item.get("ideia", ""),
               "palavras": palavras, "som": som}
    cat["elementos"] = [e for e in cat.get("elementos", []) if e.get("nome") != nome] + [entrada]
    salvar_json(caminho, cat)
    return entrada


def palavras_saida(pasta: Path) -> list[dict]:
    from legendas import palavras_no_corte
    insp = ler_json(pasta / "inspecao.json")["videos"][0]
    return palavras_no_corte(pasta, ler_json(pasta / "cortes.json"), fps_racional({"avg_frame_rate": insp["fps"]}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["sugerir", "desenhar", "validar", "previa", "promover"])
    ap.add_argument("nome", nargs="?", help="promover: o nome do elemento gerado (ex.: bussola)")
    ap.add_argument("--pasta", type=Path)
    ap.add_argument("--arquivo", type=Path, help="validar: um desenho avulso (.svg) em vez do elementos.json")
    ap.add_argument("--animacao", help="validar --arquivo: a animação que o desenho vai usar")
    ap.add_argument("--parar", action="store_true", help="validar --arquivo: com girar, vai de -25° a 0° e para")
    ap.add_argument("--palavras", help="promover: começo das palavras que chamam o elemento, separadas por vírgula")
    ap.add_argument("--modo", choices=["sobreposto", "tela"], default="sobreposto")
    ap.add_argument("--intervalo", type=float, default=6.0, help="segundos mínimos entre um elemento e outro")
    ap.add_argument("--formato", default="original")
    a = ap.parse_args()
    if a.acao == "validar" and a.arquivo:
        sys.exit(1 if validar_itens(None, a.arquivo.resolve(), a.animacao, a.parar) else 0)
    if not a.pasta:
        erro("informe --pasta")
    pasta = a.pasta.resolve()

    if a.acao == "validar":
        ruins = validar_itens(pasta, None, None, False)
        if ruins:
            erro(f"{ruins} elemento(s) gerado(s) com problema: corrija o desenho e rode de novo", 1)
        return
    if a.acao in ("previa", "promover"):
        if a.acao == "promover":
            if not a.nome:
                erro("diga o nome do elemento: elementos.py promover bussola --pasta ...")
            e = promover(pasta, a.nome, [p.strip() for p in a.palavras.split(",")] if a.palavras else None)
            print(f"ok  {e['nome']} está no catálogo (templates/gerados/): animação {e['animacao']}, "
                  f"chamado por: {', '.join(e['palavras'])}, som {e['som']}")
            return
        from comum import dimensoes_saida
        insp = ler_json(pasta / "inspecao.json")["videos"][0]
        largura, altura = dimensoes_saida(insp["largura"], insp["altura"], a.formato)
        saida = previa(pasta, largura, altura, fps_racional({"avg_frame_rate": insp["fps"]}))
        print(f"ok  {saida}")
        return

    if a.acao == "sugerir":
        if not (pasta / "cortes.json").exists():
            erro("rode propor_cortes.py antes")
        palavras = palavras_saida(pasta)
        if not palavras:
            erro("não há fala no corte")
        cortes = ler_json(pasta / "cortes.json")
        itens = sugerir(palavras, cortes["duracao_final"], a.modo, a.intervalo, carregar_catalogo())
        for it in itens:      # elemento do catálogo: o desenho vem para a pasta do trabalho
            if it.get("svg"):
                copia = pasta / it["svg"]
                copia.parent.mkdir(parents=True, exist_ok=True)
                if not copia.exists():
                    shutil.copy(PASTA_GERADOS / Path(it["svg"]).name, copia)
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
