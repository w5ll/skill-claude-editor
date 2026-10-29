"""Propõe os cortes: tira pausas longas, respirações, repetições e falsos começos.

Uso:
    python propor_cortes.py --pasta saida/2026-10-22_tema [--ritmo natural|dinamico]
        [--videos A.mp4 B.mp4]   (padrão: os vídeos de inspecao.json, na mesma ordem)
        [--perfil NOME]

Lê inspecao.json e transcricoes/, grava cortes.json e mostra a lista de trechos.

Avisos obrigatórios: as frases de "avisos_obrigatorios" do perfil de marca nunca podem ser
cortadas. O script procura cada uma na fala; se algum pedaço dela ficar fora dos trechos que
sobram, ela entra em "PARA CONFERIR". Se ficar inteira, o script diz que foi mantida.

Como mede:
- Os pontos de corte vêm do áudio, medido a cada 10 ms. O limiar entre fala e
  silêncio é calculado para cada gravação, a partir do ruído da sala e do volume
  da voz (um limiar fixo erra em quase todo celular).
- Cada trecho de fala ganha uma folga antes e depois, e a borda avança enquanto
  ainda houver som fraco (até 120 ms), para não comer consoante nem final de palavra.
- A transcrição serve para achar repetições e falsos começos e para separar
  respiração (som sem palavra) de fala.

Tudo é proposta. Claude lê os trechos, confere os pontos marcados em "conferir"
e pode apagar ou ajustar trechos à mão no cortes.json antes de renderizar.
"""

from __future__ import annotations

import argparse
import difflib
import re
import unicodedata
from pathlib import Path

import numpy as np

from comum import carregar_marca, carregar_mono, definir_perfil, envelope_db, erro, ler_json, salvar_json, tempo
from fala import PASSO, medir_fala

RITMOS = {
    # pausa_max: silêncio acima disso é encurtado
    # pausa_frase / pausa_meio: silêncio que fica no lugar (fim de frase / meio de frase)
    "natural": {"pausa_max": 0.45, "pausa_frase": 0.32, "pausa_meio": 0.20},
    "dinamico": {"pausa_max": 0.28, "pausa_frase": 0.18, "pausa_meio": 0.12},
}
FOLGA_ANTES = 0.07     # mínimo de silêncio antes da primeira sílaba
FOLGA_DEPOIS = 0.06    # mínimo depois da última
RESPIRO_MAX = 0.70     # som sem palavra mais curto que isso é tratado como respiração
SOBRA_MINIMA = 0.12    # pedaço que sobra de um corte e é curto demais para ficar

HESITACOES = {"ahn", "ah", "hum", "hmm", "hã", "ã", "eh", "uh", "humm", "ééé", "éé"}
# "ã" e "é" sem acento viram "a" e "e", que são artigo e verbo: esses só contam com o acento.
SO_COM_ACENTO = {"ã", "é", "éé", "ééé"}


def eh_hesitacao(p: str) -> bool:
    cru = re.sub(r"[^\wãéêâ]+", "", p.lower())
    if cru in SO_COM_ACENTO:
        return cru != "é"  # "é" sozinho é o verbo; "éé" arrastado é hesitação
    n = normalizar(p)
    return n in {normalizar(h) for h in HESITACOES - SO_COM_ACENTO} and n not in {"a", "e", "o"}


