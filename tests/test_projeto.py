"""Conferências do projeto inteiro: scripts, pacote da skill, textos e o que o git guarda.

Rodar: tests/rodar.sh tests.test_projeto
"""

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SKILL = RAIZ / "skill" / "welldit"
SCRIPTS = SKILL / "scripts"


def git(*args) -> list[str]:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)
    if r.returncode != 0:
        raise unittest.SkipTest("sem o git neste lugar")
    return [l for l in r.stdout.splitlines() if l]


def scripts_de_linha_de_comando() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("*.py") if '__name__ == "__main__"' in p.read_text(encoding="utf-8"))


class TestScripts(unittest.TestCase):
    def test_todo_script_responde_a_help(self):
        scripts = scripts_de_linha_de_comando()
        self.assertGreater(len(scripts), 15)
        for p in scripts:
            with self.subTest(p.name):
                r = subprocess.run([sys.executable, str(p), "--help"], capture_output=True, text=True, timeout=120, cwd=SCRIPTS)
                self.assertEqual(r.returncode, 0, r.stderr[-400:])
                self.assertIn("usage", r.stdout.lower() + r.stderr.lower())

    def test_todo_script_compila(self):
        for p in sorted(SCRIPTS.glob("*.py")):
            with self.subTest(p.name):
                compile(p.read_text(encoding="utf-8"), str(p), "exec")


class TestPacote(unittest.TestCase):
    def test_empacotar_gera_o_skill_com_o_essencial(self):
        if not shutil.which("zip"):
            raise unittest.SkipTest("sem o comando zip")
        with tempfile.TemporaryDirectory() as d:
            copia = Path(d) / "projeto"
            (copia / "skill").mkdir(parents=True)
            shutil.copytree(SKILL, copia / "skill" / "welldit", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy(RAIZ / "empacotar.sh", copia / "empacotar.sh")
            r = subprocess.run(["bash", str(copia / "empacotar.sh")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            arq = copia / "dist" / "welldit.skill"
            self.assertTrue(arq.exists())
            nomes = set(zipfile.ZipFile(arq).namelist())
            for esperado in ("welldit/SKILL.md", "welldit/scripts/editar.py", "welldit/scripts/requirements.txt",
                             "welldit/perfis/arven/marca.json", "welldit/perfis/_modelo/marca.json",
                             "welldit/assets/fontes/Sora-ExtraBold.ttf"):
                self.assertIn(esperado, nomes)
            self.assertFalse([n for n in nomes if "__pycache__" in n or n.endswith(".pyc")])


class TestSkillMd(unittest.TestCase):
    def setUp(self):
        self.texto = (SKILL / "SKILL.md").read_text(encoding="utf-8")

    def test_cabecalho(self):
        m = re.match(r"---\nname: (\S+)\ndescription: \"(.+)\"\n---\n", self.texto)
        self.assertIsNotNone(m, "o SKILL.md precisa começar com name e description entre ---")
        self.assertEqual(m.group(1), "welldit")

    def test_referencias_citadas_existem(self):
        citadas = set(re.findall(r"`?referencias/([\w-]+\.md)`?", self.texto))
        citadas |= set(re.findall(r"`([\w-]+\.md)`", self.texto.split("## Arquivos de apoio", 1)[1].split("## O fluxo", 1)[0]))
        self.assertGreater(len(citadas), 8)
        for nome in citadas:
            self.assertTrue((SKILL / "referencias" / nome).exists(), nome)

    def test_toda_referencia_esta_citada_no_skill_md(self):
        for p in (SKILL / "referencias").glob("*.md"):
            self.assertIn(p.name, self.texto, f"{p.name} não aparece no SKILL.md")

    def test_scripts_citados_existem(self):
        for nome in set(re.findall(r"scripts/([\w]+)\.py", self.texto)):
            self.assertTrue((SCRIPTS / f"{nome}.py").exists(), nome)


class TestTextos(unittest.TestCase):
    ANTIGOS = ["lunardi" + "well", "edicao-video-" + "well"]
    HISTORICOS = {"docs/comparacao-editonny.md", "docs/proximas-fases.md", "docs/roadmap.md"}

    def arquivos_de_texto(self) -> list[str]:
        return [f for f in git("ls-files") if f.endswith((".md", ".py", ".json", ".html", ".sh", ".yml", ".txt"))]

    def test_nome_antigo_nao_aparece_fora_dos_documentos_historicos(self):
        for f in self.arquivos_de_texto():
            if f in self.HISTORICOS or f.startswith("docs/fase-"):
                continue
            texto = (RAIZ / f).read_text(encoding="utf-8", errors="ignore")
            for antigo in self.ANTIGOS:
                self.assertTrue(antigo not in texto, f"{f} cita o nome antigo")

    def test_perfil_padrao_tem_o_aviso_dos_elementos_base(self):
        import json
        marca = json.loads((SKILL / "perfis" / "arven" / "marca.json").read_text(encoding="utf-8"))
        self.assertEqual(marca["creditos"], "elementos base ARVEN")
        self.assertIn("elementos base ARVEN", (RAIZ / "README.md").read_text(encoding="utf-8"))


class TestOQueOGitGuarda(unittest.TestCase):
    def test_nenhum_video_audio_ou_segredo(self):
        proibidos = re.compile(r"\.(mp4|mov|m4v|mkv|webm|m4a)$|(^|/)\.env|\.pem$|\.key$", re.I)
        for f in git("ls-files"):
            self.assertIsNone(proibidos.search(f), f"{f} não deveria estar no git")

    def test_audio_so_na_pasta_de_sons_da_skill(self):
        for f in git("ls-files"):
            if f.lower().endswith((".wav", ".mp3")):
                self.assertTrue(f.startswith("skill/welldit/assets/sons/"), f)

    def test_so_o_perfil_padrao_o_modelo_e_a_explicacao_ficam_no_git(self):
        perfis = set()
        for f in git("ls-files", "skill/welldit/perfis"):
            perfis.add(f.split("/")[3])
        self.assertEqual(perfis, {"arven", "_modelo", "LEIA.md"})

    def test_nada_de_trabalho_no_git(self):
        for f in git("ls-files"):
            self.assertFalse(f.startswith(("saida/", "material-bruto/")) and not f.endswith((".gitkeep", "LEIA.md", "README.md")), f)


if __name__ == "__main__":
    unittest.main()
