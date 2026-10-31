"""O instalar.sh: diz o que falta sem instalar nada, fala português, não mexe no que não pode.

Usa ferramentas de mentira num caminho (PATH) isolado, então não instala nada de verdade.
A instalação de verdade é provada no fluxo do GitHub (.github/workflows/instalacao.yml).

Rodar: tests/rodar.sh tests.test_instalar
"""

import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "instalar.sh"

# ferramentas do sistema que o script usa e que entram no caminho de mentira
DO_SISTEMA = ["bash", "env", "uname", "awk", "grep", "date", "dirname", "cat", "mv", "mkdir", "sh", "basename", "tr", "sed"]

FFMPEG_COMPLETO = "#!/bin/sh\necho 'Filters:'\nprintf ' T.. ass    V->V  x\\n T.. zscale V->V x\\n T.. afftdn A->A x\\n'\n"
FFMPEG_SEM_LEGENDA = "#!/bin/sh\necho 'Filters:'\nprintf ' T.. scale V->V x\\n'\n"
PYTHON_VELHO = "#!/bin/sh\nexit 1\n"

# palavras em inglês que não podem aparecer na tela (nomes de programas são permitidos)
INGLES = ["installing", "error", "failed", "missing", "please", "done", "download", "warning", "not found", "setup", "virtualenv", "venv"]


def fazer_executavel(caminho: Path, conteudo: str):
    caminho.write_text(conteudo, encoding="utf-8")
    caminho.chmod(caminho.stat().st_mode | stat.S_IEXEC)


