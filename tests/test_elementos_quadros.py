"""Comparação de quadros dos 12 elementos 3D prontos (era feita à mão na Fase 2).

Cada elemento é desenhado no navegador, no perfil padrão (arven), em 3 instantes, e comparado com o quadro de
referência guardado em tests/referencias/elementos/. A comparação tem tolerância: fonte e serrilhado variam um
pouco de um computador para outro. Se passar do limite, as imagens (referência, nova e diferença) ficam em
tests/_diferencas/ para a pessoa ver.

Para aceitar uma mudança de visual de propósito: python tests/atualizar_referencias.py quadros
Rodar: tests/rodar.sh tests.test_elementos_quadros
"""

import sys
import unittest
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "skill" / "welldit" / "scripts"))

import ambiente  # noqa: E402
import comum  # noqa: E402
import elementos  # noqa: E402

REFERENCIAS = AQUI / "referencias" / "elementos"
DIFERENCAS = AQUI / "_diferencas"
LARGURA, ALTURA = 540, 960          # vídeo imaginário: o quadro do elemento tem 40% da largura
INSTANTES = (0.3, 1.0, 1.8)         # entrada, meio e fim de 2 s
FUNDO = 128                         # cinza em que o quadro transparente é apoiado antes de comparar
LIMITE_MEDIA = 1.5                  # diferença média por pixel (0 a 255)
LIMITE_FORTE = 0.01                 # fração de pixels com diferença acima de 40


def item(nome: str) -> dict:
    return {"elemento": nome, "modo": "sobreposto", "inicio": 0.0, "duracao": 2.0, "texto": "5 minutos", "posicao": "topo"}


def desenhar_todos() -> dict[str, np.ndarray]:
    """Devolve {'esfera-0.3': quadro RGBA, ...}."""
    import cv2
    from playwright.sync_api import sync_playwright
    marca = comum.carregar_marca("arven")
    saida = {}
    with sync_playwright() as pw:
        nav = elementos.abrir_navegador(pw)
        for nome in elementos.ELEMENTOS:
            it = item(nome)
            w, h = elementos.tamanho_quadro(it, LARGURA, ALTURA)
            pagina = nav.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            pagina.goto(elementos.molde_do_item(it))
            pagina.evaluate("document.fonts.ready")
            pagina.evaluate("cfg => montar(cfg)", elementos.cfg_pagina(it, w, h, None, marca))
            pagina.evaluate("document.fonts.ready")
            for t in INSTANTES:
                pagina.evaluate(f"desenhar({t})")
                png = pagina.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": w, "height": h})
                saida[f"{nome}-{t}"] = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
            pagina.close()
        nav.close()
    return saida


def sobre_cinza(quadro: np.ndarray) -> np.ndarray:
    """Apoia o quadro (com transparência) num fundo cinza, para comparar o que a pessoa realmente vê."""
    if quadro.ndim == 3 and quadro.shape[2] == 4:
        a = quadro[:, :, 3:4].astype(np.float32) / 255
        return quadro[:, :, :3].astype(np.float32) * a + FUNDO * (1 - a)
    return quadro.astype(np.float32)


def comparar(novo: np.ndarray, ref: np.ndarray) -> tuple[float, float]:
    """(diferença média, fração de pixels muito diferentes)."""
    if novo.shape != ref.shape:
        return 255.0, 1.0
    d = np.abs(sobre_cinza(novo) - sobre_cinza(ref)).max(axis=2)
    return float(d.mean()), float((d > 40).mean())


def regravar():
    import cv2
    REFERENCIAS.mkdir(parents=True, exist_ok=True)
    for f in REFERENCIAS.glob("*.png"):
        f.unlink()
    quadros = desenhar_todos()
    for nome, q in quadros.items():
        cv2.imwrite(str(REFERENCIAS / f"{nome}.png"), q, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    print(f"ok  {len(quadros)} quadros em tests/referencias/elementos/")


class TestQuadrosDosElementos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ambiente.exigir_navegador()
        try:
            cls.quadros = desenhar_todos()
        except SystemExit:
            ambiente.indisponivel("sem o Chromium do Playwright (python -m playwright install chromium)")

    def test_ha_referencia_para_cada_elemento_e_instante(self):
        esperadas = {f"{n}-{t}.png" for n in elementos.ELEMENTOS for t in INSTANTES}
        existentes = {p.name for p in REFERENCIAS.glob("*.png")}
        self.assertEqual(esperadas, existentes, "rode python tests/atualizar_referencias.py quadros")

    def test_cada_quadro_confere_com_a_referencia(self):
        import cv2
        ruins = []
        for nome, novo in self.quadros.items():
            ref = cv2.imread(str(REFERENCIAS / f"{nome}.png"), cv2.IMREAD_UNCHANGED)
            self.assertIsNotNone(ref, f"falta a referência {nome}.png")
            media, forte = comparar(novo, ref)
            if media > LIMITE_MEDIA or forte > LIMITE_FORTE:
                ruins.append(f"{nome}: diferença média {media:.2f} (limite {LIMITE_MEDIA}), {forte * 100:.2f}% dos pontos muito diferentes")
                DIFERENCAS.mkdir(exist_ok=True)
                if novo.shape == ref.shape:
                    junto = np.hstack([sobre_cinza(ref), sobre_cinza(novo),
                                       np.abs(sobre_cinza(novo) - sobre_cinza(ref)) * 4]).clip(0, 255).astype(np.uint8)
                    cv2.imwrite(str(DIFERENCAS / f"{nome}.png"), junto)
        self.assertEqual(ruins, [], "os quadros mudaram (referência | novo | diferença em tests/_diferencas/)")

    def test_a_comparacao_enxerga_uma_cor_trocada(self):
        """Garante que o teste não é cego: trocar a cor do elemento passa do limite."""
        import cv2
        nome = f"{elementos.ELEMENTOS[0]}-1.0"
        ref = cv2.imread(str(REFERENCIAS / f"{nome}.png"), cv2.IMREAD_UNCHANGED)
        alterado = ref.copy()
        alterado[:, :, 0] = np.where(alterado[:, :, 3] > 0, 255 - alterado[:, :, 0], alterado[:, :, 0])
        media, forte = comparar(alterado, ref)
        self.assertTrue(media > LIMITE_MEDIA or forte > LIMITE_FORTE, (media, forte))

    def test_elemento_diferente_nao_passa_pelo_outro(self):
        a, b = self.quadros[f"{elementos.ELEMENTOS[0]}-1.0"], self.quadros[f"{elementos.ELEMENTOS[3]}-1.0"]
        media, forte = comparar(a, b)
        self.assertTrue(media > LIMITE_MEDIA or forte > LIMITE_FORTE)


if __name__ == "__main__":
    unittest.main()