def normalizar(p: str) -> str:
    t = unicodedata.normalize("NFKD", p.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", t)


def fim_de_frase(p: str) -> bool:
    return p.rstrip().endswith((".", "?", "!", "…"))


def ponto_mais_baixo(env: np.ndarray, t0: float, t1: float) -> float:
    """Momento mais silencioso entre t0 e t1 (onde o corte não se ouve)."""
    a, b = int(t0 / PASSO), int(t1 / PASSO)
    if b <= a:
        return (t0 + t1) / 2
    return (a + int(np.argmin(env[a:b]))) * PASSO


def subtrair(trechos: list[list[float]], i0: float, i1: float) -> list[list[float]]:
    saida = []
    for a, b in trechos:
        if i1 <= a or i0 >= b:
            saida.append([a, b])
            continue
        if i0 - a >= SOBRA_MINIMA:
            saida.append([a, i0])
        if b - i1 >= SOBRA_MINIMA:
            saida.append([i1, b])
    return saida


def palavras_em(palavras, a, b):
    return [w for w in palavras if a <= (w["i"] + w["f"]) / 2 <= b]


def frases(palavras: list[dict]) -> list[list[int]]:
    """Agrupa índices de palavras em frases (pontuação ou pausa de 0,6 s)."""
    grupos, atual = [], []
    for k, w in enumerate(palavras):
        if atual and w["i"] - palavras[atual[-1]]["f"] >= 0.6:
            grupos.append(atual)
            atual = []
        atual.append(k)
        if fim_de_frase(w["p"]):
            grupos.append(atual)
            atual = []
    if atual:
        grupos.append(atual)
    return grupos


def parecido(a: list[str], b: list[str]) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def achar_aviso(aviso: str, palavras: list[dict]) -> list[tuple[int, int]]:
    """Onde a frase do aviso aparece na fala (pode ser dita mais de uma vez): lista de (primeira, última palavra)."""
    alvo = [normalizar(p) for p in aviso.split() if normalizar(p)]
    norm = [normalizar(w["p"]) for w in palavras]
    candidatos = []
    for i in range(len(norm) - len(alvo) + 1):
        sem = parecido(norm[i:i + len(alvo)], alvo)
        if sem >= 0.8:
            candidatos.append((sem, i, i + len(alvo) - 1))
    achados, ocupado = [], set()
    for sem, i, j in sorted(candidatos, key=lambda c: (-c[0], c[1])):      # as mais parecidas primeiro
        if not ocupado & set(range(i, j + 1)):
            achados.append((i, j))
            ocupado |= set(range(i, j + 1))
    return sorted(achados)


def conferir_avisos(avisos: list[str], falas: dict[int, list[dict]], trechos: list[dict]) -> list[dict]:
    """Para cada aviso obrigatório: mantido inteiro (em alguma das vezes que foi dito), cortado ou não encontrado."""
    saida = []
    for aviso in avisos:
        ocorrencias = []
        for vid, palavras in falas.items():
            mantidos = [(t["inicio"], t["fim"]) for t in trechos if t["video"] == vid]
            for i, j in achar_aviso(aviso, palavras):
                fora = [w["p"] for w in palavras[i:j + 1]
                        if not any(a <= (w["i"] + w["f"]) / 2 < b for a, b in mantidos)]
                ocorrencias.append({"video": vid, "tempo": round(palavras[i]["i"], 2), "cortadas": fora})
        if not ocorrencias:
            saida.append({"aviso": aviso, "estado": "nao_encontrado"})
            continue
        inteira = next((o for o in ocorrencias if not o["cortadas"]), None)
        if inteira:
            saida.append({"aviso": aviso, "estado": "mantido", "video": inteira["video"], "tempo": inteira["tempo"]})
        else:   # nenhuma vez ficou inteira: mostra a que perdeu menos palavras
            o = min(ocorrencias, key=lambda o: len(o["cortadas"]))
            saida.append({"aviso": aviso, "estado": "cortado", **o})
    return saida


def achar_repeticoes(palavras: list[dict], env: np.ndarray, duracao: float):
    """Devolve (remoções, pontos para conferir)."""
    remover, conferir = [], []
    norm = [normalizar(w["p"]) for w in palavras]

    def inicio_de(k):
        anterior = palavras[k - 1]["f"] if k > 0 else max(0.0, palavras[k]["i"] - 0.3)
        return ponto_mais_baixo(env, min(anterior, palavras[k]["i"]), palavras[k]["i"])

    # 1. Falso começo ou frase regravada: a frase seguinte começa igual e vai além.
    grupos = frases(palavras)
    usados = set()
    for gi, g in enumerate(grupos):
        if len(g) < 2 or gi in usados:
            continue
        a = [norm[k] for k in g if norm[k]]
        for gj in range(gi + 1, min(gi + 3, len(grupos))):
            h = grupos[gj]
            b = [norm[k] for k in h if norm[k]]
            n = min(len(a), len(b))
            if n < 2 or len(b) < len(a) * 0.8:
                continue
            if parecido(a[:n], b[:n]) >= 0.75:
                ini, fim = inicio_de(g[0]), inicio_de(h[0])
                remover.append({
                    "inicio": round(ini, 3), "fim": round(fim, 3),
                    "motivo": "frase repetida ou começo errado: ficou a versão seguinte",
                    "texto": " ".join(palavras[k]["p"] for k in range(g[0], h[0])),
                })
                usados.update(range(gi, gj))
                break

    # 2. Repetição colada: "perde no WhatsApp, perde no WhatsApp".
    k = 0
    while k < len(palavras):
        achou = False
        for tam in range(6, 0, -1):
            if k + 2 * tam > len(palavras):
                continue
            x, y = norm[k:k + tam], norm[k + tam:k + 2 * tam]
            if not all(x) or x != y:
                continue
            if tam == 1 and len(x[0]) <= 1:
                continue
            ini, fim = inicio_de(k), inicio_de(k + tam)
            if any(ini < r["fim"] and fim > r["inicio"] for r in remover):
                continue  # já coberto por outro corte
            remover.append({
                "inicio": round(ini, 3), "fim": round(fim, 3),
                "motivo": "palavras repetidas em seguida: ficou a segunda vez",
                "texto": " ".join(w["p"] for w in palavras[k:k + tam]),
            })
            k += tam
            achou = True
            break
        if not achou:
            k += 1

    # 3. Hesitações e palavras duvidosas.
    for k, w in enumerate(palavras):
        if eh_hesitacao(w["p"]):
            fim = palavras[k + 1]["i"] if k + 1 < len(palavras) else min(duracao, w["f"] + 0.1)
            remover.append({"inicio": round(inicio_de(k), 3),
                            "fim": round(ponto_mais_baixo(env, w["f"], max(w["f"], fim)), 3),
                            "motivo": "hesitação", "texto": w["p"]})
        elif w["conf"] < 0.45:
            conferir.append({"tempo": w["i"], "motivo": "palavra com transcrição duvidosa", "texto": w["p"]})
        elif w["f"] - w["i"] > 1.5:
            conferir.append({"tempo": w["i"], "motivo": "palavra longa demais: pode ter som arrastado ou erro",
                             "texto": w["p"]})
    return remover, conferir


def propor(video_id: int, arquivo: str, transcricao: dict, ritmo: dict):
    audio = carregar_mono(arquivo)
    duracao = len(audio) / 16000
    env = envelope_db(audio, PASSO)
    medida = medir_fala(env)
    palavras = transcricao["palavras"]

    removidos = []
    falas = []
    sem_transcricao = transcricao.get("sem_transcricao", [])
    for a, b in medida["regioes"]:
        tem_palavra = any(w["f"] > a and w["i"] < b for w in palavras)
        nao_reconhecida = any(x < b and y > a for x, y in sem_transcricao)
        if not tem_palavra and b - a < RESPIRO_MAX and not nao_reconhecida:
            removidos.append({"inicio": round(a, 3), "fim": round(b, 3), "motivo": "respiração ou ruído sem fala"})
            continue
        falas.append([a, b, tem_palavra])

    # Palavras que caíram no silêncio medido (o detector pode ter perdido uma fala baixa).
    for w in palavras:
        if not any(w["f"] > a - 0.05 and w["i"] < b + 0.05 for a, b, _ in falas):
            falas.append([max(0.0, w["i"] - 0.02), min(duracao, w["f"] + 0.02), True])
    falas.sort()

    conferir = []
    ultima = max((w["f"] for w in palavras), default=0.0)
    for a, b, tem in falas:
        if not tem:
            if a > ultima:
                motivo = ("FALA NO FIM SEM TRANSCRIÇÃO: pode ser o fecho do vídeo. Rode transcrever.py --trecho "
                          f"{max(0, a - 1):.0f} {duracao:.0f} e leia antes de decidir; não corte sem ouvir")
            elif b - a >= 0.6:
                motivo = ("fala que o Whisper não reconheceu: rode transcrever.py --trecho "
                          f"{max(0, a - 1):.0f} {b + 1:.0f} antes de cortar")
            else:
                motivo = "som sem palavra transcrita (risada, barulho?)"
            conferir.append({"tempo": round(a, 3), "motivo": motivo, "texto": ""})

    # Trechos mantidos: fala com folga; pausas longas encurtadas.
    trechos: list[list[float]] = []
    for idx, (a, b, _) in enumerate(falas):
        if not trechos:
            trechos.append([max(0.0, a - FOLGA_ANTES), b])
            continue
        fim_anterior = trechos[-1][1]
        pausa = a - fim_anterior
        if pausa <= ritmo["pausa_max"]:
            trechos[-1][1] = b
            continue
        ultima = [w for w in palavras if w["f"] <= fim_anterior + 0.05]
        manter = ritmo["pausa_frase"] if ultima and fim_de_frase(ultima[-1]["p"]) else ritmo["pausa_meio"]
        depois = max(FOLGA_DEPOIS, manter * 0.45)
        antes = max(FOLGA_ANTES, manter - depois)
        removidos.append({"inicio": round(fim_anterior + depois, 3), "fim": round(a - antes, 3),
                          "motivo": f"pausa de {pausa:.1f} s encurtada"})
        trechos[-1][1] = fim_anterior + depois
        trechos.append([a - antes, b])
    if trechos:
        trechos[-1][1] = min(duracao, trechos[-1][1] + FOLGA_DEPOIS)

    reps, duvidas = achar_repeticoes(palavras, env, duracao)
    conferir += duvidas
    for r in reps:
        trechos = subtrair(trechos, r["inicio"], r["fim"])
        removidos.append(r)

    saida = []
    for a, b in trechos:
        saida.append({"video": video_id, "inicio": round(a, 3), "fim": round(b, 3),
                      "texto": " ".join(w["p"] for w in palavras_em(palavras, a, b))})
    for r in removidos:
        r["video"] = video_id
    for c in conferir:
        c["video"] = video_id
    return saida, removidos, conferir, medida, duracao


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--ritmo", choices=sorted(RITMOS), default="natural")
    ap.add_argument("--videos", nargs="*", type=Path)
    ap.add_argument("--perfil", help="perfil de marca (padrão: o da pasta do trabalho)")
    a = ap.parse_args()
    from comum import andamento, andamento_fim
    andamento(a.pasta, "propondo os cortes")
    definir_perfil(a.perfil)
    marca = carregar_marca(pasta=a.pasta)

    if a.videos:
        arquivos = [str(v.resolve()) for v in a.videos]
    else:
        insp = a.pasta / "inspecao.json"
        if not insp.exists():
            erro("rode inspecionar.py antes")
        arquivos = [v["arquivo"] for v in ler_json(insp)["videos"]]

    resultado = {"ritmo": a.ritmo, "parametros": RITMOS[a.ritmo], "videos": [], "trechos": [],
                 "removidos": [], "conferir": []}
    total = 0.0
    for vid, arq in enumerate(arquivos):
        tr = a.pasta / "transcricoes" / f"{Path(arq).stem}.json"
        if not tr.exists():
            erro(f"falta a transcrição de {Path(arq).name}: rode transcrever.py")
        trechos, removidos, conferir, medida, dur = propor(vid, arq, ler_json(tr), RITMOS[a.ritmo])
        total += dur
        resultado["videos"].append({"id": vid, "arquivo": arq, "duracao": round(dur, 3),
                                    "medida": {k: v for k, v in medida.items() if k != "regioes"}})
        resultado["trechos"] += trechos
        resultado["removidos"] += sorted(removidos, key=lambda r: r["inicio"])
        resultado["conferir"] += conferir

    # Mesma frase em trechos diferentes (regravação, inclusive em outro arquivo).
    tr = resultado["trechos"]
    for x in range(len(tr)):
        for y in range(x + 1, len(tr)):
            a_, b_ = [normalizar(p) for p in tr[x]["texto"].split()], [normalizar(p) for p in tr[y]["texto"].split()]
            if min(len(a_), len(b_)) >= 3 and parecido(a_, b_) >= 0.8:
                resultado["conferir"].append({
                    "video": tr[y]["video"], "tempo": tr[y]["inicio"],
                    "motivo": f"mesma frase dos trechos {x} e {y}: escolher a melhor tomada e apagar a outra",
                    "texto": tr[y]["texto"]})

    # Avisos obrigatórios do perfil: nunca podem ser cortados.
    if marca["avisos_obrigatorios"]:
        falas = {vid: ler_json(a.pasta / "transcricoes" / f"{Path(arq).stem}.json")["palavras"]
                 for vid, arq in enumerate(arquivos)}
        resultado["avisos_obrigatorios"] = conferir_avisos(marca["avisos_obrigatorios"], falas, resultado["trechos"])
        for av in resultado["avisos_obrigatorios"]:
            if av["estado"] == "cortado":
                resultado["conferir"].append({
                    "video": av["video"], "tempo": av["tempo"],
                    "motivo": "aviso obrigatório do perfil cortado em parte (não pode): " + ", ".join(av["cortadas"]),
                    "texto": av["aviso"]})

    final = sum(t["fim"] - t["inicio"] for t in resultado["trechos"])
    resultado["duracao_original"] = round(total, 2)
    resultado["duracao_final"] = round(final, 2)
    salvar_json(a.pasta / "cortes.json", resultado)
    andamento_fim(a.pasta, "cortes propostos")

    print(f"{tempo(total)} -> {tempo(final)}  ({len(resultado['trechos'])} trechos, "
          f"{len(resultado['removidos'])} cortes)\n")
    print("TRECHOS QUE FICAM")
    for n, t in enumerate(resultado["trechos"]):
        print(f"  {n:>2}  v{t['video']} {tempo(t['inicio'])}-{tempo(t['fim'])}  {t['texto']}")
    print("\nCORTES QUE NÃO SÃO SÓ PAUSA")
    for r in resultado["removidos"]:
        if not r["motivo"].startswith("pausa"):
            print(f"  v{r['video']} {tempo(r['inicio'])}-{tempo(r['fim'])}  {r['motivo']}"
                  f"{': ' + r['texto'] if r.get('texto') else ''}")
    for av in resultado.get("avisos_obrigatorios", []):
        if av["estado"] == "mantido":
            print(f"\naviso obrigatório mantido inteiro: v{av['video']} {tempo(av['tempo'])}  {av['aviso']}")
        elif av["estado"] == "nao_encontrado":
            print(f"\naviso obrigatório que não aparece na fala (confira se a pessoa o disse): {av['aviso']}")
    if resultado["conferir"]:
        print("\nPARA CONFERIR")
        for c in resultado["conferir"]:
            print(f"  v{c['video']} {tempo(c['tempo'])}  {c['motivo']}{': ' + c['texto'] if c['texto'] else ''}")
    print(f"\nok  {a.pasta / 'cortes.json'}")


if __name__ == "__main__":
    main()
