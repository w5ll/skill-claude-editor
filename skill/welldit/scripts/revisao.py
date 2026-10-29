"""Revisão de cortes e de legenda: a lógica por trás das telas do painel (sem servidor).

Cortes: a fala vira unidades (pedaços de até uns 14 palavras), cada uma "fica" ou "sai". Tirar e voltar mexem no
cortes.json sempre nas bordas das palavras, no silêncio entre elas: nunca no meio de uma palavra. Cada mudança
guarda o arquivo anterior em revisao/ (desfazer).

Legenda: editar o texto de um bloco, corrigir uma palavra em todos os blocos, prévia sobre um quadro do vídeo.

Veja docs/fase-6-revisao-na-tela.md.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from comum import PASTA_SKILL, ler_json, salvar_json_atomico

FOLGA_ANTES, FOLGA_DEPOIS = 0.07, 0.06       # como em propor_cortes.py
MAX_PALAVRAS_UNIDADE = 14
PAUSA_DA_UNIDADE = 0.5
UNE_ATE = 0.6                                  # trechos separados por menos que isso viram um só ao voltar
CONFIANCA_BAIXA = 0.45
PALAVRA_LONGA = 1.5
FIM_DE_FRASE = re.compile(r"[.?!…]$")
CONECTIVOS = {"porque", "que", "e", "mas", "quando", "de", "a", "o", "com", "para", "se", "ou", "como", "entao",
              "pois", "um", "uma", "do", "da", "no", "na", "em", "por", "nem", "ate"}
MAX_PEDACOS, MAX_PEDACO_S, FOLGA_OUVIR = 6, 30.0, 2.0
MAX_LEGENDA = 80


class Recusado(Exception):
    """Pedido que não faz sentido (o painel mostra a mensagem)."""


def norm(p: str) -> str:
    t = unicodedata.normalize("NFKD", p.lower())
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in t if not unicodedata.combining(c)))


# ---------- histórico (desfazer) ----------

def guardar(pasta: Path, nome: str, arquivo: Path) -> Path:
    d = pasta / "revisao"
    d.mkdir(exist_ok=True)
    n = 1
    while (d / f"{nome}-{n:03d}.json").exists():
        n += 1
    destino = d / f"{nome}-{n:03d}.json"
    shutil.copy2(arquivo, destino)
    return destino


def historico(pasta: Path, nome: str) -> list[Path]:
    return sorted((pasta / "revisao").glob(f"{nome}-[0-9][0-9][0-9].json"))


def desfazer(pasta: Path, nome: str, arquivo: Path) -> bool:
    h = historico(pasta, nome)
    if not h:
        return False
    shutil.copy2(h[-1], arquivo)
    h[-1].unlink()
    return True


# ---------- cortes ----------

def palavras_dos_videos(pasta: Path, cortes: dict) -> dict[int, list[dict]]:
    saida = {}
    for v in cortes["videos"]:
        arq = pasta / "transcricoes" / f"{Path(v['arquivo']).stem}.json"
        saida[v["id"]] = ler_json(arq)["palavras"] if arq.exists() else []
    return saida


def fica(w: dict, trechos: list[dict]) -> bool:
    meio = (w["i"] + w["f"]) / 2
    return any(t["inicio"] <= meio < t["fim"] for t in trechos)


def unidades(cortes: dict, palavras: dict[int, list[dict]]) -> list[dict]:
    saida = []
    for vid in sorted(palavras):
        ws = palavras[vid]
        trs = [t for t in cortes["trechos"] if t["video"] == vid]
        estados = [fica(w, trs) for w in ws]
        k, n = 0, len(ws)
        while k < n:
            j = k
            while j + 1 < n and estados[j + 1] == estados[k] and not FIM_DE_FRASE.search(ws[j]["p"].strip()) \
                    and ws[j + 1]["i"] - ws[j]["f"] <= PAUSA_DA_UNIDADE:
                j += 1
            # unidade comprida: parte na maior pausa
            while j - k + 1 > MAX_PALAVRAS_UNIDADE:
                corte = max(range(k, k + MAX_PALAVRAS_UNIDADE), key=lambda x: ws[x + 1]["i"] - ws[x]["f"])
                saida.append(_unidade(cortes, vid, ws, k, corte, estados[k]))
                k = corte + 1
            saida.append(_unidade(cortes, vid, ws, k, j, estados[k]))
            k = j + 1
    return saida


def _unidade(cortes: dict, vid: int, ws: list[dict], k0: int, k1: int, ficou: bool) -> dict:
    a, b = ws[k0]["i"], ws[k1]["f"]
    motivo = None
    if not ficou:
        for r in cortes.get("removidos", []):
            if r["video"] == vid and r["inicio"] < b and r["fim"] > a and not r["motivo"].startswith("pausa"):
                motivo = r["motivo"]
                break
    return {"id": f"{vid}:{k0}-{k1}", "video": vid, "k0": k0, "k1": k1, "inicio": round(a, 3), "fim": round(b, 3),
            "texto": " ".join(w["p"].strip() for w in ws[k0:k1 + 1]), "fica": ficou, "motivo": motivo,
            "palavras": [{"p": w["p"].strip(), "i": w["i"], "f": w["f"], "conf": w.get("conf", 1.0)} for w in ws[k0:k1 + 1]]}


def limites(ws: list[dict], k0: int, k1: int, duracao: float) -> tuple[float, float]:
    """Onde cortar para isolar as palavras k0..k1: no silêncio, antes da primeira e depois da última."""
    antes = FOLGA_ANTES if k0 == 0 else min(FOLGA_ANTES, max(0.0, (ws[k0]["i"] - ws[k0 - 1]["f"]) / 2))
    depois = FOLGA_DEPOIS if k1 + 1 >= len(ws) else min(FOLGA_DEPOIS, max(0.0, (ws[k1 + 1]["i"] - ws[k1]["f"]) / 2))
    return max(0.0, ws[k0]["i"] - antes), min(duracao, ws[k1]["f"] + depois)


def _texto(ws: list[dict], a: float, b: float) -> str:
    return " ".join(w["p"].strip() for w in ws if a <= (w["i"] + w["f"]) / 2 < b)


def _tem_fala(ws: list[dict], a: float, b: float) -> bool:
    return any(a <= (w["i"] + w["f"]) / 2 < b for w in ws)


def tirar(trechos: list[dict], ws: list[dict], vid: int, k0: int, k1: int, duracao: float) -> list[dict]:
    a, b = limites(ws, k0, k1, duracao)
    novos = []
    for t in trechos:
        if t["video"] != vid or t["fim"] <= a or t["inicio"] >= b:
            novos.append(t)
            continue
        if t["inicio"] < a and _tem_fala(ws, t["inicio"], a):
            novos.append({**t, "fim": round(a, 3)})
        if t["fim"] > b and _tem_fala(ws, b, t["fim"]):
            novos.append({**t, "inicio": round(b, 3)})
    return novos


def voltar(trechos: list[dict], ws: list[dict], vid: int, k0: int, k1: int, duracao: float) -> list[dict]:
    a, b = limites(ws, k0, k1, duracao)
    juntar = [i for i, t in enumerate(trechos) if t["video"] == vid and t["inicio"] <= b + UNE_ATE and t["fim"] >= a - UNE_ATE]
    if juntar:
        base = trechos[juntar[0]]
        novo = {**base, "inicio": round(min([a] + [trechos[i]["inicio"] for i in juntar]), 3),
                "fim": round(max([b] + [trechos[i]["fim"] for i in juntar]), 3)}
        posicao = juntar[0]
        restantes = [t for i, t in enumerate(trechos) if i not in juntar]
        return restantes[:posicao] + [novo] + restantes[posicao:]
    novo = {"video": vid, "inicio": round(a, 3), "fim": round(b, 3), "texto": ""}
    mesmos = [i for i, t in enumerate(trechos) if t["video"] == vid]
    if mesmos:
        antes = [i for i in mesmos if trechos[i]["inicio"] < a]
        posicao = (antes[-1] + 1) if antes else mesmos[0]
    else:
        posicao = sum(1 for t in trechos if t["video"] < vid)
    return trechos[:posicao] + [novo] + trechos[posicao:]


def alternar(pasta: Path, video: int, k0: int, k1: int, acao: str) -> dict:
    """Tira ou volta as palavras k0..k1 de um vídeo. Devolve o cortes.json novo (já gravado)."""
    if acao not in ("tirar", "voltar"):
        raise Recusado("a ação é tirar ou voltar")
    arq = pasta / "cortes.json"
    cortes = ler_json(arq)
    palavras = palavras_dos_videos(pasta, cortes)
    v = next((x for x in cortes["videos"] if x["id"] == video), None)
    if v is None or video not in palavras:
        raise Recusado("esse vídeo não faz parte dos cortes")
    ws = palavras[video]
    if not (isinstance(k0, int) and isinstance(k1, int) and 0 <= k0 <= k1 < len(ws)):
        raise Recusado("trecho fora da fala")
    duracao = float(v.get("duracao") or ws[-1]["f"] + 1)
    novos = (tirar if acao == "tirar" else voltar)(cortes["trechos"], ws, video, k0, k1, duracao)
    if not novos:
        raise Recusado("os cortes ficariam vazios: deixe pelo menos um trecho")
    guardar(pasta, "cortes", arq)
    a, b = limites(ws, k0, k1, duracao)
    for t in novos:
        t["texto"] = _texto(palavras[t["video"]], t["inicio"], t["fim"])
    cortes["trechos"] = novos
    removidos = [r for r in cortes.get("removidos", []) if not (acao == "voltar" and r["video"] == video and r["inicio"] >= a - 0.01 and r["fim"] <= b + 0.01)]
    if acao == "tirar":
        removidos.append({"inicio": round(a, 3), "fim": round(b, 3), "motivo": "tirado na revisão", "video": video,
                          "texto": _texto(ws, a, b)})
    cortes["removidos"] = removidos
    cortes["duracao_final"] = round(sum(t["fim"] - t["inicio"] for t in novos), 2)
    salvar_json_atomico(arq, cortes)
    return cortes


PEQUENAS = {"e", "o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das", "que", "em", "no", "na", "se", "ou", "eh",
            "é", "ao", "por", "com", "mas", "me", "te", "to", "ta", "tá", "né"}


def _resumo(texto: str, n: int = 70) -> str:
    return texto if len(texto) <= n else texto[:n].rsplit(" ", 1)[0] + "…"


def _motivo_do_conferir(m: str) -> tuple[str, str]:
    """(tipo, texto para a pessoa). O script fala em comandos; a tela fala em escutar."""
    if "FALA NO FIM SEM TRANSCRIÇÃO" in m:
        return "sem_palavra", "fala no fim da gravação sem transcrição: pode ser o fecho. Ouça antes de decidir"
    if "não reconheceu" in m:
        return "sem_palavra", "fala que a transcrição não reconheceu: ouça antes de cortar (pode ser fala de verdade)"
    if "som sem palavra" in m:
        return "sem_palavra", "som sem palavra transcrita (risada, barulho?): ouça"
    if "mesma frase" in m:
        return "repetida", "a mesma frase aparece em dois trechos: deixe só a melhor tomada"
    if "longa demais" in m:
        return "duvidosa", "palavra longa demais: pode ser som arrastado ou erro"
    return "duvidosa", "palavra com transcrição duvidosa"


def suspeitas(cortes: dict, uns: list[dict]) -> list[dict]:
    """Onde olhar, em ordem de aparição. Cada item: tipo, motivo, video, tempo, unidade e um trecho do texto."""
    saida = []

    def da_unidade(vid, t):
        return next((u for u in uns if u["video"] == vid and u["inicio"] - 0.01 <= t <= u["fim"] + 0.01), None)

    for u in uns:
        duv = [w for w in u["palavras"] if w["conf"] < CONFIANCA_BAIXA and (norm(w["p"]) not in PEQUENAS or w["conf"] < 0.2)]
        longas = [w for w in u["palavras"] if w["f"] - w["i"] > PALAVRA_LONGA and w not in duv]
        if duv:
            lista = ", ".join(f"“{w['p'].strip('.,!?')}”" for w in duv[:3])
            saida.append({"tipo": "duvidosa", "motivo": f"palavra duvidosa: {lista}", "video": u["video"], "tempo": duv[0]["i"],
                          "unidade": u["id"], "texto": _resumo(u["texto"])})
        if longas:
            saida.append({"tipo": "duvidosa", "motivo": f"palavra longa demais (som arrastado?): “{longas[0]['p'].strip('.,!?')}”",
                          "video": u["video"], "tempo": longas[0]["i"], "unidade": u["id"], "texto": _resumo(u["texto"])})
        if not u["fica"] and u["motivo"] and "repetid" in u["motivo"] and len(u["palavras"]) >= 3:
            saida.append({"tipo": "repetida", "motivo": "saiu por repetição: confira se ficou a melhor tomada", "video": u["video"],
                          "tempo": u["inicio"], "unidade": u["id"], "texto": _resumo(u["texto"])})
    for c in cortes.get("conferir", []):
        un = da_unidade(c["video"], c["tempo"])
        tipo, motivo = _motivo_do_conferir(c["motivo"])
        if tipo == "duvidosa":
            palavra = (c.get("texto") or "").strip(".,!? ")
            if norm(palavra) in PEQUENAS and "longa demais" not in c["motivo"]:
                continue                                            # palavra pequena: a confiança dela é sempre baixa
            if palavra:
                motivo = f"{motivo.split(':')[0]}: “{palavra}”"
            if un and any(s["unidade"] == un["id"] and s["tipo"] == "duvidosa" for s in saida):
                continue
        saida.append({"tipo": tipo, "motivo": motivo, "video": c["video"], "tempo": c["tempo"],
                      "unidade": un["id"] if un else None, "texto": _resumo(un["texto"]) if un else ""})
    for vid in sorted({u["video"] for u in uns}):
        ultima = [u for u in uns if u["video"] == vid][-1]
        saida.append({"tipo": "fim", "motivo": "fim da gravação: confira o fecho (chamada, convite)", "video": vid,
                      "tempo": ultima["inicio"], "unidade": ultima["id"], "texto": _resumo(ultima["texto"])})
    for u in uns:                                  # frase que não termina: unidade que fica, termina sem ponto e é seguida de corte
        if not u["fica"]:
            continue
        ultima = u["palavras"][-1]["p"]
        n = norm(ultima)
        proxima = next((x for x in uns if x["video"] == u["video"] and x["inicio"] > u["fim"]), None)
        cortada = proxima is not None and not proxima["fica"]
        if (not FIM_DE_FRASE.search(ultima.strip()) and cortada and not re.search(r"[,;:]$", ultima.strip())) or n in CONECTIVOS and cortada:
            saida.append({"tipo": "nao_termina", "motivo": f"a frase pode estar cortada ao meio (termina em “{ultima.strip('.,!?')}”)",
                          "video": u["video"], "tempo": u["fim"], "unidade": u["id"], "texto": _resumo(u["texto"])})
    return sorted(saida, key=lambda s: (s["video"], s["tempo"]))


def emendas(cortes: dict, uns: list[dict]) -> list[dict]:
    """Os pontos de junção entre trechos seguidos: a unidade depois da qual ela aparece e os dois pedaços a ouvir."""
    saida, trs = [], cortes["trechos"]
    for k in range(len(trs) - 1):
        a, b = trs[k], trs[k + 1]
        if a["video"] == b["video"] and abs(b["inicio"] - a["fim"]) < 0.02:
            continue
        ultima = next((u for u in reversed(uns) if u["video"] == a["video"] and u["inicio"] < a["fim"]), None)
        saida.append({"depois_de": ultima["id"] if ultima else None, "numero": k + 1,
                      "pedacos": [{"video": a["video"], "inicio": round(max(a["inicio"], a["fim"] - 1.2), 3), "fim": a["fim"]},
                                  {"video": b["video"], "inicio": b["inicio"], "fim": round(min(b["fim"], b["inicio"] + 1.2), 3)}]})
    return saida


def painel_de_cortes(pasta: Path, meta: float | None) -> dict:
    cortes = ler_json(pasta / "cortes.json")
    palavras = palavras_dos_videos(pasta, cortes)
    uns = unidades(cortes, palavras)
    nomes = {v["id"]: Path(v["arquivo"]).stem for v in cortes["videos"]}
    sus = suspeitas(cortes, uns)
    for x in sus:
        m, seg = divmod(int(x["tempo"]), 60)
        x["onde"] = f"{nomes.get(x['video'], '')} {m}:{seg:02d}".strip()
    return {"videos": [{"id": v["id"], "nome": Path(v["arquivo"]).name, "duracao": v.get("duracao")} for v in cortes["videos"]],
            "unidades": uns, "suspeitas": sus, "emendas": emendas(cortes, uns),
            "duracao_final": cortes.get("duracao_final", 0.0), "duracao_original": cortes.get("duracao_original"),
            "meta": meta, "desfazer": len(historico(pasta, "cortes"))}


# ---------- ouvir ----------

def pedacos_validos(cortes: dict, pedacos: list) -> list[dict]:
    if not isinstance(pedacos, list) or not 1 <= len(pedacos) <= MAX_PEDACOS:
        raise Recusado(f"peça de 1 a {MAX_PEDACOS} pedaços")
    videos = {v["id"]: v for v in cortes["videos"]}
    saida = []
    for p in pedacos:
        try:
            vid, a, b = int(p["video"]), float(p["inicio"]), float(p["fim"])
        except (KeyError, TypeError, ValueError):
            raise Recusado("pedaço inválido")
        v = videos.get(vid)
        limite = float(v.get("duracao") or 1e9) + 0.5 if v else 0
        if v is None or not (0 <= a < b <= limite) or b - a > MAX_PEDACO_S:
            raise Recusado(f"pedaço fora do vídeo ou maior que {MAX_PEDACO_S:g} s")
        saida.append({"video": vid, "inicio": a, "fim": b, "arquivo": v["arquivo"]})
    return saida


def audio_dos_pedacos(pedacos: list[dict], destino: Path) -> Path:
    """Extrai e junta os pedaços (só o áudio), com a mesma suavização de 8 ms nas emendas do render."""
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-y"]
    filtros = []
    for k, p in enumerate(pedacos):
        d = p["fim"] - p["inicio"]
        cmd += ["-ss", f"{p['inicio']:.3f}", "-t", f"{d:.3f}", "-i", p["arquivo"]]
        filtros.append(f"[{k}:a:0]aresample=48000,asetpts=PTS-STARTPTS,afade=t=in:d=0.008,afade=t=out:st={max(0, d - 0.008):.3f}:d=0.008[a{k}]")
    n = len(pedacos)
    filtros.append("".join(f"[a{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1[a]")
    tmp = destino.with_suffix(".parte.m4a")
    cmd += ["-filter_complex", ";".join(filtros), "-map", "[a]", "-c:a", "aac", "-b:a", "96k", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise Recusado("não consegui extrair o áudio desse trecho")
    tmp.replace(destino)
    return destino


def chave_do_audio(pedacos: list[dict]) -> str:
    base = [[p["arquivo"], Path(p["arquivo"]).stat().st_mtime_ns if Path(p["arquivo"]).exists() else 0, p["inicio"], p["fim"]] for p in pedacos]
    return hashlib.sha1(json.dumps(base).encode()).hexdigest()[:16]


# ---------- legenda ----------

def marcas_do_bloco(b: dict) -> list[str]:
    m = []
    if re.search(r"\d", b["texto"]):
        m.append("número")
    palavras = b["texto"].split()
    if any(p[:1].isupper() and not p.isupper() for p in palavras[1:]):
        m.append("nome próprio")
    if b.get("lugar") not in (None, "embaixo"):
        m.append("movida")
    return m


def painel_de_legenda(pasta: Path) -> dict:
    d = ler_json(pasta / "legendas.json")
    blocos = [{"indice": k, "texto": b["texto"], "inicio": b["inicio"], "fim": b["fim"], "lugar": b.get("lugar"),
               "marcas": marcas_do_bloco(b), "destaque": len(b.get("palavras") or []) == len(b["texto"].split())}
              for k, b in enumerate(d["blocos"])]
    return {"blocos": blocos, "desfazer": len(historico(pasta, "legendas")),
            "estilo": {k: d["estilo"].get(k) for k in ("palavras", "posicao", "formato", "largura", "altura")}}


def texto_valido(texto) -> str:
    if not isinstance(texto, str):
        raise Recusado("o texto da legenda tem que ser um texto")
    t = re.sub(r"\s+", " ", texto).strip()
    if not t:
        raise Recusado("a legenda não pode ficar vazia")
    if len(t) > MAX_LEGENDA or any(unicodedata.category(c).startswith("C") for c in t):
        raise Recusado(f"a legenda tem no máximo {MAX_LEGENDA} caracteres, em uma linha")
    return t


def editar_bloco(pasta: Path, indice: int, texto) -> dict:
    arq = pasta / "legendas.json"
    d = ler_json(arq)
    if not (isinstance(indice, int) and not isinstance(indice, bool) and 0 <= indice < len(d["blocos"])):
        raise Recusado("esse bloco não existe")
    novo = texto_valido(texto)
    if novo == d["blocos"][indice]["texto"]:
        return d
    guardar(pasta, "legendas", arq)
    d["blocos"][indice]["texto"] = novo
    salvar_json_atomico(arq, d)
    return d


def substituir(pasta: Path, de, para) -> int:
    """Troca uma palavra inteira por outra em todos os blocos. Devolve quantos blocos mudaram."""
    if not isinstance(de, str) or not de.strip() or len(de) > 40 or not isinstance(para, str) or len(para) > 40:
        raise Recusado("diga a palavra a trocar (até 40 letras) e por que trocar")
    if de.strip() == para.strip():
        raise Recusado("as duas são iguais")
    arq = pasta / "legendas.json"
    d = ler_json(arq)
    padrao = re.compile(r"(?<!\w)" + re.escape(de.strip()) + r"(?!\w)", re.IGNORECASE)
    mudou = [k for k, b in enumerate(d["blocos"]) if padrao.search(b["texto"])]
    if not mudou:
        return 0
    guardar(pasta, "legendas", arq)
    for k in mudou:
        b = d["blocos"][k]
        b["texto"] = texto_valido(padrao.sub(para.strip(), b["texto"]))
        pal = b.get("palavras") or []
        novas = b["texto"].split()
        if len(pal) == len(novas):
            for w, n in zip(pal, novas):
                w["p"] = n
    salvar_json_atomico(arq, d)
    return len(mudou)


def previa_legenda(pasta: Path, indice: int, marca: dict, destino: Path) -> Path:
    """O quadro do vídeo no começo do bloco, no formato final, com a legenda desenhada pelo mesmo código do render."""
    from comum import arquivo_da_fonte, fps_racional, trechos_no_quadro
    from legendas import gerar_ass
    from renderizar import caminho_filtro
    d = ler_json(pasta / "legendas.json")
    if not (isinstance(indice, int) and 0 <= indice < len(d["blocos"])):
        raise Recusado("esse bloco não existe")
    b = d["blocos"][indice]
    estilo = d["estilo"]
    largura, altura = estilo["largura"], estilo["altura"]
    chave = hashlib.sha1(json.dumps([b, estilo, marca.get("cores"), marca.get("legenda")], sort_keys=True, default=str).encode()).hexdigest()[:16]
    destino = destino / f"{chave}.jpg"
    if destino.exists():
        return destino
    cortes = ler_json(pasta / "cortes.json")
    insp = ler_json(pasta / "inspecao.json")["videos"]
    fps = fps_racional({"avg_frame_rate": insp[0]["fps"]})
    t0 = min(b["fim"] - 0.01, b["inicio"] + 0.05)
    tr = next((t for t in trechos_no_quadro(cortes, fps) if t["saida_inicio"] <= t0 < t["saida_fim"] + 1e-6), None)
    if tr is None:
        raise Recusado("esse bloco está fora do vídeo cortado")
    fonte = tr["inicio_exato"] + (t0 - tr["saida_inicio"])
    v = insp[tr["video"]]
    destino.parent.mkdir(parents=True, exist_ok=True)
    ass = destino.with_suffix(".ass")
    bloco = {**b, "inicio": 0.0, "fim": 2.0, "palavras": [{**w, "i": w["i"] - b["inicio"], "f": w["f"] - b["inicio"]} for w in b.get("palavras") or []]}
    ass.write_text(gerar_ass([bloco], largura, altura, estilo, marca), encoding="utf-8")
    cor = ""
    if v.get("hdr"):
        cor = (f"zscale=tin={v['cor']['transferencia']}:pin=bt2020:min=bt2020nc:t=linear:npl=100,format=gbrpf32le,"
               "zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,")
    filtro = (f"{cor}scale={largura}:{altura}:force_original_aspect_ratio=increase,crop={largura}:{altura},format=yuv420p,"
              f"ass=filename='{caminho_filtro(ass)}':fontsdir='{caminho_filtro(arquivo_da_fonte(marca).parent)}',scale=432:-2")
    tmp = destino.with_suffix(".parte.jpg")
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", f"{fonte:.3f}", "-i", v["arquivo"], "-frames:v", "1",
                        "-vf", filtro, "-q:v", "3", str(tmp)], capture_output=True, text=True)
    ass.unlink(missing_ok=True)
    if r.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise Recusado("não consegui montar a prévia desse bloco")
    tmp.replace(destino)
    return destino
