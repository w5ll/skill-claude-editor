"""Testes da detecção de frase refalada (a pessoa para um instante e fala de novo, sem avisar a câmera)."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "welldit" / "scripts"))

import propor_cortes  # noqa: E402


def falar(texto: str, inicio: float, passo: float = 0.3) -> list[dict]:
    return [{"p": p, "i": round(inicio + k * passo, 3), "f": round(inicio + k * passo + passo * 0.8, 3), "conf": 0.95}
            for k, p in enumerate(texto.split())]


def achar(palavras: list[dict]):
    duracao = palavras[-1]["f"] + 1.0
    env = np.full(int(duracao * 100), -60.0)        # silêncio em tudo: o ponto de corte cai na pausa
    for w in palavras:
        env[int(w["i"] * 100):int(w["f"] * 100)] = -20.0
    return propor_cortes.achar_repeticoes(palavras, env, duracao)[0]


class TestRefala(unittest.TestCase):
    def test_comeco_abandonado_e_refalado_depois_de_pausa(self):
        ws = falar("a primeira coisa que qualquer", 1.0) + falar("a primeira coisa que qualquer cliente busca", 4.0)
        r = achar(ws)
        self.assertEqual(len(r), 1)
        self.assertLess(r[0]["inicio"], 1.1)
        self.assertGreater(r[0]["fim"], 2.3)
        self.assertLess(r[0]["fim"], 4.0)           # a segunda vez fica inteira

    def test_aviso_de_que_vai_repetir_tira_a_tentativa_anterior(self):
        antes = falar("Então o seu cliente está buscando uma vantagem.", 1.0)
        aviso = falar("Deixa eu só repetir essa frase.", 6.0)
        nova = falar("Então basicamente o seu cliente está buscando vantagens.", 10.0)
        r = achar(antes + aviso + nova)
        self.assertTrue(any(x["motivo"].startswith("a pessoa avisou") for x in r))
        x = next(x for x in r if x["motivo"].startswith("a pessoa avisou"))
        self.assertLess(x["inicio"], 1.1)
        self.assertGreater(x["fim"], 7.5)     # inclui o aviso
        self.assertLess(x["fim"], 10.0)

    def test_frases_diferentes_nao_sao_cortadas(self):
        ws = falar("hoje eu vou falar de preço.", 1.0) + falar("o produto precisa ser melhor.", 6.0)
        self.assertEqual(achar(ws), [])

    def test_aviso_sem_tentativa_parecida_nao_corta_nada(self):
        ws = falar("hoje eu vou falar de preço.", 1.0) + falar("deixa eu repetir.", 6.0) + falar("amanhã é outro dia.", 9.0)
        self.assertEqual([x for x in achar(ws) if x["motivo"].startswith("a pessoa avisou")], [])


if __name__ == "__main__":
    unittest.main()
