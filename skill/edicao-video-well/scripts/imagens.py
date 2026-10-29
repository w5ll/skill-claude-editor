"""Imagens de apoio de uso livre, com a licença registrada.

Uso:
    python imagens.py adicionar ARQUIVO --titulo "..." --palavras a,b --autor "..." --licenca cc0 --origem URL
                                       --pessoa sim|nao --marca sim|nao [--credito "..."]
    python imagens.py listar
    python imagens.py buscar PALAVRA [PALAVRA ...]
    python imagens.py verificar
    python imagens.py sugerir --pasta saida/2026-10-22_tema [--intervalo 6]
    python imagens.py usar ID --pasta saida/... --inicio 12.5 --duracao 2 [--modo sobreposto|tela] [--texto "..."]
    python imagens.py creditos --pasta saida/...

A biblioteca fica em imagens/ na raiz do projeto (os arquivos e o registro.json). Cada imagem leva
autor, licença, origem (o endereço da página dela), data, SHA-256 e duas respostas obrigatórias:
aparece pessoa reconhecível? aparece marca de terceiros?

Licenças aceitas: cc0, dominio-publico, pexels, pixabay, unsplash (licenças próprias dos sites, que
liberam uso comercial sem crédito, com restrições: confira a página de origem), cc-by (EXIGE crédito)
e propria (foto da própria pessoa). Recusadas: cc-by-sa, cc-by-nc, cc-by-nd e "direitos reservados".

adicionar  confere os campos e a licença, reduz para no máximo 1920 px e guarda uma cópia em imagens/.
           O arquivo original não é tocado.
sugerir    procura, na fala já cortada, as palavras que chamam uma imagem da biblioteca e imprime a
           proposta (não aplica): no máximo uma a cada 6 s e nunca em cima de outro elemento.
usar       coloca a imagem no elementos.json como imagem:ID, para o elementos.py desenhar.
creditos   lista as imagens usadas no vídeo e o texto de crédito que o post precisa levar.

Só se registra o que a pessoa trouxe. Baixar imagem da internet é com o pedido dela.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import re
import shutil
import sys
import unicodedata
from pathlib import Path

from comum import PASTA_SKILL, erro, ler_json, salvar_json, tempo

PASTA_IMAGENS = PASTA_SKILL.parent.parent / "imagens"
LADO_MAXIMO = 1920
DURACAO = {"sobreposto": (1.0, 4.0), "tela": (1.0, 3.0)}
INTERVALO = 6.0

LICENCAS = {
    "cc0": {"nome": "CC0 1.0 (domínio público)", "credito": False},
    "dominio-publico": {"nome": "Domínio público", "credito": False},
    "pexels": {"nome": "Licença Pexels", "credito": False},
    "pixabay": {"nome": "Licença Pixabay", "credito": False},
    "unsplash": {"nome": "Licença Unsplash", "credito": False},
    "cc-by": {"nome": "CC BY (atribuição)", "credito": True},
    "propria": {"nome": "Imagem própria", "credito": False},
}
RECUSADAS = {
    "cc-by-sa": "obriga a licenciar o vídeo inteiro com a mesma licença",
    "cc-by-nc": "proíbe uso comercial, e o vídeo promove um trabalho",
    "cc-by-nd": "proíbe alterar a imagem, e ela é recortada e recebe película e rótulo",
    "todos-os-direitos-reservados": "sem licença de uso, a imagem não pode entrar",
}


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in t if not unicodedata.combining(c)))


def slug(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40] or "imagem"


def registro_arq(pasta: Path) -> Path:
    return pasta / "registro.json"


def carregar_registro(pasta: Path | None = None) -> dict:
    pasta = pasta or PASTA_IMAGENS
    arq = registro_arq(pasta)
    return ler_json(arq) if arq.exists() else {"versao": 1, "imagens": {}}


def sha256(arq: Path) -> str:
    return hashlib.sha256(arq.read_bytes()).hexdigest()


def sim_nao(v: str, campo: str) -> bool:
    if v not in ("sim", "nao", "não"):
        erro(f"{campo}: responda sim ou nao")
    return v == "sim"


# ---------- adicionar ----------

def checar_licenca(licenca: str, autor: str, origem: str, credito: str):
    if licenca in RECUSADAS:
        erro(f"a licença {licenca} não serve: {RECUSADAS[licenca]}")
    if licenca not in LICENCAS:
        erro(f"licença desconhecida \"{licenca}\". Aceitas: {', '.join(LICENCAS)}")
    if licenca != "propria" and not origem.startswith(("http://", "https://")):
        erro("diga a origem: o endereço da página da imagem (--origem https://...)")
    if licenca != "propria" and not autor.strip():
        erro("diga o autor (--autor)")
    if LICENCAS[licenca]["credito"] and not credito.strip():
        erro(f"a licença {licenca} exige crédito: diga o texto com --credito \"Foto: Fulano, CC BY 4.0\"")


def adicionar(arquivo: Path, titulo: str, palavras: list[str], autor: str, licenca: str, origem: str, pessoa: bool,
              marca: bool, credito: str = "", pasta: Path | None = None) -> dict:
    import cv2
    pasta = pasta or PASTA_IMAGENS
    checar_licenca(licenca, autor, origem, credito)
    if not titulo.strip():
        erro("diga o título (--titulo)")
    stems = [norm(p) for p in palavras if norm(p)]
    if not stems:
        erro("diga pelo menos uma palavra que chama a imagem (--palavras a,b)")
    if not arquivo.exists():
        erro(f"não achei {arquivo}")
    img = cv2.imread(str(arquivo))
    if img is None:
        erro(f"{arquivo.name} não é uma imagem que eu consiga abrir (use JPG, PNG ou WebP)")
    h, w = img.shape[:2]
    maior = max(h, w)
    if maior > LADO_MAXIMO:
        img = cv2.resize(img, (round(w * LADO_MAXIMO / maior), round(h * LADO_MAXIMO / maior)), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
    reg = carregar_registro(pasta)
    base, n = slug(titulo), 1
    id_ = base
    while id_ in reg["imagens"] or (pasta / f"{id_}.jpg").exists():
        n += 1
        id_ = f"{base}-{n}"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{id_}.jpg"
    cv2.imwrite(str(destino), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    entrada = {"arquivo": destino.name, "titulo": titulo.strip(), "palavras": stems, "autor": autor.strip() or "própria",
               "licenca": licenca, "origem": origem.strip(), "credito": credito.strip(),
               "pessoa_reconhecivel": pessoa, "marca_de_terceiros": marca, "largura": w, "altura": h,
               "registrada_em": datetime.date.today().isoformat(), "sha256": sha256(destino)}
    reg["imagens"][id_] = entrada
    salvar_json(registro_arq(pasta), reg)
    return {"id": id_, **entrada}


# ---------- consultar ----------

def buscar(reg: dict, termos: list[str]) -> list[tuple[str, dict]]:
    ns = [norm(t) for t in termos if norm(t)]
    saida = []
    for id_, e in reg["imagens"].items():
        texto = norm(e["titulo"]) + "".join(e["palavras"])
        if any(n in texto for n in ns):
            saida.append((id_, e))
    return saida


def verificar(pasta: Path | None = None) -> list[tuple[str, str, str]]:
    """[(id, nivel, texto)]; nível: FALHOU ou aviso."""
    pasta = pasta or PASTA_IMAGENS
    saida = []
    for id_, e in carregar_registro(pasta)["imagens"].items():
        arq = pasta / e["arquivo"]
        if not arq.exists():
            saida.append((id_, "FALHOU", f"falta o arquivo {e['arquivo']}"))
            continue
        if sha256(arq) != e["sha256"]:
            saida.append((id_, "FALHOU", "o arquivo mudou depois do registro (SHA-256 diferente): confira a origem e registre de novo"))
        if e["licenca"] in RECUSADAS or e["licenca"] not in LICENCAS:
            saida.append((id_, "FALHOU", f"licença {e['licenca']} não aceita"))
        elif LICENCAS[e["licenca"]]["credito"] and not e.get("credito"):
            saida.append((id_, "FALHOU", "licença com crédito obrigatório e sem o texto do crédito"))
        if e["licenca"] != "propria" and not str(e.get("origem", "")).startswith("http"):
            saida.append((id_, "FALHOU", "sem a origem (endereço da página da imagem)"))
        if e.get("pessoa_reconhecivel"):
            saida.append((id_, "aviso", "aparece pessoa reconhecível: uso comercial precisa de autorização dela"))
        if e.get("marca_de_terceiros"):
            saida.append((id_, "aviso", "aparece marca de terceiros: evite em vídeo que promove um trabalho"))
    return saida


def carregar_imagem(id_: str, pasta: Path | None = None) -> tuple[str, str]:
    """(data URI, SHA-256) de uma imagem registrada e íntegra. Erro claro se não puder ser usada."""
    pasta = pasta or PASTA_IMAGENS
    e = carregar_registro(pasta)["imagens"].get(id_)
    if e is None:
        erro(f"a imagem \"{id_}\" não está registrada em {pasta}. Veja: python imagens.py listar")
    problemas = [t for i, n, t in verificar(pasta) if i == id_ and n == "FALHOU"]
    if problemas:
        erro(f"a imagem \"{id_}\" não pode ser usada: {problemas[0]}")
    dados = (pasta / e["arquivo"]).read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(dados).decode(), e["sha256"]


# ---------- no vídeo ----------

def janelas(pasta: Path) -> list[tuple[float, float]]:
    arq = pasta / "elementos.json"
    if not arq.exists():
        return []
    return [(i["inicio"], i["inicio"] + i["duracao"]) for i in ler_json(arq).get("itens", [])]


def em_conflito(ini: float, fim: float, ocupado: list[tuple[float, float]], intervalo: float) -> tuple[float, float] | None:
    """O elemento que está colado: sobrepõe, ou começa a menos de `intervalo` segundos do início do outro."""
    return next(((a, b) for a, b in ocupado if abs(ini - a) < intervalo or (a < fim and ini < b)), None)


def sugerir(palavras: list[dict], reg: dict, ocupado: list[tuple[float, float]], duracao_video: float,
            intervalo: float = INTERVALO, duracao: float = 2.0) -> list[dict]:
    propostas, ultimo = [], -999.0
    todos = sorted(ocupado)
    for w in palavras:
        if w["i"] - ultimo < intervalo:
            continue
        n = norm(w["p"])
        if len(n) < 3:
            continue
        for id_, e in reg["imagens"].items():
            if any(n.startswith(st) for st in e["palavras"]):
                ini = max(0.0, round(w["i"] - 0.12, 3))
                fim = ini + duracao
                if fim > duracao_video or em_conflito(ini, fim, todos, intervalo):
                    break
                propostas.append({"imagem": id_, "titulo": e["titulo"], "inicio": ini, "duracao": duracao,
                                  "gatilho": w["p"].strip(".,!?"), "fala_em": round(w["i"], 3)})
                todos.append((ini, fim))
                ultimo = w["i"]
                break
    return propostas


def usar(pasta: Path, id_: str, inicio: float, duracao: float, modo: str, texto: str,
         pasta_imagens: Path | None = None) -> dict:
    carregar_imagem(id_, pasta_imagens)            # recusa imagem que não pode ser usada
    lo, hi = DURACAO[modo]
    if not lo <= duracao <= hi:
        erro(f"no modo {modo} a imagem fica de {lo:g} a {hi:g} s")
    arq = pasta / "elementos.json"
    dados = ler_json(arq) if arq.exists() else {"itens": []}
    colado = em_conflito(inicio, inicio + duracao, janelas(pasta), INTERVALO)
    if colado:
        erro(f"já há um elemento perto de {tempo(inicio)} (de {tempo(colado[0])} a {tempo(colado[1])}): "
             f"um a cada {INTERVALO:g} s no máximo")
    item = {"elemento": f"imagem:{id_}", "inicio": round(inicio, 3), "duracao": round(duracao, 2), "modo": modo,
            "posicao": "auto", "texto": texto, "gatilho": "", "fala_em": round(inicio, 3)}
    dados["itens"] = sorted(dados.get("itens", []) + [item], key=lambda i: i["inicio"])
    salvar_json(arq, dados)
    return item


def creditos(pasta: Path, pasta_imagens: Path | None = None) -> tuple[list[str], list[str]]:
    """(linhas de registro de todas as imagens usadas, textos de crédito obrigatórios)."""
    reg = carregar_registro(pasta_imagens)
    arq = pasta / "elementos.json"
    usadas = []
    for it in (ler_json(arq).get("itens", []) if arq.exists() else []):
        if str(it["elemento"]).startswith("imagem:"):
            id_ = it["elemento"].split(":", 1)[1]
            if id_ not in usadas:
                usadas.append(id_)
    registro, obrigatorios = [], []
    for id_ in usadas:
        e = reg["imagens"].get(id_)
        if e is None:
            registro.append(f"{id_}: NÃO ESTÁ NO REGISTRO")
            continue
        registro.append(f"{e['titulo']} · {e['autor']} · {LICENCAS.get(e['licenca'], {}).get('nome', e['licenca'])}"
                        f"{' · ' + e['origem'] if e['origem'] else ''}")
        if LICENCAS.get(e["licenca"], {}).get("credito") and e.get("credito"):
            obrigatorios.append(e["credito"])
    return registro, obrigatorios


# ---------- linha de comando ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["adicionar", "listar", "buscar", "verificar", "sugerir", "usar", "creditos"])
    ap.add_argument("alvo", nargs="*", help="adicionar: o arquivo · buscar: palavras · usar: o id")
    ap.add_argument("--pasta", type=Path)
    ap.add_argument("--titulo", default="")
    ap.add_argument("--palavras", default="")
    ap.add_argument("--autor", default="")
    ap.add_argument("--licenca", default="")
    ap.add_argument("--origem", default="")
    ap.add_argument("--pessoa")
    ap.add_argument("--marca")
    ap.add_argument("--credito", default="")
    ap.add_argument("--inicio", type=float)
    ap.add_argument("--duracao", type=float, default=2.0)
    ap.add_argument("--modo", choices=list(DURACAO), default="sobreposto")
    ap.add_argument("--texto", default="")
    ap.add_argument("--intervalo", type=float, default=INTERVALO)
    a = ap.parse_args()

    if a.acao == "adicionar":
        if len(a.alvo) != 1:
            erro("diga o arquivo: imagens.py adicionar foto.jpg --titulo ...")
        if not a.licenca:
            erro("diga a licença (--licenca): " + ", ".join(LICENCAS))
        e = adicionar(Path(a.alvo[0]), a.titulo, [p for p in a.palavras.split(",")], a.autor, a.licenca, a.origem,
                      sim_nao(a.pessoa or "", "--pessoa"), sim_nao(a.marca or "", "--marca"), a.credito)
        print(f"ok  {e['id']} registrada ({e['largura']}x{e['altura']}, {LICENCAS[e['licenca']]['nome']})")
    elif a.acao == "listar":
        reg = carregar_registro()
        for id_, e in reg["imagens"].items():
            print(f"  {id_}: {e['titulo']} · {LICENCAS.get(e['licenca'], {}).get('nome', e['licenca'])} · chama: {', '.join(e['palavras'])}")
        if not reg["imagens"]:
            print(f"a biblioteca está vazia ({PASTA_IMAGENS})")
    elif a.acao == "buscar":
        achadas = buscar(carregar_registro(), a.alvo)
        for id_, e in achadas:
            print(f"  {id_}: {e['titulo']}")
        if not achadas:
            print("nenhuma imagem com essas palavras")
    elif a.acao == "verificar":
        r = verificar()
        for id_, nivel, t in r:
            print(f"  {nivel:<7} {id_}: {t}")
        if any(n == "FALHOU" for _, n, _ in r):
            sys.exit(1)
        print(f"ok  {len(carregar_registro()['imagens'])} imagem(ns) conferidas" + (" (com avisos)" if r else ""))
    else:
        if not a.pasta:
            erro("informe --pasta")
        pasta = a.pasta.resolve()
        if a.acao == "sugerir":
            from elementos import palavras_saida
            cortes = ler_json(pasta / "cortes.json")
            props = sugerir(palavras_saida(pasta), carregar_registro(), janelas(pasta), cortes["duracao_final"], a.intervalo)
            for p in props:
                print(f"  {tempo(p['inicio'])}  {p['imagem']} ({p['titulo']}) quando fala \"{p['gatilho']}\"")
            print(f"{len(props)} imagem(ns) proposta(s). Aplique com: imagens.py usar ID --pasta ... --inicio S")
        elif a.acao == "usar":
            if len(a.alvo) != 1 or a.inicio is None:
                erro("use: imagens.py usar ID --pasta ... --inicio S [--duracao D] [--modo sobreposto|tela]")
            item = usar(pasta, a.alvo[0], a.inicio, a.duracao, a.modo, a.texto)
            print(f"ok  imagem {a.alvo[0]} em {tempo(item['inicio'])} ({item['duracao']} s, {item['modo']})")
        else:
            registro, obrigatorios = creditos(pasta)
            linhas = ["Imagens de apoio usadas neste vídeo:"] + [f"- {r}" for r in registro]
            if obrigatorios:
                linhas += ["", "Crédito obrigatório no texto do post:"] + [f"- {c}" for c in obrigatorios]
            (pasta / "creditos-imagens.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")
            print("\n".join(linhas) if registro else "nenhuma imagem de apoio neste vídeo")


if __name__ == "__main__":
    main()
