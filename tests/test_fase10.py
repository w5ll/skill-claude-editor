"""Testes da Fase 10 (pacote de publicação e capa). Rodar: .venv/bin/python -m unittest discover -s tests -v"""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "edicao-video-well" / "scripts"))

import publicar  # noqa: E402

LIM = publicar.limites()
ESTILO = {"altura": 1920, "largura": 1080, "tamanho": 0.046, "posicao": "auto"}


def niveis(itens):
    return [n for n, _ in itens]


class TestVideo(unittest.TestCase):
    def conf(self, **kw):
        base = dict(duracao=45, mb=30, largura=1080, altura=1920, fps=30, tem_audio=True, codec_v="h264", codec_a="aac")
        base.update(kw)
        return publicar.conferir_numeros(lim=LIM, **base)

    def test_video_bom_passa(self):
        self.assertEqual(set(niveis(self.conf())), {publicar.OK})

    def test_duracao_longa_avisa_e_muito_longa_falha(self):
        self.assertIn(publicar.AVISO, niveis(self.conf(duracao=120)))
        self.assertNotIn(publicar.FALHOU, niveis(self.conf(duracao=120)))
        self.assertIn(publicar.FALHOU, niveis(self.conf(duracao=200)))

    def test_sem_som_e_horizontal_falham(self):
        self.assertIn(publicar.FALHOU, niveis(self.conf(tem_audio=False, codec_a=None)))
        self.assertIn(publicar.FALHOU, niveis(self.conf(largura=1920, altura=1080)))

    def test_largura_pequena(self):
        self.assertIn(publicar.AVISO, niveis(self.conf(largura=720, altura=1280)))
        self.assertIn(publicar.FALHOU, niveis(self.conf(largura=540, altura=960)))


class TestTexto(unittest.TestCase):
    def test_hashtags_e_tamanho(self):
        self.assertIn(publicar.AVISO, niveis(publicar.conferir_texto("oi " + " ".join(f"#a{i}" for i in range(8)), None, LIM)))
        self.assertIn(publicar.FALHOU, niveis(publicar.conferir_texto("oi " + " ".join(f"#a{i}" for i in range(31)), None, LIM)))
        self.assertIn(publicar.FALHOU, niveis(publicar.conferir_texto("x" * 2201, None, LIM)))
        self.assertIn(publicar.FALHOU, niveis(publicar.conferir_texto("  ", None, LIM)))
        self.assertEqual(set(niveis(publicar.conferir_texto("Um texto curto. #marketing", None, LIM))), {publicar.OK})

    def test_numero_que_nao_foi_falado(self):
        falados = publicar.numeros_falados([{"p": "cinco", "i": 0, "f": 1}, {"p": "clientes", "i": 1, "f": 2},
                                            {"p": "1.500", "i": 2, "f": 3}])
        self.assertEqual(falados, {"5", "1500"})
        r = publicar.conferir_texto("Você perde 30 clientes", falados, LIM)
        self.assertTrue(any(n == publicar.AVISO and "30" in t for n, t in r))
        r = publicar.conferir_texto("Você perde 5 clientes de 1.500 por mês", falados, LIM)
        self.assertEqual(set(niveis(r)), {publicar.OK})

    def test_numero_em_hashtag_nao_conta(self):
        self.assertEqual(publicar.nao_falados("bom #2026", set()), [])

    def test_titulo(self):
        self.assertIn(publicar.AVISO, niveis(publicar.conferir_titulo("um dois três quatro cinco seis sete oito nove", None, LIM)))
        self.assertIn(publicar.FALHOU, niveis(publicar.conferir_titulo(" ".join(["a"] * 15), None, LIM)))
        self.assertEqual(set(niveis(publicar.conferir_titulo("Você perde *5 clientes*", {"5"}, LIM))), {publicar.OK})


class TestLegenda(unittest.TestCase):
    def test_legenda_padrao_passa(self):
        blocos = [{"inicio": 1.0, "fim": 2.0, "texto": "oi"}, {"inicio": 3.0, "fim": 4.0, "texto": "tchau", "y": 1459}]
        self.assertNotIn(publicar.FALHOU, niveis(publicar.conferir_legenda(blocos, ESTILO, LIM)))

    def test_legenda_perto_da_borda_falha(self):
        blocos = [{"inicio": 5.0, "fim": 6.0, "texto": "baixo demais", "y": 1800}]
        self.assertIn(publicar.FALHOU, niveis(publicar.conferir_legenda(blocos, ESTILO, LIM)))
        blocos = [{"inicio": 5.0, "fim": 6.0, "texto": "alto demais", "y": 150}]
        self.assertIn(publicar.FALHOU, niveis(publicar.conferir_legenda(blocos, ESTILO, LIM)))


class RostosFalso:
    def __init__(self, f):
        self.f = f

    def em(self, t):
        return self.f(t)


def rosto(w=0.4, cx=0.5, achou=True):
    return {"cx": cx * 1080, "cy": 700, "w": w * 1080, "h": w * 1080 * 1.3, "olhos": 650, "boca": 780, "achou": achou}


