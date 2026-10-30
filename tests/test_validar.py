"""Testes do validar dos desenhos gerados (Fase 2), sem navegador: só a conferência do texto do desenho.

Rodar: tests/rodar.sh tests.test_validar
"""

import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "skill" / "welldit" / "scripts"))

import elementos  # noqa: E402

EXEMPLOS = RAIZ / "skill" / "welldit" / "templates" / "exemplos-gerados"
ANIMACAO_DOS_EXEMPLOS = {"bussola": "girar", "engrenagem": "girar", "escada": "aparecer", "trevo": "brilhar"}

SOMBRA = '<ellipse cx="200" cy="368" rx="120" ry="18" fill="url(#sombra)"/>'
FORMA = '<circle id="gira" cx="200" cy="200" r="80" fill="url(#met)"/>'
BOM = SOMBRA + FORMA


def erros(svg: str, animacao: str | None = "girar", parar: bool = False) -> list[str]:
    return elementos.validar_svg(svg, animacao, parar)[0]


class TestExemplos(unittest.TestCase):
    def test_os_quatro_exemplos_passam_sem_erro_nem_aviso(self):
        self.assertEqual(sorted(p.stem for p in EXEMPLOS.glob("*.svg")), sorted(ANIMACAO_DOS_EXEMPLOS))
        for nome, animacao in ANIMACAO_DOS_EXEMPLOS.items():
            with self.subTest(nome):
                e, a = elementos.validar_svg((EXEMPLOS / f"{nome}.svg").read_text(encoding="utf-8"), animacao)
                self.assertEqual((e, a), ([], []))

    def test_desenho_minimo_bom_passa(self):
        self.assertEqual(erros(BOM), [])


class TestRecusas(unittest.TestCase):
    def assertRecusa(self, svg, trecho, **kw):
        e = erros(svg, **kw)
        self.assertTrue(any(trecho in x for x in e), f"esperava um erro com '{trecho}', veio {e}")

    def test_texto_pessoa_logotipo_vao_por_tag_proibida(self):
        self.assertRecusa(BOM + "<text>oi</text>", "texto")
        self.assertRecusa(BOM + '<image href="x.png"/>', "imagem")
        self.assertRecusa(BOM + '<foreignObject/>', "foreignObject")
        self.assertRecusa(BOM + "<use/>", "<use>")

    def test_codigo_e_enderecos_externos(self):
        self.assertRecusa(BOM + "<script>alert(1)</script>", "script")
        self.assertRecusa('<circle cx="1" cy="1" r="1" onclick="x()"/>' + SOMBRA, "evento")
        self.assertRecusa('<circle cx="1" cy="1" r="1" href="http://x"/>' + SOMBRA, "href")
        self.assertRecusa('<circle cx="1" cy="1" r="1" style="fill:red"/>' + SOMBRA, "style")
        self.assertRecusa(BOM + "<style>*{}</style>", "style")

    def test_estrutura_e_tamanho(self):
        self.assertRecusa("<g>", "XML")
        self.assertRecusa("<g></g>", "nenhuma forma")
        self.assertRecusa("<svg>" + BOM + "</svg>", "sem a tag <svg>")
        self.assertRecusa("<!DOCTYPE x>" + BOM, "DOCTYPE")
        muitas = SOMBRA + "".join(f'<circle id="c{i}" cx="{i}" cy="1" r="1" fill="url(#met)"/>' for i in range(elementos.MAX_FORMAS + 1))
        self.assertRecusa(muitas, "máximo")

    def test_cor_fora_da_marca_e_id_repetido(self):
        self.assertRecusa('<circle cx="1" cy="1" r="1" fill="red"/>' + SOMBRA, "fill")
        self.assertRecusa(BOM + '<circle id="gira" cx="1" cy="1" r="1" fill="url(#met)"/>', "mais de uma vez")
        self.assertRecusa(SOMBRA + '<circle id="met" cx="1" cy="1" r="1" fill="url(#met)"/>', "reservado")

    def test_animacao(self):
        self.assertRecusa(BOM, "faltou dizer a animação", animacao=None)
        self.assertRecusa(BOM, "animação desconhecida", animacao="voar")
        self.assertRecusa(SOMBRA + '<circle cx="1" cy="1" r="1" fill="url(#met)"/>', 'id="gira"')
        self.assertRecusa(BOM, "aparecer", animacao="aparecer")
        self.assertRecusa(BOM, '"parar"', animacao="pulsar", parar=True)

    def test_aviso_sem_sombra_nao_reprova(self):
        e, a = elementos.validar_svg(FORMA, "girar")
        self.assertEqual(e, [])
        self.assertTrue(any("sombra" in x for x in a))


if __name__ == "__main__":
    unittest.main()
