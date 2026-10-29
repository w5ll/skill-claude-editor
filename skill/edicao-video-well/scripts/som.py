"""Música de fundo e efeitos sonoros. Só quando o Well pedir com essas palavras.

Uso:
    python som.py listar
    python som.py planejar --pasta saida/2026-10-22_tema [--musica calmo|animado|batida|ARQUIVO]
        [--efeitos] [--abaixo 22] [--sobe 6] [--inicio-musica 0]
    python som.py desligar --pasta saida/2026-10-22_tema

planejar  grava som.json, que o renderizar.py mistura por baixo da voz:
          - música: fica 22 dB abaixo da voz enquanto ele fala e sobe 6 dB nas pausas
            (abaixa sozinha quando ele volta a falar); entra com 0,5 s de subida e sai
            suave no fim. Se for mais curta que o vídeo, repete com 1 s de transição.
          - efeitos: um som para cada elemento 3D, no instante em que o elemento aparece
            (mensagem com som de mensagem, relógio com tique-taque, gráfico com acerto...).
            Elemento gerado segue a animação dele (girar passagem, aparecer clique, brilhar
            brilho...; veja por_animacao em assets/sons/sons.json).
            Tela cheia ganha uma passagem de ar. No mínimo 1,2 s entre um efeito e outro.
desligar  apaga som.json (sai só a voz).

Músicas e efeitos da skill são de domínio público (CC0), com a origem em assets/sons/sons.json.
Música que o Well mandar: passe o caminho do arquivo em --musica; ele responde pelo direito de uso.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np

from comum import PASTA_SKILL, erro, ler_json, salvar_json, tempo

PASTA_SONS = PASTA_SKILL / "assets" / "sons"
TAXA = 48000
ESPACO_EFEITOS = 1.2
EFEITO_ABAIXO_DA_VOZ = 6.0   # o efeito fica 6 dB abaixo da voz (aparece sem atropelar a fala)
POP_DO_ELEMENTO = 0.15       # o elemento "estala" na tela cerca de 0,15 s depois de começar a entrar


def catalogo() -> dict:
    return ler_json(PASTA_SONS / "sons.json")


def decodificar(arquivo, canais: int) -> np.ndarray:
    bruto = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(arquivo), "-vn", "-map", "0:a:0",
                            "-ac", str(canais), "-ar", str(TAXA), "-f", "f32le", "-"],
                           check=True, capture_output=True).stdout
    return np.frombuffer(bruto, dtype=np.float32).reshape(-1, canais).copy()


def envelope(som: np.ndarray) -> np.ndarray:
    """Nível em dB a cada 10 ms (janela de 20 ms), do som em mono."""
    mono = som.mean(axis=1).astype(np.float64)
    n = TAXA // 100
    q = np.concatenate([mono ** 2, np.zeros(2 * n)])
    acc = np.concatenate([[0.0], np.cumsum(q)])
    ini = np.arange(0, len(mono), n)
    rms = np.sqrt(np.maximum((acc[ini + 2 * n] - acc[ini]) / (2 * n), 1e-12))
    return 20 * np.log10(rms)


def nivel_db(som: np.ndarray, mascara10ms: np.ndarray | None = None) -> float:
    if mascara10ms is not None:
        n = TAXA // 100
        idx = np.repeat(mascara10ms, n)[:len(som)]
        som = som[:len(idx)][idx]
    if som.size == 0:
        return -90.0
    return float(10 * np.log10(max(np.mean(som.astype(np.float64) ** 2), 1e-12)))


def mascara_de_fala(voz: np.ndarray) -> np.ndarray:
    from fala import medir_fala
    env = envelope(voz)
    m = medir_fala(env)
    mask = np.zeros(len(env), bool)
    for a, b in m["regioes"]:
        mask[int(a * 100):int(b * 100) + 1] = True
    return mask


def suavizar_mascara(mask: np.ndarray, ataque: float = 0.08, soltura: float = 0.35) -> np.ndarray:
    """0 a 1, sobe rápido quando a fala começa e desce devagar quando ela para."""
    a_sobe, a_desce = 1 - np.exp(-0.01 / ataque), 1 - np.exp(-0.01 / soltura)
    saida = np.zeros(len(mask))
    v = 0.0
    # Olha um pouco à frente: a música já está baixa quando a primeira sílaba chega.
    adiante = np.concatenate([mask[5:], np.zeros(5, bool)]) | mask
    for k, m in enumerate(adiante):
        v += (1.0 - v) * a_sobe if m else (0.0 - v) * a_desce
        saida[k] = v
    return saida


def repetir(musica: np.ndarray, tamanho: int) -> np.ndarray:
    if len(musica) >= tamanho:
        return musica[:tamanho]
    cruz = TAXA
    saida = musica.copy()
    r = np.linspace(0, 1, cruz, dtype=np.float32)[:, None]
    while len(saida) < tamanho:
        saida = np.vstack([saida[:-cruz], saida[-cruz:] * (1 - r) + musica[:cruz] * r, musica[cruz:]])
    return saida[:tamanho]


def mixar(voz: np.ndarray, plano: dict) -> tuple[np.ndarray, dict]:
    """Voz + música + efeitos. Devolve a mistura e as medidas."""
    canais = voz.shape[1]
    mix = voz.astype(np.float32).copy()
    fala = mascara_de_fala(voz)
    voz_db = nivel_db(voz, fala)
    rel = {"voz_db": round(voz_db, 1)}
    cat = catalogo()

    mus = plano.get("musica")
    if mus:
        arq = Path(mus["arquivo"])
        if not arq.is_absolute():
            arq = PASTA_SONS / arq
        if not arq.exists():
            erro(f"música não encontrada: {arq}")
        musica = decodificar(arq, canais)
        musica = musica[int(float(mus.get("inicio_na_musica", 0)) * TAXA):]
        if len(musica) < TAXA * 2:
            erro("a música é curta demais")
        entra = int(float(mus.get("entra_em", 0)) * TAXA)
        trilha = repetir(musica, max(0, len(voz) - entra))
        base = voz_db - float(mus.get("abaixo_da_voz_db", 22)) - nivel_db(trilha)
        sobe = float(mus.get("sobe_na_pausa_db", 6))
        curva = suavizar_mascara(fala)
        ganho_db = base + sobe * (1 - curva)
        ganho = np.repeat(10 ** (ganho_db / 20), TAXA // 100)
        ganho = np.concatenate([ganho, np.full(max(0, len(voz) - len(ganho)), ganho[-1] if len(ganho) else 1.0)])
        g = ganho[entra:entra + len(trilha)].astype(np.float32)[:, None]
        trilha = trilha * g
        sobe_n = min(int(0.5 * TAXA), len(trilha))
        trilha[:sobe_n] *= np.linspace(0, 1, sobe_n, dtype=np.float32)[:, None]
        saida_n = min(int(float(mus.get("saida_s", 1.5)) * TAXA), len(trilha) // 3)
        if saida_n > 0:
            trilha[-saida_n:] *= np.linspace(1, 0, saida_n, dtype=np.float32)[:, None]
        mix[entra:entra + len(trilha)] += trilha
        so_musica = np.zeros_like(voz)
        so_musica[entra:entra + len(trilha)] = trilha
        rel["musica"] = {"arquivo": str(arq), "abaixo_da_voz_na_fala_db": round(voz_db - nivel_db(so_musica, fala), 1),
                         "abaixo_da_voz_nas_pausas_db": round(voz_db - nivel_db(so_musica, ~fala), 1)}

    feitos = []
    for ef in plano.get("efeitos", []):
        info = cat["efeitos"].get(ef["som"])
        if info is None:
            erro(f"efeito desconhecido: {ef['som']} (veja python som.py listar)")
        som = decodificar(PASTA_SONS / info["arquivo"], canais)
        if ef.get("duracao_max"):
            n = int(float(ef["duracao_max"]) * TAXA)
            if len(som) > n:
                som = som[:n].copy()
                f = min(int(0.15 * TAXA), n)
                som[-f:] *= np.linspace(1, 0, f, dtype=np.float32)[:, None]
        pico = float(np.max(np.abs(som))) or 1.0
        ativo = som[np.abs(som).max(axis=1) > pico * 0.03]
        alvo = voz_db - EFEITO_ABAIXO_DA_VOZ + float(ef.get("ganho_db", 0))
        som = som * (10 ** ((alvo - nivel_db(ativo)) / 20))
        ini = int(round((float(ef["tempo"]) - info["ataque"]) * TAXA))
        a, b = max(0, ini), min(len(mix), ini + len(som))
        if b > a:
            mix[a:b] += som[a - ini:b - ini]
            feitos.append({"som": ef["som"], "tempo": ef["tempo"]})
    rel["efeitos"] = feitos
    return mix, rel


def planejar(pasta: Path, musica: str | None, efeitos: bool, abaixo: float, sobe: float, inicio: float) -> dict:
    cat = catalogo()
    plano = {"musica": None, "efeitos": []}
    if musica and musica != "nenhuma":
        if musica in cat["musicas"]:
            arq = cat["musicas"][musica]["arquivo"]
        else:
            caminho = Path(musica).expanduser().resolve()
            if not caminho.exists():
                erro(f"música não encontrada: {musica} (use {', '.join(cat['musicas'])} ou o caminho do arquivo)")
            arq = str(caminho)
        plano["musica"] = {"arquivo": arq, "abaixo_da_voz_db": abaixo, "sobe_na_pausa_db": sobe,
                           "inicio_na_musica": inicio, "entra_em": 0.0, "saida_s": 1.5}
    if efeitos:
        arq = pasta / "elementos.json"
        itens = ler_json(arq).get("itens", []) if arq.exists() else []
        ultimo = -99.0
        for n, it in enumerate(sorted(itens, key=lambda x: x["inicio"])):
            if it["modo"] == "tela":
                nome = cat["por_elemento"]["tela"]
            elif it["elemento"].startswith("cena:"):      # cena explicativa: passagem ao entrar, clique a cada parte
                nome = cat["por_elemento"].get("cena")
            elif it["elemento"].startswith("gerado:"):   # elemento gerado: o som segue a animação dele
                nome = it.get("som") or cat.get("por_animacao", {}).get(it.get("animacao"))
            else:
                nome = cat["por_elemento"].get(it["elemento"])
            t = round(it["inicio"] + POP_DO_ELEMENTO, 3)
            if nome and t - ultimo >= ESPACO_EFEITOS:
                ef = {"som": nome, "tempo": t, "ganho_db": 0, "elemento": it["elemento"]}
                if nome == "tique-taque":
                    ef["duracao_max"] = round(it["duracao"], 2)
                plano["efeitos"].append(ef)
                ultimo = t
            if it["elemento"].startswith("cena:"):
                from cenas import momentos
                for f in momentos(it)[1:]:      # a primeira parte coincide com a entrada da cena
                    tc = round(f, 3)
                    if "clique" in cat["efeitos"] and tc - ultimo >= ESPACO_EFEITOS:
                        plano["efeitos"].append({"som": "clique", "tempo": tc, "ganho_db": 0, "elemento": it["elemento"]})
                        ultimo = tc
    return plano


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["listar", "planejar", "desligar"])
    ap.add_argument("--pasta", type=Path)
    ap.add_argument("--musica", help="calmo, animado, batida, nenhuma ou o caminho de um arquivo")
    ap.add_argument("--efeitos", action="store_true", help="um efeito para cada elemento 3D")
    ap.add_argument("--abaixo", type=float, default=22.0, help="dB da música abaixo da voz enquanto ele fala")
    ap.add_argument("--sobe", type=float, default=6.0, help="dB que a música sobe nas pausas")
    ap.add_argument("--inicio-musica", type=float, default=0.0, help="segundo da música em que ela começa")
    a = ap.parse_args()
    cat = catalogo()
    if a.acao == "listar":
        print("MÚSICAS (domínio público)")
        for k, m in cat["musicas"].items():
            print(f"  {k:<8} {m['titulo']} · {m['autor']} · {m['descricao']}")
        print("\nEFEITOS (domínio público)")
        por = {}
        for el, s in cat["por_elemento"].items():
            por.setdefault(s, []).append(el)
        for an, s in cat.get("por_animacao", {}).items():
            por.setdefault(s, []).append(f"gerado com {an}")
        for k, e in cat["efeitos"].items():
            print(f"  {k:<15} {e['descricao']}  (entra com: {', '.join(por.get(k, [])) or 'à mão'})")
        return
    if not a.pasta:
        erro("informe --pasta")
    pasta = a.pasta.resolve()
    arq = pasta / "som.json"
    if a.acao == "desligar":
        if arq.exists():
            arq.unlink()
        print("sem música e sem efeitos (som.json apagado)")
        return
    if not a.musica and not a.efeitos:
        erro("diga o que entra: --musica e/ou --efeitos")
    plano = planejar(pasta, a.musica, a.efeitos, a.abaixo, a.sobe, a.inicio_musica)
    salvar_json(arq, plano)
    from comum import andamento_fim
    andamento_fim(pasta, "som planejado")
    if plano["musica"]:
        m = plano["musica"]
        print(f"música: {Path(m['arquivo']).name} · {m['abaixo_da_voz_db']:.0f} dB abaixo da voz na fala, "
              f"sobe {m['sobe_na_pausa_db']:.0f} dB nas pausas")
    for ef in plano["efeitos"]:
        print(f"  efeito {ef['som']:<15} em {tempo(ef['tempo'])}  (elemento {ef['elemento']})")
    if a.efeitos and not plano["efeitos"]:
        print("nenhum efeito: não há elementos 3D (rode elementos.py sugerir antes)")
    print(f"ok  {arq}")


if __name__ == "__main__":
    main()
