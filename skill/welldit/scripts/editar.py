"""Orquestrador da edição: roda a próxima etapa, para nos portões de aprovação e retoma de onde parou.

Uso:
    python editar.py novo VIDEO [VIDEO ...] [--serie NOME] [--perfil NOME] [--tema curto]
    python editar.py proximo --pasta saida/2026-10-22_tema
    python editar.py estado  --pasta ... [--json]
    python editar.py cartao  --pasta ...
    python editar.py aprovar --pasta ... [PORTAO] [--resposta "A,C"] [--seguir]
    python editar.py ajustar --pasta ... --escolha chave=valor
    python editar.py refazer --pasta ... ETAPA

O estado fica em trabalho.json na pasta do trabalho (a conversa e o painel leem o mesmo arquivo).
Cada etapa chama os scripts de sempre; nada editorial é decidido aqui: portão é portão. A saída de cada
etapa é curta (uma linha); o texto completo vai para etapas/<nome>.log. Veja docs/fase-4-orquestrador.md.

Uma etapa só roda quando as que ela usa estão prontas. O hash de cada etapa junta as escolhas que a afetam,
o conteúdo dos arquivos de que ela depende e a execução das etapas anteriores: mudou algo, ela é refeita e
as seguintes também; não mudou nada, ela é pulada.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from comum import PASTA_SKILL, assinatura_dos_cortes, erro, ler_json, salvar_json_atomico, tempo

PASTA_RAIZ = PASTA_SKILL.parent.parent
SCRIPTS = Path(__file__).resolve().parent
LINHAS_POR_ETAPA = 1
MAX_RESUMO = 150

class Cancelado(Exception):
    """O executor levanta isto quando a pessoa cancela: a etapa vira interrompida, não falha."""


class PedidoRecusado(Exception):
    """Um pedido que não pode ser atendido (resposta incompleta, portão errado...). O painel mostra a mensagem."""


ESCOLHAS_PADRAO = {
    "ritmo": "natural", "formato": "original", "hdr": None, "ruido": "auto", "termos": [],
    "legenda": {"ligada": True, "palavras": 3, "posicao": "auto", "tamanho": 0.046, "maiusculas": False, "destaque": True},
    "elementos": {"ligado": True, "modo": "sobreposto", "intervalo": 6, "permitidos": [], "proibidos": [], "gerados": True},
    "camera": "nenhum", "som": {"musica": "nenhuma", "efeitos": False}, "volume": -14.0,
    "amostra": "conferir", "fatos": True, "gancho_olhar": True,
    "meta_duracao": None,       # segundos; só uma referência na tela de revisão dos cortes
    "pausas_ok": [],            # segundos (no vídeo editado) de pausas que a pessoa aceitou na conferência
}


# ---------- as etapas ----------

Comando = tuple[list[str], bool]          # (argumentos depois do script, opcional)


@dataclass
class Etapa:
    nome: str
    titulo: str
    depende: tuple = ()
    chaves: tuple = ()                    # escolhas que mudam o resultado
    arquivos: tuple = ()                  # arquivos (relativos à pasta) cujo conteúdo muda o resultado
    saidas: tuple = ()                    # o que precisa existir quando a etapa termina
    comandos: Callable = lambda t, p: []  # (trabalho, pasta) -> [(script, [args], opcional)]
    pulada: Callable = lambda t: False
    portao: Callable = lambda t, p: None  # (trabalho, pasta) -> dict do portão a abrir, ou None


def _v(t, chave, padrao=None):
    return t["escolhas"].get(chave, padrao)


def _p(t, p):
    return str(p)


def _formato(t):
    return _v(t, "formato", "original")


def _janela_da_amostra(pasta: Path) -> tuple[float, float]:
    """12 s a partir de um pouco antes do primeiro elemento (ou do começo, se não houver)."""
    cortes = pasta / "cortes.json"
    total = ler_json(cortes).get("duracao_final", 0.0) if cortes.exists() else 0.0
    inicio = 0.0
    arq = pasta / "elementos.json"
    if arq.exists():
        itens = ler_json(arq).get("itens", [])
        if itens:
            inicio = max(0.0, min(i["inicio"] for i in itens) - 3.0)
    fim = min(total, inicio + 12.0) if total else inicio + 12.0
    if total and fim - inicio < 8.0:
        inicio = max(0.0, fim - 12.0)
    return round(inicio, 2), round(fim, 2)


def _args_render(t) -> list[str]:
    a = ["--formato", _formato(t), "--ruido", _v(t, "ruido", "nao") if _v(t, "ruido") != "auto" else "nao",
         "--volume", str(_v(t, "volume", -14.0))]
    if _v(t, "hdr"):
        a += ["--hdr", _v(t, "hdr")]
    if not _v(t, "legenda", {}).get("ligada", True):
        a += ["--sem-legenda"]
    if not _v(t, "elementos", {}).get("ligado", True):
        a += ["--sem-elementos"]
    som = _v(t, "som", {})
    if som.get("musica", "nenhuma") == "nenhuma" and not som.get("efeitos"):
        a += ["--sem-som"]
    return a


def _c_inspecionar(t, p):
    cmd = ["inspecionar.py", *t["videos"], "--pasta", str(p)]
    if t.get("perfil"):
        cmd += ["--perfil", t["perfil"]]
    return [(cmd[0], cmd[1:], False)]


def _c_transcrever(t, p):
    cmd = [*t["videos"], "--pasta", str(p)]
    if _v(t, "termos"):
        cmd += ["--termos", ",".join(_v(t, "termos"))]
    return [("transcrever.py", cmd, False)]


def _c_elementos(t, p):
    el = _v(t, "elementos", {})
    cmds = [("elementos.py", ["sugerir", "--pasta", str(p), "--modo", el.get("modo", "sobreposto"),
                              "--intervalo", str(el.get("intervalo", 6))], False)]
    if (p / "serie.json").exists() and (el.get("proibidos") or el.get("permitidos") or el.get("gerados") is False):
        cmds.append(("serie.py", ["elementos", "--pasta", str(p)], False))
    cmds.append(("cenas.py", ["sugerir", "--pasta", str(p)], True))
    if (PASTA_RAIZ / "imagens" / "registro.json").exists():
        cmds.append(("imagens.py", ["sugerir", "--pasta", str(p)], True))
    return cmds


def _legenda_reaproveitavel(t, p) -> bool:
    """A legenda já existe, foi feita para estes cortes e com este estilo: só as posições precisam ser recalculadas."""
    arq, cortes = p / "legendas.json", p / "cortes.json"
    if not (arq.exists() and cortes.exists()):
        return False
    leg, estilo = _v(t, "legenda", {}), ler_json(arq).get("estilo", {})
    return (estilo.get("cortes") == assinatura_dos_cortes(ler_json(cortes)) and estilo.get("formato") == _formato(t)
            and estilo.get("palavras") == leg.get("palavras", 3) and estilo.get("posicao") == leg.get("posicao", "auto")
            and estilo.get("tamanho") == leg.get("tamanho", 0.046) and bool(estilo.get("maiusculas")) == bool(leg.get("maiusculas"))
            and estilo.get("destaque", True) == (leg.get("destaque") is not False))


def _c_legenda(t, p):
    leg = _v(t, "legenda", {})
    if _legenda_reaproveitavel(t, p):           # mudou só a câmera: o texto revisado fica
        return [("legendas.py", ["--pasta", str(p), "--reaproveitar"], False)]
    a = ["--pasta", str(p), "--formato", _formato(t), "--palavras", str(leg.get("palavras", 3)),
         "--posicao", leg.get("posicao", "auto"), "--tamanho", str(leg.get("tamanho", 0.046))]
    if leg.get("maiusculas"):
        a.append("--maiusculas")
    if leg.get("destaque") is False:
        a.append("--sem-destaque")
    return [("legendas.py", a, False)]


def _c_som(t, p):
    som = _v(t, "som", {})
    a = ["planejar", "--pasta", str(p)]
    if som.get("musica", "nenhuma") != "nenhuma":
        a += ["--musica", som["musica"]]
    if som.get("efeitos"):
        a.append("--efeitos")
    return [("som.py", a, False)]


def _c_amostra(t, p):
    ini, fim = _janela_da_amostra(p)
    return [("renderizar.py", ["--pasta", str(p), "--amostra", str(ini), str(fim), *_args_render(t)], False)]


def _c_video(t, p):
    return [("renderizar.py", ["--pasta", str(p), *_args_render(t)], False)]


def _ultimo_video(p: Path) -> Path | None:
    achados = sorted(x for x in p.glob("*-v[0-9][0-9][0-9].mp4") if not x.name.startswith("amostra"))
    return achados[-1] if achados else None


def _c_conferir(t, p):
    v = _ultimo_video(p)
    if not v:
        return []
    a = ["--pasta", str(p), "--video", str(v), "--retranscrever"]
    if _v(t, "pausas_ok"):
        a += ["--pausas-ok", *(str(x) for x in _v(t, "pausas_ok"))]
    return [("conferir.py", a, False)]


def _portao_fatos(t, p):
    arq = p / "fatos.json"
    pend = [i for i in ler_json(arq)["itens"] if i["gravidade"] == "alta" and i["status"] == "pendente"] if arq.exists() else []
    if not pend:
        return None
    return {"nome": "fatos", "tipo": "julgamento", "pergunta": f"{len(pend)} ponto(s) da fala para confirmar, corrigir ou cortar (fatos.py mostrar)",
            "arquivos": ["fatos.json"]}


def _portao_gancho(t, p):
    prop = ler_json(p / "gancho.json").get("propostas", []) if (p / "gancho.json").exists() else []
    des = ler_json(p / "olhar.json").get("desvios", []) if (p / "olhar.json").exists() else []
    if not prop and not des:
        return None
    return {"nome": "gancho_olhar", "tipo": "julgamento",
            "pergunta": f"{len(prop)} proposta(s) de gancho e {len(des)} trecho(s) de leitura para decidir",
            "arquivos": ["gancho.json", "olhar.json", "olhar-quadros.jpg"]}


def _portao_amostra(t, p):
    if _v(t, "amostra", "conferir") != "aprovar":
        return None
    return {"nome": "amostra", "tipo": "aprovacao", "pergunta": "Aprovar a amostra antes do vídeo inteiro?",
            "arquivos": [x.name for x in sorted(p.glob("amostra-v*.mp4"))[-1:]]}


def _portao_conferir(t, p):
    v = _ultimo_video(p)
    arq = v.with_suffix(".conferencia.json") if v else None
    if arq and arq.exists() and not ler_json(arq).get("aprovado", True):
        return {"nome": "problemas", "tipo": "julgamento", "pergunta": "A conferência achou problemas: corrigir ou aceitar",
                "arquivos": [arq.name]}
    return None


ETAPAS = [
    Etapa("inspecionar", "inspecionar", (), ("perfil",), ("@videos",), ("inspecao.json",), _c_inspecionar,
          portao=lambda t, p: {"nome": "cartao", "tipo": "aprovacao", "pergunta": "Aprovar o cartão de ajustes", "arquivos": []}),
    Etapa("transcrever", "transcrever", ("inspecionar",), ("termos",), (), ("transcricoes",), _c_transcrever),
    Etapa("cortes", "cortes", ("transcrever",), ("ritmo",), (), ("cortes.json",),
          lambda t, p: [("propor_cortes.py", ["--pasta", str(p), "--ritmo", _v(t, "ritmo", "natural")], False)],
          portao=lambda t, p: {"nome": "cortes", "tipo": "julgamento",
                               "pergunta": "Revisar os cortes (cortes.json): tomadas, fim da gravação, o que não pode sair",
                               "arquivos": ["cortes.json"]}),
    Etapa("fatos", "fatos", ("cortes",), ("fatos",), ("cortes.json",), ("fatos.json",),
          lambda t, p: [("fatos.py", ["marcar", "--pasta", str(p)], False)],
          pulada=lambda t: not _v(t, "fatos", True), portao=_portao_fatos),
    Etapa("rosto", "rosto", ("cortes",), ("formato",), ("cortes.json",), ("rosto.json",),
          lambda t, p: [("rosto.py", ["--pasta", str(p), "--formato", _formato(t)], False)]),
    Etapa("gancho_olhar", "gancho e olhar", ("cortes", "rosto"), ("formato", "gancho_olhar"), ("cortes.json", "rosto.json"),
          ("gancho.json",),
          lambda t, p: [("gancho.py", ["avaliar", "--pasta", str(p)], False),
                        ("olhar.py", ["medir", "--pasta", str(p), "--formato", _formato(t)], True)],
          pulada=lambda t: not _v(t, "gancho_olhar", True), portao=_portao_gancho),
    Etapa("elementos", "elementos", ("cortes", "rosto"), ("elementos", "formato"), ("cortes.json", "rosto.json"),
          ("elementos.json",), _c_elementos, pulada=lambda t: not _v(t, "elementos", {}).get("ligado", True),
          portao=lambda t, p: {"nome": "elementos", "tipo": "julgamento",
                               "pergunta": "Revisar os elementos (elementos.json, cenas e imagens sugeridas) com a prévia",
                               "arquivos": ["elementos.json", "cenas-sugeridas.json"]}),
    Etapa("camera", "câmera", ("cortes", "rosto", "elementos"), ("camera",), ("cortes.json", "rosto.json", "elementos.json"),
          ("camera.json",),
          lambda t, p: [("camera.py", ["planejar", "--pasta", str(p), "--intensidade", _v(t, "camera", "normal")], False)],
          pulada=lambda t: _v(t, "camera", "nenhum") == "nenhum"),
    Etapa("legenda", "legenda", ("cortes", "rosto", "camera"), ("legenda", "formato"),
          ("cortes.json", "rosto.json", "camera.json"), ("legendas.json",), _c_legenda,
          pulada=lambda t: not _v(t, "legenda", {}).get("ligada", True),
          portao=lambda t, p: {"nome": "legenda", "tipo": "julgamento",
                               "pergunta": "Revisar a grafia da legenda (legendas.json)", "arquivos": ["legendas.json"]}),
    Etapa("som", "som", ("elementos",), ("som",), ("elementos.json",), ("som.json",), _c_som,
          pulada=lambda t: _v(t, "som", {}).get("musica", "nenhuma") == "nenhuma" and not _v(t, "som", {}).get("efeitos")),
    Etapa("amostra", "amostra", ("cortes", "legenda", "camera", "som", "elementos"),
          ("formato", "hdr", "ruido", "volume", "legenda", "elementos", "som"),
          ("@cortes-completo", "legendas.json", "camera.json", "som.json", "elementos.json"), ("@amostra",),
          _c_amostra, portao=_portao_amostra),
    Etapa("video", "vídeo inteiro", ("amostra",), ("formato", "hdr", "ruido", "volume"),
          ("@cortes-completo", "legendas.json", "camera.json", "som.json", "elementos.json"), ("@video",), _c_video),
    Etapa("conferir", "conferir", ("video",), ("pausas_ok",), (), ("@conferencia",), _c_conferir, portao=_portao_conferir),
    Etapa("entrega", "entrega", ("conferir",), (), (), (), lambda t, p: []),
]
POR_NOME = {e.nome: e for e in ETAPAS}


# ---------- estado ----------

def curto(pasta: Path) -> str:
    """O caminho como a pessoa digitaria: relativo à pasta atual, quando for mais curto."""
    rel = os.path.relpath(pasta)
    return rel if len(rel) < len(str(pasta)) else str(pasta)


def agora() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def caminho_estado(pasta: Path) -> Path:
    return pasta / "trabalho.json"


def carregar(pasta: Path) -> dict:
    arq = caminho_estado(pasta)
    if not arq.exists():
        erro(f"não há trabalho.json em {pasta}: rode editar.py novo")
    t = ler_json(arq)
    for nome, e in t.get("etapas", {}).items():          # processo que sumiu no meio: interrompida
        if e.get("estado") == "rodando" and not _vivo(e.get("pid")):
            e["estado"] = "interrompida"
    return t


def salvar(pasta: Path, t: dict):
    salvar_json_atomico(caminho_estado(pasta), t)


def _vivo(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def _hash_arquivo(pasta: Path, nome: str, t: dict) -> str:
    if nome == "@videos":
        partes = []
        for v in t["videos"]:
            s = Path(v).stat() if Path(v).exists() else None
            partes.append([v, s.st_size if s else 0, s.st_mtime_ns if s else 0])
        return hashlib.sha1(json.dumps(partes).encode()).hexdigest()[:12]
    f = pasta / nome
    if nome == "@cortes-completo":       # com o ganho de cada trecho: a amostra e o vídeo dependem dele
        f = pasta / "cortes.json"
    elif nome == "cortes.json" and f.is_file():     # sem o ganho: rosto, elementos, câmera e legenda não dependem dele
        try:
            return assinatura_dos_cortes(json.loads(f.read_text(encoding="utf-8")))
        except ValueError:
            pass
    return hashlib.sha1(f.read_bytes()).hexdigest()[:12] if f.is_file() else "-"


def hash_esperado(t: dict, e: Etapa, pasta: Path) -> str:
    base = {"escolhas": {k: t["escolhas"].get(k) for k in e.chaves},
            "perfil": t.get("perfil") if "perfil" in e.chaves else None,
            "arquivos": {a: _hash_arquivo(pasta, a, t) for a in e.arquivos},
            "execucoes": {d: t["etapas"].get(d, {}).get("execucao") for d in e.depende}}
    return hashlib.sha1(json.dumps(base, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _saidas_ok(e: Etapa, pasta: Path, t: dict) -> bool:
    for s in e.saidas:
        if s == "@amostra" and not list(pasta.glob("amostra-v*.mp4")):
            return False
        elif s == "@video" and _ultimo_video(pasta) is None:
            return False
        elif s == "@conferencia":
            v = _ultimo_video(pasta)
            if not (v and v.with_suffix(".conferencia.json").exists()):
                return False
        elif not s.startswith("@") and not (pasta / s).exists():
            return False
    return True


def situacao(t: dict, e: Etapa, pasta: Path) -> str:
    """pendente, rodando, interrompida, falhou, feita, desatualizada ou pulada."""
    if e.pulada(t):
        return "pulada"
    reg = t["etapas"].get(e.nome)
    if not reg:
        return "pendente"
    if reg["estado"] == "pulada":       # antes era pulada e agora não é mais
        return "pendente"
    if reg["estado"] in ("rodando", "interrompida", "falhou"):
        return reg["estado"]
    if reg["estado"] == "feita" and (reg.get("hash") != hash_esperado(t, e, pasta) or not _saidas_ok(e, pasta, t)):
        return "desatualizada"
    return reg["estado"]


def _aprovado(t: dict, nome: str, hash_etapa: str) -> bool:
    return any(a["portao"] == nome and a.get("etapa_hash") == hash_etapa for a in t.get("aprovacoes", []))


# ---------- escolhas e cartão ----------

def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40] or "edicao"


def escolhas_da_serie(s: dict) -> tuple[dict, dict]:
    """(escolhas, origens) a partir de uma série: o que a série define vem dela, o resto fica no padrão."""
    esc = json.loads(json.dumps(ESCOLHAS_PADRAO))
    org = {}
    for chave in ("ritmo", "formato", "ruido", "termos"):
        if chave in s:
            esc[chave], org[chave] = s[chave], "serie"
    for chave in ("legenda", "elementos"):
        if chave in s:
            esc[chave] = {**esc[chave], **s[chave]}
            org[chave] = "serie"
    if "camera" in s:
        esc["camera"], org["camera"] = s["camera"].get("zoom", "nenhum"), "serie"
    if "som" in s:
        esc["som"] = {**esc["som"], **{k: v for k, v in s["som"].items() if k != "volume"}}
        org["som"] = "serie"
        if "volume" in s["som"]:
            esc["volume"], org["volume"] = s["som"]["volume"], "serie"
    return esc, org


def _sugestao_de_ruido(insp: dict) -> str:
    sug = [((v.get("audio") or {}).get("ruido") or {}).get("sugestao", "nao") for v in insp["videos"]]
    return "forte" if "forte" in sug else ("leve" if "leve" in sug else "nao")


def montar_cartao(t: dict, insp: dict) -> dict:
    """O cartão como dados: pendências com opções em letra, ajustes com a origem, e a linha técnica."""
    esc, org = t["escolhas"], t.get("origens", {})
    pend, avisos = [], []
    letras = iter("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    if any(v["hdr"] for v in insp["videos"]) and not esc.get("hdr"):
        pend.append({"id": "hdr", "pergunta": "O vídeo está em HDR (padrão do iPhone).", "opcoes": [
            {"letra": next(letras), "texto": "converter para cor padrão, fica igual em todo celular", "recomendada": True, "efeito": {"hdr": "sdr"}},
            {"letra": next(letras), "texto": "manter HDR", "recomendada": False, "efeito": {"hdr": "manter"}}]})
    sug = _sugestao_de_ruido(insp)
    if esc.get("ruido", "auto") == "auto" and sug != "nao":
        diff = min(((v.get("audio") or {}).get("ruido") or {}).get("diferenca_db", 99) for v in insp["videos"])
        pend.append({"id": "ruido", "pergunta": f"Tem chiado de fundo ({diff} dB abaixo da voz).", "opcoes": [
            {"letra": next(letras), "texto": f"redução de ruído {sug}", "recomendada": True, "efeito": {"ruido": sug}},
            {"letra": next(letras), "texto": "deixar como está", "recomendada": False, "efeito": {"ruido": "nao"}}]})
    for v in insp["videos"]:
        au = v.get("audio") or {}
        if (au.get("estouro") or {}).get("estouro") in ("certo", "possível"):
            avisos.append(f"{v['nome']}: áudio possivelmente estourado (não tem conserto na edição; só regravando a frase)")
        if (au.get("eco") or {}).get("eco") in ("sim", "pouco"):
            avisos.append(f"{v['nome']}: a sala tem eco (não dá para tirar na edição)")
        if au and au.get("faixas_de_audio", 1) > 1:
            avisos.append(f"{v['nome']}: mais de uma faixa de áudio (a skill usa a primeira)")
    return {"pendencias": pend, "avisos": avisos, "origens": org}


def _tag(org: dict, chave: str, padrao: str = "sugerido") -> str:
    return {"serie": "_(da série)_", "pediu": "_(você pediu)_", "video": "_(do seu vídeo)_"}.get(org.get(chave), f"_({padrao})_")


def texto_do_cartao(t: dict, insp: dict) -> str:
    c = montar_cartao(t, insp)
    esc, org = t["escolhas"], c["origens"]
    out = [f"### 🎬 {t.get('tema', 'Edição')} · ajustes para aprovar", ""]
    if c["pendencias"] or c["avisos"]:
        out += ["**⚠️ Preciso que você escolha**", ""]
        for p in c["pendencias"]:
            ops = " · ".join(f"**{o['letra']})** {o['texto']}{' (recomendado)' if o['recomendada'] else ''}" for o in p["opcoes"])
            out.append(f"- {p['pergunta']} {ops}")
        out += [f"- Aviso: {a}" for a in c["avisos"]]
        out.append("")
    out += ["**📋 Ajustes**", ""]
    vids = " · ".join(f"{i}. `{v['nome']}` ({int(v['duracao'] // 60)}:{int(v['duracao'] % 60):02d})" for i, v in enumerate(insp["videos"], 1))
    out.append(f"- 🎞️ **Vídeos**: {vids} _(você mandou)_")
    out.append(f"- ✂️ **Limpeza**: ritmo {'dinâmico' if esc['ritmo'] == 'dinamico' else 'natural'}; tiro pausas longas, respirações, erros e repetições {_tag(org, 'ritmo')}")
    leg = esc["legenda"]
    out.append("- 💬 **Legenda**: " + ("desligada" if not leg.get("ligada", True) else
               f"até {leg.get('palavras', 3)} palavras por vez, "
               f"{ {'auto': 'fora do rosto', 'baixo': 'embaixo', 'meio': 'no meio', 'alto': 'em cima'}[leg.get('posicao', 'auto')] }") + f" {_tag(org, 'legenda')}")
    el = esc["elementos"]
    out.append("- ✨ **Elementos 3D**: " + ("desligados" if not el.get("ligado", True) else
               f"nas palavras que combinam, {'em tela cheia' if el.get('modo') == 'tela' else 'sobrepostos, fora do rosto'}, um a cada {el.get('intervalo', 6)} s no máximo"
               + (", sem elementos novos desenhados" if el.get("gerados") is False else "")) + f" {_tag(org, 'elementos')}")
    out.append("- 🎥 **Câmera**: " + ("parada, sem zoom" if esc["camera"] == "nenhum" else f"zoom de ênfase {esc['camera']}") + f" {_tag(org, 'camera')}")
    som = esc["som"]
    out.append("- 🔊 **Som**: " + " · ".join(["sem música" if som.get("musica", "nenhuma") == "nenhuma" else f"música {som['musica']}",
               "efeito em cada elemento 3D" if som.get("efeitos") else "sem efeito", f"voz em {esc['volume']} LUFS"]) + f" {_tag(org, 'som')}")
    out.append(f"- 🎨 **Imagem**: {'cor padrão (convertida do HDR)' if esc.get('hdr') == 'sdr' else 'cor original'} _(sugerido)_")
    maior = max(v["largura"] for v in insp["videos"])
    fmt = esc["formato"]
    sug = f"; reduzido de {maior} para 1080 de largura, o tamanho do Instagram" if maior > 1080 and "@" not in fmt else ""
    out.append(f"- 📐 **Formato**: {fmt}{sug} {_tag(org, 'formato')}")
    rev = {"conferir": "eu confiro uma amostra de 8 a 15 s antes do vídeo inteiro", "aprovar": "você aprova a amostra antes do vídeo inteiro",
           "nao": "sem amostra"}[esc["amostra"]]
    out.append(f"- 👀 **Revisão**: {rev} _(sugerido)_")
    out.append(f"- 📁 **Entrega**: `{t['pasta_relativa']}/{t['pasta_relativa'].split('/')[-1]}-v001.mp4` _(sugerido)_")
    if c["pendencias"]:
        exemplo = " e ".join(f"**{p['opcoes'][0]['letra']}**" for p in c["pendencias"])
        out += ["", f"👉 Responda {exemplo} para começar, ou diga o que mudar."]
    else:
        out += ["", "👉 Responda **ok** para começar, ou diga o que mudar."]
    return "\n".join(out)


def aplicar_resposta(t: dict, insp: dict, resposta: str) -> list[str]:
    """Aplica as letras às escolhas. Devolve o que ficou sem resposta (vazio = pode aprovar)."""
    c = montar_cartao(t, insp)
    letras = {x.upper() for x in re.findall(r"[A-Za-z]", resposta or "")} if resposta else set()
    faltam = []
    for p in c["pendencias"]:
        escolhidas = [o for o in p["opcoes"] if o["letra"] in letras]
        if len(escolhidas) != 1:
            faltam.append(f"{p['pergunta']} (responda uma letra: {' ou '.join(o['letra'] for o in p['opcoes'])})")
            continue
        for k, v in escolhidas[0]["efeito"].items():
            if k == "hdr" and v == "manter" and t["escolhas"]["camera"] != "nenhum":
                faltam.append("o zoom não funciona com HDR mantido: escolha converter, ou tire o zoom (ajustar camera=nenhum)")
                break
            t["escolhas"][k] = v
            t.setdefault("origens", {})[k] = "pediu"
    return faltam


# ---------- execução ----------

def _resumo_da_saida(texto: str) -> str:
    linhas = [l.strip() for l in texto.splitlines() if l.strip() and not l.strip().startswith(("Warning", "carregando"))]
    final = [l for l in linhas if l.startswith("ok")] or linhas[-1:]
    r = " | ".join(x[:MAX_RESUMO] for x in final[-2:])
    return r[:MAX_RESUMO * 2]


def resumo_da_etapa(nome: str, pasta: Path, texto: str) -> str:
    """Uma linha com o que a etapa produziu, lida dos arquivos dela (sem caminhos nem listas)."""
    try:
        if nome == "inspecionar":
            v = ler_json(pasta / "inspecao.json")["videos"]
            return (f"{len(v)} vídeo(s), {tempo(sum(x['duracao'] for x in v))}, {v[0]['largura']}x{v[0]['altura']}"
                    f"{', HDR' if any(x['hdr'] for x in v) else ''}")
        if nome == "transcrever":
            n = sum(len(ler_json(f)["palavras"]) for f in (pasta / "transcricoes").glob("*.json"))
            return f"{n} palavras"
        if nome == "cortes":
            c = ler_json(pasta / "cortes.json")
            return (f"{tempo(c['duracao_original'])} → {tempo(c['duracao_final'])} em {len(c['trechos'])} trechos, "
                    f"{len(c.get('conferir', []))} para conferir")
        if nome == "fatos":
            n = sum(1 for i in ler_json(pasta / "fatos.json")["itens"] if i["gravidade"] == "alta" and i["status"] == "pendente")
            return f"{n} ponto(s) para confirmar" if n else "nada para confirmar"
        if nome == "rosto":
            ts = ler_json(pasta / "rosto.json")["trechos"]
            return f"rosto achado em {sum(t['achou'] for t in ts) / max(1, len(ts)):.0%} das medidas"
        if nome == "gancho_olhar":
            g = ler_json(pasta / "gancho.json")
            o = ler_json(pasta / "olhar.json")["desvios"] if (pasta / "olhar.json").exists() else []
            return f"gancho nota {g['abertura']['nota']}/5, {len(g['propostas'])} proposta(s); {len(o)} trecho(s) de leitura"
        if nome == "elementos":
            n = len(ler_json(pasta / "elementos.json")["itens"])
            c = len(ler_json(pasta / "cenas-sugeridas.json")["propostas"]) if (pasta / "cenas-sugeridas.json").exists() else 0
            return f"{n} elemento(s), {c} cena(s) sugerida(s)"
        if nome == "camera":
            return f"{len(ler_json(pasta / 'camera.json')['blocos'])} blocos de câmera"
        if nome == "legenda":
            return f"{len(ler_json(pasta / 'legendas.json')['blocos'])} blocos de legenda"
        if nome == "som":
            return f"{len(ler_json(pasta / 'som.json')['efeitos'])} efeito(s) sonoro(s)"
        if nome == "amostra":
            return sorted(pasta.glob("amostra-v*.mp4"))[-1].name
        if nome == "video":
            v = _ultimo_video(pasta)
            return f"{v.name} ({v.stat().st_size / 1e6:.0f} MB)"
        if nome == "conferir":
            c = ler_json(_ultimo_video(pasta).with_suffix(".conferencia.json"))
            ruins = [x["item"] for x in c["checks"] if not x["ok"]]
            return "tudo certo" if not ruins else f"{len(ruins)} problema(s): " + "; ".join(r[:40] for r in ruins[:3])
    except (OSError, KeyError, ValueError, IndexError, TypeError, AttributeError):
        pass
    return _resumo_da_saida(texto.replace(str(pasta) + "/", ""))


def executar_subprocesso(argv: list[str], log: Path) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(SCRIPTS / argv[0]), *argv[1:]], capture_output=True, text=True)
    saida = (p.stdout or "") + (("\n" + p.stderr) if p.stderr else "")
    with log.open("a", encoding="utf-8") as f:
        f.write(f"$ {' '.join(argv)}\n{saida}\n")
    return p.returncode, saida


def _pedido(t: dict, pasta: Path, g: dict):
    d = pasta / "pedidos"
    d.mkdir(exist_ok=True)
    salvar_json_atomico(d / f"{g['nome']}.json", {
        "portao": g["nome"], "tipo": g["tipo"], "tarefa": g["pergunta"], "arquivos": g.get("arquivos", []),
        "resposta_esperada": {"arquivo": f"respostas/{g['nome']}.json", "esquema": {"aprovado": "true ou false", "notas": "texto curto"}}})


def _abrir_portao(t: dict, pasta: Path, g: dict, hash_etapa: str):
    g = {**g, "aberto_em": agora(), "etapa_hash": hash_etapa}
    t["portao"] = g
    _pedido(t, pasta, g)


def proximo(pasta: Path, executor=executar_subprocesso, saida=print) -> str:
    """Roda etapas até o próximo portão ou o fim. Devolve: 'portao', 'fim' ou 'falhou'."""
    t = carregar(pasta)
    if t.get("portao"):
        saida(f"⏸ portão aberto: {t['portao']['pergunta']}. Para seguir: editar.py aprovar --pasta {curto(pasta)}")
        return "portao"
    (pasta / "etapas").mkdir(exist_ok=True)
    for e in ETAPAS:
        sit = situacao(t, e, pasta)
        if sit == "pulada":
            t["etapas"][e.nome] = {"estado": "pulada"}
            continue
        esperado = hash_esperado(t, e, pasta)
        if sit == "feita":
            pass
        else:
            cmds = e.comandos(t, pasta)
            reg = {"estado": "rodando", "inicio": agora(), "pid": os.getpid()}
            t["etapas"][e.nome] = reg
            salvar(pasta, t)
            t0 = time.time()
            texto = ""
            for script, args, opcional in cmds:
                try:
                    codigo, texto = executor([script, *args], pasta / "etapas" / f"{e.nome}.log")
                except Cancelado:
                    reg.update(estado="interrompida", fim=agora(), resumo="cancelada")
                    reg.pop("pid", None)
                    salvar(pasta, t)
                    saida(f"↺ {e.titulo}: cancelada. Para continuar: editar.py proximo --pasta {curto(pasta)}")
                    return "cancelado"
                if codigo != 0 and not opcional:
                    reg.update(estado="falhou", fim=agora(), resumo=_resumo_da_saida(texto.replace(str(pasta) + "/", "")))
                    salvar(pasta, t)
                    saida(f"✗ {e.titulo}: falhou. {reg['resumo']} (veja etapas/{e.nome}.log)")
                    return "falhou"
            if e.nome in ("amostra", "video") and not _saidas_ok(e, pasta, t):
                reg.update(estado="falhou", fim=agora(), resumo="não gerou o arquivo esperado")
                salvar(pasta, t)
                saida(f"✗ {e.titulo}: não gerou o arquivo esperado (veja etapas/{e.nome}.log)")
                return "falhou"
            ultimo = resumo_da_etapa(e.nome, pasta, texto)
            reg.update(estado="feita", fim=agora(), hash=esperado, execucao=uuid.uuid4().hex[:8], resumo=ultimo)
            reg.pop("pid", None)
            salvar(pasta, t)
            saida(f"✓ {e.titulo} ({time.time() - t0:.0f} s){': ' + ultimo if ultimo else ''}")
        g = e.portao(t, pasta)
        if g and not _aprovado(t, g["nome"], esperado):
            if g["nome"] == "cartao":
                insp = ler_json(pasta / "inspecao.json")
                g["pergunta"] = "Aprovar o cartão de ajustes (editar.py cartao)"
                _abrir_portao(t, pasta, {**g, "cartao": montar_cartao(t, insp)}, esperado)
            else:
                _abrir_portao(t, pasta, g, esperado)
            salvar(pasta, t)
            saida(f"⏸ portão: {g['pergunta']}. Quando decidir: editar.py aprovar --pasta {curto(pasta)}")
            return "portao"
    salvar(pasta, t)
    saida("✓ edição completa")
    return "fim"


def aprovar(pasta: Path, portao: str | None, resposta: str | None) -> str:
    t = carregar(pasta)
    g = t.get("portao")
    if not g:
        raise PedidoRecusado("não há portão aberto")
    if portao and portao != g["nome"]:
        raise PedidoRecusado(f"o portão aberto é {g['nome']}, não {portao}")
    if g["nome"] == "cartao":
        faltam = aplicar_resposta(t, ler_json(pasta / "inspecao.json"), resposta or "")
        if faltam:                 # nada é gravado pela metade: as letras das perguntas não mudam entre uma tentativa e outra
            raise PedidoRecusado("faltam respostas: " + "; ".join(faltam))
    resp = pasta / "respostas" / f"{g['nome']}.json"
    if resp.exists():
        r = ler_json(resp)
        if r.get("aprovado") is not True:
            raise PedidoRecusado(f"a resposta de {g['nome']} não aprova ({r.get('notas', 'sem notas')}): ajuste e responda de novo")
    t.setdefault("aprovacoes", []).append({"portao": g["nome"], "etapa_hash": g["etapa_hash"], "resposta": resposta or "ok",
                                           "quando": agora(), "quem": "pessoa"})
    t["portao"] = None
    salvar(pasta, t)
    return g["nome"]


def aprovar_e_seguir(pasta: Path, portao: str | None, resposta: str | None, executor=executar_subprocesso, saida=print) -> str:
    """Aprova o portão aberto e já roda até o próximo: uma chamada em vez de duas."""
    nome = aprovar(pasta, portao, resposta)
    saida(f"ok  portão {nome} aprovado")
    return proximo(pasta, executor, saida)


def _valor(txt: str):
    try:
        return json.loads(txt)
    except ValueError:
        return txt


def ajustar(pasta: Path, escolha: str) -> list[str]:
    """Muda uma escolha (chave ou chave.sub=valor). Devolve as etapas que serão refeitas."""
    if "=" not in escolha:
        raise PedidoRecusado("use chave=valor, por exemplo camera=leve ou legenda.palavras=2")
    caminho, valor = escolha.split("=", 1)
    chaves = caminho.split(".")
    t = carregar(pasta)
    if chaves[0] not in ESCOLHAS_PADRAO:
        raise PedidoRecusado(f"escolha desconhecida: {chaves[0]} (use {', '.join(ESCOLHAS_PADRAO)})")
    antes = {e.nome: situacao(t, e, pasta) for e in ETAPAS}
    alvo = t["escolhas"]
    for k in chaves[:-1]:
        alvo = alvo.setdefault(k, {})
    alvo[chaves[-1]] = _valor(valor)
    t.setdefault("origens", {})[chaves[0]] = "pediu"
    salvar(pasta, t)
    return [e.nome for e in ETAPAS if antes[e.nome] == "feita" and situacao(t, e, pasta) == "desatualizada"]


def refazer(pasta: Path, nome: str):
    if nome not in POR_NOME:
        raise PedidoRecusado(f"etapa desconhecida: {nome} (use {', '.join(POR_NOME)})")
    t = carregar(pasta)
    t["etapas"].pop(nome, None)
    t["portao"] = None
    t["aprovacoes"] = [a for a in t.get("aprovacoes", []) if a["portao"] != (POR_NOME[nome].portao(t, pasta) or {}).get("nome")]
    salvar(pasta, t)


# ---------- estado e saída curta ----------

SIMBOLO = {"feita": "✓", "pulada": "–", "pendente": "·", "rodando": "▶", "interrompida": "↺", "falhou": "✗", "desatualizada": "↻"}


def linhas_do_estado(t: dict, pasta: Path) -> list[str]:
    out = [f"{pasta.name} · perfil {t.get('perfil') or 'padrão'}" + (f" · série {t['serie']}" if t.get("serie") else "")]
    for e in ETAPAS:
        s = situacao(t, e, pasta)
        resumo = (t["etapas"].get(e.nome, {}).get("resumo") or "")[:70] if s in ("feita", "falhou") else ""
        out.append(f" {SIMBOLO[s]} {e.titulo:<14} {s}{'  ' + resumo if resumo else ''}")
    if t.get("portao"):
        out.append(f"⏸ portão: {t['portao']['pergunta']}")
    return out


def estado_json(t: dict, pasta: Path) -> dict:
    return {"pasta": pasta.name, "perfil": t.get("perfil"), "serie": t.get("serie"),
            "etapas": {e.nome: situacao(t, e, pasta) for e in ETAPAS},
            "portao": ({"nome": t["portao"]["nome"], "tipo": t["portao"]["tipo"], "pergunta": t["portao"]["pergunta"]}
                       if t.get("portao") else None)}


# ---------- novo ----------

def novo(videos: list[Path], serie: str | None, perfil: str | None, tema: str | None, base: Path | None = None) -> Path:
    for v in videos:
        if not v.exists():
            erro(f"não achei {v}")
    tema = _slug(tema or videos[0].stem)
    base = base or PASTA_RAIZ / "saida"
    nome = f"{datetime.date.today().isoformat()}_{tema}"
    pasta, n = base / nome, 2
    while pasta.exists():                       # nunca sobrescreve
        pasta = base / f"{nome}-{n}"
        n += 1
    pasta.mkdir(parents=True)
    esc, org = json.loads(json.dumps(ESCOLHAS_PADRAO)), {}
    if serie:
        import serie as mod_serie
        s = mod_serie.carregar(serie)
        problemas = mod_serie.validar(s)
        if problemas:
            erro("a série tem problema: " + "; ".join(problemas))
        esc, org = escolhas_da_serie(s)
        salvar_json_atomico(pasta / "serie.json", s)
    t = {"versao": 1, "tema": tema.replace("-", " "), "perfil": perfil, "serie": serie,
         "videos": [str(v.resolve()) for v in videos], "escolhas": esc, "origens": org, "etapas": {}, "portao": None,
         "aprovacoes": [], "criado_em": agora(),
         "pasta_relativa": str(pasta.relative_to(PASTA_RAIZ)) if pasta.is_relative_to(PASTA_RAIZ) else str(pasta)}
    salvar(pasta, t)
    return pasta


# ---------- linha de comando ----------

def main():
    try:
        _main()
    except PedidoRecusado as e:
        erro(str(e), 1)


def _main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["novo", "proximo", "estado", "cartao", "aprovar", "ajustar", "refazer"])
    ap.add_argument("alvo", nargs="*", help="novo: os vídeos · aprovar: o portão · refazer: a etapa")
    ap.add_argument("--pasta", type=Path)
    ap.add_argument("--serie")
    ap.add_argument("--perfil")
    ap.add_argument("--tema")
    ap.add_argument("--resposta")
    ap.add_argument("--escolha")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--seguir", action="store_true", help="aprovar: depois de aprovar, já roda até o próximo portão")
    a = ap.parse_args()

    if a.acao == "novo":
        if not a.alvo:
            erro("diga os vídeos: editar.py novo VIDEO [VIDEO ...]")
        p = novo([Path(x) for x in a.alvo], a.serie, a.perfil, a.tema)
        print(f"ok  {p}\n    próximo passo: editar.py proximo --pasta {curto(p)}")
        return
    if not a.pasta:
        erro("informe --pasta")
    pasta = a.pasta.resolve()
    if a.acao == "proximo":
        sys.exit({"portao": 0, "fim": 0, "falhou": 1, "cancelado": 0}[proximo(pasta)])
    elif a.acao == "estado":
        t = carregar(pasta)
        print(json.dumps(estado_json(t, pasta), ensure_ascii=False) if a.json else "\n".join(linhas_do_estado(t, pasta)))
    elif a.acao == "cartao":
        t = carregar(pasta)
        if not (pasta / "inspecao.json").exists():
            erro("o cartão sai depois da inspeção: rode editar.py proximo")
        print(texto_do_cartao(t, ler_json(pasta / "inspecao.json")))
    elif a.acao == "aprovar":
        if a.seguir:
            sys.exit({"portao": 0, "fim": 0, "falhou": 1, "cancelado": 0}[aprovar_e_seguir(pasta, a.alvo[0] if a.alvo else None, a.resposta)])
        nome = aprovar(pasta, a.alvo[0] if a.alvo else None, a.resposta)
        print(f"ok  portão {nome} aprovado. Siga com: editar.py proximo --pasta {curto(pasta)}")
    elif a.acao == "ajustar":
        if not a.escolha:
            erro("use --escolha chave=valor")
        refeitas = ajustar(pasta, a.escolha)
        print(f"ok  escolha mudada. Serão refeitas: {', '.join(refeitas) if refeitas else 'nenhuma etapa já feita'}")
    else:
        if len(a.alvo) != 1:
            erro("diga a etapa: editar.py refazer ETAPA --pasta ...")
        refazer(pasta, a.alvo[0])
        print(f"ok  {a.alvo[0]} será refeita (e as que dependem dela)")


if __name__ == "__main__":
    main()
