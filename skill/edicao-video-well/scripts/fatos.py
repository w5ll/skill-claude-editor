"""Fatos: marca na fala o que precisa ser confirmado antes de renderizar.

Uso:
    python fatos.py marcar    --pasta saida/2026-10-22_tema [--tudo]
    python fatos.py mostrar   --pasta saida/2026-10-22_tema [--tudo]
    python fatos.py responder ID --pasta ... --status confirmado|corrigir|cortar [--nota "130 mil"]
    python fatos.py adicionar --pasta ... --video 0 --segundo 12.4 --trecho "texto" --motivo "..."
    python fatos.py pendentes --pasta ...

marcar     lê as transcrições (e o cortes.json, se existir) e grava fatos.json com os números, datas,
           fontes e referências de norma (gravidade ALTA, precisam de resposta) e as comparações e
           absolutos (média, para olhar). Com --tudo, também as contagens pequenas e os nomes.
           Rodar de novo conserva as respostas já dadas.
mostrar    imprime o bloco do cartão, em português.
responder  grava a resposta: confirmado, corrigir (com a nota do valor certo) ou cortar.
adicionar  marca à mão algo que o script não achou.
pendentes  lista as marcas ALTAS sem resposta e sai com erro se houver alguma (o vídeo inteiro só
           deve ser renderizado sem pendência).

A skill só marca e pergunta: nunca decide se um fato é verdadeiro. É heurística sobre fala
transcrita: número por extenso e frase mal transcrita podem escapar.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

from comum import erro, ler_json, salvar_json, tempo

ALTA, MEDIA, BAIXA = "alta", "média", "baixa"
PAUSA_FRASE = 0.6

UNIDADES = {"reais", "real", "anos", "ano", "meses", "mes", "dias", "semanas", "semana", "horas", "hora",
            "minutos", "vezes", "clientes", "pessoas", "contratos", "leads", "processos", "casos", "empresas",
            "mil", "milhao", "milhoes", "bilhao", "bilhoes", "porcento"}
NUM_PALAVRAS = {"dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9,
                "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14, "quinze": 15,
                "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20, "trinta": 30,
                "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90,
                "cem": 100, "cento": 100, "duzentos": 200, "trezentos": 300, "quinhentos": 500, "mil": 1000,
                "milhao": 10 ** 6, "milhoes": 10 ** 6, "bilhao": 10 ** 9, "bilhoes": 10 ** 9}
MESES = {"janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"}
FONTES = {"pesquisa", "pesquisas", "estudo", "estudos", "dados", "estatistica", "estatisticas", "levantamento",
          "levantamentos", "relatorio"}
APOS_SEGUNDO = {"a", "o", "os", "as", "um", "uma", "pesquisa", "estudo", "dados", "levantamento", "especialistas"}
NORMAS = {"lei", "leis", "artigo", "artigos", "art", "decreto", "resolucao", "sumula", "portaria", "regulamento",
          "provimento", "instrucao"}
COMPARACOES = {"dobro", "triplo", "quadruplo", "metade"}
ABSOLUTOS = {"sempre", "nunca", "jamais", "todos", "todas", "ninguem", "nenhum", "nenhuma", "garantido", "garantida",
             "garantia", "garanto", "certeza", "impossivel", "100%"}
NUMERO_RE = re.compile(r"^\d+(?:[.,]\d+)*%?$")


def norm(p: str) -> str:
    t = unicodedata.normalize("NFKD", p.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"^[^a-z0-9$%]+|[^a-z0-9%]+$", "", t)


def valor(tok: str) -> float | None:
    if tok in NUM_PALAVRAS:
        return float(NUM_PALAVRAS[tok])
    if NUMERO_RE.match(tok):
        n = tok.rstrip("%")
        n = n.replace(".", "") if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", n) else n.replace(",", ".")
        try:
            return float(n)
        except ValueError:
            return None
    return None


def eh_ano(tok: str) -> bool:
    return bool(re.fullmatch(r"(?:19|20)\d{2}", tok))


def achar_na_frase(palavras: list[dict]) -> list[dict]:
    """Marcas de uma frase. Cada marca: tipo, gravidade, trecho, i (segundo da primeira palavra)."""
    toks = [norm(w["p"]) for w in palavras]
    n = len(toks)
    marcas, usado = [], set()

    def marca(tipo, grav, a, b):
        marcas.append({"tipo": tipo, "gravidade": grav, "trecho": " ".join(w["p"].strip() for w in palavras[a:b + 1]),
                       "i": palavras[a]["i"]})
        usado.update(range(a, b + 1))

    k = 0
    while k < n:
        t = toks[k]
        if t in NORMAS:                                   # "lei 13.709", "artigo 5"
            fim = k
            while fim + 1 < n and fim - k < 2 and (valor(toks[fim + 1]) is not None or toks[fim + 1] in ("de", "n", "no")):
                fim += 1
            marca("norma", ALTA, k, fim)
            k = fim + 1
            continue
        if t in MESES:                                    # "10 de março de 2024"
            a, b = k, k
            if k >= 2 and toks[k - 1] == "de" and valor(toks[k - 2]) is not None:
                a = k - 2
            if k + 2 < n and toks[k + 1] == "de" and eh_ano(toks[k + 2]):
                b = k + 2
            marca("data", ALTA, a, b)
            k = b + 1
            continue
        if eh_ano(t) and not (k + 1 < n and toks[k + 1] in UNIDADES):
            marca("data", ALTA, k, k)
            k += 1
            continue
        if valor(t) is not None and t not in ("um", "uma"):
            fim = k
            while fim + 1 < n and (valor(toks[fim + 1]) is not None
                                   or (toks[fim + 1] == "e" and fim + 2 < n and valor(toks[fim + 2]) is not None)):
                fim += 2 if toks[fim + 1] == "e" else 1
            ini = k
            if k > 0 and palavras[k - 1]["p"].strip().lower() in ("r$", "rs"):
                ini = k - 1
            prox = toks[fim + 1] if fim + 1 < n else ""
            if prox == "por" and fim + 2 < n and toks[fim + 2] == "cento":
                fim += 2
                grande = True
            elif prox in UNIDADES:
                fim += 1
                grande = True
            else:
                grande = False
            v = max(valor(x) or 0 for x in toks[k:fim + 1])
            percentual = t.endswith("%") or grande
            marca("numero", ALTA if (v >= 10 or percentual or ini < k) else BAIXA, ini, fim)
            k = fim + 1
            continue
        if t in FONTES or (t == "segundo" and (k == 0 or (k + 1 < n and toks[k + 1] in APOS_SEGUNDO))):
            marca("fonte", ALTA, k, min(n - 1, k + 2))
            k += 3
            continue
        if t in COMPARACOES:
            marca("comparacao", MEDIA, k, k)
        elif t in ABSOLUTOS:
            marca("absoluto", MEDIA, k, k)
        k += 1
    for k, w in enumerate(palavras):                      # nomes próprios (baixa): maiúscula no meio da frase
        txt = re.sub(r"^[^\w]+|[^\w]+$", "", w["p"])
        if k > 0 and k not in usado and len(txt) > 2 and txt[0].isupper() and not txt.isupper():
            marcas.append({"tipo": "nome", "gravidade": BAIXA, "trecho": txt, "i": w["i"]})
    return sorted(marcas, key=lambda m: m["i"])


def frases(palavras: list[dict]) -> list[list[dict]]:
    grupos, atual = [], []
    for w in palavras:
        if atual and (w["i"] - atual[-1]["f"] > PAUSA_FRASE or re.search(r"[.?!…]$", atual[-1]["p"])):
            grupos.append(atual)
            atual = []
        atual.append(w)
    if atual:
        grupos.append(atual)
    return grupos


MOTIVOS = {
    "numero": "valor ou quantidade dita em voz alta",
    "data": "data ou ano",
    "fonte": "afirmação apoiada numa fonte que a fala não nomeia",
    "norma": "referência a uma lei ou norma, que precisa estar exata",
    "comparacao": "comparação forte",
    "absoluto": "afirmação absoluta",
    "nome": "nome próprio citado",
    "manual": "marcado à mão",
}
PERGUNTAS = {
    "numero": "O valor está certo?",
    "data": "A data está certa?",
    "fonte": "Qual é a fonte? Se não souber dizer, o melhor é cortar ou regravar de outro jeito.",
    "norma": "O número e o nome da norma estão exatos?",
    "comparacao": "A comparação é verdadeira?",
    "absoluto": "Isso vale sempre, sem exceção?",
    "nome": "O nome está certo e pode ser citado?",
    "manual": "Está certo?",
}


def marcar_transcricoes(videos: dict[int, list[dict]], tudo: bool = False) -> list[dict]:
    itens = []
    for vid, palavras in sorted(videos.items()):
        for frase in frases(palavras):
            texto = " ".join(w["p"].strip() for w in frase)
            for m in achar_na_frase(frase):
                if m["gravidade"] == BAIXA and not tudo:
                    continue
                itens.append({"tipo": m["tipo"], "gravidade": m["gravidade"], "video": vid, "tempo": round(m["i"], 2),
                              "frase": texto, "trecho": m["trecho"], "motivo": MOTIVOS[m["tipo"]],
                              "pergunta": PERGUNTAS[m["tipo"]]})
    return itens


def chave(i: dict) -> tuple:
    return (i["video"], round(i["tempo"], 1), i["tipo"], norm(i["trecho"]))


def mesclar(novos: list[dict], antigos: list[dict]) -> list[dict]:
    """Conserva respostas e marcas manuais de uma rodada anterior."""
    por_chave = {chave(a): a for a in antigos}
    saida = []
    for n in novos:
        a = por_chave.pop(chave(n), None)
        if a and a.get("status") in ("confirmado", "corrigir", "cortar"):
            n["status"], n["nota"] = a["status"], a.get("nota", "")
        saida.append(n)
    saida += [a for a in por_chave.values() if a["tipo"] == "manual"]
    saida.sort(key=lambda i: (i["video"], i["tempo"]))
    for k, i in enumerate(saida, 1):
        i["id"] = k
    return saida


def definir_status(itens: list[dict], trechos: list[dict] | None):
    for i in itens:
        if i.get("status") in ("confirmado", "corrigir", "cortar"):
            continue
        fica = True
        if trechos is not None:
            fica = any(t["video"] == i["video"] and t["inicio"] <= i["tempo"] < t["fim"] for t in trechos)
        i["fica"] = fica
        i["status"] = "fora_do_corte" if not fica else ("pendente" if i["gravidade"] == ALTA else "revisar")
    for i in itens:
        if "fica" not in i:
            i["fica"] = True


def pendentes(itens: list[dict]) -> list[dict]:
    return [i for i in itens if i["gravidade"] == ALTA and i["status"] == "pendente"]


def bloco_do_cartao(itens: list[dict], tudo: bool = False) -> str:
    pend = [i for i in itens if i["status"] == "pendente"]
    olhar = [i for i in itens if i["status"] == "revisar" and (tudo or i["gravidade"] == MEDIA)]
    respondidos = [i for i in itens if i["status"] in ("confirmado", "corrigir", "cortar")]
    if not (pend or olhar):
        return "### 🔎 Fatos\n\nNada para confirmar na fala." + (f" ({len(respondidos)} já respondidos)" if respondidos else "")
    linhas = ["### 🔎 Conferir antes de editar", ""]
    if pend:
        linhas += [f"Marquei **{len(pend)}** ponto(s) da sua fala que precisam da sua palavra. Para cada um, responda "
                   "**confirmo**, **corrijo para ...** ou **corta**:", ""]
        for i in pend:
            linhas += [f"{i['id']}. **{tempo(i['tempo'])}** · {i['motivo']}: \"{i['trecho']}\"",
                       f"   Na frase: \"{i['frase']}\"", f"   {i['pergunta']}"]
    if olhar:
        linhas += ["", "**Para olhar** (não precisa responder, só avise se algo estiver errado):", ""]
        linhas += [f"- {tempo(i['tempo'])} · {i['motivo']}: \"{i['trecho']}\"" for i in olhar]
    if respondidos:
        linhas += ["", f"_{len(respondidos)} ponto(s) já respondido(s)._"]
    return "\n".join(linhas)


def carregar_videos(pasta: Path) -> tuple[dict[int, list[dict]], list[dict] | None]:
    cortes_arq = pasta / "cortes.json"
    cortes = ler_json(cortes_arq) if cortes_arq.exists() else None
    if cortes:
        arquivos = [(v["id"], v["arquivo"]) for v in cortes["videos"]]
    else:
        insp = pasta / "inspecao.json"
        if not insp.exists():
            erro("rode inspecionar.py e transcrever.py antes")
        arquivos = [(k, v["arquivo"]) for k, v in enumerate(ler_json(insp)["videos"])]
    videos = {}
    for vid, arq in arquivos:
        tr = pasta / "transcricoes" / f"{Path(arq).stem}.json"
        if not tr.exists():
            erro(f"falta a transcrição de {Path(arq).name}: rode transcrever.py")
        videos[vid] = ler_json(tr)["palavras"]
    return videos, (cortes["trechos"] if cortes else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["marcar", "mostrar", "responder", "adicionar", "pendentes"])
    ap.add_argument("id", nargs="?", type=int)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--tudo", action="store_true")
    ap.add_argument("--status", choices=["confirmado", "corrigir", "cortar"])
    ap.add_argument("--nota", default="")
    ap.add_argument("--video", type=int, default=0)
    ap.add_argument("--segundo", type=float)
    ap.add_argument("--trecho")
    ap.add_argument("--motivo", default="")
    a = ap.parse_args()
    pasta = a.pasta.resolve()
    arq = pasta / "fatos.json"

    if a.acao == "marcar":
        videos, trechos = carregar_videos(pasta)
        antigos = ler_json(arq)["itens"] if arq.exists() else []
        itens = mesclar(marcar_transcricoes(videos, a.tudo), antigos)
        definir_status(itens, trechos)
        salvar_json(arq, {"versao": 1, "itens": itens})
        print(bloco_do_cartao(itens, a.tudo))
        print(f"\nok  {arq}")
        return
    if not arq.exists():
        erro("rode fatos.py marcar antes")
    dados = ler_json(arq)
    itens = dados["itens"]
    if a.acao == "mostrar":
        print(bloco_do_cartao(itens, a.tudo))
    elif a.acao == "pendentes":
        p = pendentes(itens)
        for i in p:
            print(f"  {i['id']}. {tempo(i['tempo'])} {i['motivo']}: \"{i['trecho']}\"")
        if p:
            erro(f"{len(p)} ponto(s) sem resposta: o vídeo inteiro só depois delas", 1)
        print("ok  nenhuma pendência")
    elif a.acao == "responder":
        if a.id is None or not a.status:
            erro("use: fatos.py responder ID --pasta ... --status confirmado|corrigir|cortar")
        alvo = next((i for i in itens if i["id"] == a.id), None)
        if alvo is None:
            erro(f"não existe o ponto {a.id}")
        if a.status == "corrigir" and not a.nota:
            erro("diga o valor certo com --nota")
        alvo["status"], alvo["nota"] = a.status, a.nota
        salvar_json(arq, dados)
        print(f"ok  ponto {a.id}: {a.status}{' (' + a.nota + ')' if a.nota else ''}")
        if a.status != "confirmado":
            print("Ajuste a legenda e o cortes.json e rode de novo o que vem depois.")
    else:
        if a.segundo is None or not a.trecho:
            erro("use: fatos.py adicionar --pasta ... --video N --segundo S --trecho \"texto\" --motivo \"...\"")
        itens.append({"tipo": "manual", "gravidade": ALTA, "video": a.video, "tempo": round(a.segundo, 2),
                      "frase": a.trecho, "trecho": a.trecho, "motivo": a.motivo or MOTIVOS["manual"],
                      "pergunta": PERGUNTAS["manual"], "status": "pendente", "fica": True})
        itens.sort(key=lambda i: (i["video"], i["tempo"]))
        for k, i in enumerate(itens, 1):
            i["id"] = k
        salvar_json(arq, {**dados, "itens": itens})
        print(f"ok  ponto marcado ({len(itens)} no total)")


if __name__ == "__main__":
    main()
