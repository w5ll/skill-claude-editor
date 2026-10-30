"""Testes dos cortes (propor_cortes.py) com áudio e fala sintéticos: sem vídeo real e sem transcrição.

O áudio é feito de rajadas de ruído (a "fala") com silêncio entre elas; a transcrição é escrita à mão.
Rodar: tests/rodar.sh tests.test_cortes
"""

import sys
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "welldit" / "scripts"))

import ambiente  # noqa: E402
import propor_cortes as pc  # noqa: E402

TAXA = 16000
DINAMICO = pc.RITMOS["dinamico"]


def audio(duracao: float, rajadas: list[tuple[float, float]]) -> np.ndarray:
    """Ruído baixo de sala e, nas rajadas, 'voz' bem mais alta."""
    rng = np.random.default_rng(7)
    x = rng.normal(0, 0.002, int(duracao * TAXA))
    for a, b in rajadas:
        i, j = int(a * TAXA), int(b * TAXA)
        x[i:j] += rng.normal(0, 0.15, j - i)
    return x.astype(np.float32)


def gravar(pasta: Path, x: np.ndarray) -> Path:
    arq = pasta / "fala.wav"
    with wave.open(str(arq), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return arq


def palavra(p, i, f):
    return {"p": p, "i": i, "f": f, "conf": 0.95}


# fala: 0,2 a 1,6 | pausa de 1,4 s | 3,0 a 4,4 | respiração em 4,9 a 5,2 | 6,0 a 7,0
RAJADAS = [(0.2, 1.6), (3.0, 4.4), (4.9, 5.2), (6.0, 7.0)]
PALAVRAS = [palavra("Defina", 0.25, 0.7), palavra("uma", 0.75, 0.95), palavra("meta.", 1.0, 1.55),
            palavra("Não", 3.05, 3.4), palavra("pare", 3.45, 3.9), palavra("agora.", 3.95, 4.35),
            palavra("Obrigado.", 6.05, 6.95)]


class TestPropor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ambiente.exigir_ffmpeg_completo()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.arq = gravar(Path(cls.tmp.name), audio(7.6, RAJADAS))
        cls.trechos, cls.removidos, cls.conferir, _, cls.duracao = pc.propor(
            0, str(cls.arq), {"palavras": PALAVRAS}, DINAMICO)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pausa_longa_vira_corte(self):
        pausas = [r for r in self.removidos if "pausa" in r["motivo"]]
        self.assertGreaterEqual(len(pausas), 1)
        self.assertTrue(any(1.6 <= r["inicio"] < r["fim"] <= 3.0 for r in pausas), pausas)

    def test_respiracao_sem_palavra_sai(self):
        self.assertTrue(any("respiração" in r["motivo"] and 4.8 <= r["inicio"] <= 5.3 for r in self.removidos), self.removidos)
        for t in self.trechos:
            self.assertFalse(t["inicio"] < 5.0 < t["fim"], "a respiração ficou dentro de um trecho")

    def test_nenhuma_palavra_fica_de_fora_dos_trechos(self):
        for w in PALAVRAS:
            meio = (w["i"] + w["f"]) / 2
            self.assertTrue(any(t["inicio"] <= meio <= t["fim"] for t in self.trechos), w["p"])

    def test_trechos_em_ordem_sem_sobreposicao_e_com_folga_na_borda(self):
        for a, b in zip(self.trechos, self.trechos[1:]):
            self.assertLessEqual(a["fim"], b["inicio"])
        for t in self.trechos:
            self.assertLess(t["inicio"], t["fim"])
        primeiro = self.trechos[0]
        self.assertLessEqual(primeiro["inicio"], 0.2 - pc.FOLGA_ANTES + 0.03)
        self.assertGreaterEqual(self.trechos[-1]["fim"], 7.0)

    def test_ritmo_natural_corta_menos_que_o_dinamico(self):
        natural, *_ = pc.propor(0, str(self.arq), {"palavras": PALAVRAS}, pc.RITMOS["natural"])
        total = lambda ts: sum(t["fim"] - t["inicio"] for t in ts)
        self.assertGreater(total(natural), total(self.trechos))


class TestRepeticao(unittest.TestCase):
    def test_frase_repetida_perde_a_primeira_tentativa(self):
        palavras = [palavra("Eu", 0.2, 0.4), palavra("acho", 0.45, 0.7), palavra("que", 0.75, 0.9),
                    palavra("Eu", 1.4, 1.6), palavra("acho", 1.65, 1.9), palavra("que", 1.95, 2.1),
                    palavra("vale", 2.15, 2.5), palavra("a", 2.55, 2.65), palavra("pena.", 2.7, 3.2)]
        env = pc.envelope_db(audio(3.4, [(0.2, 0.95), (1.4, 3.2)]), pc.PASSO)
        removidos, _ = pc.achar_repeticoes(palavras, env, 3.4)
        self.assertEqual(len(removidos), 1, removidos)
        self.assertLessEqual(removidos[0]["inicio"], 1.4)
        self.assertGreaterEqual(removidos[0]["inicio"], 0.0)
        self.assertLessEqual(removidos[0]["fim"], 1.4)

    def test_fala_sem_repeticao_nao_perde_nada(self):
        palavras = [palavra("Defina", 0.25, 0.7), palavra("uma", 0.75, 0.95), palavra("meta.", 1.0, 1.55)]
        removidos, _ = pc.achar_repeticoes(palavras, pc.envelope_db(audio(2.0, [(0.2, 1.6)]), pc.PASSO), 2.0)
        self.assertEqual(removidos, [])


class TestAvisoObrigatorio(unittest.TestCase):
    AVISO = "Esta publicação não substitui a consulta"
    FALA = [palavra(p, 1.0 + 0.3 * k, 1.25 + 0.3 * k)
            for k, p in enumerate("Esta publicação não substitui a consulta com um profissional".split())]

    def conferir(self, trechos):
        return pc.conferir_avisos([self.AVISO], {0: self.FALA}, trechos)[0]

    def test_mantido_quando_o_trecho_cobre_a_frase_inteira(self):
        r = self.conferir([{"video": 0, "inicio": 0.0, "fim": 6.0}])
        self.assertEqual(r["estado"], "mantido")

    def test_cortado_quando_falta_um_pedaco_e_diz_quais_palavras(self):
        r = self.conferir([{"video": 0, "inicio": 0.0, "fim": 1.9}])
        self.assertEqual(r["estado"], "cortado")
        self.assertIn("consulta", r["cortadas"])

    def test_nao_encontrado_quando_a_pessoa_nao_disse(self):
        r = pc.conferir_avisos([self.AVISO], {0: [palavra("Olá.", 0.1, 0.4)]}, [{"video": 0, "inicio": 0, "fim": 1}])[0]
        self.assertEqual(r["estado"], "nao_encontrado")

    def test_frase_dita_com_pequena_variacao_ainda_e_achada(self):
        fala = [palavra(p, 0.3 * k, 0.3 * k + 0.25) for k, p in enumerate("esta publicacao nao substitui a consulta".split())]
        self.assertEqual(len(pc.achar_aviso(self.AVISO, fala)), 1)


class TestPecasPequenas(unittest.TestCase):
    def test_hesitacao_e_normalizacao(self):
        self.assertTrue(pc.eh_hesitacao("ahn"))
        self.assertFalse(pc.eh_hesitacao("não"))
        self.assertEqual(pc.normalizar("Não,"), pc.normalizar("nao"))

    def test_subtrair_remove_o_miolo_e_descarta_sobra_curta(self):
        self.assertEqual(pc.subtrair([[0, 10]], 4, 6), [[0, 4], [6, 10]])
        self.assertEqual(pc.subtrair([[0, 10]], 0.05, 6), [[6, 10]])      # sobra de 0,05 s é curta demais
        self.assertEqual(pc.subtrair([[0, 3]], 5, 6), [[0, 3]])

    def test_frases_quebram_na_pontuacao_e_na_pausa(self):
        p = [palavra("a", 0, 0.2), palavra("b.", 0.25, 0.5), palavra("c", 0.55, 0.8), palavra("d", 1.6, 1.9)]
        self.assertEqual(pc.frases(p), [[0, 1], [2], [3]])


if __name__ == "__main__":
    unittest.main()
