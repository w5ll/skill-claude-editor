"""O que a máquina tem para os testes: ffmpeg completo e navegador do Playwright.

Na máquina da pessoa, faltar ferramenta faz o teste pular com uma mensagem clara.
Nos testes automáticos (WELLDIT_TESTES_AUTOMATICOS=1) faltar ferramenta reprova, para um teste não ficar
verde só porque a máquina não tinha o navegador.
"""

import os
import shutil
import subprocess
import unittest

FILTROS = ("ass", "zscale", "afftdn")


def automatico() -> bool:
    return os.environ.get("WELLDIT_TESTES_AUTOMATICOS") == "1"


def indisponivel(motivo: str):
    """Pula o teste (na máquina da pessoa) ou reprova (nos testes automáticos)."""
    if automatico():
        raise AssertionError(f"faltou na máquina dos testes automáticos: {motivo}")
    raise unittest.SkipTest(motivo)


def filtros_que_faltam() -> list[str]:
    if not shutil.which("ffmpeg"):
        return list(FILTROS)
    saida = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    nomes = {linha.split()[1] for linha in saida.splitlines() if len(linha.split()) > 1}
    return [f for f in FILTROS if f not in nomes]


def exigir_ffmpeg_completo():
    faltam = filtros_que_faltam()
    if faltam:
        indisponivel("este teste precisa do ffmpeg completo (falta: " + ", ".join(faltam) + "). Veja a instalação no README: "
                     "no Mac, brew install ffmpeg-full")


def exigir_navegador():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        from elementos import abrir_navegador  # noqa: F401
    except ImportError:
        indisponivel("sem o Playwright instalado (pip install -r skill/welldit/scripts/requirements.txt)")


if __name__ == "__main__":
    faltam = filtros_que_faltam()
    print("ffmpeg completo: " + ("ok" if not faltam else "falta " + ", ".join(faltam)))
    raise SystemExit(1 if faltam else 0)
