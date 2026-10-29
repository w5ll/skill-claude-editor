"""Painel da edição no navegador: enviar vídeos brutos e ver em que etapa cada edição está.

Uso (da pasta do projeto, com o .venv ativo):
    python skill/welldit/scripts/painel.py [--porta 8765] [--sem-abrir] [--perfil NOME]

Abre http://localhost:8765 no navegador. Só funciona no próprio computador (não fica
visível na rede). Para parar: Ctrl+C no terminal.

O que ele faz:
- Enviar: arraste os vídeos para a página e eles vão para material-bruto/. Nunca
  sobrescreve: se já existir um arquivo com o mesmo nome, o novo ganha um número.
- Acompanhar: lê saida/ e mostra cada edição com as etapas (inspeção, transcrição,
  cortes, rosto, legenda, amostra, vídeo, conferência) e o que está rodando agora, com
  a porcentagem nas etapas longas (os scripts gravam andamento.json).
- Ver: toca a amostra e as versões, mostra a conferência e as folhas de quadros.

Quem edita e aprova continua sendo a conversa no Claude Code. O painel não muda nada
na edição: só recebe arquivos em material-bruto/ e lê saida/.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import threading
import time
import unicodedata
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from comum import arquivo_da_fonte, carregar_marca, definir_perfil

PASTA_SKILL = Path(__file__).resolve().parent.parent
MOLDE = PASTA_SKILL / "templates" / "painel.html"
EXTENSOES = {".mov", ".mp4", ".m4v", ".mkv", ".webm", ".avi", ".txt", ".md", ".docx", ".pdf"}
BLOCO = 1024 * 1024


def nome_seguro(nome: str) -> str:
    nome = Path(nome).name
    nome = unicodedata.normalize("NFC", nome)
    nome = re.sub(r"[^\w.\- ]+", "_", nome).strip(" .") or "video"
    return nome[:120]


def sem_sobrescrever(pasta: Path, nome: str) -> Path:
    destino = pasta / nome
    base, ext = destino.stem, destino.suffix
    n = 2
    while destino.exists() or destino.with_name(destino.name + ".parte").exists():
        destino = pasta / f"{base}-{n}{ext}"
        n += 1
    return destino


def ler(arq: Path) -> dict | None:
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def vivo(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def tamanho(arq: Path) -> int:
    try:
        return arq.stat().st_size
    except OSError:
        return 0


class Painel:
    def __init__(self, raiz: Path):
        self.raiz = raiz
        self.bruto = raiz / "material-bruto"
        self.saida = raiz / "saida"
        self.miniaturas = raiz / ".painel" / "miniaturas"
        self.bruto.mkdir(exist_ok=True)
        self.saida.mkdir(exist_ok=True)

    def rel(self, p: Path) -> str:
        return p.resolve().relative_to(self.raiz).as_posix()

    def permitido(self, rel: str) -> Path | None:
        alvo = (self.raiz / rel).resolve()
        for base in (self.bruto, self.saida, self.miniaturas):
            try:
                alvo.relative_to(base.resolve())
                return alvo if alvo.is_file() else None
            except ValueError:
                continue
        return None

    def miniatura(self, video: Path) -> Path | None:
        self.miniaturas.mkdir(parents=True, exist_ok=True)
        st = video.stat()
        destino = self.miniaturas / f"{video.stem}-{st.st_size}-{int(st.st_mtime)}.jpg"
        if not destino.exists() and shutil.which("ffmpeg"):
            subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-ss", "1", "-i", str(video), "-frames:v", "1",
                            "-vf", "scale=-2:320", "-q:v", "4", str(destino)], capture_output=True, timeout=60)
        return destino if destino.exists() else None

    def estado(self) -> dict:
        brutos = []
        for f in sorted(self.bruto.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file() and f.suffix.lower() in EXTENSOES and f.name.lower() != "readme.md":
                brutos.append({"nome": f.name, "caminho": self.rel(f), "tamanho": tamanho(f),
                               "modificado": f.stat().st_mtime, "video": f.suffix.lower() in
                               {".mov", ".mp4", ".m4v", ".mkv", ".webm", ".avi"}})
        enviando = [f.name[:-6] for f in self.bruto.glob("*.parte")]
        trabalhos = [self.trabalho(p) for p in sorted(self.saida.iterdir(), key=lambda x: x.stat().st_mtime,
                                                       reverse=True) if p.is_dir()]
        return {"brutos": brutos, "enviando": enviando, "trabalhos": trabalhos, "agora": time.time()}

    def trabalho(self, pasta: Path) -> dict:
        insp = ler(pasta / "inspecao.json")
        videos = [v["nome"] for v in (insp or {}).get("videos", [])]
        transcritos = [v for v in videos if (pasta / "transcricoes" / f"{Path(v).stem}.json").exists()]
        cortes = ler(pasta / "cortes.json")
        mp4 = sorted(pasta.glob("*.mp4"), key=lambda x: x.stat().st_mtime)
        prontas = [m for m in mp4 if m.with_suffix(".render.json").exists()]
        amostras = [m for m in prontas if m.name.startswith("amostra-")]
        finais = [m for m in prontas if not m.name.startswith("amostra-")]
        conferencias = {m.name: ler(m.with_suffix(".conferencia.json")) for m in mp4}
        ultima = finais[-1] if finais else None
        conf_final = conferencias.get(ultima.name) if ultima else None

        def etapa(chave, nome, feito, detalhe=""):
            return {"chave": chave, "nome": nome, "feito": bool(feito), "detalhe": detalhe}

        etapas = [
            etapa("inspecao", "Inspeção", insp, f"{len(videos)} vídeo(s)" if videos else ""),
            etapa("transcricao", "Transcrição", videos and len(transcritos) == len(videos),
                  f"{len(transcritos)} de {len(videos)}" if videos else ""),
            etapa("cortes", "Cortes", cortes, (f"{_tempo(cortes.get('duracao_original'))} → "
                                               f"{_tempo(cortes.get('duracao_final'))}") if cortes else ""),
            etapa("rosto", "Rosto", (pasta / "rosto.json").exists()),
            etapa("legenda", "Legenda", (pasta / "legendas.json").exists()),
            etapa("amostra", "Amostra", amostras, f"{len(amostras)} amostra(s)" if amostras else ""),
            etapa("video", "Vídeo", finais, ultima.name if ultima else ""),
            etapa("conferencia", "Conferência", conf_final and conf_final.get("aprovado"),
                  ("aprovado" if conf_final.get("aprovado") else "com problema") if conf_final else ""),
        ]
        extras = [nome for arq, nome in (("elementos.json", "elementos 3D"), ("camera.json", "zoom"),
                                         ("som.json", "música e efeitos")) if (pasta / arq).exists()]

        agora = ler(pasta / "andamento.json")
        if agora:
            if agora.get("concluido"):
                agora["situacao"] = "concluido"
            elif vivo(agora.get("pid")):
                agora["situacao"] = "rodando"
            else:
                agora["situacao"] = "parou"

        versoes = []
        for m in reversed(mp4):
            conf = conferencias.get(m.name)
            folhas = [self.rel(f) for f in sorted(pasta.glob(f"{m.stem}.emendas*.jpg"))]
            quadros = m.with_suffix(".quadros.jpg")
            versoes.append({
                "nome": m.name, "caminho": self.rel(m), "tamanho": tamanho(m), "amostra": m.name.startswith("amostra-"),
                "pronta": m.with_suffix(".render.json").exists(),
                "modificado": m.stat().st_mtime,
                "conferencia": None if not conf else {"aprovado": conf.get("aprovado"), "checks": conf.get("checks", [])},
                "quadros": self.rel(quadros) if quadros.exists() else None, "emendas": folhas,
            })
        return {"nome": pasta.name, "caminho": self.rel(pasta), "modificado": pasta.stat().st_mtime,
                "videos": videos, "etapas": etapas, "extras": extras, "agora": agora, "versoes": versoes}


def _tempo(s) -> str:
    if s is None:
        return "?"
    m, seg = divmod(int(round(float(s))), 60)
    return f"{m}:{seg:02d}"


def criar_handler(painel: Painel, marca: dict):
    class Handler(BaseHTTPRequestHandler):
        server_version = "PainelEdicao/1"

        def log_message(self, *args):  # silencioso
            pass

        def _json(self, dados, status=200):
            corpo = json.dumps(dados, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def _arquivo(self, arq: Path, tipo: str | None = None):
            tipo = tipo or mimetypes.guess_type(arq.name)[0] or "application/octet-stream"
            if arq.suffix.lower() == ".mov":
                tipo = "video/quicktime"
            total = arq.stat().st_size
            ini, fim = 0, total - 1
            faixa = self.headers.get("Range")
            status = HTTPStatus.OK
            if faixa and faixa.startswith("bytes="):
                a, _, b = faixa[6:].split(",")[0].partition("-")
                if a:
                    ini = int(a)
                    fim = int(b) if b else total - 1
                else:
                    ini = max(0, total - int(b))
                fim = min(fim, total - 1)
                if ini > fim:
                    self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                    self.send_header("Content-Range", f"bytes */{total}")
                    self.end_headers()
                    return
                status = HTTPStatus.PARTIAL_CONTENT
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(fim - ini + 1))
            if status == HTTPStatus.PARTIAL_CONTENT:
                self.send_header("Content-Range", f"bytes {ini}-{fim}/{total}")
            self.end_headers()
            try:
                with open(arq, "rb") as f:
                    f.seek(ini)
                    falta = fim - ini + 1
                    while falta > 0:
                        pedaco = f.read(min(BLOCO, falta))
                        if not pedaco:
                            break
                        self.wfile.write(pedaco)
                        falta -= len(pedaco)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            if url.path == "/":
                corpo = MOLDE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)
            elif url.path == "/fonte.ttf":
                self._arquivo(arquivo_da_fonte(marca), "font/ttf")
            elif url.path == "/marca.json":
                publica = {k: v for k, v in marca.items() if not k.startswith("_")}   # sem o caminho da pasta
                self._json(publica)
            elif url.path == "/api/estado":
                self._json(painel.estado())
            elif url.path == "/arquivo":
                arq = painel.permitido(q.get("c", [""])[0])
                if arq is None:
                    self._json({"erro": "arquivo não encontrado"}, 404)
                else:
                    self._arquivo(arq)
            elif url.path == "/miniatura":
                arq = painel.permitido(q.get("c", [""])[0])
                mini = painel.miniatura(arq) if arq else None
                if mini is None:
                    self._json({"erro": "sem miniatura"}, 404)
                else:
                    self._arquivo(mini, "image/jpeg")
            else:
                self._json({"erro": "não existe"}, 404)

        def do_PUT(self):
            url = urlparse(self.path)
            if url.path != "/api/enviar":
                self._json({"erro": "não existe"}, 404)
                return
            nome = nome_seguro(parse_qs(url.query).get("nome", ["video"])[0])
            if Path(nome).suffix.lower() not in EXTENSOES:
                self._json({"erro": f"tipo de arquivo não aceito: {Path(nome).suffix or 'sem extensão'}"}, 400)
                return
            try:
                total = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                total = -1
            if total < 0:
                self._json({"erro": "tamanho do arquivo desconhecido"}, 411)
                return
            if shutil.disk_usage(painel.bruto).free < total + 2 * 1024 ** 3:
                self._json({"erro": "pouco espaço no disco para esse vídeo"}, 507)
                return
            destino = sem_sobrescrever(painel.bruto, nome)
            parte = destino.with_name(destino.name + ".parte")
            recebido = 0
            try:
                with open(parte, "wb") as f:
                    while recebido < total:
                        pedaco = self.rfile.read(min(BLOCO, total - recebido))
                        if not pedaco:
                            break
                        f.write(pedaco)
                        recebido += len(pedaco)
            except (ConnectionResetError, BrokenPipeError):
                pass
            if recebido != total:
                parte.unlink(missing_ok=True)
                self._json({"erro": "o envio foi interrompido; tente de novo"}, 400)
                return
            parte.replace(destino)
            self._json({"ok": True, "nome": destino.name, "caminho": painel.rel(destino)})

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--porta", type=int, default=8765)
    ap.add_argument("--raiz", type=Path, default=PASTA_SKILL.parent.parent,
                    help="pasta do projeto (onde ficam material-bruto/ e saida/)")
    ap.add_argument("--sem-abrir", action="store_true", help="não abre o navegador")
    ap.add_argument("--perfil", help="perfil de marca do painel (nome, cores, fonte e créditos); padrão: arven")
    a = ap.parse_args()
    definir_perfil(a.perfil)
    marca = carregar_marca()
    painel = Painel(a.raiz.resolve())
    servidor = ThreadingHTTPServer(("127.0.0.1", a.porta), criar_handler(painel, marca))
    url = f"http://localhost:{a.porta}"
    print(f"painel aberto em {url}  (Ctrl+C para parar) · perfil de marca: {marca['perfil']}")
    print(f"vídeos brutos: {painel.bruto}")
    if not a.sem_abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\npainel fechado")


if __name__ == "__main__":
    main()
