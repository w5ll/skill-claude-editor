"""A fila do painel: uma edição por vez, na ordem de chegada.

Um trabalhador único (fora do servidor HTTP) roda editar.proximo de cada edição. Cancelar mata o grupo de
processos da etapa em andamento e a etapa fica interrompida (não falha); retomar é enfileirar de novo.
A fila não sobrevive a um reinício do painel (as edições sim, pelo trabalho.json).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import editar
from editar import Cancelado

SCRIPTS = Path(__file__).resolve().parent


def executor_cancelavel(job: dict, scripts: Path | None = None):
    """Roda cada script como processo próprio, para poder matar o grupo inteiro ao cancelar."""

    def executar(argv: list[str], log: Path) -> tuple[int, str]:
        if job["cancelar"].is_set():
            raise Cancelado()
        base = scripts or SCRIPTS
        p = subprocess.Popen([sys.executable, str(base / argv[0]), *argv[1:]], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
        job["processo"] = p
        saida, erro = p.communicate()
        job["processo"] = None
        texto = (saida or "") + (("\n" + erro) if erro else "")
        with log.open("a", encoding="utf-8") as f:
            f.write(f"$ {' '.join(argv)}\n{texto}\n")
        if job["cancelar"].is_set():
            raise Cancelado()
        return p.returncode, texto

    return executar


def matar(p: subprocess.Popen | None):
    if p is None or p.poll() is not None:
        return
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except (OSError, AttributeError):
        p.terminate()
    for _ in range(20):                       # dá 2 s para sair; depois, sem dó
        if p.poll() is not None:
            return
        time.sleep(0.1)
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except (OSError, AttributeError):
        p.kill()


class Fila:
    def __init__(self, fabrica_de_executor=executor_cancelavel, proximo=None):
        self.fabrica = fabrica_de_executor
        self.proximo = proximo or editar.proximo
        self.cond = threading.Condition()
        self.itens: list[Path] = []
        self.atual: dict | None = None
        self.ultimo: dict[str, dict] = {}
        self.parando = False
        self.thread = threading.Thread(target=self._laco, daemon=True)
        self.thread.start()

    # ---- consultas ----
    def ocupada(self, pasta: Path) -> bool:
        with self.cond:
            return (self.atual is not None and self.atual["pasta"] == pasta) or pasta in self.itens

    def estado(self) -> dict:
        with self.cond:
            return {"rodando": self.atual["pasta"].name if self.atual else None,
                    "fila": [p.name for p in self.itens],
                    "ultimo": {k: {"resultado": v["resultado"], "linhas": v["linhas"][-6:]} for k, v in self.ultimo.items()}}

    def posicao(self, pasta: Path) -> int | None:
        """0 = rodando; 1, 2... = lugar na fila; None = fora."""
        with self.cond:
            if self.atual is not None and self.atual["pasta"] == pasta:
                return 0
            return self.itens.index(pasta) + 1 if pasta in self.itens else None

    # ---- ações ----
    def enfileirar(self, pasta: Path) -> str:
        with self.cond:
            if (self.atual is not None and self.atual["pasta"] == pasta) or pasta in self.itens:
                return "ja_esta"
            self.itens.append(pasta)
            self.ultimo.pop(pasta.name, None)
            self.cond.notify_all()
            return "rodando" if self.atual is None and len(self.itens) == 1 else "na_fila"

    def cancelar(self, pasta: Path) -> bool:
        with self.cond:
            if pasta in self.itens:
                self.itens.remove(pasta)
                return True
            job = self.atual if (self.atual is not None and self.atual["pasta"] == pasta) else None
        if job is None:
            return False
        job["cancelar"].set()
        matar(job.get("processo"))
        return True

    def esperar_ociosa(self, limite: float = 10.0) -> bool:
        """Para os testes: espera a fila esvaziar."""
        fim = time.time() + limite
        while time.time() < fim:
            with self.cond:
                if self.atual is None and not self.itens:
                    return True
            time.sleep(0.02)
        return False

    def parar(self):
        with self.cond:
            self.parando = True
            self.cond.notify_all()

    # ---- o trabalhador ----
    def _laco(self):
        while True:
            with self.cond:
                while not self.itens and not self.parando:
                    self.cond.wait()
                if self.parando:
                    return
                pasta = self.itens.pop(0)
                self.atual = {"pasta": pasta, "cancelar": threading.Event(), "processo": None, "inicio": time.time()}
                job = self.atual
            linhas: list[str] = []
            try:
                resultado = self.proximo(pasta, self.fabrica(job), linhas.append)
            except SystemExit:
                resultado, _ = "erro", linhas.append("a etapa terminou com erro (veja o registro da edição)")
            except Exception as e:  # noqa: BLE001  (o trabalhador nunca morre por causa de uma edição)
                resultado, _ = "erro", linhas.append(f"erro: {str(e)[:200]}")
            with self.cond:
                self.ultimo[pasta.name] = {"resultado": resultado, "linhas": linhas, "fim": time.time()}
                self.atual = None
                self.cond.notify_all()
