"""Monta a legenda do vídeo editado, no tempo do corte, palavra por palavra.

Uso:
    python legendas.py --pasta saida/2026-10-22_tema [--palavras 3] [--posicao auto|baixo|meio|alto]
        [--maiusculas] [--sem-destaque] [--perfil NOME]
    python legendas.py --pasta saida/2026-10-22_tema --reaproveitar
        (refaz o .ass e o .srt a partir de legendas.json editado à mão)

Grava:
- legendas.json   os blocos de texto com tempo (é aqui que se corrige grafia)
- legendas.ass    o desenho da legenda que vai queimado no vídeo
- legendas.srt    arquivo de legenda separado, se a pessoa quiser subir à parte

Visual: o do perfil de marca (perfis/NOME/marca.json). No perfil padrão, arven: Sora ExtraBold,
texto #eaefef com contorno escuro, palavra que está sendo falada em #a8b4d4. Até 3 palavras
por vez, fora do rosto e dentro da área segura do Instagram (longe dos botões da direita e da
legenda do post). Os "termos" do perfil corrigem a caixa e a acentuação de marcas e termos.

Posição auto (padrão): fica embaixo, como sempre. Com rosto.json (rosto.py), cada bloco
confere se cobre olhos, boca ou queixo, já com o zoom da câmera (camera.json). Se cobrir,
desce para logo abaixo do queixo; se não couber, sobe para acima da testa; se nem assim
couber, fica embaixo e o script avisa o momento. Rode de novo depois de mudar o corte,
o rosto ou a câmera (o renderizar.py confere).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import unicodedata

from comum import (arquivo_da_fonte, assinatura_da_marca, assinatura_dos_cortes, carregar_marca, definir_perfil,
                   dimensoes_saida, erro, fps_racional, ler_json, salvar_json, trechos_no_quadro)

PAUSA_QUEBRA = 0.30   # pausa que fecha um bloco de legenda
TEMPO_MINIMO = 0.45   # cada bloco fica pelo menos isso na tela
LARGURA_UTIL = 0.74   # fração da largura do vídeo que o texto pode ocupar (área segura)


def cor_ass(hexa: str) -> str:
    """#rrggbb -> &H00bbggrr (formato do ASS)."""
    h = hexa.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def limpar(p: str) -> str:
    """Tira vírgula e ponto do fim (legenda de Reels fica mais limpa); mantém ? e !."""
    return re.sub(r"[.,;:…]+$", "", p.strip())


class Medidor:
    """Largura real do texto na fonte da legenda (não dá para estimar contando letras)."""

    def __init__(self, tamanho_px: float, arquivo_fonte: Path):
        from fontTools.ttLib import TTFont
        fonte = TTFont(arquivo_fonte)
        self.mapa = fonte.getBestCmap()
        self.avancos = fonte["hmtx"].metrics
        self.escala = tamanho_px / fonte["head"].unitsPerEm
        self.padrao = self.avancos.get(self.mapa.get(ord("n")), (600, 0))[0]

    def __call__(self, texto: str) -> float:
        total = sum(self.avancos.get(self.mapa.get(ord(c)), (self.padrao, 0))[0] for c in texto)
        return total * self.escala


def _sem_acento(t: str) -> str:
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def corrigir_termos(palavras: list[dict], termos: list[str]) -> list[dict]:
    """Grafia certa das marcas e termos do perfil: só a caixa e a acentuação de palavras soltas
    ("whatsapp" vira "WhatsApp"). Termo de várias palavras não entra. A pontuação fica como está."""
    mapa = {_sem_acento(t): t for t in termos if t and " " not in t.strip()}
    if not mapa:
        return palavras
    saida = []
    for w in palavras:
        m = re.fullmatch(r"(\W*)(.*?)(\W*)", w["p"], flags=re.S)
        miolo = m.group(2) if m else w["p"]
        certo = mapa.get(_sem_acento(miolo))
        saida.append({**w, "p": f"{m.group(1)}{certo}{m.group(3)}"} if certo and m else w)
    return saida


