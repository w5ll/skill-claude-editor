"""Painel da edição no navegador: enviar vídeos, rodar a edição inteira com cliques e acompanhar cada etapa.

Uso (da pasta do projeto, com o .venv ativo):
    python skill/welldit/scripts/painel.py [--porta 8765] [--sem-abrir] [--perfil NOME]

Abre o navegador no endereço que aparece no terminal (com um código de sessão). Só funciona no próprio
computador (não fica visível na rede). Para parar: Ctrl+C no terminal.

O que ele faz:
- Enviar: arraste os vídeos para a página e eles vão para material-bruto/. Nunca sobrescreve.
- Editar: escolha os vídeos, a série e o perfil, preencha o cartão de ajustes (já vem com o recomendado) e
  aprove os portões. O painel roda o editar.py, uma edição por vez; dá para cancelar e retomar.
- Acompanhar: as etapas, o progresso das longas, as versões, a conferência e as folhas de quadros.
- Aprovar a entrega e abrir a pasta.

Segurança: código de sessão novo a cada abertura (cookie HttpOnly), conferência de Host e de origem, e só
ações conhecidas: nunca um comando livre. Veja painel_seguranca.py e docs/fase-5-painel-executa.md.
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
import sys
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import editar
import serie as modulo_serie
from comum import arquivo_da_fonte, carregar_marca, definir_perfil, perfis_disponiveis
from fila import Fila
from painel_seguranca import CABECALHO, Sessao

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


class Recusa(Exception):
    """Um pedido que o painel não aceita. `status` é o código HTTP."""

    def __init__(self, mensagem: str, status: int = 400):
        super().__init__(mensagem)
        self.status = status


REGEX_NOME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$")
REGEX_FORMATO = re.compile(r"^(original|9:16|4:5|1:1|16:9)(@\d{3,4})?$")
OPCOES_FIXAS = {"ritmo": ["natural", "dinamico"], "camera": ["nenhum", "leve", "normal", "forte"],
                "amostra": ["conferir", "aprovar", "nao"]}


def validar_escolha(chave: str, valor) -> str:
    """Só estas escolhas, só com estes valores. Devolve o texto 'chave=valor' que o editar.py entende."""
    if chave in OPCOES_FIXAS:
        if valor not in OPCOES_FIXAS[chave]:
            raise Recusa(f"{chave}: use {', '.join(OPCOES_FIXAS[chave])}")
        return f"{chave}={valor}"
    if chave == "som.musica":
        validas = ["nenhuma", *modulo_serie.nomes_de_musicas()]
        if valor not in validas:
            raise Recusa(f"som.musica: use {', '.join(validas)}")
        return f"{chave}={valor}"
    if chave in ("som.efeitos", "legenda.ligada", "elementos.ligado"):
        if not isinstance(valor, bool):
            raise Recusa(f"{chave}: use sim ou não")
        return f"{chave}={'true' if valor else 'false'}"
    if chave == "legenda.palavras":
        if not (isinstance(valor, int) and not isinstance(valor, bool) and 1 <= valor <= 6):
            raise Recusa("legenda.palavras: de 1 a 6")
        return f"{chave}={valor}"
    if chave == "formato":
        if not (isinstance(valor, str) and REGEX_FORMATO.match(valor)):
            raise Recusa("formato: original, 9:16, 4:5, 1:1 ou 16:9, com @1080 se quiser reduzir")
        return f"{chave}={valor}"
    raise Recusa(f"escolha que o painel não muda: {chave}")


def abrir_no_sistema(pasta: Path):
    comando = ["open", str(pasta)] if sys.platform == "darwin" else ["xdg-open", str(pasta)]
    if shutil.which(comando[0]) is None:
        raise Recusa("não achei como abrir a pasta neste computador", 501)
    subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Painel:
    def __init__(self, raiz: Path, fila: Fila | None = None, sessao: Sessao | None = None, abrir=abrir_no_sistema):
        self.raiz = raiz = raiz.resolve()          # com link simbólico no caminho (como o /var do macOS), rel() quebraria
        self.bruto = raiz / "material-bruto"
        self.saida = raiz / "saida"
        self.miniaturas = raiz / ".painel" / "miniaturas"
        self.bruto.mkdir(exist_ok=True)
        self.saida.mkdir(exist_ok=True)
        self.fila = fila or Fila()
        self.sessao = sessao
        self.abrir = abrir
        self._cache: dict[str, tuple] = {}

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
        return {"brutos": brutos, "enviando": enviando, "trabalhos": trabalhos, "agora": time.time(),
                "fila": self.fila.estado(),
                "opcoes": {"series": modulo_serie.listar(), "perfis": [p for p in perfis_disponiveis() if not p.startswith("_")]}}

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
                "videos": videos, "etapas": etapas, "extras": extras, "agora": agora, "versoes": versoes,
                "orq": self.orquestrada(pasta)}

    def orquestrada(self, pasta: Path) -> dict | None:
        """O estado da edição conduzida pelo editar.py (None para as edições feitas só na conversa)."""
        if not (pasta / "trabalho.json").exists():
            return None
        assinatura = tuple(sorted((p.name, p.stat().st_mtime_ns) for p in pasta.glob("*.json")))
        guardado = self._cache.get(pasta.name)
        if guardado and guardado[0] == assinatura:
            base = guardado[1]
        else:
            try:
                t = editar.carregar(pasta)
            except SystemExit:
                return None
            portao = None
            g = t.get("portao")
            if g:
                portao = {"nome": g["nome"], "tipo": g["tipo"], "pergunta": g["pergunta"],
                          "arquivos": [{"nome": a, "caminho": self.rel(pasta / a)} for a in g.get("arquivos", [])
                                       if (pasta / a).is_file()]}
                if g["nome"] == "cartao" and (pasta / "inspecao.json").exists():
                    insp = ler(pasta / "inspecao.json") or {"videos": []}
                    portao["cartao"] = editar.montar_cartao(t, insp)
                    portao["texto"] = editar.texto_do_cartao(t, insp)
            etapas = {e.nome: {"titulo": e.titulo, "situacao": editar.situacao(t, e, pasta),
                               "resumo": (t["etapas"].get(e.nome, {}).get("resumo") or "")[:90]} for e in editar.ETAPAS}
            base = {"serie": t.get("serie"), "perfil": t.get("perfil"), "tema": t.get("tema"), "etapas": etapas,
                    "portao": portao, "escolhas": t["escolhas"], "entrega_aprovada": t.get("entrega_aprovada"),
                    "pasta_relativa": t.get("pasta_relativa")}
            self._cache[pasta.name] = (assinatura, base)
        ult = self.fila.estado()["ultimo"].get(pasta.name)
        return {**base, "posicao": self.fila.posicao(pasta), "ultimo": ult}


def _tempo(s) -> str:
    if s is None:
        return "?"
    m, seg = divmod(int(round(float(s))), 60)
    return f"{m}:{seg:02d}"


class Acoes:
    """Tudo que o painel faz além de mostrar. Cada ação é uma função fixa: não existe comando livre."""

    def __init__(self, painel: Painel):
        self.p = painel

    # ---- validações ----
    def pasta(self, nome) -> Path:
        if not isinstance(nome, str) or not REGEX_NOME.match(nome):
            raise Recusa("nome de edição inválido")
        pasta = (self.p.saida / nome).resolve()
        if pasta.parent != self.p.saida.resolve() or not pasta.is_dir():
            raise Recusa("essa edição não existe", 404)
        if not (pasta / "trabalho.json").exists():
            raise Recusa("essa edição foi feita só na conversa e não tem painel de execução")
        return pasta

    def livre(self, pasta: Path):
        if self.p.fila.ocupada(pasta):
            raise Recusa("essa edição está rodando ou na fila: espere terminar ou cancele", 409)

    # ---- ações ----
    def novo(self, d: dict) -> dict:
        nomes = d.get("videos")
        if not isinstance(nomes, list) or not nomes or len(nomes) > 8:
            raise Recusa("escolha de 1 a 8 vídeos")
        videos = []
        for n in nomes:
            if not isinstance(n, str) or n != nome_seguro(n) or "/" in n or "\\" in n:
                raise Recusa(f"nome de vídeo inválido: {str(n)[:40]}")
            v = self.p.bruto / n
            if not v.is_file() or v.suffix.lower() not in {".mov", ".mp4", ".m4v", ".mkv", ".webm", ".avi"}:
                raise Recusa(f"não achei o vídeo {n} em material-bruto", 404)
            videos.append(v)
        serie = d.get("serie") or None
        if serie is not None and serie not in modulo_serie.listar():
            raise Recusa("série desconhecida")
        perfil = d.get("perfil") or None
        if perfil is not None and perfil not in perfis_disponiveis():
            raise Recusa("perfil desconhecido")
        tema = d.get("tema")
        if tema is not None and (not isinstance(tema, str) or len(tema) > 60):
            raise Recusa("o nome da edição tem no máximo 60 letras")
        if serie:
            problemas = modulo_serie.validar(modulo_serie.carregar(serie))
            if problemas:
                raise Recusa("a série tem problema: " + "; ".join(problemas[:2]))
        pasta = editar.novo(videos, serie, perfil, tema or None, base=self.p.saida)
        situacao = self.p.fila.enfileirar(pasta) if d.get("iniciar", True) else "parada"
        return {"ok": True, "pasta": pasta.name, "fila": situacao}

    def aprovar(self, d: dict) -> dict:
        pasta = self.pasta(d.get("pasta"))
        self.livre(pasta)
        ajustes = d.get("escolhas") or []
        if not isinstance(ajustes, list) or len(ajustes) > 20:
            raise Recusa("escolhas em formato inválido")
        textos = []
        for a in ajustes:
            if not isinstance(a, dict) or "chave" not in a or "valor" not in a:
                raise Recusa("escolhas em formato inválido")
            textos.append(validar_escolha(a["chave"], a["valor"]))
        try:
            for texto in textos:
                editar.ajustar(pasta, texto)
            nome = editar.aprovar(pasta, d.get("portao") or None, d.get("resposta") or None)
        except editar.PedidoRecusado as e:
            raise Recusa(str(e)) from e
        situacao = self.p.fila.enfileirar(pasta) if d.get("seguir", True) else "parada"
        return {"ok": True, "portao": nome, "fila": situacao}

    def iniciar(self, d: dict) -> dict:
        pasta = self.pasta(d.get("pasta"))
        self.livre(pasta)
        return {"ok": True, "fila": self.p.fila.enfileirar(pasta)}

    def cancelar(self, d: dict) -> dict:
        pasta = self.pasta(d.get("pasta"))
        if not self.p.fila.cancelar(pasta):
            raise Recusa("essa edição não está rodando nem na fila", 409)
        return {"ok": True}

    def ajustar(self, d: dict) -> dict:
        pasta = self.pasta(d.get("pasta"))
        self.livre(pasta)
        texto = validar_escolha(d.get("chave"), d.get("valor"))
        try:
            refeitas = editar.ajustar(pasta, texto)
        except editar.PedidoRecusado as e:
            raise Recusa(str(e)) from e
        return {"ok": True, "refeitas": refeitas}

    def refazer(self, d: dict) -> dict:
        pasta = self.pasta(d.get("pasta"))
        self.livre(pasta)
        etapa = d.get("etapa")
        if etapa not in editar.POR_NOME:
            raise Recusa("etapa desconhecida")
        try:
            editar.refazer(pasta, etapa)
        except editar.PedidoRecusado as e:
            raise Recusa(str(e)) from e
        return {"ok": True}

    def aprovar_entrega(self, d: dict) -> dict:
        pasta = self.pasta(d.get("pasta"))
        self.livre(pasta)
        arq = d.get("arquivo")
        if not isinstance(arq, str) or not re.fullmatch(r"[\w.-]+-v\d{3}\.mp4", arq) or arq.startswith("amostra-"):
            raise Recusa("escolha uma das versões do vídeo inteiro")
        if not (pasta / arq).is_file():
            raise Recusa("essa versão não existe", 404)
        t = editar.carregar(pasta)
        t["entrega_aprovada"] = {"arquivo": arq, "quando": editar.agora(), "quem": "pessoa"}
        editar.salvar(pasta, t)
        return {"ok": True, "arquivo": arq}

    def abrir_pasta(self, d: dict) -> dict:
        pasta = self.pasta(d.get("pasta"))
        self.p.abrir(pasta)
        return {"ok": True}

    ROTAS = {"/api/novo": "novo", "/api/aprovar": "aprovar", "/api/iniciar": "iniciar", "/api/cancelar": "cancelar",
             "/api/ajustar": "ajustar", "/api/refazer": "refazer", "/api/aprovar-entrega": "aprovar_entrega",
             "/api/abrir-pasta": "abrir_pasta"}


PAGINA_SEM_SESSAO = PASTA_SKILL / "templates" / "painel-sessao.html"
MAX_CORPO = 64 * 1024


def criar_handler(painel: Painel, marca: dict):
    acoes = Acoes(painel)

    class Handler(BaseHTTPRequestHandler):
        server_version = "PainelEdicao/2"

        def log_message(self, *args):  # silencioso
            pass

        def _json(self, dados, status=200, extra=None):
            corpo = json.dumps(dados, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(corpo)

        def _html(self, corpo: bytes, status=200):
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        # ---- conferências de segurança ----
        def _permitido(self, mutante: bool, sessao: bool = True) -> bool:
            """Host, origem, cabeçalho e sessão. Responde o erro e devolve False se algo estiver errado."""
            s = painel.sessao
            if s is None or not s.host_ok(self.headers.get("Host")):
                self._json({"erro": "host não permitido"}, 403)
                return False
            if mutante and not (s.cabecalho_ok(self.headers.get(CABECALHO)) and s.origem_ok(self.headers.get("Origin"))):
                self._json({"erro": "pedido de origem não permitida"}, 403)
                return False
            if sessao and not s.cookie_ok(self.headers.get("Cookie")):
                self._json({"erro": "sem sessão: abra o endereço que o painel mostrou no terminal"}, 401)
                return False
            return True

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
                if not self._permitido(False, sessao=False):
                    return
                s = painel.sessao
                if s.codigo_ok(q.get("s", [""])[0]):      # o código vira cookie e some do endereço
                    self.send_response(302)
                    self.send_header("Set-Cookie", s.set_cookie())
                    self.send_header("Location", "/")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                elif s.cookie_ok(self.headers.get("Cookie")):
                    self._html(MOLDE.read_bytes())
                else:
                    self._html(PAGINA_SEM_SESSAO.read_bytes(), 401)
            elif url.path in ("/fonte.ttf", "/marca.json"):          # só a aparência do perfil: sem dados da edição
                if not self._permitido(False, sessao=False):
                    return
                if url.path == "/fonte.ttf":
                    self._arquivo(arquivo_da_fonte(marca), "font/ttf")
                else:
                    self._json({k: v for k, v in marca.items() if not k.startswith("_")})
            elif url.path == "/api/estado":
                if self._permitido(False):
                    self._json(painel.estado())
            elif url.path == "/arquivo":
                if not self._permitido(False):
                    return
                arq = painel.permitido(q.get("c", [""])[0])
                if arq is None:
                    self._json({"erro": "arquivo não encontrado"}, 404)
                else:
                    self._arquivo(arq)
            elif url.path == "/miniatura":
                if not self._permitido(False):
                    return
                arq = painel.permitido(q.get("c", [""])[0])
                mini = painel.miniatura(arq) if arq else None
                if mini is None:
                    self._json({"erro": "sem miniatura"}, 404)
                else:
                    self._arquivo(mini, "image/jpeg")
            else:
                self._json({"erro": "não existe"}, 404)

        def do_POST(self):
            url = urlparse(self.path)
            metodo = Acoes.ROTAS.get(url.path)
            if metodo is None:
                self._json({"erro": "não existe"}, 404)
                return
            if not self._permitido(True):
                return
            try:
                total = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                total = -1
            if not 0 <= total <= MAX_CORPO:
                self._json({"erro": "pedido grande demais"}, 413)
                return
            try:
                dados = json.loads(self.rfile.read(total) or b"{}")
                if not isinstance(dados, dict):
                    raise ValueError
            except ValueError:
                self._json({"erro": "o pedido não é um JSON válido"}, 400)
                return
            try:
                self._json(getattr(acoes, metodo)(dados))
            except Recusa as e:
                self._json({"erro": str(e)}, e.status)
            except Exception as e:  # noqa: BLE001  (um erro inesperado não derruba o painel)
                self._json({"erro": f"erro inesperado: {str(e)[:120]}"}, 500)

        def do_PUT(self):
            url = urlparse(self.path)
            if url.path != "/api/enviar":
                self._json({"erro": "não existe"}, 404)
                return
            if not self._permitido(True):
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
    painel.sessao = Sessao(servidor.server_address[1])
    url = painel.sessao.endereco()
    print(f"painel aberto em {url}  (Ctrl+C para parar) · perfil de marca: {marca['perfil']}")
    print("o endereço tem o código de sessão: quem não o tiver não consegue usar o painel")
    print(f"vídeos brutos: {painel.bruto}")
    if not a.sem_abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\npainel fechado")
    finally:
        painel.fila.parar()


if __name__ == "__main__":
    main()
