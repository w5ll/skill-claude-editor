"""Cenas explicativas: texto e números animados, cada parte entrando quando é falada.

Uso:
    python cenas.py sugerir  --pasta saida/2026-10-22_tema
    python cenas.py aplicar N --pasta saida/... [--modo painel|tela]
    python cenas.py validar  --pasta saida/...
    python cenas.py previa   --pasta saida/... [--formato 9:16@1080]

Tipos: lista (passos numerados), antes-depois, numero (um número que sobe) e de-para (um número
que vira outro). Modos: painel (cartão no lugar livre do quadro, fora do rosto) e tela (a tela
inteira por até 6 s). A cena é um item do elementos.json com "elemento": "cena:TIPO"; quem desenha
é o elementos.py, com templates/cenas.html. Veja docs/fase-12-cenas-explicativas.md.

sugerir   lê a fala já cortada e propõe cenas (cenas-sugeridas.json): ordens seguidas ("primeiro",
          "segundo"...), "antes... agora", "de X para Y" e os números mais fortes. O texto sai das
          próprias palavras da pessoa: resuma e corrija antes de mostrar.
aplicar   transforma a proposta N em item do elementos.json (recusa se encosta em outro elemento).
validar   confere cada cena: limites, sincronia, gatilho falado, número falado, folga dos outros.
previa    monta cenas-previa.jpg: um quadro em cada momento em que algo entra, sobre o vídeo.

Todo número da cena tem que ter sido falado. A cena resume a fala: nunca afirma algo novo.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

from comum import arquivo_da_fonte, carregar_marca, definir_perfil, erro, ler_json, salvar_json, tempo

TIPOS = ("lista", "antes-depois", "numero", "de-para")
LIMITE_PALAVRAS = {"titulo": 6, "texto": 6, "rotulo": 5}
PASSOS = (2, 5)
DURACAO = {"sobreposto": (3.0, 14.0), "tela": (2.0, 6.0)}
FOLGA = 1.5                 # segundos entre a cena e outro elemento
LEITURA = 2.2               # depois do último gatilho, a cena fica isto para dar tempo de ler
ANTES_DA_FALA = 0.05        # cada parte entra um pouco antes da palavra
ENTRADA = 0.6               # a cena começa isto antes da primeira parte (a entrada leva 0,45 s)
MAX_ORDENS = 40.0           # segundos entre a primeira e a última ordem de uma lista
MAX_ANTES_DEPOIS = 10.0
ALTURA_PAINEL = {"lista": (0.09, 0.092, 0.11), "antes-depois": 0.60, "numero": 0.42, "de-para": 0.64}
SEGURO_TOPO, SEGURO_BASE = 0.12, 0.80      # como a legenda: nada importante fora disso
FOLGA_ROSTO = 0.02
ENCOLHE_MIN = 0.8          # o painel pode encolher até 80% para caber fora do rosto

ORDINAIS = {"primeiro": 1, "primeira": 1, "segundo": 2, "segunda": 2, "terceiro": 3, "terceira": 3,
            "quarto": 4, "quarta": 4, "quinto": 5, "quinta": 5}
APOS_ORDEM = {"passo", "lugar", "ponto", "motivo", "erro", "dica", "caso", "de", "e", "que", "é"}
MARCAS_DEPOIS = {"agora", "hoje", "depois", "atualmente"}
NAO_ANTES = {"de", "que", "disso", "mesmo", "do", "da", "dos", "das", "tudo"}
UNIDADES_ROTULO = {"anos", "meses", "dias", "horas", "minutos", "semanas", "clientes", "pessoas", "contratos",
                   "leads", "processos", "casos", "empresas", "vezes", "reais"}

UNIDADES = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
            "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
            "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20,
            "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70, "oitenta": 80,
            "noventa": 90, "cem": 100, "cento": 100, "duzentos": 200, "trezentos": 300, "quatrocentos": 400,
            "quinhentos": 500, "seiscentos": 600, "setecentos": 700, "oitocentos": 800, "novecentos": 900}
MULTIPLOS = {"mil": 1e3, "milhao": 1e6, "milhoes": 1e6, "bilhao": 1e9, "bilhoes": 1e9}
NOME_MULTIPLO = {"mil": " mil", "milhao": " milhão", "milhoes": " milhões", "bilhao": " bilhão", "bilhoes": " bilhões"}


def norm(p: str) -> str:
    t = unicodedata.normalize("NFKD", p.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"^[^a-z0-9$%]+|[^a-z0-9%]+$", "", t)


def limpo(p: str) -> str:
    return re.sub(r"^[^\w$%]+|[^\w%]+$", "", p)


def numero_digitos(tok: str) -> float | None:
    if not re.fullmatch(r"\d+(?:[.,]\d+)*%?", tok):
        return None
    n = tok.rstrip("%")
    n = n.replace(".", "") if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", n) else n.replace(",", ".")
    try:
        return float(n)
    except ValueError:
        return None


# ---------- números falados ----------

def ler_numero(palavras: list[dict], k: int) -> dict | None:
    """O número que começa na palavra k, como a pessoa falou, pronto para a cena.

    Devolve valor (o que aparece), sufixo, prefixo, total (valor real), rotulo (unidade que vem depois) e as
    posições das palavras (ini, fim).
    """
    toks = [norm(w["p"]) for w in palavras]
    n = len(toks)
    t = toks[k]
    prefixo = "R$ " if k > 0 and palavras[k - 1]["p"].strip().lower() in ("r$", "rs") else ""
    ini = k - 1 if prefixo else k
    valor, total, sufixo, fim = None, None, "", k
    dig = numero_digitos(t)
    if dig is not None:
        valor = total = dig
        if t.endswith("%"):
            sufixo = "%"
        if k + 1 < n and toks[k + 1] in MULTIPLOS:
            fim = k + 1
            total = dig * MULTIPLOS[toks[k + 1]]
            sufixo += NOME_MULTIPLO[toks[k + 1]]
    elif t in UNIDADES or t in MULTIPLOS:
        atual, soma, cabeca, ultimo_mult, j = 0.0, 0.0, None, None, k
        while j < n:
            x = toks[j]
            if x in UNIDADES:
                atual += UNIDADES[x]
            elif x in MULTIPLOS:
                parte = atual if atual else 1.0
                soma += parte * MULTIPLOS[x]
                cabeca, ultimo_mult, atual = parte, x, 0.0
            elif x == "e" and j + 1 < n and (toks[j + 1] in UNIDADES or toks[j + 1] in MULTIPLOS):
                pass
            else:
                break
            j += 1
        fim = j - 1
        total = soma + atual
        if ultimo_mult and atual == 0 and cabeca is not None:
            valor, sufixo = cabeca, NOME_MULTIPLO[ultimo_mult]
            if ultimo_mult in ("milhao", "bilhao") and cabeca > 1:
                sufixo = NOME_MULTIPLO["milhoes" if ultimo_mult == "milhao" else "bilhoes"]
        else:
            valor = total
    else:
        return None
    rotulo = ""
    prox = toks[fim + 1] if fim + 1 < n else ""
    if prox == "por" and fim + 2 < n and toks[fim + 2] == "cento":
        sufixo, fim = "%", fim + 2
    elif prox in ("reais", "real"):
        prefixo, fim = prefixo or "R$ ", fim + 1
    elif prox in UNIDADES_ROTULO:
        rotulo, fim = limpo(palavras[fim + 1]["p"]), fim + 1
    return {"valor": valor, "total": total, "prefixo": prefixo, "sufixo": sufixo, "rotulo": rotulo,
            "ini": ini, "fim": fim, "fala_em": palavras[ini]["i"]}


def valores_falados(palavras: list[dict]) -> set[float]:
    """Todos os valores que a fala diz, inclusive a parte antes do "mil" ("cento e trinta mil" dá 130000 e 130)."""
    saida: set[float] = set()
    k = 0
    while k < len(palavras):
        r = ler_numero(palavras, k)
        if r is None:
            k += 1
            continue
        saida.update({round(r["total"], 6), round(r["valor"], 6)})
        k = max(k + 1, r["fim"] + 1)
    return saida


def valor_de_cena_falado(o: dict, falados: set[float]) -> bool:
    v = float(o["valor"])
    candidatos = {v}
    suf = str(o.get("sufixo", ""))
    for nome, mult in (("mil", 1e3), ("milh", 1e6), ("bilh", 1e9)):
        if nome in suf:
            candidatos.add(v * mult)
    return any(round(c, 6) in falados for c in candidatos)


# ---------- sugerir ----------

def fim_de_trecho(palavras: list[dict], k: int, maximo: int = 6) -> int:
    """Índice da última palavra do trecho que começa em k: até a pontuação, uma pausa ou `maximo` palavras."""
    f = k
    while f + 1 < len(palavras) and f - k + 1 < maximo:
        if re.search(r"[.?!…;:]$", palavras[f]["p"]) or palavras[f + 1]["i"] - palavras[f]["f"] > 0.5:
            break
        f += 1
    return f


def texto_de(palavras: list[dict], a: int, b: int) -> str:
    t = " ".join(limpo(w["p"]) for w in palavras[a:b + 1] if limpo(w["p"]))
    return t[:1].upper() + t[1:]


def comeca_frase(palavras: list[dict], k: int) -> bool:
    return k == 0 or bool(re.search(r"[.?!…,;:]$", palavras[k - 1]["p"])) or palavras[k]["i"] - palavras[k - 1]["f"] >= 0.3


def listas(palavras: list[dict]) -> list[dict]:
    toks = [norm(w["p"]) for w in palavras]
    achados = []
    for k, t in enumerate(toks):
        o = ORDINAIS.get(t)
        if o is None:
            continue
        seguinte = toks[k + 1] if k + 1 < len(toks) else ""
        if not (comeca_frase(palavras, k) or seguinte in ("passo", "lugar", "ponto", "motivo", "erro", "dica", "caso")):
            continue
        achados.append((o, k))
    saida, usados = [], set()
    for a, (o, k) in enumerate(achados):
        if o != 1 or k in usados:
            continue
        cadeia = [(o, k)]
        for o2, k2 in achados[a + 1:]:
            if o2 == cadeia[-1][0] + 1 and palavras[k2]["i"] - palavras[cadeia[-1][1]]["i"] <= MAX_ORDENS:
                cadeia.append((o2, k2))
        if len(cadeia) < PASSOS[0]:
            continue
        cadeia = cadeia[:PASSOS[1]]
        passos = []
        for o2, k2 in cadeia:
            a2 = k2 + 1
            while a2 < len(palavras) and norm(palavras[a2]["p"]) in APOS_ORDEM:
                a2 += 1
            if a2 >= len(palavras):
                a2 = k2 + 1
            b2 = fim_de_trecho(palavras, a2)
            passos.append({"texto": texto_de(palavras, a2, b2), "gatilho": limpo(palavras[k2]["p"]).lower(),
                           "fala_em": round(palavras[k2]["i"], 2)})
            usados.add(k2)
        saida.append({"tipo": "lista", "cena": {"titulo": "", "passos": passos}})
    return saida


ABERTURA = 3                # palavras da abertura que se repete ("Seu objetivo é...")
MAX_PASSO_REPETIDO = 8      # palavras entre uma abertura e a seguinte
ARTIGOS = {"a", "o", "as", "os", "de", "do", "da", "que", "e", "um", "uma", "eu", "se", "em", "no", "na", "para",
           "com", "nao", "mais", "ser", "tem", "gente", "voce", "isso", "como", "mas", "por"}


def repetidas(palavras: list[dict]) -> list[dict]:
    """Lista dita sem ordinais: a mesma abertura 3 ou mais vezes, cada vez seguida de um item curto.

    Exemplo: "Seu objetivo é aposentar seus pais. Seu objetivo é comprar uma casa. Seu objetivo é ter..."
    """
    toks = [norm(w["p"]) for w in palavras]
    saida, usados = [], set()
    for k in range(len(toks) - ABERTURA):
        gram = tuple(toks[k:k + ABERTURA])
        if k in usados or not all(gram) or all(g in ARTIGOS for g in gram) or sum(g not in ARTIGOS for g in gram) < 2:
            continue
        pos, j = [k], k + ABERTURA
        while j + ABERTURA <= len(toks) and palavras[j]["i"] - palavras[k]["i"] <= MAX_ORDENS:
            if tuple(toks[j:j + ABERTURA]) == gram:
                pos.append(j)
                j += ABERTURA
            else:
                j += 1
        if len(pos) < 3:
            continue
        pos = pos[:PASSOS[1]]
        passos, ok = [], True
        for n, a in enumerate(pos):
            ini = a + ABERTURA
            fim = (pos[n + 1] - 1) if n + 1 < len(pos) else fim_de_trecho(palavras, ini)
            if fim - ini + 1 < 1 or fim - ini + 1 > MAX_PASSO_REPETIDO:
                ok = False
                break
            passos.append({"texto": texto_de(palavras, ini, min(fim, ini + LIMITE_PALAVRAS["texto"] - 1)),
                           "gatilho": limpo(palavras[ini]["p"]).lower(), "fala_em": round(palavras[ini]["i"], 2)})
        if ok:
            usados.update(pos)
            saida.append({"tipo": "lista", "cena": {"titulo": "", "passos": passos}})
    return saida


def antes_depois(palavras: list[dict]) -> list[dict]:
    toks = [norm(w["p"]) for w in palavras]
    saida = []
    for k, t in enumerate(toks):
        if t != "antes" or (k + 1 < len(toks) and toks[k + 1] in NAO_ANTES):
            continue
        for m in range(k + 1, len(toks)):
            if palavras[m]["i"] - palavras[k]["i"] > MAX_ANTES_DEPOIS:
                break
            if toks[m] in MARCAS_DEPOIS:
                a1, b1 = k + 1, fim_de_trecho(palavras, k + 1)
                if b1 >= m:
                    b1 = max(a1, m - 1)
                a2, b2 = m + 1, fim_de_trecho(palavras, m + 1)
                if a1 > b1 or a2 >= len(palavras):
                    break
                saida.append({"tipo": "antes-depois", "cena": {
                    "antes": {"texto": texto_de(palavras, a1, b1), "gatilho": "antes", "fala_em": round(palavras[k]["i"], 2)},
                    "depois": {"texto": texto_de(palavras, a2, b2), "gatilho": toks[m],
                               "fala_em": round(palavras[m]["i"], 2)}}})
                break
    return saida


def numeros_e_de_para(palavras: list[dict]) -> tuple[list[dict], list[dict]]:
    toks = [norm(w["p"]) for w in palavras]
    achados, k = [], 0
    while k < len(palavras):
        r = ler_numero(palavras, k)
        if r is None:
            k += 1
            continue
        achados.append(r)
        k = max(k + 1, r["fim"] + 1)
    de_para, usados = [], set()
    for a, r in enumerate(achados):
        if r["ini"] > 0 and toks[r["ini"] - 1] == "de" and r["fim"] + 2 < len(toks) and toks[r["fim"] + 1] in ("para", "a"):
            nxt = next((x for x in achados[a + 1:] if x["ini"] == r["fim"] + 2), None)
            if nxt:
                rot = nxt["rotulo"] or r["rotulo"]
                de_para.append({"tipo": "de-para", "cena": {
                    "de": {"valor": r["valor"], "prefixo": r["prefixo"], "sufixo": r["sufixo"],
                           "fala_em": round(r["fala_em"], 2)},
                    "para": {"valor": nxt["valor"], "prefixo": nxt["prefixo"], "sufixo": nxt["sufixo"],
                             "fala_em": round(nxt["fala_em"], 2)},
                    "rotulo": rot, "decimais": decimais(r["valor"], nxt["valor"])}})
                usados.update({id(r), id(nxt)})
    fortes = [r for r in achados if id(r) not in usados and (r["prefixo"] or "%" in r["sufixo"] or r["sufixo"].strip())]
    fortes.sort(key=lambda r: (not (r["prefixo"] or "%" in r["sufixo"]), -r["total"]))
    numeros = [{"tipo": "numero", "cena": {"valor": r["valor"], "prefixo": r["prefixo"], "sufixo": r["sufixo"],
                                           "rotulo": r["rotulo"], "decimais": decimais(r["valor"]),
                                           "fala_em": round(r["fala_em"], 2)}} for r in fortes[:2]]
    return numeros, de_para


def decimais(*valores: float) -> int:
    return 1 if any(abs(v - round(v)) > 1e-9 for v in valores) else 0


def momentos(item: dict) -> list[float]:
    """Os segundos do vídeo cortado em que cada parte da cena é falada."""
    c = item["cena"]
    t = item.get("tipo") or tipo_do_item(item)
    if t == "lista":
        return [p["fala_em"] for p in c["passos"]]
    if t == "antes-depois":
        return [c["antes"]["fala_em"], c["depois"]["fala_em"]]
    if t == "numero":
        return [c["fala_em"]]
    return [c["de"]["fala_em"], c["para"]["fala_em"]]


def montar_item(tipo: str, cena: dict, modo: str = "sobreposto") -> dict:
    """O item do elementos.json de uma proposta: começa um pouco antes da primeira parte e vai até ler a última."""
    base = {"tipo": tipo, "cena": cena}
    falas = momentos(base)
    inicio = max(0.0, round(falas[0] - ENTRADA, 2))
    duracao = round(falas[-1] + LEITURA - inicio, 2)
    lo, hi = DURACAO[modo]
    duracao = max(lo, min(hi, duracao))
    if tipo == "numero":
        duracao = max(duracao, 3.5)
    return {"elemento": f"cena:{tipo}", "inicio": inicio, "duracao": duracao, "modo": modo, "posicao": "auto",
            "texto": "", "gatilho": "", "fala_em": falas[0], "cena": cena}


def sugerir(palavras: list[dict]) -> list[dict]:
    numeros, de_para = numeros_e_de_para(palavras)
    propostas = []
    em_lista = listas(palavras)
    # lista sem ordinais só entra se não repetir uma que os ordinais já acharam
    ocupados = [(c["cena"]["passos"][0]["fala_em"], c["cena"]["passos"][-1]["fala_em"]) for c in em_lista]
    sem_ordem = [c for c in repetidas(palavras)
                 if not any(a - 1 <= c["cena"]["passos"][0]["fala_em"] <= b + 1 for a, b in ocupados)]
    for p in em_lista + sem_ordem + antes_depois(palavras) + de_para + numeros:
        item = montar_item(p["tipo"], p["cena"])
        propostas.append({"tipo": p["tipo"], "item": item})
    return sorted(propostas, key=lambda p: p["item"]["inicio"])


# ---------- validar ----------

def tipo_do_item(item: dict) -> str:
    return str(item["elemento"]).split(":", 1)[1]


def eh_cena(item: dict) -> bool:
    return str(item.get("elemento", "")).startswith("cena:")


def palavras_de(texto: str) -> int:
    return len(texto.split())


def validar_item(item: dict, palavras: list[dict], outros: list[tuple[float, float]]) -> list[str]:
    p = []
    t = tipo_do_item(item)
    c = item.get("cena") or {}
    nome = f"cena {t} em {tempo(item['inicio'])}"
    if t not in TIPOS:
        return [f"{nome}: tipo desconhecido (use {', '.join(TIPOS)})"]
    modo = item.get("modo")
    if modo not in DURACAO:
        return [f"{nome}: o modo é sobreposto (painel) ou tela"]
    lo, hi = DURACAO[modo]
    if not lo <= item["duracao"] <= hi:
        p.append(f"{nome}: no modo {'tela' if modo == 'tela' else 'painel'} a cena dura de {lo:g} a {hi:g} s (está com {item['duracao']:g})")
    falas = []
    try:
        falas = momentos({"tipo": t, "cena": c})
    except (KeyError, TypeError):
        return p + [f"{nome}: faltam campos da cena (veja docs/fase-12-cenas-explicativas.md)"]

    def limite(texto: str, campo: str):
        if palavras_de(str(texto)) > LIMITE_PALAVRAS[campo]:
            p.append(f"{nome}: \"{texto}\" tem mais de {LIMITE_PALAVRAS[campo]} palavras")

    if c.get("titulo"):
        limite(c["titulo"], "titulo")
    if c.get("rotulo"):
        limite(c["rotulo"], "rotulo")
    falados = valores_falados(palavras)
    if t == "lista":
        n = len(c["passos"])
        if not PASSOS[0] <= n <= PASSOS[1]:
            p.append(f"{nome}: a lista tem de {PASSOS[0]} a {PASSOS[1]} passos (tem {n})")
        for i, ps in enumerate(c["passos"], 1):
            if not str(ps.get("texto", "")).strip():
                p.append(f"{nome}: o passo {i} está sem texto")
            else:
                limite(ps["texto"], "texto")
    elif t == "antes-depois":
        for lado in ("antes", "depois"):
            if not str(c[lado].get("texto", "")).strip():
                p.append(f"{nome}: o {lado} está sem texto")
            else:
                limite(c[lado]["texto"], "texto")
    else:
        for campo in (["valor"] if t == "numero" else ["de", "para"]):
            o = c if t == "numero" else c[campo]
            if "valor" not in o:
                p.append(f"{nome}: falta o valor")
            elif not valor_de_cena_falado(o, falados):
                p.append(f"{nome}: o número {o.get('prefixo', '')}{o['valor']:g}{o.get('sufixo', '')} não foi falado. "
                         "Todo número da cena tem que estar na fala")
    if falas != sorted(falas):
        p.append(f"{nome}: as partes têm que entrar na ordem em que são faladas")
    for f in falas:
        if not item["inicio"] <= f <= item["inicio"] + item["duracao"] - 0.8:
            p.append(f"{nome}: a parte falada em {tempo(f)} fica fora da cena ou sem tempo de leitura "
                     f"(a cena vai de {tempo(item['inicio'])} a {tempo(item['inicio'] + item['duracao'])})")
    # gatilho: a palavra existe na fala, no momento dito
    gatilhos = []
    if t == "lista":
        gatilhos = [(ps.get("gatilho"), ps["fala_em"]) for ps in c["passos"]]
    elif t == "antes-depois":
        gatilhos = [(c["antes"].get("gatilho"), c["antes"]["fala_em"]), (c["depois"].get("gatilho"), c["depois"]["fala_em"])]
    for g, f in gatilhos:
        if g and not any(norm(w["p"]) == norm(str(g)) and abs(w["i"] - f) <= 0.6 for w in palavras):
            p.append(f"{nome}: não achei \"{g}\" na fala perto de {tempo(f)}")
    for a, b in outros:
        if item["inicio"] < b + FOLGA and item["inicio"] + item["duracao"] > a - FOLGA:
            p.append(f"{nome}: encosta em outro elemento ({tempo(a)} a {tempo(b)}); deixe {FOLGA:g} s de folga")
    return p


def validar(itens: list[dict], palavras: list[dict]) -> list[str]:
    cenas = [(i, it) for i, it in enumerate(itens) if eh_cena(it)]
    problemas = []
    for i, it in cenas:
        outros = [(o["inicio"], o["inicio"] + o["duracao"]) for j, o in enumerate(itens) if j != i]
        problemas += validar_item(it, palavras, outros)
    return problemas


# ---------- lugar do painel ----------

def altura_do_painel(item: dict, largura: int) -> int:
    u = largura * 0.88
    t = tipo_do_item(item)
    if t == "lista":
        base, titulo, linha = ALTURA_PAINEL["lista"]
        c = item["cena"]
        h = u * (base + (titulo if c.get("titulo") else 0) + linha * len(c["passos"]))
    else:
        h = u * ALTURA_PAINEL[t]
    return int(round(h / 2) * 2)


def resolver_caixa(item: dict, largura: int, altura: int, rostos, camera) -> str | None:
    """Põe o painel fora do rosto, acima ou abaixo (com o zoom da câmera). Grava item['caixa_usada'] = [x, y, w, h]."""
    item.pop("caixa_usada", None)
    if item["modo"] == "tela":
        return None
    w = int(round(largura * 0.88 / 2) * 2)
    h = altura_do_painel(item, largura)
    x = (largura - w) // 2
    topo, base = altura * SEGURO_TOPO, altura * SEGURO_BASE
    zonas = []
    if rostos is not None:
        from rosto import zona_protegida
        for t, r in rostos.amostras(item["inicio"], item["inicio"] + item["duracao"]):
            z = zona_protegida(r)
            zonas.append(camera.na_tela(z, t) if camera else z)
    if not zonas:
        item["caixa_usada"] = [x, int(topo), w, h]
        return None
    zy0, zy1 = min(z[1] for z in zonas), max(z[3] for z in zonas)
    folga = altura * FOLGA_ROSTO
    acima = (zy0 - folga - h, zy0 - folga)
    abaixo = (zy1 + folga, zy1 + folga + h)
    for y0, y1 in (acima, abaixo):
        if y0 >= topo and y1 <= base:
            item["caixa_usada"] = [x, int(round(y0)), w, h]
            return None
    # a folga cheia não coube: encolhe o painel até 20% (a altura é proporcional à largura)
    for livre_y0, livre_y1 in ((topo, zy0 - folga), (zy1 + folga, base)):
        disponivel = livre_y1 - livre_y0
        if h * ENCOLHE_MIN <= disponivel < h:
            k = disponivel / h
            w2, h2 = int(w * k) // 2 * 2, int(h * k) // 2 * 2
            item["caixa_usada"] = [(largura - w2) // 2, int(round(livre_y0)), w2, h2]
            return None
    # ainda não coube: aceita uma folga menor (um quarto) antes de desistir
    minima = folga / 4
    if topo + h <= zy0 - minima:
        item["caixa_usada"] = [x, int(round(max(topo, zy0 - folga - h))), w, h]
        return None
    if base - h >= zy1 + minima:
        item["caixa_usada"] = [x, int(round(min(base - h, zy1 + folga))), w, h]
        return None
    # não coube: o que invade menos o rosto
    y0 = max(topo, min(zy0 - folga - h, base - h))
    item["caixa_usada"] = [x, int(round(y0)), w, h]
    return (f"a cena em {item['inicio']:.1f} s não cabe fora do rosto: use o modo tela, encurte a cena "
            "ou tire um passo")


# ---------- configuração da página ----------

def cfg_da_cena(item: dict, w: int, h: int, marca: dict) -> dict:
    """O que o molde cenas.html recebe. Os tempos 'em' são desde o início da cena."""
    t = tipo_do_item(item)
    c = item["cena"]

    def em(f: float) -> float:
        return round(max(ENTRADA - 0.1, f - item["inicio"] - ANTES_DA_FALA), 3)

    if t == "lista":
        cena = {"titulo": c.get("titulo", ""), "passos": [{"texto": p["texto"], "em": em(p["fala_em"])} for p in c["passos"]]}
    elif t == "antes-depois":
        cena = {"antes": {"texto": c["antes"]["texto"]}, "depois": {"texto": c["depois"]["texto"], "em": em(c["depois"]["fala_em"])}}
    elif t == "numero":
        cena = {**{k: c.get(k, "") for k in ("valor", "prefixo", "sufixo", "rotulo")}, "decimais": c.get("decimais", 0),
                "em": em(c["fala_em"])}
    else:
        cena = {"de": c["de"], "para": c["para"], "rotulo": c.get("rotulo", ""), "decimais": c.get("decimais", 0),
                "em": em(c["para"]["fala_em"])}
    return {"tipo": t, "modo": "tela" if item["modo"] == "tela" else "sobreposto", "largura": w, "altura": h,
            "duracao": item["duracao"], "cores": marca["cores"], "cena": cena,
            "fonte": {"familia": marca["legenda"]["fonte"], "url": arquivo_da_fonte(marca).as_uri()}}


# ---------- prévia ----------

def instantes_da_previa(item: dict, cfg: dict) -> list[tuple[float, str]]:
    c = cfg["cena"]
    t = cfg["tipo"]
    if t == "lista":
        marcas = [(p["em"] + 0.6, f"passo {i}") for i, p in enumerate(c["passos"], 1)]
    elif t == "antes-depois":
        marcas = [(0.7, "antes"), (c["depois"]["em"] + 0.6, "depois")]
    elif t == "numero":
        marcas = [(c["em"] + 1.4, "numero")]
    else:
        marcas = [(c["em"] - 0.1, "de"), (c["em"] + 1.5, "para")]
    return [(round(min(x, item["duracao"] - 0.4), 2), nome) for x, nome in marcas]


def previa(pasta: Path, largura: int, altura: int, fps) -> Path:
    import cv2
    import numpy as np
    from elementos import abrir_navegador, quadro_do_video, tamanho_quadro, posicao_quadro, resolver_posicao
    from camera import Camera
    from rosto import Rostos
    from comum import PASTA_SKILL
    arq = pasta / "elementos.json"
    itens = [i for i in ler_json(arq).get("itens", []) if eh_cena(i)] if arq.exists() else []
    if not itens:
        erro("não há cenas no elementos.json: rode cenas.py aplicar antes")
    marca = carregar_marca(pasta=pasta)
    cortes = ler_json(pasta / "cortes.json")
    insp = ler_json(pasta / "inspecao.json")["videos"]
    rostos, camera = Rostos.carregar(pasta, largura, altura), Camera.carregar(pasta, largura, altura)
    molde = (PASTA_SKILL / "templates" / "cenas.html").resolve().as_uri()
    from playwright.sync_api import sync_playwright
    import tempfile
    linhas = []
    with tempfile.TemporaryDirectory() as tmp_txt, sync_playwright() as pw:
        tmp = Path(tmp_txt)
        nav = abrir_navegador(pw)
        for n, item in enumerate(itens):
            aviso = resolver_posicao(item, largura, altura, rostos, camera)
            if aviso:
                print(f"  atenção: {aviso}")
            w, h = tamanho_quadro(item, largura, altura)
            x, y = posicao_quadro(item, largura, altura)
            cfg = cfg_da_cena(item, w, h, marca)
            pagina = nav.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            pagina.goto(molde)
            pagina.evaluate("document.fonts.ready")
            pagina.evaluate("cfg => montar(cfg)", cfg)
            celulas = []
            for k, (t, nome) in enumerate(instantes_da_previa(item, cfg)):
                pagina.evaluate(f"desenhar({t})")
                png = tmp / f"c{n}_{k}.png"
                pagina.screenshot(path=str(png), omit_background=True, clip={"x": 0, "y": 0, "width": w, "height": h})
                fundo = tmp / f"f{n}_{k}.jpg"
                base = cv2.imread(str(fundo)) if quadro_do_video(pasta, cortes, insp, fps, largura, altura, item["inicio"] + t, fundo) else None
                if base is None:
                    base = np.full((768, 432, 3), 40, np.uint8)
                esc = base.shape[1] / largura
                sobre = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
                sobre = cv2.resize(sobre, (max(1, round(w * esc)), max(1, round(h * esc))), interpolation=cv2.INTER_AREA)
                x0, y0 = round(x * esc), round(y * esc)
                hh, ww = min(sobre.shape[0], base.shape[0] - y0), min(sobre.shape[1], base.shape[1] - x0)
                if hh > 0 and ww > 0:
                    a = sobre[:hh, :ww, 3:4] / 255.0
                    base[y0:y0 + hh, x0:x0 + ww] = (sobre[:hh, :ww, :3] * a + base[y0:y0 + hh, x0:x0 + ww] * (1 - a)).astype(np.uint8)
                cv2.putText(base, f"{tempo(item['inicio'] + t)} {nome}", (8, base.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (255, 255, 255), 2)
                celulas.append(base)
            pagina.close()
            linhas.append(np.hstack(celulas))
        nav.close()
    largura_max = max(l.shape[1] for l in linhas)
    linhas = [np.pad(l, ((0, 0), (0, largura_max - l.shape[1]), (0, 0))) for l in linhas]
    destino = pasta / "cenas-previa.jpg"
    cv2.imwrite(str(destino), np.vstack(linhas), [cv2.IMWRITE_JPEG_QUALITY, 90])
    return destino


# ---------- linha de comando ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["sugerir", "aplicar", "validar", "previa"])
    ap.add_argument("n", nargs="?", type=int)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--modo", choices=["painel", "tela"], default="painel")
    ap.add_argument("--formato", default="original")
    ap.add_argument("--perfil", help="perfil de marca (padrão: o da pasta do trabalho)")
    a = ap.parse_args()
    definir_perfil(a.perfil)
    pasta = a.pasta.resolve()
    if not (pasta / "cortes.json").exists():
        erro("rode propor_cortes.py antes")
    from elementos import palavras_saida
    from comum import fps_racional
    palavras = palavras_saida(pasta)
    arq_el, arq_sug = pasta / "elementos.json", pasta / "cenas-sugeridas.json"
    elementos = ler_json(arq_el) if arq_el.exists() else {"itens": []}

    if a.acao == "sugerir":
        props = sugerir(palavras)
        salvar_json(arq_sug, {"propostas": props})
        for n, p in enumerate(props):
            it = p["item"]
            print(f"  {n:>2}  {tempo(it['inicio'])}  {p['tipo']:<12} {resumo(it)}")
        print(f"{len(props)} proposta(s). Resuma os textos, aplique com: cenas.py aplicar N --pasta ...")
        if not props:
            print("nenhuma lista, antes e depois, de-para ou número forte na fala")
    elif a.acao == "aplicar":
        if not arq_sug.exists():
            erro("rode cenas.py sugerir antes")
        props = ler_json(arq_sug)["propostas"]
        if a.n is None or not 0 <= a.n < len(props):
            erro(f"diga qual proposta, de 0 a {len(props) - 1}")
        p = props[a.n]
        modo = "tela" if a.modo == "tela" else "sobreposto"
        item = montar_item(p["tipo"], p["item"]["cena"], modo)
        ocupado = [(o["inicio"], o["inicio"] + o["duracao"]) for o in elementos["itens"]]
        for x, y in ocupado:
            if item["inicio"] < y + FOLGA and item["inicio"] + item["duracao"] > x - FOLGA:
                erro(f"encosta em outro elemento ({tempo(x)} a {tempo(y)}): tire o elemento ou escolha outra cena")
        elementos["itens"] = sorted(elementos["itens"] + [item], key=lambda i: i["inicio"])
        salvar_json(arq_el, elementos)
        print(f"ok  cena {p['tipo']} em {tempo(item['inicio'])} ({item['duracao']} s, {a.modo}). "
              "Edite os textos no elementos.json e rode cenas.py validar")
    elif a.acao == "validar":
        problemas = validar(elementos["itens"], palavras)
        n_cenas = sum(1 for i in elementos["itens"] if eh_cena(i))
        for pr in problemas:
            print(f"  problema: {pr}")
        if problemas:
            erro(f"{len(problemas)} problema(s) nas cenas", 1)
        print(f"ok  {n_cenas} cena(s) conferida(s)")
    else:
        from comum import dimensoes_saida
        insp = ler_json(pasta / "inspecao.json")["videos"][0]
        largura, altura = dimensoes_saida(insp["largura"], insp["altura"], a.formato)
        print(f"ok  {previa(pasta, largura, altura, fps_racional({'avg_frame_rate': insp['fps']}))}")


def resumo(item: dict) -> str:
    t, c = tipo_do_item(item), item["cena"]
    if t == "lista":
        return " | ".join(p["texto"] for p in c["passos"])
    if t == "antes-depois":
        return f"antes: {c['antes']['texto']} → depois: {c['depois']['texto']}"
    if t == "numero":
        return f"{c['prefixo']}{c['valor']:g}{c['sufixo']} {c.get('rotulo', '')}".strip()
    return f"de {c['de']['prefixo']}{c['de']['valor']:g}{c['de']['sufixo']} para {c['para']['prefixo']}{c['para']['valor']:g}{c['para']['sufixo']}"


if __name__ == "__main__":
    main()