def palavras_no_corte(pasta: Path, cortes: dict, fps) -> list[dict]:
    trechos = trechos_no_quadro(cortes, fps)
    transcricoes = {}
    for v in cortes["videos"]:
        tr = pasta / "transcricoes" / f"{Path(v['arquivo']).stem}.json"
        transcricoes[v["id"]] = ler_json(tr)["palavras"]
    saida = []
    for t in trechos:
        for w in transcricoes[t["video"]]:
            meio = (w["i"] + w["f"]) / 2
            if not (t["inicio_exato"] <= meio < t["fim_exato"]):
                continue
            i = t["saida_inicio"] + max(0.0, w["i"] - t["inicio_exato"])
            f = t["saida_inicio"] + min(t["fim_exato"], w["f"]) - t["inicio_exato"]
            saida.append({"p": w["p"].strip(), "i": round(i, 3), "f": round(max(f, i + 0.05), 3)})
    return saida


def agrupar(palavras: list[dict], max_palavras: int, cabe=lambda texto: True) -> list[dict]:
    blocos, atual = [], []

    def fechar():
        if atual:
            blocos.append({"texto": " ".join(limpar(w["p"]) for w in atual),
                           "inicio": atual[0]["i"], "fim": atual[-1]["f"],
                           "palavras": [{"p": limpar(w["p"]), "i": w["i"], "f": w["f"]} for w in atual]})
        atual.clear()

    for k, w in enumerate(palavras):
        if atual:
            pausa = w["i"] - atual[-1]["f"]
            junto = " ".join(limpar(x["p"]) for x in atual + [w])
            if len(atual) >= max_palavras or pausa > PAUSA_QUEBRA or not cabe(junto):
                fechar()
        atual.append(w)
        if re.search(r"[.?!…]$", w["p"]):
            fechar()
    fechar()

    # Tempo mínimo na tela, sem invadir o bloco seguinte.
    for n, b in enumerate(blocos):
        limite = blocos[n + 1]["inicio"] if n + 1 < len(blocos) else b["fim"] + 1.0
        if b["fim"] - b["inicio"] < TEMPO_MINIMO:
            b["fim"] = min(limite, b["inicio"] + TEMPO_MINIMO)
        if 0 < limite - b["fim"] < 0.25:  # emenda blocos quase colados (evita piscar)
            b["fim"] = limite
        b["inicio"], b["fim"] = round(b["inicio"], 3), round(b["fim"], 3)
    return blocos


