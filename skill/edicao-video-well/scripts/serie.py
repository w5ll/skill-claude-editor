"""Série: o jeito de editar que todos os vídeos de uma série seguem.

Uso:
    python serie.py listar
    python serie.py validar NOME
    python serie.py cartao NOME
    python serie.py aplicar NOME --pasta saida/2026-10-22_tema
    python serie.py elementos --pasta saida/2026-10-22_tema
    python serie.py texto --pasta saida/2026-10-22_tema --arquivo texto-do-post.md

Cada série é um arquivo series/<nome>.json na raiz do projeto (fora da skill: é da pessoa).
Veja series/_modelo.json. Todo campo é opcional; o que falta segue o padrão da skill.

listar     as séries que existem.
validar    confere cada campo e diz, em português, o que está errado.
cartao     as linhas do cartão de ajustes que a série preenche, marcadas "(da série X)".
aplicar    copia a série para <pasta>/serie.json (uma cópia: mudar a série depois não altera esta
           edição) e imprime os comandos de cada etapa com os parâmetros da série.
elementos  tira do elementos.json o que a série proíbe ou não permite.
texto      confere se o texto do post traz as hashtags fixas e os avisos obrigatórios da série.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import unicodedata
from pathlib import Path

from comum import PASTA_SKILL, erro, ler_json, salvar_json

PASTA_RAIZ = PASTA_SKILL.parent.parent
PASTA_SERIES = PASTA_RAIZ / "series"

RITMOS = ("natural", "dinamico")
ZOOMS = ("nenhum", "leve", "normal", "forte")
RUIDOS = ("auto", "nao", "leve", "forte")
MODOS = ("sobreposto", "tela")
POSICOES = ("auto", "baixo", "meio", "alto")
CAMPOS = {"nome", "descricao", "ritmo", "formato", "legenda", "elementos", "camera", "som", "ruido", "termos",
          "publicacao"}
CAMPOS_LEGENDA = {"ligada", "palavras", "posicao", "tamanho", "maiusculas", "destaque"}
CAMPOS_ELEMENTOS = {"ligado", "modo", "intervalo", "permitidos", "proibidos", "gerados"}
CAMPOS_SOM = {"musica", "efeitos", "volume"}
CAMPOS_PUBLICACAO = {"hashtags_fixas", "avisos_obrigatorios", "chamada"}


def nomes_de_elementos() -> list[str]:
    from elementos import ELEMENTOS
    return list(ELEMENTOS)


def nomes_de_musicas() -> list[str]:
    return list(ler_json(PASTA_SKILL / "assets" / "sons" / "sons.json")["musicas"])


def caminho(nome: str) -> Path:
    if not re.fullmatch(r"[a-z0-9_][a-z0-9_-]*", nome):
        erro("o nome da série usa só letras minúsculas sem acento, números, hífen e sublinhado")
    return PASTA_SERIES / f"{nome}.json"


def carregar(nome: str) -> dict:
    arq = caminho(nome)
    if not arq.exists():
        erro(f"não achei a série {nome}. Séries que existem: {', '.join(listar()) or 'nenhuma'}")
    return ler_json(arq)


def listar() -> list[str]:
    return sorted(p.stem for p in PASTA_SERIES.glob("*.json") if not p.stem.startswith("_")) if PASTA_SERIES.exists() else []


# ---------- validação ----------

def _desconhecidos(dados: dict, validos: set, onde: str) -> list[str]:
    return [f"{onde}: campo desconhecido \"{c}\" (use {', '.join(sorted(validos))})" for c in dados if c not in validos]


def validar(s: dict, musicas: list[str] | None = None, elementos: list[str] | None = None) -> list[str]:
    musicas = musicas if musicas is not None else nomes_de_musicas()
    elementos = elementos if elementos is not None else nomes_de_elementos()
    p = _desconhecidos(s, CAMPOS, "série")
    if s.get("ritmo") not in (None, *RITMOS):
        p.append(f"ritmo \"{s['ritmo']}\": use {' ou '.join(RITMOS)}")
    if s.get("ruido") not in (None, *RUIDOS):
        p.append(f"ruído \"{s['ruido']}\": use {', '.join(RUIDOS)}")
    if "formato" in s:
        from comum import FORMATOS
        prop, _, tam = str(s["formato"]).partition("@")
        if prop != "original" and prop not in FORMATOS:
            p.append(f"formato \"{s['formato']}\": use original ou {', '.join(FORMATOS)}, com @1080 se quiser reduzir")
        if tam and not tam.isdigit():
            p.append(f"formato \"{s['formato']}\": o tamanho depois do @ tem que ser um número")
    leg = s.get("legenda") or {}
    p += _desconhecidos(leg, CAMPOS_LEGENDA, "legenda")
    if "palavras" in leg and not (isinstance(leg["palavras"], int) and 1 <= leg["palavras"] <= 6):
        p.append("legenda.palavras: um número de 1 a 6")
    if leg.get("posicao") not in (None, *POSICOES):
        p.append(f"legenda.posicao \"{leg['posicao']}\": use {', '.join(POSICOES)}")
    if "tamanho" in leg and not (isinstance(leg["tamanho"], (int, float)) and 0.02 <= leg["tamanho"] <= 0.09):
        p.append("legenda.tamanho: entre 0,02 e 0,09 (fração da altura do vídeo)")
    el = s.get("elementos") or {}
    p += _desconhecidos(el, CAMPOS_ELEMENTOS, "elementos")
    if el.get("modo") not in (None, *MODOS):
        p.append(f"elementos.modo \"{el['modo']}\": use {' ou '.join(MODOS)}")
    if "intervalo" in el and not (isinstance(el["intervalo"], (int, float)) and el["intervalo"] >= 3):
        p.append("elementos.intervalo: pelo menos 3 segundos entre um elemento e outro")
    for chave in ("permitidos", "proibidos"):
        for e in el.get(chave, []):
            if e not in elementos and e not in ("gerado", "imagem"):
                p.append(f"elementos.{chave}: \"{e}\" não existe (use {', '.join(elementos)}, gerado ou imagem)")
    cam = s.get("camera") or {}
    p += _desconhecidos(cam, {"zoom"}, "camera")
    if cam.get("zoom") not in (None, *ZOOMS):
        p.append(f"camera.zoom \"{cam['zoom']}\": use {', '.join(ZOOMS)}")
    som = s.get("som") or {}
    p += _desconhecidos(som, CAMPOS_SOM, "som")
    if som.get("musica") not in (None, "nenhuma", *musicas):
        p.append(f"som.musica \"{som['musica']}\": use nenhuma, {', '.join(musicas)}")
    if "volume" in som and not (isinstance(som["volume"], (int, float)) and -23 <= som["volume"] <= -9):
        p.append("som.volume: entre -23 e -9 (LUFS; o padrão das redes é -14)")
    if "termos" in s and not (isinstance(s["termos"], list) and all(isinstance(t, str) and t.strip() for t in s["termos"])):
        p.append("termos: uma lista de palavras")
    pub = s.get("publicacao") or {}
    p += _desconhecidos(pub, CAMPOS_PUBLICACAO, "publicacao")
    for h in pub.get("hashtags_fixas", []):
        if not re.fullmatch(r"#\w+", h):
            p.append(f"publicacao.hashtags_fixas: \"{h}\" não é uma hashtag (#palavra)")
    for chave in ("hashtags_fixas", "avisos_obrigatorios"):
        if chave in pub and not isinstance(pub[chave], list):
            p.append(f"publicacao.{chave}: uma lista")
    return p


# ---------- cartão e comandos ----------

def linhas_do_cartao(s: dict) -> list[str]:
    origem = f"_(da série {s.get('nome', '')})_"
    r = []
    if "ritmo" in s:
        r.append(f"- ✂️ **Limpeza**: ritmo {'dinâmico' if s['ritmo'] == 'dinamico' else 'natural'} {origem}")
    leg = s.get("legenda")
    if leg is not None:
        if leg.get("ligada") is False:
            r.append(f"- 💬 **Legenda**: desligada {origem}")
        else:
            pos = {"auto": "fora do rosto", "baixo": "embaixo", "meio": "no meio", "alto": "em cima"}[leg.get("posicao", "auto")]
            r.append(f"- 💬 **Legenda**: até {leg.get('palavras', 3)} palavras por vez, {pos}"
                     f"{', em maiúsculas' if leg.get('maiusculas') else ''}"
                     f"{'' if leg.get('destaque', True) else ', sem destacar a palavra falada'} {origem}")
    el = s.get("elementos")
    if el is not None:
        if el.get("ligado") is False:
            r.append(f"- ✨ **Elementos 3D**: desligados {origem}")
        else:
            nota = []
            if el.get("permitidos"):
                nota.append("só " + ", ".join(el["permitidos"]))
            if el.get("proibidos"):
                nota.append("sem " + ", ".join(el["proibidos"]))
            if el.get("gerados") is False:
                nota.append("sem elementos novos desenhados")
            r.append(f"- ✨ **Elementos 3D**: modo {'tela cheia' if el.get('modo') == 'tela' else 'sobreposto'}, "
                     f"um a cada {el.get('intervalo', 6)} s no máximo{' · ' + ' · '.join(nota) if nota else ''} {origem}")
    cam = s.get("camera")
    if cam is not None:
        z = cam.get("zoom", "nenhum")
        r.append(f"- 🎥 **Câmera**: {'parada, sem zoom' if z == 'nenhum' else 'zoom de ênfase ' + z} {origem}")
    som = s.get("som")
    if som is not None:
        m = som.get("musica", "nenhuma")
        partes = ["sem música" if m == "nenhuma" else f"música {m}"]
        partes.append("efeito em cada elemento 3D" if som.get("efeitos") else "sem efeito")
        if "volume" in som:
            partes.append(f"voz em {som['volume']} LUFS")
        r.append(f"- 🔊 **Som**: {' · '.join(partes)} {origem}")
    if "formato" in s:
        r.append(f"- 📐 **Formato**: {s['formato']} {origem}")
    return r


def abertos(s: dict) -> list[str]:
    todos = {"ritmo": "ritmo", "legenda": "legenda", "elementos": "elementos 3D", "camera": "câmera", "som": "som",
             "formato": "formato"}
    return [nome for chave, nome in todos.items() if chave not in s]


def comandos(s: dict, pasta: str) -> list[str]:
    """Os comandos de cada etapa, com os parâmetros da série."""
    formato = s.get("formato", "original")
    c = []
    termos = ",".join(s.get("termos", []))
    c.append(f"python scripts/transcrever.py BRUTO.mov --pasta {pasta}" + (f' --termos "{termos}"' if termos else ""))
    c.append(f"python scripts/propor_cortes.py --pasta {pasta} --ritmo {s.get('ritmo', 'natural')}")
    c.append(f"python scripts/rosto.py --pasta {pasta} --formato {formato}")
    el = s.get("elementos") or {}
    if el.get("ligado") is not False:
        c.append(f"python scripts/elementos.py sugerir --pasta {pasta} --modo {el.get('modo', 'sobreposto')}"
                 f" --intervalo {el.get('intervalo', 6)}")
        if el.get("proibidos") or el.get("permitidos") or el.get("gerados") is False:
            c.append(f"python scripts/serie.py elementos --pasta {pasta}")
    zoom = (s.get("camera") or {}).get("zoom", "nenhum")
    if zoom != "nenhum":
        c.append(f"python scripts/camera.py planejar --pasta {pasta} --intensidade {zoom}")
    leg = s.get("legenda") or {}
    if leg.get("ligada") is not False:
        linha = f"python scripts/legendas.py --pasta {pasta} --formato {formato}"
        if "palavras" in leg:
            linha += f" --palavras {leg['palavras']}"
        if "posicao" in leg:
            linha += f" --posicao {leg['posicao']}"
        if "tamanho" in leg:
            linha += f" --tamanho {leg['tamanho']}"
        if leg.get("maiusculas"):
            linha += " --maiusculas"
        if leg.get("destaque") is False:
            linha += " --sem-destaque"
        c.append(linha)
    som = s.get("som") or {}
    if som.get("musica", "nenhuma") != "nenhuma" or som.get("efeitos"):
        linha = f"python scripts/som.py planejar --pasta {pasta}"
        if som.get("musica", "nenhuma") != "nenhuma":
            linha += f" --musica {som['musica']}"
        if som.get("efeitos"):
            linha += " --efeitos"
        c.append(linha)
    render = f"python scripts/renderizar.py --pasta {pasta} --formato {formato}"
    ruido = s.get("ruido", "auto")
    render += " --ruido <leve ou forte, conforme a inspeção>" if ruido == "auto" else f" --ruido {ruido}"
    if "volume" in som:
        render += f" --volume {som['volume']}"
    if el.get("ligado") is False:
        render += " --sem-elementos"
    if leg.get("ligada") is False:
        render += " --sem-legenda"
    c.append(render)
    return c


# ---------- elementos e texto ----------

def filtrar_elementos(itens: list[dict], s: dict) -> tuple[list[dict], list[dict]]:
    """(os que ficam, os que saem) segundo permitidos, proibidos e gerados."""
    el = s.get("elementos") or {}
    permitidos, proibidos = set(el.get("permitidos", [])), set(el.get("proibidos", []))
    ficam, saem = [], []
    for it in itens:
        nome = str(it["elemento"])
        tipo = nome.split(":")[0] if ":" in nome else nome
        gerado_fora = tipo == "gerado" and el.get("gerados") is False
        proibido = nome in proibidos or tipo in proibidos
        fora_da_lista = bool(permitidos) and not (nome in permitidos or tipo in permitidos)
        (saem if (gerado_fora or proibido or fora_da_lista) else ficam).append(it)
    return ficam, saem


def normalizar(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip()


def faltando_no_texto(texto: str, s: dict) -> list[str]:
    pub = s.get("publicacao") or {}
    achadas = {h.lower() for h in re.findall(r"(?<!\w)#\w+", texto)}
    falta = [f"hashtag fixa {h}" for h in pub.get("hashtags_fixas", []) if h.lower() not in achadas]
    n = normalizar(texto)
    falta += [f"aviso obrigatório: \"{a}\"" for a in pub.get("avisos_obrigatorios", []) if normalizar(a) not in n]
    return falta


# ---------- linha de comando ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["listar", "validar", "cartao", "aplicar", "elementos", "texto"])
    ap.add_argument("nome", nargs="?")
    ap.add_argument("--pasta", type=Path)
    ap.add_argument("--arquivo", type=Path)
    a = ap.parse_args()

    if a.acao == "listar":
        for n in listar():
            print(f"  {n}: {carregar(n).get('descricao', '')}")
        if not listar():
            print(f"nenhuma série em {PASTA_SERIES}. Copie series/_modelo.json para series/<nome>.json")
        return
    if a.acao in ("validar", "cartao", "aplicar"):
        if not a.nome:
            erro("diga o nome da série")
        s = carregar(a.nome)
        problemas = validar(s)
        if problemas:
            for p in problemas:
                print(f"  problema: {p}")
            erro(f"a série {a.nome} tem {len(problemas)} problema(s)", 1)
        if a.acao == "validar":
            print(f"ok  a série {a.nome} está certa")
        elif a.acao == "cartao":
            print("\n".join(linhas_do_cartao(s)))
            if abertos(s):
                print(f"\nA série não define: {', '.join(abertos(s))} (valem os padrões; confirme no cartão)")
        else:
            if not a.pasta:
                erro("informe --pasta")
            pasta = a.pasta.resolve()
            pasta.mkdir(parents=True, exist_ok=True)
            salvar_json(pasta / "serie.json", s)
            print(f"ok  série {a.nome} copiada para {pasta / 'serie.json'}\n")
            print("\n".join(comandos(s, str(a.pasta))))
        return

    if not a.pasta:
        erro("informe --pasta")
    pasta = a.pasta.resolve()
    if not (pasta / "serie.json").exists():
        erro("rode serie.py aplicar NOME --pasta ... antes")
    s = ler_json(pasta / "serie.json")
    if a.acao == "elementos":
        arq = pasta / "elementos.json"
        if not arq.exists():
            erro("rode elementos.py sugerir antes")
        dados = ler_json(arq)
        ficam, saem = filtrar_elementos(dados.get("itens", []), s)
        if saem:
            shutil.copy(arq, pasta / "elementos.anterior.json")
            salvar_json(arq, {**dados, "itens": ficam})
        for it in saem:
            print(f"  tirei {it['elemento']} de {it['inicio']:.1f} s (a série não usa)")
        print(f"ok  {len(ficam)} elemento(s) ficam, {len(saem)} saíram")
    else:
        if not a.arquivo:
            erro("informe --arquivo com o texto do post")
        texto = a.arquivo.read_text(encoding="utf-8")
        falta = faltando_no_texto(texto, s)
        for f in falta:
            print(f"  falta: {f}")
        if falta:
            sys.exit(1)
        print("ok  o texto traz as hashtags fixas e os avisos da série")


if __name__ == "__main__":
    main()