def resumo_da_pasta(pasta: Path) -> dict:
    saida = {}
    for p in sorted(pasta.rglob("*")):
        if p.is_file():
            saida[str(p.relative_to(pasta))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return saida


@unittest.skipIf(os.name == "nt", "o instalar.sh é para Mac e Linux")
class InstalarSh(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.projeto = self.tmp / "projeto"
        self.projeto.mkdir()
        shutil.copy(SCRIPT, self.projeto / "instalar.sh")
        self.ferramentas = self.tmp / "ferramentas"
        self.ferramentas.mkdir()
        for nome in DO_SISTEMA:
            origem = shutil.which(nome)
            if origem:
                (self.ferramentas / nome).symlink_to(origem)

    def rodar(self, *opcoes: str, entrada: str = ""):
        ambiente = {"PATH": str(self.ferramentas), "HOME": str(self.tmp), "WELLDIT_BREW": "", "LANG": "pt_BR.UTF-8"}
        return subprocess.run(["bash", str(self.projeto / "instalar.sh"), *opcoes], cwd=self.projeto, env=ambiente,
                              capture_output=True, text=True, input=entrada, timeout=60)

    def com_python_bom(self):
        # o Python que roda os testes (3.10 a 3.13 nos testes automáticos) faz papel de Python do computador
        if not ((3, 10) <= sys.version_info[:2] <= (3, 13)):
            self.skipTest("o Python deste teste está fora da faixa 3.10 a 3.13")
        (self.ferramentas / "python3").symlink_to(Path(sys.executable).resolve())

    def test_sem_nada_diz_o_que_falta_e_nao_cria_nada(self):
        r = self.rodar("--so-conferir")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("falta: Python 3.12", r.stdout)
        self.assertIn("falta: ffmpeg completo", r.stdout)
        self.assertIn("Rode ./instalar.sh", r.stdout)
        self.assertFalse((self.projeto / ".venv").exists())
        self.assertEqual(sorted(p.name for p in self.projeto.iterdir()), ["instalacao.log", "instalar.sh"])

    def test_python_velho_nao_serve(self):
        fazer_executavel(self.ferramentas / "python3", PYTHON_VELHO)
        r = self.rodar("--so-conferir")
        self.assertIn("falta: Python 3.12", r.stdout)

    def test_ffmpeg_sem_legenda_nao_serve(self):
        self.com_python_bom()
        fazer_executavel(self.ferramentas / "ffmpeg", FFMPEG_SEM_LEGENDA)
        fazer_executavel(self.ferramentas / "ffprobe", "#!/bin/sh\nexit 0\n")
        r = self.rodar("--so-conferir")
        self.assertIn("pronto: Python", r.stdout)
        self.assertIn("falta: ffmpeg completo", r.stdout)

    def test_ffmpeg_completo_e_python_bom_passam(self):
        self.com_python_bom()
        fazer_executavel(self.ferramentas / "ffmpeg", FFMPEG_COMPLETO)
        fazer_executavel(self.ferramentas / "ffprobe", "#!/bin/sh\nexit 0\n")
        r = self.rodar("--so-conferir")
        self.assertIn("pronto: Python", r.stdout)
        self.assertIn("pronto: ffmpeg completo", r.stdout)
        self.assertNotIn("falta: ffmpeg", r.stdout)

    def test_ambiente_ruim_nao_e_apagado(self):
        self.com_python_bom()
        fazer_executavel(self.ferramentas / "ffmpeg", FFMPEG_COMPLETO)
        fazer_executavel(self.ferramentas / "ffprobe", "#!/bin/sh\nexit 0\n")
        (self.projeto / ".venv" / "bin").mkdir(parents=True)
        fazer_executavel(self.projeto / ".venv" / "bin" / "python", PYTHON_VELHO)
        (self.projeto / ".venv" / "minha-coisa.txt").write_text("não apague", encoding="utf-8")
        antes = resumo_da_pasta(self.projeto / ".venv")
        r = self.rodar("--so-conferir")
        self.assertIn("falta: ambiente da skill", r.stdout)
        self.assertEqual(antes, resumo_da_pasta(self.projeto / ".venv"))

    def test_sem_terminal_e_sem_sim_nao_instala(self):
        # sem --sim e sem terminal o script não consegue perguntar, então não instala nada
        r = self.rodar()
        self.assertEqual(r.returncode, 1)
        self.assertIn("falta: Python 3.12", r.stdout)
        self.assertFalse((self.projeto / ".venv").exists())

    def test_nao_mexe_em_material_bruto_nem_saida(self):
        for pasta in ("material-bruto", "saida/2026-01-01_teste"):
            (self.projeto / pasta).mkdir(parents=True)
            (self.projeto / pasta / "arquivo.txt").write_text("meu vídeo", encoding="utf-8")
        antes = {k: v for k, v in resumo_da_pasta(self.projeto).items() if k.startswith(("material-bruto", "saida"))}
        self.rodar("--so-conferir")
        self.rodar()
        depois = {k: v for k, v in resumo_da_pasta(self.projeto).items() if k.startswith(("material-bruto", "saida"))}
        self.assertEqual(antes, depois)
        self.assertEqual(len(antes), 2)

    def test_o_script_nem_cita_material_bruto_e_saida_fora_de_comentario(self):
        for numero, linha in enumerate(SCRIPT.read_text(encoding="utf-8").splitlines(), 1):
            codigo = linha.split("#", 1)[0]
            self.assertNotRegex(codigo, r"material-bruto|saida/|\bsaida\b", f"linha {numero}: {linha}")

    def test_tela_em_portugues_sem_travessao(self):
        self.com_python_bom()
        fazer_executavel(self.ferramentas / "ffmpeg", FFMPEG_SEM_LEGENDA)
        for argumentos in (["--so-conferir"], ["--help"]):
            texto = self.rodar(*argumentos).stdout.lower()
            self.assertNotIn("—", texto)
            self.assertNotIn("–", texto)
            for palavra in INGLES:
                self.assertNotRegex(texto, rf"\b{re.escape(palavra)}\b", f"palavra em inglês na tela: {palavra}")
        codigo = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("—", codigo)
        self.assertNotIn("–", codigo)

    def test_opcao_desconhecida(self):
        r = self.rodar("--qualquer-coisa")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--help", r.stdout)

    def test_ajuda(self):
        r = self.rodar("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("--so-conferir", r.stdout)

    def test_sintaxe_do_bash(self):
        r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_o_script_nao_entra_na_skill(self):
        self.assertFalse((RAIZ / "skill" / "welldit" / "instalar.sh").exists())
        self.assertTrue(os.access(SCRIPT, os.X_OK), "instalar.sh precisa ser executável (chmod +x)")


if __name__ == "__main__":
    unittest.main()