class TestCapa(unittest.TestCase):
    def test_prefere_rosto_grande_centrado_em_pausa(self):
        bom = publicar.nota_geometrica(rosto(0.4, 0.5), 1080, True)
        pequeno = publicar.nota_geometrica(rosto(0.1, 0.5), 1080, True)
        torto = publicar.nota_geometrica(rosto(0.4, 0.9), 1080, True)
        falando = publicar.nota_geometrica(rosto(0.4, 0.5), 1080, False)
        self.assertGreater(bom, pequeno)
        self.assertGreater(bom, torto)
        self.assertGreater(bom, falando)
        self.assertIsNone(publicar.nota_geometrica(rosto(achou=False), 1080, True))
        self.assertIsNone(publicar.nota_geometrica(None, 1080, True))

    def test_candidatos_descartam_emenda_e_sem_rosto(self):
        rostos = RostosFalso(lambda t: rosto(achou=not 4.0 <= t < 6.0))
        c = publicar.candidatos_geometricos(rostos, 12.0, [8.0], [], 1080)
        ts = [x["t"] for x in c]
        self.assertTrue(all(not (4.0 <= t < 6.0) for t in ts))
        self.assertTrue(all(abs(t - 8.0) >= 0.3 for t in ts))
        self.assertTrue(all(0.3 <= t <= 11.7 for t in ts))

    def test_escolhidos_ficam_longe_uns_dos_outros(self):
        cands = [{"t": t / 2, "nota": 1 - t / 100} for t in range(0, 60)]
        top = publicar.escolher(cands, "nota", 4)
        self.assertEqual(len(top), 4)
        ts = sorted(c["t"] for c in top)
        self.assertTrue(all(b - a >= publicar.SEPARACAO_CAPAS for a, b in zip(ts, ts[1:])))

    def test_zona_do_titulo(self):
        z = publicar.zona_titulo(rosto(0.4), 1080, 1920, LIM)
        self.assertIsNotNone(z)
        self.assertGreaterEqual(z[0], 300)           # dentro do corte 3:4 (240 + 60)
        self.assertLessEqual(z[1], 1920 - 300)
        self.assertGreaterEqual(z[1] - z[0], 260)
        self.assertLessEqual(z[1] - z[0], publicar.ALTURA_MAXIMA_TITULO + 1e-6)

    def test_zona_escolhe_o_lado_livre_e_recusa_sem_espaco(self):
        alto = {**rosto(0.4), "cy": 450}              # rosto no topo: o título vai embaixo
        z = publicar.zona_titulo(alto, 1080, 1920, LIM)
        from rosto import zona_protegida
        self.assertGreater(z[0], zona_protegida(alto)[3])
        baixo = {**rosto(0.4), "cy": 1250}            # rosto embaixo: o título vai em cima
        z = publicar.zona_titulo(baixo, 1080, 1920, LIM)
        self.assertLess(z[1], zona_protegida(baixo)[1])
        enorme = {**rosto(0.9), "cy": 960, "h": 1500}
        self.assertIsNone(publicar.zona_titulo(enorme, 1080, 1920, LIM))

    def test_capa_desenhada_no_navegador(self):
        import cv2
        fundo = np.zeros((1920, 1080, 3), np.uint8)
        fundo[:] = (90, 70, 50)
        cv2.circle(fundo, (540, 800), 220, (170, 190, 220), -1)
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "base.png"
            cv2.imwrite(str(base), fundo)
            try:
                jpg = publicar.desenhar_capa(base, "Você perde *5 clientes* por mês", 1080, 1920, (1100, 1560))
            except SystemExit:
                self.skipTest("sem navegador para desenhar a capa")
            capa = Path(d) / "capa.jpg"
            capa.write_bytes(jpg)
            img = cv2.imread(str(capa))
            self.assertEqual(img.shape[:2], (1920, 1080))
            # há texto claro na faixa do título e nada claro demais acima dela
            faixa = img[1100:1560]
            self.assertGreater(int((faixa.min(axis=2) > 200).sum()), 2000)
            grade = Path(d) / "grade.jpg"
            publicar.grade_do_perfil(capa, grade)
            g = cv2.imread(str(grade))
            self.assertEqual(g.shape[0], 960)
            self.assertGreater(g.shape[1], 540)


class TestPacote(unittest.TestCase):
    def test_pacote_nao_sobrescreve_e_nao_monta_com_falha(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            video = pasta / "tema-v001.mp4"
            video.write_bytes(b"x")
            capa, texto = pasta / "capa-v001.jpg", pasta / "texto.md"
            capa.write_bytes(b"x")
            texto.write_text("Um texto. #a", encoding="utf-8")
            ok = [("Vídeo", publicar.OK, "tudo certo"), ("Texto do post", publicar.AVISO, "só um aviso")]
            original = publicar.comando_conferir
            publicar.comando_conferir = lambda *a, **k: ok
            try:
                publicar.comando_pacote(pasta, video, texto, capa, False)
                publicar.comando_pacote(pasta, video, texto, capa, False)
                self.assertTrue((pasta / "publicacao-tema-v001" / "capa.jpg").exists())
                self.assertTrue((pasta / "publicacao-tema-v001-2" / "conferencia.md").exists())
                publicar.comando_conferir = lambda *a, **k: [("Vídeo", publicar.FALHOU, "sem som")]
                with self.assertRaises(SystemExit):
                    publicar.comando_pacote(pasta, video, texto, capa, False)
                self.assertFalse((pasta / "publicacao-tema-v001-3").exists())
                publicar.comando_pacote(pasta, video, texto, capa, True)
                self.assertTrue((pasta / "publicacao-tema-v001-3").exists())
            finally:
                publicar.comando_conferir = original


if __name__ == "__main__":
    unittest.main()
