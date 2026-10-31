"""Testes da legenda (legendas.py) com falas sintéticas: sem vídeo e sem ffmpeg.

A referência `tests/referencias/legenda-arven.ass` é o arquivo que o perfil padrão (arven) gera para a fala
de teste: ele tem que sair igual byte a byte. Para aceitar uma mudança de propósito:
python tests/atualizar_referencias.py
Rodar: tests/rodar.sh tests.test_legenda
"""

import copy
import sys
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent / "skill" / "welldit" / "scripts"))

import comum  # noqa: E402
import legendas  # noqa: E402

REFERENCIA = AQUI / "referencias" / "legenda-arven.ass"
ESTILO = {"palavras": 3, "posicao": "auto", "tamanho": 0.052, "maiusculas": False, "destaque": True,
          "largura": 1080, "altura": 1920}

FALA = [("Defina", 0.30, 0.70), ("uma", 0.75, 0.90), ("meta", 0.95, 1.40), ("clara.", 1.45, 1.90),
        ("Depois,", 2.60, 3.00), ("responda", 3.05, 3.50), ("no", 3.55, 3.65), ("whatsapp", 3.70, 4.30),
        ("em", 4.35, 4.50), ("cinco", 4.55, 4.90), ("minutos?", 4.95, 5.50)]


def palavras():
    return [{"p": p, "i": i, "f": f} for p, i, f in FALA]


def blocos_de_teste():
    return legendas.agrupar(palavras(), ESTILO["palavras"])


def ass_do_perfil(marca=None, estilo=None) -> str:
    marca = marca or comum.carregar_marca("arven")
    blocos = blocos_de_teste()
    return legendas.gerar_ass(blocos, 1080, 1920, {**ESTILO, **(estilo or {})}, marca)


class TestPerfilPadrao(unittest.TestCase):
    def test_ass_do_arven_igual_a_referencia_byte_a_byte(self):
        self.assertTrue(REFERENCIA.exists(), "falta tests/referencias/legenda-arven.ass (rode tests/atualizar_referencias.py)")
        self.assertEqual(ass_do_perfil().encode("utf-8"), REFERENCIA.read_bytes())

    def test_estilo_usa_a_fonte_e_as_cores_do_perfil(self):
        marca = comum.carregar_marca("arven")
        ass = ass_do_perfil(marca)
        self.assertIn("Style: Legenda,Sora ExtraBold,", ass)
        self.assertIn(legendas.cor_ass(marca["cores"]["texto"]), ass)
        self.assertIn(legendas.cor_ass(marca["cores"]["destaque"]), ass)


class TestOutroPerfil(unittest.TestCase):
    def marca_outra(self):
        marca = copy.deepcopy(comum.carregar_marca("arven"))
        marca["cores"]["texto"] = "#ffee00"
        marca["cores"]["destaque"] = "#00ccff"
        marca["cores"]["fundo_profundo"] = "#112233"
        return marca

    def test_trocar_as_cores_muda_so_as_cores(self):
        padrao = ass_do_perfil()
        outra = ass_do_perfil(self.marca_outra())
        self.assertNotEqual(padrao, outra)
        for cor in ("#ffee00", "#00ccff", "#112233"):
            self.assertIn(legendas.cor_ass(cor), outra)
        self.assertNotIn(legendas.cor_ass("#eaefef"), outra)
        # as linhas de fala (tempo e texto) são as mesmas
        falas = lambda s: [l.split(",,", 1)[0].split(",Legenda")[0] for l in s.splitlines() if l.startswith("Dialogue")]
        self.assertEqual(falas(padrao), falas(outra))

    def test_cor_ass(self):
        self.assertEqual(legendas.cor_ass("#a8b4d4"), "&H00D4B4A8")


class TestBlocos(unittest.TestCase):
    def test_no_maximo_tres_palavras_e_quebra_no_fim_de_frase(self):
        blocos = blocos_de_teste()
        for b in blocos:
            self.assertLessEqual(len(b["texto"].split()), 3, b)
        self.assertEqual([b["texto"] for b in blocos][:2], ["Defina uma meta", "clara"])

    def test_pontuacao_do_fim_sai_mas_interrogacao_fica(self):
        textos = " ".join(b["texto"] for b in blocos_de_teste())
        self.assertNotIn("clara.", textos)
        self.assertNotIn("Depois,", textos)
        self.assertIn("minutos?", textos)

    def test_pausa_longa_fecha_o_bloco(self):
        blocos = legendas.agrupar([{"p": "um", "i": 0.0, "f": 0.3}, {"p": "dois", "i": 1.5, "f": 1.8}], 3)
        self.assertEqual(len(blocos), 2)

    def test_cada_bloco_fica_pelo_menos_o_tempo_minimo_sem_invadir_o_proximo(self):
        blocos = legendas.agrupar([{"p": "oi", "i": 0.0, "f": 0.1}, {"p": "tudo", "i": 0.2, "f": 0.3}], 1)
        self.assertGreaterEqual(blocos[0]["fim"] - blocos[0]["inicio"], 0.1)
        self.assertLessEqual(blocos[0]["fim"], blocos[1]["inicio"])
        self.assertGreaterEqual(blocos[1]["fim"] - blocos[1]["inicio"], legendas.TEMPO_MINIMO - 1e-9)

    def test_medida_do_texto_cabe_na_largura(self):
        marca = comum.carregar_marca("arven")
        medir = legendas.Medidor(1920 * 0.052, comum.arquivo_da_fonte(marca))
        largura_util = 1080 * legendas.LARGURA_UTIL
        blocos = legendas.agrupar(palavras(), 8, cabe=lambda t: medir(t) <= largura_util)
        for b in blocos:
            self.assertLessEqual(medir(b["texto"]), largura_util, b["texto"])
        self.assertGreater(len(blocos), 1)


class TestTermos(unittest.TestCase):
    def test_grafia_da_marca_vem_do_perfil(self):
        saida = legendas.corrigir_termos(palavras(), ["WhatsApp"])
        self.assertIn("WhatsApp", [w["p"] for w in saida])

    def test_sem_termos_nada_muda(self):
        self.assertEqual(legendas.corrigir_termos(palavras(), []), palavras())

    def test_so_a_caixa_muda_e_a_pontuacao_fica(self):
        saida = legendas.corrigir_termos([{"p": "whatsapp,", "i": 0, "f": 1}], ["WhatsApp"])
        self.assertEqual(saida[0]["p"], "WhatsApp,")


class TestTempos(unittest.TestCase):
    def test_tempo_ass_e_srt(self):
        self.assertEqual(legendas.t_ass(3661.5), "1:01:01.50")
        self.assertEqual(legendas.t_srt(3661.5), "01:01:01,500")


if __name__ == "__main__":
    unittest.main()
