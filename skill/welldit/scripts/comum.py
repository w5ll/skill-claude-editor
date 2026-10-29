"""Funções compartilhadas pelos scripts da skill de edição de vídeo."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

PASTA_SKILL = Path(__file__).resolve().parent.parent
PASTA_FONTES = PASTA_SKILL / "assets" / "fontes"
PASTA_PERFIS = PASTA_SKILL / "perfis"
PERFIL_PADRAO = "arven"
CORES_DA_MARCA = ["fundo", "fundo_profundo", "cartao", "linha", "elemento_3d", "destaque", "texto", "apoio", "rotulo"]
PACOTES_DE_GATILHOS = ["geral", "marketing", "juridico"]
TAXA_ANALISE = 16000  # áudio mono usado para medir fala e transcrever


def erro(msg: str, codigo: int = 2):
    print(f"erro: {msg}", file=sys.stderr)
    sys.exit(codigo)


def aviso(msg: str):
    print(msg, file=sys.stderr)


def exigir(binario: str):
    if shutil.which(binario) is None:
        erro(f"'{binario}' não está instalado. Veja referencias/instalacao.md.")


def rodar(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """Roda um comando sem passar pelo shell (nomes de arquivo nunca viram código)."""
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def ler_json(caminho) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def salvar_json(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------- perfil de marca ----------
# O perfil (perfis/<nome>/marca.json) tem as cores, a fonte, o nome e as regras de quem edita.
# Escolha, da mais forte para a mais fraca: definir_perfil() (o --perfil do script), o perfil.json
# da pasta do trabalho, a variável WELLDIT_PERFIL e o perfil padrão.

_PERFIL_FORCADO: list[str] = []


def definir_perfil(nome: str | None):
    """Chamado pelos scripts logo depois de ler o --perfil."""
    _PERFIL_FORCADO[:] = [nome] if nome else []


def nome_do_perfil(pasta=None, perfil: str | None = None) -> str:
    if perfil:
        return perfil
    if _PERFIL_FORCADO:
        return _PERFIL_FORCADO[0]
    if pasta is not None and (Path(pasta) / "perfil.json").exists():
        try:
            nome = json.loads((Path(pasta) / "perfil.json").read_text(encoding="utf-8")).get("perfil")
        except (OSError, ValueError):
            nome = None
        if nome:
            return nome
    return os.environ.get("WELLDIT_PERFIL") or PERFIL_PADRAO


def perfis_disponiveis() -> list[str]:
    if not PASTA_PERFIS.exists():
        return []
    return sorted(p.name for p in PASTA_PERFIS.iterdir() if (p / "marca.json").exists())


def procurar_na_marca(pasta_perfil: Path, relativo: str) -> Path | None:
    """Um arquivo do perfil: primeiro na pasta dele, depois na pasta da skill (fontes padrão)."""
    for base in (pasta_perfil, PASTA_SKILL):
        arq = (base / relativo).resolve()
        if arq.is_file():
            return arq
    return None


def problemas_da_marca(marca: dict, pasta_perfil: Path) -> list[str]:
    """O que está errado no marca.json, em português."""
    problemas = []
    for campo in ("nome", "cores", "legenda"):
        if campo not in marca:
            problemas.append(f'falta o campo "{campo}"')
    cores = marca.get("cores", {})
    for c in CORES_DA_MARCA:
        if c not in cores:
            problemas.append(f'falta a cor "{c}" em cores')
        elif not re.fullmatch(r"#[0-9a-fA-F]{6}", str(cores[c])):
            problemas.append(f'a cor "{c}" ({cores[c]}) deve estar no formato #rrggbb')
    leg = marca.get("legenda", {})
    for campo in ("fonte", "arquivo_fonte"):
        if campo not in leg:
            problemas.append(f'falta "{campo}" em legenda')
    if leg.get("arquivo_fonte") and not procurar_na_marca(pasta_perfil, leg["arquivo_fonte"]):
        problemas.append(f'não achei a fonte {leg["arquivo_fonte"]} (procurei na pasta do perfil e na da skill)')
    for chave in ("cor_texto", "cor_palavra_falada", "cor_contorno"):
        if leg.get(chave) and leg[chave] not in cores:
            problemas.append(f'legenda.{chave} usa "{leg[chave]}", que não é uma das cores')
    for g in marca.get("gatilhos", []):
        if g not in PACOTES_DE_GATILHOS:
            problemas.append(f'pacote de gatilhos desconhecido: "{g}" (use {", ".join(PACOTES_DE_GATILHOS)})')
    for campo in ("avisos_obrigatorios", "termos", "gatilhos"):
        if campo in marca and not isinstance(marca[campo], list):
            problemas.append(f'"{campo}" deve ser uma lista')
    return problemas


def carregar_marca(perfil: str | None = None, pasta=None) -> dict:
    """O perfil de marca escolhido, já com os campos opcionais preenchidos."""
    nome = nome_do_perfil(pasta, perfil)
    arq = PASTA_PERFIS / nome / "marca.json"
    if not re.fullmatch(r"[\w-]+", nome) or not arq.exists():
        erro(f'não existe o perfil "{nome}". Perfis disponíveis: {", ".join(perfis_disponiveis()) or "nenhum"}. '
             "Para criar o seu: python scripts/perfil.py novo NOME")
    marca = ler_json(arq)
    problemas = problemas_da_marca(marca, arq.parent)
    if problemas:
        erro(f'o perfil "{nome}" tem problema: ' + "; ".join(problemas))
    marca.setdefault("arroba", "")
    marca.setdefault("creditos", "")
    marca.setdefault("gatilhos", ["geral"])
    if "geral" not in marca["gatilhos"]:         # o pacote geral está sempre ligado
        marca["gatilhos"] = ["geral"] + list(marca["gatilhos"])
    marca.setdefault("avisos_obrigatorios", [])
    marca.setdefault("termos", [])
    marca["legenda"].setdefault("cor_texto", "texto")
    marca["legenda"].setdefault("cor_palavra_falada", "destaque")
    marca["legenda"].setdefault("cor_contorno", "fundo_profundo")
    marca["perfil"] = nome
    marca["_pasta"] = str(arq.parent)
    return marca


def arquivo_da_fonte(marca: dict) -> Path:
    return procurar_na_marca(Path(marca["_pasta"]), marca["legenda"]["arquivo_fonte"])


def assinatura_da_marca(marca: dict) -> str:
    """Resume tudo que muda o desenho (cores, fonte, @). Muda o perfil ou o arquivo, muda a assinatura."""
    base = {"cores": marca["cores"], "legenda": marca["legenda"], "arroba": marca["arroba"],
            "fonte": hashlib.sha1(arquivo_da_fonte(marca).read_bytes()).hexdigest()}
    return hashlib.sha1(json.dumps(base, sort_keys=True).encode()).hexdigest()[:12]



def sondar(arquivo) -> dict:
    """Metadados do vídeo pelo ffprobe."""
    exigir("ffprobe")
    saida = rodar([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(arquivo),
    ]).stdout
    return json.loads(saida)


def fluxo(info: dict, tipo: str) -> dict | None:
    for s in info.get("streams", []):
        if s.get("codec_type") == tipo and not s.get("disposition", {}).get("attached_pic"):
            return s
    return None


def rotacao(video: dict) -> int:
    for lado in video.get("side_data_list", []) or []:
        if "rotation" in lado:
            return int(round(float(lado["rotation"]))) % 360
    tag = (video.get("tags") or {}).get("rotate")
    return int(tag) % 360 if tag else 0


def dimensoes_exibidas(video: dict) -> tuple[int, int]:
    """Largura e altura como o vídeo aparece na tela (já considerando rotação do celular)."""
    w, h = int(video["width"]), int(video["height"])
    if rotacao(video) in (90, 270):
        w, h = h, w
    return w, h


def fps_racional(video: dict) -> Fraction:
    for chave in ("avg_frame_rate", "r_frame_rate"):
        valor = video.get(chave, "0/0")
        try:
            f = Fraction(valor)
            if f > 0:
                return f
        except (ZeroDivisionError, ValueError):
            pass
    return Fraction(30, 1)


def eh_hdr(video: dict) -> bool:
    return video.get("color_transfer") in ("arib-std-b67", "smpte2084")


def carregar_mono(arquivo, inicio: float | None = None, fim: float | None = None) -> np.ndarray:
    """Decodifica o áudio em mono 16 kHz (float32)."""
    exigir("ffmpeg")
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if inicio is not None:
        cmd += ["-ss", f"{inicio:.3f}"]
    if fim is not None:
        cmd += ["-to", f"{fim:.3f}"]
    cmd += ["-i", str(arquivo), "-vn", "-ac", "1", "-ar", str(TAXA_ANALISE), "-f", "f32le", "-"]
    bruto = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(bruto, dtype=np.float32)


def envelope_db(audio: np.ndarray, passo: float = 0.01) -> np.ndarray:
    """Nível em dB a cada 10 ms (janela de 20 ms)."""
    n = int(TAXA_ANALISE * passo)
    if len(audio) < n:
        return np.full(1, -90.0)
    janela = 2 * n
    quadrado = np.concatenate([audio.astype(np.float64) ** 2, np.zeros(janela)])
    acumulado = np.concatenate([[0.0], np.cumsum(quadrado)])
    inicios = np.arange(0, len(audio), n)
    soma = acumulado[inicios + janela] - acumulado[inicios]
    rms = np.sqrt(np.maximum(soma / janela, 1e-12))
    return 20 * np.log10(rms)


def tempo(segundos: float) -> str:
    """0:42.3"""
    m, s = divmod(max(0.0, segundos), 60)
    return f"{int(m)}:{s:04.1f}"


def medir_volume(arquivo, filtro: str | None = None) -> dict:
    """Volume integrado (LUFS) e pico real (dBTP) pelo ebur128 do ffmpeg."""
    af = (filtro + "," if filtro else "") + "ebur128=peak=true"
    proc = subprocess.run(
        ["ffmpeg", "-v", "info", "-nostdin", "-i", str(arquivo), "-vn", "-af", af, "-f", "null", "-"],
        capture_output=True, text=True,
    )
    texto = proc.stderr
    resumo = texto[texto.rfind("Summary:"):] if "Summary:" in texto else ""
    volume = pico = None
    for linha in resumo.splitlines():
        linha = linha.strip()
        if linha.startswith("I:"):
            volume = float(linha.split()[1])
        elif linha.startswith("Peak:"):
            pico = float(linha.split()[1])
    return {"volume_lufs": volume, "pico_dbtp": pico}


def trechos_no_quadro(cortes: dict, fps: Fraction) -> list[dict]:
    """Encaixa cada trecho na grade de quadros e calcula onde ele cai no vídeo final.

    Imagem e som cortam no mesmo instante exato; sem isso o som se descola da boca
    um pouquinho a cada corte e o erro se acumula.
    """
    saida, posicao = [], 0
    for t in cortes["trechos"]:
        q0 = int(round(t["inicio"] * fps))
        q1 = int(round(t["fim"] * fps))
        if q1 <= q0:
            continue
        saida.append({
            **t,
            "quadro_inicio": q0,
            "quadro_fim": q1,
            "inicio_exato": float(q0 / fps),
            "fim_exato": float(q1 / fps),
            "saida_inicio": float(posicao / fps),
            "saida_fim": float((posicao + q1 - q0) / fps),
        })
        posicao += q1 - q0
    return saida


FORMATOS = {"9:16": (9, 16), "4:5": (4, 5), "1:1": (1, 1), "16:9": (16, 9)}


def dimensoes_saida(largura: int, altura: int, formato: str) -> tuple[int, int]:
    """Tamanho final.

    formato = proporção, com tamanho opcional depois de '@':
      'original'       mantém a proporção e o tamanho do vídeo bruto
      '9:16', '4:5'... corta o centro na proporção pedida, sem esticar
      'original@1080'  mesma proporção, reduzida para 1080 de largura (o que o Instagram usa)
      '9:16@1080'      corta em 9:16 e reduz para 1080x1920
    Nunca aumenta: se o bruto já for menor que o tamanho pedido, fica o do bruto.
    """
    proporcao, _, limite = formato.partition("@")
    if proporcao == "original":
        w, h = largura, altura
    elif proporcao in FORMATOS:
        rw, rh = FORMATOS[proporcao]
        if largura * rh > altura * rw:          # sobra largura: corta as laterais
            w, h = altura * rw // rh, altura
        else:                                   # sobra altura: corta em cima e embaixo
            w, h = largura, largura * rh // rw
    else:
        erro(f"formato desconhecido: {formato} (use original, {', '.join(FORMATOS)}, com @1080 se quiser reduzir)")
    if limite:
        if not limite.isdigit():
            erro(f"tamanho inválido em {formato}: use, por exemplo, 9:16@1080")
        alvo = int(limite)
        menor = min(w, h)  # vertical: a largura; horizontal: a altura
        if alvo < menor:
            w, h = round(w * alvo / menor), round(h * alvo / menor)
    return w - w % 2, h - h % 2


# ---------- andamento (o painel lê isto para mostrar a etapa ao vivo) ----------

_ULTIMO_ANDAMENTO = {"t": 0.0}


def andamento(pasta, etapa: str, progresso: float | None = None, detalhe: str = "", forcar: bool = True):
    """Grava em <pasta>/andamento.json o que está rodando agora. Nunca atrapalha o script."""
    import os
    import time
    agora = time.time()
    if not forcar and agora - _ULTIMO_ANDAMENTO["t"] < 1.0:
        return
    _ULTIMO_ANDAMENTO["t"] = agora
    try:
        pasta = Path(pasta)
        pasta.mkdir(parents=True, exist_ok=True)
        dados = {"etapa": etapa, "progresso": None if progresso is None else round(max(0.0, min(1.0, progresso)), 3),
                 "detalhe": detalhe, "pid": os.getpid(), "atualizado": round(agora, 1), "concluido": False}
        tmp = pasta / ".andamento.tmp"
        tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        tmp.replace(pasta / "andamento.json")
    except Exception:  # noqa: BLE001
        pass


def andamento_fim(pasta, etapa: str, detalhe: str = ""):
    import time
    try:
        dados = {"etapa": etapa, "progresso": 1.0, "detalhe": detalhe, "pid": None,
                 "atualizado": round(time.time(), 1), "concluido": True}
        tmp = Path(pasta) / ".andamento.tmp"
        tmp.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        tmp.replace(Path(pasta) / "andamento.json")
    except Exception:  # noqa: BLE001
        pass
