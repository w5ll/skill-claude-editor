"""Publicidade: acha o melhor gancho entre TODAS as frases do vídeo (inclusive a do fim), puxa para o começo e acerta o roteiro.

Uso:
    python publicidade.py listar  --pasta saida/2026-10-22_tema [--perfil NOME]
    python publicidade.py aplicar --pasta saida/2026-10-22_tema [--unidade N | --auto]

listar   olha as frases inteiras do vídeo já cortado (a frase vai até o ponto, a interrogação ou a
         exclamação, mesmo que tenha pausas no meio), dá uma nota a cada uma e grava publicidade.json
         com as melhores. A nota premia: falar com a pessoa ("você"), dizer para quem é, trazer
         resultado ou prova (número, "crescendo", "indicaria"), fazer pergunta, abrir sem enrolação e
         durar pouco. Chamada para ação ("me segue", "comente", "clique") não é gancho: fica no fim.
aplicar  puxa a frase escolhida para o começo (--unidade N, da lista) ou a melhor (--auto, que não
         faz nada se o começo já é tão bom quanto). O roteiro é acertado junto:
           - a frase sai do lugar de onde estava, sem ficar repetida (pode ser a última do vídeo);
           - "e", "então", "aí", "de fato"... soltos no começo da frase puxada saem;
           - uma saudação solta que abria o vídeo sai;
           - o resto segue na ordem em que foi falado, e a chamada para ação continua no fim.

Só frases inteiras mudam de lugar, cortadas no silêncio entre as palavras. Nunca se inventa frase
nem se junta metade de uma frase com metade de outra. A versão anterior do cortes.json fica em
cortes.anterior.json. Depois de aplicar, rode de novo rosto, elementos, câmera e legenda.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from comum import definir_perfil, erro, ler_json, salvar_json, tempo
from gancho import (MULETAS, _corte_antes, _corte_depois, _texto, eh_saudacao, frases_do_corte,
                    guardar_versao, norm, palavras_por_trecho, sha, sinais)

MIN_PALAVRAS = 4
MAX_S = 35.0                 # uma frase maior que isto não serve de gancho
IDEAL_S = 8.0
GANHO_AUTO = 2               # --auto só puxa se a melhor tem isto de pontos a mais que o começo atual
TOPO = 5

PUBLICO = {"advogado", "advogada", "empresario", "empresaria", "empreendedor", "empreendedora", "medico", "medica",
           "dentista", "dono", "dona", "donos", "gestor", "gestora", "lojista", "quem", "autonomo", "profissional"}
PROVA = {"resultado", "resultados", "crescendo", "crescer", "cresceu", "crescimento", "faturamento", "vendas", "lucro",
         "indicaria", "indico", "recomendo", "recomendaria", "surpreendente", "mudou", "dobrou", "triplicou",
         "economizei", "ganhei", "garantia", "comprovado"}
ACAO = ("segue", "seguir", "comenta", "comente", "clique", "clica", "link", "chama", "chame", "garanta", "aproveite",
        "manda", "mande", "salva", "salve", "compartilha", "compartilhe", "agende", "agenda", "fale", "baixe", "acesse")
CONECTIVOS = {"e", "entao", "ai", "mas", "bom", "olha", "tipo", "ne"}
DEPENDE = {"mas", "entao", "dai", "porque", "pois", "logo", "ou"}     # frase que só se entende com a anterior


def _acao(palavras: list[str]) -> bool:
    ns = [norm(p) for p in palavras]
    return any(n in ACAO for n in ns)


def unidades(trechos: list[dict], pal: list[list[dict]]) -> list[dict]:
    """Frases inteiras (do começo da frase até o ponto final), na ordem do vídeo cortado."""
    frases = frases_do_corte(trechos, pal)
    saida, atual = [], []
    for f in frases:
        if atual and f["comeca"]:
            saida.append(atual)         # a anterior nunca fechou (acabou sem ponto): vira unidade incompleta
            atual = []
        atual.append(f)
        if f["fecha"]:
            saida.append(atual)
            atual = []
    if atual:
        saida.append(atual)
    r = []
    for n, g in enumerate(saida):
        palavras = [p for f in g for p in f["palavras"]]
        r.append({"n": n, "frases": g, "palavras": palavras, "texto": " ".join(palavras),
                  "inicio": g[0]["saida_i"], "fim": g[-1]["saida_f"], "duracao": g[-1]["saida_f"] - g[0]["saida_i"],
                  "completa": bool(g[0]["comeca"] and g[-1]["fecha"])})
    return r


def pontuar(u: dict) -> dict:
    """Nota de gancho de uma frase, com o motivo de cada ponto."""
    ns = [norm(p) for p in u["palavras"]]
    s = sinais(u["palavras"], frase=u["palavras"], frase_dur=0.0)
    sem_enrolacao = not (ns and (ns[0] in MULETAS - CONECTIVOS))
    pts, motivos = 0, []

    def ponto(ok: bool, texto: str):
        nonlocal pts
        if ok:
            pts += 1
            motivos.append(texto)

    ponto(sem_enrolacao, "abre sem enrolação")
    ponto(s["fala_com_a_pessoa"], "fala com a pessoa")
    ponto(s["promessa_ou_tensao"], "traz número, negação forte ou promessa")
    ponto(any(n in PUBLICO for n in ns), "diz para quem é")
    ponto(any(n in PROVA for n in ns), "traz resultado ou prova")
    ponto(any("?" in p for p in u["palavras"]), "faz uma pergunta")
    ponto(u["duracao"] <= IDEAL_S, "é curta")
    if u["duracao"] > 20:
        pts -= 1
        motivos.append("é longa (desconta 1 ponto)")
    if ns and ns[0] in DEPENDE:
        pts -= 1
        motivos.append("só se entende com a frase anterior (desconta 1 ponto)")
    if _acao(u["palavras"]):
        pts -= 2
        motivos.append("é chamada para ação (desconta 2 pontos)")
    return {"nota": max(0, pts), "motivos": motivos}


def candidatas(uns: list[dict]) -> list[dict]:
    r = []
    for u in uns:
        if not u["completa"] or len(u["palavras"]) < MIN_PALAVRAS or u["duracao"] > MAX_S:
            continue
        if eh_saudacao(u["frases"][0]) or _acao(u["palavras"]):
            continue
        p = pontuar(u)
        r.append({"unidade": u["n"], "nota": p["nota"], "motivos": p["motivos"], "texto": u["texto"],
                  "inicio": round(u["inicio"], 2), "duracao": round(u["duracao"], 2), "e_a_primeira": u["n"] == 0})
    return sorted(r, key=lambda c: (-c["nota"], c["inicio"]))


def listar(trechos: list[dict], pal: list[list[dict]]) -> dict:
    uns = unidades(trechos, pal)
    cands = candidatas(uns)
    atual = pontuar(uns[0])["nota"] if uns else 0
    return {"nota_do_comeco": atual, "texto_do_comeco": uns[0]["texto"] if uns else "",
            "candidatas": cands[:TOPO], "frases": len(uns)}


# ---------- roteiro ----------

def _sem_conectivos(ws: list[dict], k0: int, k1: int) -> int:
    """Primeiro índice depois de "e", "então", "aí", "de fato"... soltos no começo (sobram pelo menos 4 palavras)."""
    k = k0
    while k1 - k >= MIN_PALAVRAS:
        n = norm(ws[k]["p"])
        if n in CONECTIVOS:
            k += 1
        elif n == "de" and norm(ws[k + 1]["p"]) == "fato":
            k += 2
        else:
            break
    return k


def _pedacos(u: dict, aparar: bool) -> list[tuple[int, int, int]]:
    """(trecho, k0, k1) de cada parte contínua da frase; `aparar` tira conectivos do começo."""
    partes: list[list[int]] = []
    for f in u["frases"]:
        if partes and partes[-1][0] == f["trecho"] and partes[-1][2] + 1 == f["k0"]:
            partes[-1][2] = f["k1"]
        else:
            partes.append([f["trecho"], f["k0"], f["k1"]])
    return [(a, b, c) for a, b, c in partes]


def _recorte(trechos, pal, n: int, k0: int, k1: int) -> dict:
    t, ws = trechos[n], pal[n]
    a = _corte_antes(ws, k0, t["inicio"]) if k0 > 0 else t["inicio"]
    b = _corte_depois(ws, k1, t["fim"]) if k1 + 1 < len(ws) else t["fim"]
    return {**t, "inicio": round(a, 3), "fim": round(b, 3), "texto": _texto(ws, a, b)}


def puxar(trechos: list[dict], pal: list[list[dict]], uns: list[dict], escolhida: int) -> list[dict]:
    """Novos trechos: a frase escolhida primeiro (sem conectivos soltos) e o resto na ordem em que foi falado."""
    alvo = next(u for u in uns if u["n"] == escolhida)
    saida: list[dict] = []
    ultimo: tuple[int, int] | None = None       # (trecho, k1) da última parte colocada, para juntar partes contínuas
    for n, k0, k1 in _pedacos(alvo, True):
        if not saida:
            k0 = _sem_conectivos(pal[n], k0, k1)
        saida.append(_recorte(trechos, pal, n, k0, k1))
    for u in uns:
        if u["n"] == escolhida:
            ultimo = None
            continue
        if u["n"] == 0 and escolhida != 0 and eh_saudacao(u["frases"][0]):
            ultimo = None
            continue                            # a saudação que abria o vídeo sai: o gancho já abriu
        for n, k0, k1 in _pedacos(u, False):
            novo = _recorte(trechos, pal, n, k0, k1)
            if ultimo and ultimo[0] == n and ultimo[1] + 1 == k0:
                ant = saida[-1]                 # continua a mesma fala: junta, sem criar emenda nova
                ant["fim"], ant["texto"] = novo["fim"], _texto(pal[n], ant["inicio"], novo["fim"])
            else:
                saida.append(novo)
            ultimo = (n, k1)
    return saida


def roteiro_final(novos: list[dict]) -> list[str]:
    return [t["texto"] for t in novos]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["listar", "aplicar"])
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--unidade", type=int, help="aplicar: a frase da lista (campo \"unidade\")")
    ap.add_argument("--auto", action="store_true", help="aplicar: usa a melhor, se o começo ainda não é tão bom")
    ap.add_argument("--perfil", help="perfil de marca (padrão: o da pasta do trabalho)")
    a = ap.parse_args()
    definir_perfil(a.perfil)
    pasta = a.pasta.resolve()
    arq_cortes = pasta / "cortes.json"
    if not arq_cortes.exists():
        erro("rode propor_cortes.py antes")
    cortes = ler_json(arq_cortes)
    pal = palavras_por_trecho(pasta, cortes)
    r = listar(cortes["trechos"], pal)
    r["cortes_sha"] = sha(arq_cortes)
    saida = pasta / "publicidade.json"

    if a.acao == "listar":
        salvar_json(saida, r)
        print(f"Começo atual: nota {r['nota_do_comeco']}  \"{r['texto_do_comeco'][:90]}\"")
        if not r["candidatas"]:
            print("  nenhuma frase serve de gancho (todas muito curtas, longas ou chamada para ação)")
        for c in r["candidatas"]:
            marca = "  (já é a primeira)" if c["e_a_primeira"] else ""
            print(f"\nunidade {c['unidade']}: nota {c['nota']}, em {tempo(c['inicio'])} ({c['duracao']} s){marca}\n"
                  f"  {c['texto']}\n  porque: {', '.join(c['motivos']) or 'nada se destaca'}")
        print(f"\nok  {saida}")
        return

    if a.auto == (a.unidade is not None):
        erro("use --unidade N ou --auto (um dos dois)")
    if not r["candidatas"]:
        print("sem gancho melhor: nenhuma frase serve")
        return
    if a.auto:
        melhor = r["candidatas"][0]
        if melhor["e_a_primeira"] or melhor["nota"] < r["nota_do_comeco"] + GANHO_AUTO:
            print(f"o começo já prende (nota {r['nota_do_comeco']}): nada a puxar")
            return
        escolhida = melhor["unidade"]
    else:
        if a.unidade not in [c["unidade"] for c in r["candidatas"]]:
            erro(f"a unidade {a.unidade} não está na lista: rode publicidade.py listar")
        escolhida = a.unidade
    uns = unidades(cortes["trechos"], pal)
    novos = puxar(cortes["trechos"], pal, uns, escolhida)
    copia = guardar_versao(arq_cortes)
    cortes["trechos"] = novos
    cortes["duracao_final"] = round(sum(t["fim"] - t["inicio"] for t in novos), 2)
    cortes["gancho_publicidade"] = {"unidade": escolhida, "texto": next(u["texto"] for u in uns if u["n"] == escolhida)}
    salvar_json(arq_cortes, cortes)
    print(f"gancho puxado para o começo: {cortes['gancho_publicidade']['texto']}")
    print("roteiro agora:")
    for k, texto in enumerate(roteiro_final(novos), 1):
        print(f"  {k}. {texto}")
    print(f"ok  {arq_cortes} (versão anterior em {copia.name}). Rode de novo: rosto, elementos, câmera e legenda")


if __name__ == "__main__":
    main()