def t_ass(s: float) -> str:
    cs = int(round(s * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    seg, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{seg:02d}.{cs:02d}"


def t_srt(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    seg, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{seg:02d},{ms:03d}"


def escapar(t: str) -> str:
    return t.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


SEGURO_TOPO = 0.12    # nada importante acima de 12% da altura
SEGURO_BASE = 0.80    # nem abaixo de 80% (legenda do post e botões)
FOLGA_ROSTO = 0.015   # distância mínima entre a legenda e o rosto (fração da altura)


def base_padrao(estilo: dict) -> float:
    return estilo["altura"] * (1 - 0.24)


def caixa_texto(estilo: dict) -> float:
    tamanho = estilo["altura"] * estilo["tamanho"]
    return tamanho * 1.1 + 2 * max(2, tamanho * 0.09)


def posicionar(blocos: list[dict], estilo: dict, pasta: Path, medir) -> list[str]:
    """Escolhe a altura de cada bloco para não cobrir o rosto. Devolve avisos."""
    for b in blocos:
        b.pop("y", None)
        b.pop("lugar", None)
    if estilo["posicao"] != "auto":
        return []
    from camera import Camera
    from rosto import Rostos, zona_protegida
    largura, altura = estilo["largura"], estilo["altura"]
    rostos = Rostos.carregar(pasta, largura, altura)
    if rostos is None:
        return ["sem rosto.json: legenda embaixo, sem desviar do rosto (rode rosto.py)"]
    camera = Camera.carregar(pasta, largura, altura)
    alto_txt = caixa_texto(estilo)
    folga = altura * FOLGA_ROSTO
    padrao = base_padrao(estilo)
    avisos, anterior = [], None
    caixa = (lambda t: t.upper()) if estilo["maiusculas"] else (lambda t: t)
    for b in blocos:
        zonas = []
        for t, r in rostos.amostras(b["inicio"], b["fim"]):
            z = zona_protegida(r)
            zonas.append(camera.na_tela(z, t) if camera else z)
        if not zonas:
            continue
        zx0, zy0 = min(z[0] for z in zonas), min(z[1] for z in zonas)
        zx1, zy1 = max(z[2] for z in zonas), max(z[3] for z in zonas)
        meia = medir(caixa(b["texto"])) / 2 + alto_txt * 0.2
        cruza_x = largura / 2 - meia < zx1 and largura / 2 + meia > zx0

        def livre(y):
            return not (cruza_x and y - alto_txt < zy1 + folga and y > zy0 - folga)

        def cabe(y):
            return y - alto_txt >= altura * SEGURO_TOPO and y <= altura * SEGURO_BASE

        opcoes = [(padrao, "embaixo")]
        if anterior and anterior[1] != "embaixo":
            opcoes.append(anterior)
        opcoes += [(zy1 + folga + alto_txt, "abaixo do queixo"), (zy0 - folga, "acima da testa")]
        escolha = next(((y, nome) for y, nome in opcoes if cabe(y) and livre(y)), None)
        if escolha is None:
            escolha = (padrao, "embaixo")
            avisos.append(f"a legenda encosta no rosto em {b['inicio']:.1f} s (\"{b['texto']}\"): "
                          "o rosto ocupa quase a tela toda; confira o quadro")
        b["y"], b["lugar"] = round(escolha[0]), escolha[1]
        anterior = escolha
    return avisos


def gerar_ass(blocos, largura, altura, estilo, marca) -> str:
    cores = marca["cores"]
    leg = marca["legenda"]
    tamanho = round(altura * estilo["tamanho"])
    contorno = max(2, round(tamanho * 0.09))
    alinhamento = {"auto": 2, "baixo": 2, "meio": 5, "alto": 8}[estilo["posicao"]]
    # Área segura: texto importante entre 12% e 80% da altura (botões e legenda do post embaixo).
    margem_v = {"auto": round(altura * 0.24), "baixo": round(altura * 0.24), "meio": round(altura * 0.04),
                "alto": round(altura * 0.16)}[estilo["posicao"]]
    margem_h = round(largura * (1 - LARGURA_UTIL) / 2)
    texto, destaque, sombra = (cor_ass(cores[leg["cor_texto"]]), cor_ass(cores[leg["cor_palavra_falada"]]),
                               cor_ass(cores[leg["cor_contorno"]]))
    linhas = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {largura}", f"PlayResY: {altura}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        f"Style: Legenda,{leg['fonte']},{tamanho},{texto},{texto},{sombra},&H80{sombra[4:]},0,0,0,0,100,100,0,0,1,"
        f"{contorno},{max(1, contorno // 2)},{alinhamento},{margem_h},{margem_h},{margem_v},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def caixa(t):
        return t.upper() if estilo["maiusculas"] else t

    for b in blocos:
        pal = b.get("palavras") or []
        partes = [caixa(escapar(p)) for p in b["texto"].split()]
        pos = f"{{\\an2\\pos({largura // 2},{b['y']})}}" if b.get("y") is not None else ""
        if not estilo["destaque"] or len(pal) != len(partes):
            # Sem destaque, ou o texto foi corrigido à mão e mudou o número de palavras.
            linhas.append(f"Dialogue: 0,{t_ass(b['inicio'])},{t_ass(b['fim'])},Legenda,,0,0,0,,{pos}{' '.join(partes)}")
            continue
        for k, w in enumerate(pal):
            ini = b["inicio"] if k == 0 else w["i"]
            fim = pal[k + 1]["i"] if k + 1 < len(pal) else b["fim"]
            if fim <= ini:
                continue
            txt = " ".join(
                (f"{{\\c{destaque}}}{p}{{\\c{texto}}}" if j == k else p) for j, p in enumerate(partes))
            linhas.append(f"Dialogue: 0,{t_ass(ini)},{t_ass(fim)},Legenda,,0,0,0,,{pos}{txt}")
    return "\n".join(linhas) + "\n"


def gerar_srt(blocos) -> str:
    return "\n".join(f"{n}\n{t_srt(b['inicio'])} --> {t_srt(b['fim'])}\n{b['texto']}\n"
                     for n, b in enumerate(blocos, 1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", type=Path, required=True)
    ap.add_argument("--palavras", type=int, default=3, help="máximo de palavras por bloco")
    ap.add_argument("--posicao", choices=["auto", "baixo", "meio", "alto"], default="auto")
    ap.add_argument("--formato", default="original", help="o mesmo que vai no renderizar.py")
    ap.add_argument("--tamanho", type=float, default=0.046, help="altura da letra em fração da altura do vídeo")
    ap.add_argument("--maiusculas", action="store_true")
    ap.add_argument("--sem-destaque", action="store_true", help="não pinta a palavra falada")
    ap.add_argument("--reaproveitar", action="store_true", help="usa legendas.json já editado")
    ap.add_argument("--perfil", help="perfil de marca (padrão: o da pasta do trabalho)")
    a = ap.parse_args()
    from comum import andamento, andamento_fim
    andamento(a.pasta, "montando a legenda")
    definir_perfil(a.perfil)
    marca = carregar_marca(pasta=a.pasta)
    fonte = arquivo_da_fonte(marca)

    insp = ler_json(a.pasta / "inspecao.json")["videos"][0]
    cortes_arq = a.pasta / "cortes.json"
    if not cortes_arq.exists():
        erro("rode propor_cortes.py antes")
    cortes = ler_json(cortes_arq)
    fps = fps_racional({"avg_frame_rate": insp["fps"]})

    destino = a.pasta / "legendas.json"
    if a.reaproveitar:
        if not destino.exists():
            erro("não existe legendas.json para reaproveitar")
        dados = ler_json(destino)
        blocos, estilo = dados["blocos"], dados["estilo"]
        largura, altura = estilo["largura"], estilo["altura"]
    else:
        largura, altura = dimensoes_saida(insp["largura"], insp["altura"], a.formato)
        estilo = {"palavras": a.palavras, "posicao": a.posicao, "tamanho": a.tamanho,
                  "maiusculas": a.maiusculas, "destaque": not a.sem_destaque,
                  "formato": a.formato, "largura": largura, "altura": altura}
        medir = Medidor(altura * a.tamanho, fonte)
        limite = largura * LARGURA_UTIL
        caixa = (lambda t: t.upper()) if a.maiusculas else (lambda t: t)
        falas = corrigir_termos(palavras_no_corte(a.pasta, cortes, fps), marca["termos"])
        blocos = agrupar(falas, a.palavras, cabe=lambda t: medir(caixa(t)) <= limite)

    from camera import assinatura_camera
    avisos = posicionar(blocos, estilo, a.pasta.resolve(), Medidor(altura * estilo["tamanho"], fonte))
    estilo["camera"] = assinatura_camera(a.pasta.resolve())
    if not a.reaproveitar:
        estilo["cortes"] = assinatura_dos_cortes(cortes)      # o editar.py só reaproveita o texto se os cortes forem os mesmos
    estilo["perfil"] = {"nome": marca["perfil"], "assinatura": assinatura_da_marca(marca)}
    salvar_json(destino, {"estilo": estilo, "blocos": blocos})

    ass = gerar_ass(blocos, estilo["largura"], estilo["altura"], estilo, marca)
    (a.pasta / "legendas.ass").write_text(ass, encoding="utf-8")
    (a.pasta / "legendas.srt").write_text(gerar_srt(blocos), encoding="utf-8")
    print(f"{len(blocos)} blocos de legenda")
    for b in blocos[:12]:
        print(f"  {b['inicio']:6.2f}-{b['fim']:6.2f}  {b['texto']}{'  (' + b['lugar'] + ')' if b.get('lugar') else ''}")
    lugares = [b["lugar"] for b in blocos if b.get("lugar") and b["lugar"] != "embaixo"]
    if lugares:
        print(f"  {len(lugares)} bloco(s) mudaram de lugar para não cobrir o rosto")
    for av in avisos:
        print(f"  atenção: {av}")
    if len(blocos) > 12:
        print("  ...")
    andamento_fim(a.pasta, "legenda pronta")
    print(f"ok  {destino}  {a.pasta / 'legendas.ass'}  {a.pasta / 'legendas.srt'}")


if __name__ == "__main__":
    main()
