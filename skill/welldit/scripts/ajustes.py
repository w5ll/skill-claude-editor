"""Ajustes de elementos, zoom, som e conferência: a lógica por trás das telas do painel (sem servidor).

Cada função mexe no mesmo arquivo que a conversa edita à mão (elementos.json, camera.json, som.json, cortes.json),
com limites e valores de uma lista. Cada mudança guarda o arquivo anterior em revisao/ (desfazer), como na Fase 6.
Um pedido recusado não mexe em nada e não deixa histórico.

Veja docs/fase-7-ajustes-no-painel.md.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import shutil
import subprocess
import threading
from pathlib import Path

from comum import (PASTA_SKILL, assinatura_da_marca, assinatura_dos_cortes, carregar_marca, dimensoes_saida, fps_racional,
                   ler_json, salvar_json_atomico, tempo)
from revisao import Recusado, desfazer, guardar, historico

PASTA_SONS = PASTA_SKILL / "assets" / "sons"
POSICOES = ["auto", "topo", "esquerda", "direita", "meio"]
MODOS = ["sobreposto", "tela"]
DURACAO_MIN, DURACAO_MAX, DURACAO_TELA_MAX = 1.0, 4.0, 3.0
MAX_ROTULO = 40
GANHO_EFEITO = (-12.0, 6.0)
GANHO_TRECHO = (-12.0, 12.0)
MUSICA_ABAIXO = (10.0, 30.0)
MUSICA_SOBE = (0.0, 12.0)
SEGUNDOS_DA_MUSICA = 30
NIVEIS_DE_ZOOM = ["aberto", "perto", "enfase"]
_TRAVA_PREVIA = threading.Lock()         # uma prévia por vez: cada uma abre um navegador


def _numero(v, nome: str, minimo: float, maximo: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise Recusado(f"{nome}: use um número")
    if not minimo <= v <= maximo:
        raise Recusado(f"{nome}: de {minimo:g} a {maximo:g}")
    return round(float(v), 3)


# ---------- elementos ----------

def _el():
    import elementos        # fica de fora do topo: o módulo é grande e só a tela de elementos usa
    return elementos


def tipo_do_item(item: dict) -> str:
    e = _el()
    return "imagem" if e.eh_imagem(item) else "cena" if e.eh_cena(item) else "gerado" if e.eh_gerado(item) else "pronto"


def id_do_item(item: dict) -> str:
    return f"{item['elemento']}@{float(item['inicio']):.3f}"


def _itens(pasta: Path) -> list[dict]:
    arq = pasta / "elementos.json"
    if not arq.exists():
        raise Recusado("os elementos ainda não foram sugeridos")
    return ler_json(arq).get("itens", [])


def _achar(itens: list[dict], id_: str) -> int:
    for k, it in enumerate(itens):
        if id_do_item(it) == id_:
            return k
    raise Recusado("esse elemento não está mais na lista: atualize a tela")


def _catalogo() -> dict[str, dict]:
    return {e["nome"]: e for e in _el().carregar_catalogo()}


def _problema_do_desenho(pasta: Path, item: dict) -> str | None:
    e = _el()
    try:
        erros, _ = e.validar_svg(e.ler_svg(pasta, item), item.get("animacao"), bool(item.get("parar")))
    except SystemExit:               # ler_svg avisa com erro(): o desenho sumiu ou está fora da pasta
        return "o arquivo do desenho não foi encontrado"
    return erros[0] if erros else None


def painel_de_elementos(pasta: Path) -> dict:
    e = _el()
    itens = _itens(pasta)
    cortes = ler_json(pasta / "cortes.json") if (pasta / "cortes.json").exists() else {}
    cat = _catalogo()
    saida = []
    for k, it in enumerate(itens):
        tipo = tipo_do_item(it)
        nome = it["elemento"].split(":", 1)[-1]
        saida.append({"id": id_do_item(it), "indice": k, "tipo": tipo, "elemento": it["elemento"], "nome": nome,
                      "inicio": it["inicio"], "duracao": it["duracao"], "modo": it.get("modo", "sobreposto"),
                      "posicao": it.get("posicao", "auto"), "texto": it.get("texto", ""), "gatilho": it.get("gatilho", ""),
                      "ideia": it.get("ideia", ""), "animacao": it.get("animacao"),
                      "problema": _problema_do_desenho(pasta, it) if tipo == "gerado" else None,
                      "no_catalogo": tipo == "gerado" and nome in cat,
                      "previa": tipo != "cena", "editavel": tipo in ("pronto", "gerado")})
    return {"itens": saida, "desfazer": len(historico(pasta, "elementos")), "prontos": list(e.ELEMENTOS),
            "catalogo": [{"nome": n, "ideia": c.get("ideia", "")} for n, c in cat.items()],
            "posicoes": POSICOES, "modos": MODOS, "duracao_final": cortes.get("duracao_final"),
            "duracao": [DURACAO_MIN, DURACAO_MAX], "duracao_tela": [DURACAO_MIN, DURACAO_TELA_MAX], "max_rotulo": MAX_ROTULO}


def _mudar_elementos(pasta: Path, funcao):
    """Aplica `funcao(itens)` numa cópia; só se nada for recusado é que guarda o anterior e grava."""
    arq = pasta / "elementos.json"
    dados = copy.deepcopy(ler_json(arq)) if arq.exists() else None
    if dados is None:
        raise Recusado("os elementos ainda não foram sugeridos")
    itens = dados.setdefault("itens", [])
    funcao(itens)
    dados["itens"] = sorted(itens, key=lambda i: i["inicio"])
    guardar(pasta, "elementos", arq)
    salvar_json_atomico(arq, dados)


def _sem_choque(itens: list[dict], inicio: float, duracao: float, ignorar: int | None, total: float | None):
    if total is not None and inicio + duracao > total + 1e-6:
        raise Recusado(f"o elemento passaria do fim do vídeo ({tempo(total)})")
    for k, it in enumerate(itens):
        if k != ignorar and inicio < it["inicio"] + it["duracao"] and it["inicio"] < inicio + duracao:
            raise Recusado(f"choca com outro elemento em {tempo(it['inicio'])}: dois elementos não ficam juntos na tela")


def _total(pasta: Path) -> float | None:
    arq = pasta / "cortes.json"
    return float(ler_json(arq).get("duracao_final") or 0) or None if arq.exists() else None


def _campos_do_elemento(pasta: Path, elemento) -> dict:
    """Os campos que mudam quando o item é de um elemento pronto ou do catálogo (o resto do item fica)."""
    e = _el()
    if not isinstance(elemento, str):
        raise Recusado("escolha um elemento")
    if elemento in e.ELEMENTOS:
        return {"elemento": elemento}
    if elemento.startswith("gerado:"):
        ent = _catalogo().get(elemento.split(":", 1)[1])
        if ent is None:
            raise Recusado("esse elemento não está no catálogo")
        destino = pasta / "elementos-gerados" / f"{ent['nome']}.svg"
        if not destino.exists():
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(e.PASTA_GERADOS / ent["svg"], destino)
        return {"elemento": elemento, "svg": f"elementos-gerados/{ent['nome']}.svg", "animacao": ent["animacao"],
                **({"parar": True} if ent.get("parar") else {}), "ideia": ent.get("ideia", "")}
    raise Recusado("escolha um dos elementos prontos ou do catálogo")


def tirar_elemento(pasta: Path, id_: str):
    def f(itens):
        del itens[_achar(itens, id_)]
    _mudar_elementos(pasta, f)


def trocar_elemento(pasta: Path, id_: str, elemento):
    novos = _campos_do_elemento(pasta, elemento)

    def f(itens):
        k = _achar(itens, id_)
        if tipo_do_item(itens[k]) not in ("pronto", "gerado"):
            raise Recusado("cena e imagem de apoio não trocam de elemento: tire e adicione outro")
        for chave in ("svg", "animacao", "parar", "ideia", "som"):
            itens[k].pop(chave, None)
        itens[k].update(novos)
    _mudar_elementos(pasta, f)


def mudar_rotulo(pasta: Path, id_: str, texto):
    if not isinstance(texto, str) or len(texto.strip()) > MAX_ROTULO or re.search(r"[<>\x00-\x1f]", texto):
        raise Recusado(f"o rótulo tem no máximo {MAX_ROTULO} letras, sem < nem >")

    def f(itens):
        k = _achar(itens, id_)
        if tipo_do_item(itens[k]) not in ("pronto", "gerado"):
            raise Recusado("o texto de cena e de imagem de apoio vem da fala: tire ou troque de momento")
        itens[k]["texto"] = texto.strip()
    _mudar_elementos(pasta, f)


def mudar_tempo(pasta: Path, id_: str, inicio, duracao):
    inicio = _numero(inicio, "momento", 0, 36000)
    total = _total(pasta)

    def f(itens):
        k = _achar(itens, id_)
        it = itens[k]
        maxima = DURACAO_TELA_MAX if it.get("modo") == "tela" else DURACAO_MAX
        d = _numero(duracao, "duração", DURACAO_MIN, maxima)
        _sem_choque(itens, inicio, d, k, total)
        it["inicio"], it["duracao"] = inicio, d
    _mudar_elementos(pasta, f)


def mudar_modo(pasta: Path, id_: str, modo, posicao=None):
    if modo not in MODOS:
        raise Recusado("modo: sobreposto ou tela")
    if posicao is not None and posicao not in POSICOES:
        raise Recusado(f"posição: {', '.join(POSICOES)}")
    total = _total(pasta)

    def f(itens):
        k = _achar(itens, id_)
        it = itens[k]
        if tipo_do_item(it) == "cena":
            raise Recusado("a cena não muda de modo")
        d = min(it["duracao"], DURACAO_TELA_MAX) if modo == "tela" else it["duracao"]
        _sem_choque(itens, it["inicio"], d, k, total)
        it["modo"], it["duracao"] = modo, d
        if posicao is not None:
            it["posicao"] = posicao
    _mudar_elementos(pasta, f)


def adicionar_elemento(pasta: Path, elemento, inicio, modo="sobreposto"):
    campos = _campos_do_elemento(pasta, elemento)
    if modo not in MODOS:
        raise Recusado("modo: sobreposto ou tela")
    inicio = _numero(inicio, "momento", 0, 36000)
    duracao = 1.8 if modo == "tela" else 2.0
    total = _total(pasta)

    def f(itens):
        _sem_choque(itens, inicio, duracao, None, total)
        itens.append({**campos, "inicio": inicio, "duracao": duracao, "modo": modo, "posicao": "auto", "texto": "",
                      "gatilho": "adicionado na tela", "fala_em": inicio})
    _mudar_elementos(pasta, f)


def desfazer_elementos(pasta: Path) -> bool:
    return desfazer(pasta, "elementos", pasta / "elementos.json")


def promover_elemento(pasta: Path, id_: str, palavras) -> dict:
    e = _el()
    itens = _itens(pasta)
    it = itens[_achar(itens, id_)]
    if tipo_do_item(it) != "gerado":
        raise Recusado("só um elemento desenhado na hora vai para o catálogo")
    nome = it["elemento"].split(":", 1)[1]
    if not re.fullmatch(r"[a-z][a-z0-9-]*", nome):
        raise Recusado("o nome do elemento deve ter só letras minúsculas sem acento, números e hífen")
    if _problema_do_desenho(pasta, it):
        raise Recusado("o desenho não passou na validação: " + str(_problema_do_desenho(pasta, it)))
    if not isinstance(palavras, list) or not 1 <= len(palavras) <= 8 or not all(
            isinstance(p, str) and re.fullmatch(r"[A-Za-zÀ-ÿ0-9-]{3,24}", p.strip()) for p in palavras):
        raise Recusado("diga de 1 a 8 palavras (de 3 a 24 letras, sem espaço) que chamam o elemento")
    try:
        return e.promover(pasta, nome, [p.strip() for p in palavras])
    except SystemExit:
        raise Recusado("não consegui guardar no catálogo: veja se o desenho e as palavras estão certos") from None


def _dimensoes(pasta: Path, formato: str) -> tuple[int, int, object]:
    insp = ler_json(pasta / "inspecao.json")["videos"][0]
    largura, altura = dimensoes_saida(insp["largura"], insp["altura"], formato or "original")
    return largura, altura, fps_racional({"avg_frame_rate": insp["fps"]})


def _chave_de_cache(pasta: Path, *partes) -> str:
    arqs = []
    for nome in ("cortes.json", "rosto.json", "camera.json"):
        f = pasta / nome
        arqs.append(hashlib.sha1(f.read_bytes()).hexdigest()[:10] if f.exists() else "-")
    base = json.dumps([partes, arqs, assinatura_da_marca(carregar_marca(pasta=pasta))], sort_keys=True, default=str)
    return hashlib.sha1(base.encode()).hexdigest()[:16]


def previa_do_elemento(pasta: Path, id_: str, formato: str, pasta_cache: Path) -> Path:
    """A prévia de um elemento (o mesmo desenho da folha elementos-previa.jpg), guardada para não refazer."""
    itens = _itens(pasta)
    k = _achar(itens, id_)
    if tipo_do_item(itens[k]) == "cena":
        raise Recusado("a cena tem a prévia em cenas.py previa")
    destino = pasta_cache / f"{_chave_de_cache(pasta, itens[k], formato)}.jpg"
    if destino.exists():
        return destino
    largura, altura, fps = _dimensoes(pasta, formato)
    pasta_cache.mkdir(parents=True, exist_ok=True)
    with _TRAVA_PREVIA:
        if destino.exists():
            return destino
        try:
            _el().previa(pasta, largura, altura, fps, indices=[k], saida=destino, compacta=True)
        except SystemExit:
            raise Recusado("não consegui montar a prévia desse elemento (veja se o desenho passa na validação)") from None
    return destino


# ---------- zoom ----------

def _camera(pasta: Path) -> dict:
    arq = pasta / "camera.json"
    if not arq.exists():
        raise Recusado("o zoom ainda não foi planejado (ou está desligado)")
    return ler_json(arq)


def _nivel_do_bloco(zoom: float, niveis: tuple) -> str:
    for nome, z in zip(NIVEIS_DE_ZOOM, niveis):
        if abs(float(zoom) - z) < 1e-3:
            return nome
    return "outro"


def painel_de_zoom(pasta: Path) -> dict:
    from camera import INTENSIDADES
    if not (pasta / "camera.json").exists():
        return {"planejado": False, "intensidade": None, "niveis": {}, "blocos": [], "desfazer": 0, "duracao": None}
    dados = _camera(pasta)
    inten = dados.get("intensidade", "normal")
    niveis = INTENSIDADES.get(inten, INTENSIDADES["normal"])
    blocos = [{"indice": k, "inicio": b["inicio"], "fim": b["fim"], "zoom": b["zoom"], "motivo": b.get("motivo", ""),
               "nivel": _nivel_do_bloco(b["zoom"], niveis), "enfase": str(b.get("motivo", "")).startswith("ênfase")}
              for k, b in enumerate(dados["blocos"])]
    return {"planejado": True, "intensidade": inten, "niveis": dict(zip(NIVEIS_DE_ZOOM, niveis)), "blocos": blocos,
            "desfazer": len(historico(pasta, "camera")), "duracao": dados.get("duracao")}


def _zoom_constante_nos_elementos(pasta: Path, blocos: list[dict], a: float, b: float):
    from camera import janelas_ocupadas
    for ja, jb in janelas_ocupadas(pasta):
        if jb <= a or ja >= b:
            continue
        if len({round(float(x["zoom"]), 4) for x in blocos if x["inicio"] < jb and x["fim"] > ja}) > 1:
            raise Recusado(f"o zoom mudaria com um elemento 3D na tela (em {tempo(ja + 0.05)}): "
                           "mexa no elemento primeiro, ou escolha o mesmo nível do bloco ao lado")


def _mudar_bloco(pasta: Path, indice, zoom_de, motivo: str):
    from camera import INTENSIDADES
    dados = copy.deepcopy(_camera(pasta))
    blocos = dados["blocos"]
    if isinstance(indice, bool) or not isinstance(indice, int) or not 0 <= indice < len(blocos):
        raise Recusado("esse bloco de zoom não existe: atualize a tela")
    niveis = INTENSIDADES.get(dados.get("intensidade", "normal"), INTENSIDADES["normal"])
    b = blocos[indice]
    novo = zoom_de(blocos, indice, niveis)
    if abs(float(b["zoom"]) - novo) < 1e-6:
        raise Recusado("o bloco já está nesse nível")
    b["zoom"], b["motivo"] = novo, motivo
    _zoom_constante_nos_elementos(pasta, blocos, b["inicio"], b["fim"])
    guardar(pasta, "camera", pasta / "camera.json")
    salvar_json_atomico(pasta / "camera.json", dados)


def definir_nivel_do_zoom(pasta: Path, indice, nivel):
    if nivel not in NIVEIS_DE_ZOOM:
        raise Recusado(f"nível: {', '.join(NIVEIS_DE_ZOOM)}")
    _mudar_bloco(pasta, indice, lambda bl, i, niveis: niveis[NIVEIS_DE_ZOOM.index(nivel)], f"manual: {nivel}")


def tirar_enfase(pasta: Path, indice):
    def vizinho(blocos, i, niveis):
        if not str(blocos[i].get("motivo", "")).startswith("ênfase"):
            raise Recusado("esse bloco não é uma aproximação de ênfase")
        outro = blocos[i - 1] if i > 0 else blocos[i + 1] if i + 1 < len(blocos) else None
        return float(outro["zoom"]) if outro is not None else niveis[0]
    _mudar_bloco(pasta, indice, vizinho, "frase (sem ênfase)")


def desfazer_zoom(pasta: Path) -> bool:
    return desfazer(pasta, "camera", pasta / "camera.json")


def previa_do_zoom(pasta: Path, indice, formato: str, pasta_cache: Path) -> Path:
    """Um quadro do vídeo no meio do bloco, já com o zoom e o ponto fixo que o render usa."""
    from camera import Camera
    from elementos import quadro_do_video
    dados = _camera(pasta)
    if isinstance(indice, bool) or not isinstance(indice, int) or not 0 <= indice < len(dados["blocos"]):
        raise Recusado("esse bloco de zoom não existe")
    b = dados["blocos"][indice]
    destino = pasta_cache / f"{_chave_de_cache(pasta, b, formato)}.jpg"
    if destino.exists():
        return destino
    largura, altura, fps = _dimensoes(pasta, formato)
    cortes = ler_json(pasta / "cortes.json")
    insp = ler_json(pasta / "inspecao.json")["videos"]
    pasta_cache.mkdir(parents=True, exist_ok=True)
    bruto = destino.with_suffix(".bruto.jpg")
    meio = (b["inicio"] + b["fim"]) / 2
    if not quadro_do_video(pasta, cortes, insp, fps, largura, altura, meio, bruto):
        raise Recusado("não consegui tirar um quadro do vídeo nesse momento")
    z, x0, y0 = Camera.carregar(pasta, largura, altura).transformar(meio)
    k = 432 / largura                                     # o quadro vem reduzido para 432 de largura
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(bruto), "-vf",
                        f"crop=iw/{z:.4f}:ih/{z:.4f}:{x0 * k:.2f}:{y0 * k:.2f},scale=432:-2", "-q:v", "3", str(destino)],
                       capture_output=True)
    if r.returncode != 0 or not destino.exists():
        raise Recusado("não consegui montar a prévia do zoom")
    bruto.unlink(missing_ok=True)
    return destino


# ---------- som ----------

def _catalogo_de_sons() -> dict:
    return ler_json(PASTA_SONS / "sons.json")


def _plano_de_som(pasta: Path) -> dict:
    arq = pasta / "som.json"
    if not arq.exists():
        raise Recusado("o som ainda não foi planejado (ou está desligado)")
    return ler_json(arq)


def painel_de_som(pasta: Path) -> dict:
    cat = _catalogo_de_sons()
    plano = ler_json(pasta / "som.json") if (pasta / "som.json").exists() else {"musica": None, "efeitos": []}
    m = plano.get("musica")
    atual = None
    if m:
        nome = next((n for n, x in cat["musicas"].items() if x["arquivo"] == m["arquivo"]), None)
        atual = {"nome": nome or "arquivo da pessoa", "abaixo_da_voz_db": m["abaixo_da_voz_db"],
                 "sobe_na_pausa_db": m["sobe_na_pausa_db"]}
    efeitos = [{"indice": k, "som": e["som"], "tempo": e["tempo"], "ganho_db": e.get("ganho_db", 0), "elemento": e.get("elemento", ""),
                "descricao": cat["efeitos"].get(e["som"], {}).get("descricao", "")} for k, e in enumerate(plano.get("efeitos", []))]
    return {"planejado": (pasta / "som.json").exists(), "musica": atual,
            "musicas": [{"nome": n, "titulo": x["titulo"], "autor": x["autor"], "descricao": x["descricao"]} for n, x in cat["musicas"].items()],
            "sons": [{"nome": n, "descricao": x["descricao"]} for n, x in cat["efeitos"].items()],
            "efeitos": efeitos, "desfazer": len(historico(pasta, "som")),
            "limites": {"ganho_efeito": GANHO_EFEITO, "abaixo": MUSICA_ABAIXO, "sobe": MUSICA_SOBE}}


def _mudar_som(pasta: Path, funcao):
    dados = copy.deepcopy(_plano_de_som(pasta))
    funcao(dados)
    guardar(pasta, "som", pasta / "som.json")
    salvar_json_atomico(pasta / "som.json", dados)


def _efeito(dados: dict, indice) -> dict:
    if isinstance(indice, bool) or not isinstance(indice, int) or not 0 <= indice < len(dados.get("efeitos", [])):
        raise Recusado("esse efeito não existe: atualize a tela")
    return dados["efeitos"][indice]


def nivel_da_musica(pasta: Path, abaixo, sobe):
    abaixo = _numero(abaixo, "música abaixo da voz", *MUSICA_ABAIXO)
    sobe = _numero(sobe, "subida nas pausas", *MUSICA_SOBE)

    def f(dados):
        if not dados.get("musica"):
            raise Recusado("não há música nesta edição: escolha uma antes")
        dados["musica"]["abaixo_da_voz_db"], dados["musica"]["sobe_na_pausa_db"] = abaixo, sobe
    _mudar_som(pasta, f)


def ganho_do_efeito(pasta: Path, indice, ganho):
    ganho = _numero(ganho, "ganho do efeito", *GANHO_EFEITO)
    _mudar_som(pasta, lambda d: _efeito(d, indice).update(ganho_db=ganho))


def trocar_som_do_efeito(pasta: Path, indice, som):
    if som not in _catalogo_de_sons()["efeitos"]:
        raise Recusado("escolha um dos efeitos da lista")

    def f(d):
        e = _efeito(d, indice)
        e["som"] = som
        e.pop("duracao_max", None)
        if som == "tique-taque":
            e["duracao_max"] = 2.0
    _mudar_som(pasta, f)


def tirar_efeito(pasta: Path, indice):
    def f(d):
        _efeito(d, indice)
        del d["efeitos"][indice]
    _mudar_som(pasta, f)


def desfazer_som(pasta: Path) -> bool:
    return desfazer(pasta, "som", pasta / "som.json")


def som_para_ouvir(tipo: str, nome: str, pasta_cache: Path) -> Path:
    """O arquivo de uma música (os primeiros 30 s) ou de um efeito da skill. Só nomes do catálogo, nunca um caminho."""
    cat = _catalogo_de_sons()
    if tipo == "efeito" and nome in cat["efeitos"]:
        return PASTA_SONS / cat["efeitos"][nome]["arquivo"]
    if tipo == "musica" and nome in cat["musicas"]:
        origem = PASTA_SONS / cat["musicas"][nome]["arquivo"]
        destino = pasta_cache / f"musica-{nome}-{SEGUNDOS_DA_MUSICA}s.m4a"
        if destino.exists():
            return destino
        if shutil.which("ffmpeg") is None:
            return origem
        pasta_cache.mkdir(parents=True, exist_ok=True)
        parcial = destino.with_name(destino.name + ".parte.m4a")
        r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", str(origem), "-t", str(SEGUNDOS_DA_MUSICA), "-vn",
                            "-c:a", "aac", "-b:a", "96k", str(parcial)], capture_output=True)
        if r.returncode != 0 or not parcial.exists():
            return origem
        parcial.replace(destino)
        return destino
    raise Recusado("esse som não existe")


# ---------- conferência ----------

def _ultimo_video(pasta: Path) -> Path | None:
    achados = sorted(x for x in pasta.glob("*-v[0-9][0-9][0-9].mp4") if not x.name.startswith("amostra"))
    return achados[-1] if achados else None


def painel_de_conferencia(pasta: Path, pausas_ok: list | None = None) -> dict:
    v = _ultimo_video(pasta)
    arq = v.with_suffix(".conferencia.json") if v else None
    if not (arq and arq.exists()):
        raise Recusado("a conferência ainda não foi feita")
    c = ler_json(arq)
    return {"video": v.name, "aprovado": c.get("aprovado", False), "checks": c.get("checks", []),
            "correcoes": c.get("correcoes", []), "pausas_ok": list(pausas_ok or [])}


def _correcao(pasta: Path, tipo: str, **achar) -> dict:
    for c in painel_de_conferencia(pasta)["correcoes"]:
        if c.get("tipo") == tipo and all(abs(float(c.get(k, 0)) - float(v)) < 0.011 for k, v in achar.items()):
            return c
    raise Recusado("essa correção não é mais necessária: atualize a tela")


def pausa_aceitavel(pasta: Path, inicio) -> float:
    """Confere que a pausa é uma das que a conferência achou e devolve o segundo que vai para `pausas_ok`."""
    inicio = _numero(inicio, "pausa", 0, 36000)
    return float(_correcao(pasta, "pausa", inicio=inicio)["inicio"])


def aplicar_ganho(pasta: Path, trecho, ganho):
    if isinstance(trecho, bool) or not isinstance(trecho, int) or trecho < 0:
        raise Recusado("trecho inválido")
    ganho = _numero(ganho, "ganho", *GANHO_TRECHO)
    c = _correcao(pasta, "ganho", trecho=trecho, ganho_db=ganho)
    arq = pasta / "cortes.json"
    cortes = copy.deepcopy(ler_json(arq))
    if trecho >= len(cortes["trechos"]):
        raise Recusado("esse trecho não existe mais nos cortes")
    cortes["trechos"][trecho]["ganho_db"] = c["ganho_db"]
    guardar(pasta, "cortes", arq)           # o mesmo histórico da revisão dos cortes: o Desfazer de lá também desfaz isto
    salvar_json_atomico(arq, cortes)
