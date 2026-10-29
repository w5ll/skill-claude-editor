"""Gancho: avalia se os 3 primeiros segundos do vídeo cortado prendem e propõe melhorias.

Uso:
    python gancho.py avaliar --pasta saida/2026-10-22_tema
    python gancho.py aplicar --pasta saida/2026-10-22_tema --proposta puxar_frase [--frase 0]
    python gancho.py aplicar --pasta saida/2026-10-22_tema --proposta cortar_abertura

avaliar  olha os primeiros 3 s do vídeo já cortado, dá uma nota de 0 a 5 (1 ponto por sinal:
         começa rápido, sem enrolação, fala com a pessoa, promessa ou tensão, frase curta) e grava
         gancho.json com as propostas, da mais leve à mais forte:
           cortar_abertura  a primeira frase é só saudação e a seguinte já entra no assunto;
           puxar_frase      (nota 2 ou menos) move para o começo uma frase inteira do meio, com nota
                            pelo menos 2 pontos maior que a do começo atual (nunca a última frase);
           tela_cheia       abrir com um elemento 3D em tela cheia, se há palavra-gatilho nos 3 s.
aplicar  aplica UMA proposta ao cortes.json (a versão atual fica em cortes.anterior.json). Só rode
         depois do "ok" de quem grava. Depois, rode de novo rosto, elementos, câmera e legenda.

Só frases inteiras mudam de lugar, cortadas no silêncio entre as palavras. Nunca se inventa frase
nem se junta metade de uma frase com metade de outra. Uma frase que atravessa dois trechos, ou que
não fecha em ponto, interrogação ou exclamação, não é candidata.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
from pathlib import Path

from camera import NUMEROS, normalizar
from comum import erro, ler_json, salvar_json, tempo

JANELA = 3.0                 # segundos olhados no começo
RAPIDO = 0.3                 # primeira palavra até aqui
FRASE_MIN, FRASE_MAX = 3, 14  # palavras da primeira frase
FRASE_MAX_S = 5.0
CAND_MIN, CAND_MAX = 3, 12   # palavras de uma frase candidata
CAND_MIN_S, CAND_MAX_S = 1.5, 6.0
GANHO_MIN = 2                # a candidata precisa ter isto de pontos a mais que o começo
NOTA_PUXAR = 2               # só propõe puxar frase com nota até aqui
SAUDACAO_MAX_PALAVRAS = 6
FOLGA_ANTES, FOLGA_DEPOIS = 0.07, 0.06

MULETAS = {"oi", "ola", "ei", "opa", "entao", "bom", "gente", "pessoal", "galera", "fala", "salve", "bora", "ai"}
SAUDACAO = MULETAS | {"e", "tudo", "bem", "dia", "boa", "tarde", "noite", "certo", "beleza", "ne", "amigos",
                      "amigas", "gente", "pessoa", "pessoas", "hoje", "aqui"}
VOCE = {"voce", "voces", "seu", "sua", "seus", "suas", "te", "contigo"}
PROMESSA = {"erro", "erros", "segredo", "segredos", "problema", "problemas", "motivo", "motivos", "como",
            "porque", "verdade", "mentira", "mito", "cuidado", "atencao", "descobri", "prejuizo"}
NEGACOES_FORTES = {"nunca", "nenhum", "nenhuma", "ninguem", "jamais", "zero"}
FIM_DE_FRASE = re.compile(r"[.?!…]$")


def norm(p: str) -> str:
    return normalizar(p.strip().strip(".,!?…;:\"'"))


# ---------- sinais e nota ----------

def sinais(palavras: list[str], com_ritmo: bool = False, primeira_em: float = 0.0, frase: list[str] | None = None,
           frase_dur: float = 0.0) -> dict:
    """Sinais de um trecho de fala. `palavras`: todas as palavras olhadas; `frase`: a primeira frase."""
    frase = frase if frase is not None else palavras
    ns = [norm(p) for p in palavras]
    nf = [norm(p) for p in frase]
    abre_com_muleta = bool(nf) and (nf[0] in MULETAS or (nf[0] == "e" and len(nf) > 1 and nf[1] == "ai"))
    forte = any(n in NEGACOES_FORTES or n in NUMEROS or (re.fullmatch(r"\d+%?", n) and n not in {"0", "1"})
                for n in ns)
    r = {
        "sem_enrolacao": not abre_com_muleta,
        "fala_com_a_pessoa": any(n in VOCE for n in ns) or any("?" in p for p in palavras),
        "promessa_ou_tensao": forte or any(n in PROMESSA for n in ns),
        "frase_curta": FRASE_MIN <= len(nf) <= FRASE_MAX and (frase_dur <= 0 or frase_dur <= FRASE_MAX_S),
    }
    if com_ritmo:
        r = {"comeca_rapido": primeira_em <= RAPIDO, **r}
    return r


def nota(s: dict) -> int:
    return sum(1 for v in s.values() if v)


ROTULOS = {
    "comeca_rapido": "a primeira palavra demora mais de 0,3 s",
    "sem_enrolacao": "abre com saudação ou muleta (\"oi\", \"então\", \"gente\"...)",
    "fala_com_a_pessoa": "não fala com a pessoa (sem \"você\" nem pergunta)",
    "promessa_ou_tensao": "sem número, negação forte nem palavra de promessa ou problema",
    "frase_curta": "a primeira frase é longa demais ou curta demais",
}


# ---------- frases ----------

def palavras_por_trecho(pasta: Path, cortes: dict) -> list[list[dict]]:
    """Palavras de cada trecho, em tempo do vídeo original."""
    trans = {}
    for v in cortes["videos"]:
        trans[v["id"]] = ler_json(pasta / "transcricoes" / f"{Path(v['arquivo']).stem}.json")["palavras"]
    saida = []
    for t in cortes["trechos"]:
        saida.append([{"p": w["p"].strip(), "i": w["i"], "f": w["f"]} for w in trans[t["video"]]
                      if t["inicio"] <= (w["i"] + w["f"]) / 2 < t["fim"]])
    return saida


def frases_do_corte(trechos: list[dict], pal: list[list[dict]]) -> list[dict]:
    """Frases na ordem do vídeo cortado.

    `ws` traz as palavras com o tempo do vídeo cortado. `comeca`: a frase anterior fechou em ponto,
    interrogação ou exclamação (ou é a primeira). `novo_trecho`: a frase abre um trecho.
    """
    frases, deslocamento = [], 0.0
    anterior_fechou = True
    for n, (t, ws) in enumerate(zip(trechos, pal)):
        grupos, atual = [], []
        for k, w in enumerate(ws):
            if atual and (w["i"] - ws[atual[-1]]["f"] > 0.5 or FIM_DE_FRASE.search(ws[atual[-1]]["p"])):
                grupos.append(atual)
                atual = []
            atual.append(k)
        if atual:
            grupos.append(atual)
        for g in grupos:
            ini, fim = ws[g[0]], ws[g[-1]]
            fecha = bool(FIM_DE_FRASE.search(fim["p"]))
            frases.append({
                "trecho": n, "k0": g[0], "k1": g[-1],
                "palavras": [w["p"] for w in ws[g[0]:g[-1] + 1]],
                "ws": [{"p": w["p"], "i": deslocamento + w["i"] - t["inicio"], "f": deslocamento + w["f"] - t["inicio"]}
                       for w in ws[g[0]:g[-1] + 1]],
                "saida_i": deslocamento + ini["i"] - t["inicio"], "saida_f": deslocamento + fim["f"] - t["inicio"],
                "comeca": anterior_fechou, "novo_trecho": g[0] == 0, "fecha": fecha,
            })
            anterior_fechou = fecha
        deslocamento += t["fim"] - t["inicio"]
    return frases


def avaliar_abertura(frases: list[dict], palavras_saida: list[dict]) -> dict:
    janela = [w for w in palavras_saida if w["i"] < JANELA]
    if not janela or not frases:
        return {"nota": 0, "sinais": {}, "texto": "", "faltou": ["não há fala nos primeiros 3 s"]}
    primeira = frases[0]
    s = sinais([w["p"] for w in janela], com_ritmo=True, primeira_em=janela[0]["i"], frase=primeira["palavras"],
               frase_dur=primeira["saida_f"] - primeira["saida_i"])
    return {"nota": nota(s), "nota_conteudo": nota({k: v for k, v in s.items() if k != "comeca_rapido"}),
            "sinais": s, "texto": " ".join(w["p"] for w in janela),
            "faltou": [ROTULOS[k] for k, v in s.items() if not v]}


# ---------- propostas ----------

def eh_saudacao(f: dict) -> bool:
    ns = [norm(p) for p in f["palavras"]]
    return len(ns) <= SAUDACAO_MAX_PALAVRAS and all(n in SAUDACAO for n in ns)


def candidatas(frases: list[dict], limite_nota: int) -> list[dict]:
    saida = []
    for n, f in enumerate(frases):
        if n == 0 or n == len(frases) - 1:
            continue        # a primeira já é o começo; a última é o fecho
        dur = f["saida_f"] - f["saida_i"]
        if not (f["comeca"] and f["fecha"] and CAND_MIN <= len(f["palavras"]) <= CAND_MAX
                and CAND_MIN_S <= dur <= CAND_MAX_S):
            continue
        s = sinais(f["palavras"], frase_dur=dur)
        pts = min(5, nota(s) + (1 if any("?" in p for p in f["palavras"]) else 0))
        if pts >= limite_nota + GANHO_MIN:
            saida.append({"frase": n, "nota": pts, "texto": " ".join(f["palavras"]), "inicio": round(f["saida_i"], 2),
                          "duracao": round(dur, 2), "trecho": f["trecho"], "k0": f["k0"], "k1": f["k1"]})
    return sorted(saida, key=lambda c: (-c["nota"], c["inicio"]))[:3]


def propor(trechos: list[dict], pal: list[list[dict]], duracao_video: float) -> dict:
    frases = frases_do_corte(trechos, pal)
    palavras_saida = [w for f in frases for w in f["ws"]]
    ab = avaliar_abertura(frases, palavras_saida)
    propostas = []
    if (len(frases) > 1 and eh_saudacao(frases[0]) and not eh_saudacao(frases[1]) and frases[0]["saida_f"] < JANELA + 1
            and (frases[0]["fecha"] or frases[1]["novo_trecho"] or frases[1]["saida_i"] - frases[0]["saida_f"] >= 0.3)):
        ganho = frases[1]["saida_i"] - frases[0]["saida_i"]
        propostas.append({"tipo": "cortar_abertura", "texto": " ".join(frases[0]["palavras"]),
                          "motivo": f"a primeira frase é só saudação e a seguinte já entra no assunto; "
                                    f"o vídeo entra no assunto {ganho:.1f} s mais cedo",
                          "ganho_segundos": round(ganho, 2)})
    if ab["nota"] <= NOTA_PUXAR:
        base = ab.get("nota_conteudo", 0)
        cands = candidatas(frases, base)
        if cands:
            propostas.append({"tipo": "puxar_frase", "candidatas": cands,
                              "motivo": f"o começo tem nota {ab['nota']} de 5; a frase \"{cands[0]['texto']}\" tem "
                                        f"{cands[0]['nota']} e prende mais. Ela sai do lugar e vai para o começo"})
    try:
        from elementos import sugerir
        itens = sugerir(palavras_saida, duracao_video, "tela", 6.0)
        itens = [i for i in itens if i["inicio"] < JANELA]
        if itens:
            propostas.append({"tipo": "tela_cheia", "elemento": itens[0]["elemento"],
                              "quando": itens[0]["inicio"], "gatilho": itens[0]["gatilho"],
                              "motivo": f"abrir com o elemento \"{itens[0]['elemento']}\" em tela cheia quando "
                                        f"fala \"{itens[0]['gatilho']}\" (rode elementos.py sugerir --modo tela)"})
    except Exception:       # noqa: BLE001  (sem o módulo de elementos a proposta simplesmente não aparece)
        pass
    return {"abertura": ab, "propostas": propostas}


# ---------- aplicar ----------

def _texto(ws: list[dict], a: float, b: float) -> str:
    return " ".join(w["p"] for w in ws if a <= (w["i"] + w["f"]) / 2 < b)


def _corte_antes(ws: list[dict], k: int, limite: float) -> float:
    """Ponto de corte no silêncio antes da palavra k."""
    folga = FOLGA_ANTES
    if k > 0:
        folga = min(folga, max(0.0, (ws[k]["i"] - ws[k - 1]["f"]) / 2))
    return max(limite, ws[k]["i"] - folga)


def _corte_depois(ws: list[dict], k: int, limite: float) -> float:
    folga = FOLGA_DEPOIS
    if k + 1 < len(ws):
        folga = min(folga, max(0.0, (ws[k + 1]["i"] - ws[k]["f"]) / 2))
    return min(limite, ws[k]["f"] + folga)


def puxar_frase(trechos: list[dict], pal: list[list[dict]], trecho: int, k0: int, k1: int) -> list[dict]:
    t, ws = trechos[trecho], pal[trecho]
    a = _corte_antes(ws, k0, t["inicio"]) if k0 > 0 else t["inicio"]
    b = _corte_depois(ws, k1, t["fim"]) if k1 + 1 < len(ws) else t["fim"]
    pedacos = [("frase", a, b), ("antes", t["inicio"], a), ("depois", b, t["fim"])]
    novos = {}
    for nome, x, y in pedacos:
        txt = _texto(ws, x, y)
        if y - x > 1e-6 and txt:        # pedaço sem palavra é só silêncio: some
            novos[nome] = {**t, "inicio": round(x, 3), "fim": round(y, 3), "texto": txt}
    return [novos["frase"]] + trechos[:trecho] + [novos[n] for n in ("antes", "depois") if n in novos] \
        + trechos[trecho + 1:]


def cortar_abertura(trechos: list[dict], pal: list[list[dict]], frases: list[dict]) -> list[dict]:
    alvo = frases[1]
    n, ws = alvo["trecho"], pal[alvo["trecho"]]
    inicio = _corte_antes(ws, alvo["k0"], trechos[n]["inicio"]) if alvo["k0"] > 0 else trechos[n]["inicio"]
    t = {**trechos[n], "inicio": round(inicio, 3)}
    t["texto"] = _texto(ws, t["inicio"], t["fim"])
    return [t] + trechos[n + 1:]


def sha(arq: Path) -> str:
    return hashlib.sha1(arq.read_bytes()).hexdigest()[:16]


def guardar_versao(arq: Path) -> Path:
    destino = arq.with_name(arq.stem + ".anterior.json")
    n = 2
    while destino.exists():
        destino = arq.with_name(f"{arq.stem}.anterior.{n}.json")
        n += 1
    shutil.copy(arq, destino)
    return destino


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["avaliar", "aplicar"])
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--proposta", choices=["puxar_frase", "cortar_abertura"])
    ap.add_argument("--frase", type=int, default=0, help="puxar_frase: qual candidata (0 é a melhor)")
    a = ap.parse_args()
    pasta = a.pasta.resolve()
    arq_cortes = pasta / "cortes.json"
    if not arq_cortes.exists():
        erro("rode propor_cortes.py antes")
    cortes = ler_json(arq_cortes)
    pal = palavras_por_trecho(pasta, cortes)
    saida = pasta / "gancho.json"

    if a.acao == "avaliar":
        r = propor(cortes["trechos"], pal, cortes.get("duracao_final", 0.0))
        r["cortes_sha"] = sha(arq_cortes)
        salvar_json(saida, r)
        ab = r["abertura"]
        print(f"Gancho: nota {ab['nota']} de 5")
        print(f"  primeiros 3 s: {ab['texto']}")
        for f in ab["faltou"]:
            print(f"  falta: {f}")
        if not r["propostas"]:
            print("  sem proposta: o começo está bom ou não há alternativa segura")
        for p in r["propostas"]:
            print(f"\nPROPOSTA {p['tipo']}\n  {p['motivo']}")
            for n, c in enumerate(p.get("candidatas", [])):
                print(f"  candidata {n}: nota {c['nota']}, em {tempo(c['inicio'])} ({c['duracao']} s): {c['texto']}")
        print(f"\nok  {saida}")
        return

    if not a.proposta:
        erro("diga qual proposta aplicar: --proposta puxar_frase ou cortar_abertura")
    if not saida.exists():
        erro("rode gancho.py avaliar antes")
    dados = ler_json(saida)
    if dados.get("cortes_sha") != sha(arq_cortes):
        erro("o cortes.json mudou desde a avaliação: rode gancho.py avaliar de novo")
    prop = next((p for p in dados["propostas"] if p["tipo"] == a.proposta), None)
    if not prop:
        erro(f"a avaliação não propôs {a.proposta}")
    if a.proposta == "puxar_frase":
        if not 0 <= a.frase < len(prop["candidatas"]):
            erro(f"--frase vai de 0 a {len(prop['candidatas']) - 1}")
        c = prop["candidatas"][a.frase]
        novos = puxar_frase(cortes["trechos"], pal, c["trecho"], c["k0"], c["k1"])
        print(f"frase puxada para o começo: {c['texto']}")
    else:
        frases = frases_do_corte(cortes["trechos"], pal)
        novos = cortar_abertura(cortes["trechos"], pal, frases)
        print(f"abertura cortada: {prop['texto']}")
    copia = guardar_versao(arq_cortes)
    cortes["trechos"] = novos
    cortes["duracao_final"] = round(sum(t["fim"] - t["inicio"] for t in novos), 2)
    salvar_json(arq_cortes, cortes)
    saida.unlink()
    print(f"ok  {arq_cortes} (versão anterior em {copia.name}). Rode de novo: rosto, elementos, câmera e legenda")


if __name__ == "__main__":
    main()
