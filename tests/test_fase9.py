"""Testes da Fase 9 (gancho e olhar) com dados sintéticos: não precisam de vídeo nem de ffmpeg.

Rodar na raiz do projeto: .venv/bin/python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "edicao-video-well" / "scripts"))

import gancho  # noqa: E402
import olhar  # noqa: E402


def falar(texto: str, inicio: float, passo: float = 0.3) -> list[dict]:
    """Palavras com tempo, uma a cada `passo` segundos."""
    return [{"p": p, "i": round(inicio + k * passo, 3), "f": round(inicio + k * passo + passo * 0.8, 3)}
            for k, p in enumerate(texto.split())]


def trecho(ws: list[dict], folga: float = 0.2) -> dict:
    return {"video": 0, "inicio": round(ws[0]["i"] - folga, 3), "fim": round(ws[-1]["f"] + folga, 3), "texto": ""}


FRACO = "Oi pessoal, então hoje eu vou falar sobre uma coisa que acontece."
FORTE = "Você nunca perde 5 clientes por mês?"
FECHO = "Me segue para ver mais."


class TestGancho(unittest.TestCase):
    def montar(self, partes: list[tuple[str, float]]):
        """Cada parte vira um trecho; devolve (trechos, palavras por trecho)."""
        pal = [falar(t, i) for t, i in partes]
        return [trecho(p) for p in pal], pal

    def avaliar(self, partes):
        trechos, pal = self.montar(partes)
        dur = sum(t["fim"] - t["inicio"] for t in trechos)
        return gancho.propor(trechos, pal, dur), trechos, pal

    def test_abertura_fraca_tem_nota_baixa_e_forte_tem_alta(self):
        fraco, _, _ = self.avaliar([(FRACO, 0.8), (FORTE, 10.0), (FECHO, 20.0)])
        forte, _, _ = self.avaliar([(FORTE, 0.1), (FRACO, 10.0), (FECHO, 20.0)])
        self.assertLessEqual(fraco["abertura"]["nota"], 2)
        self.assertGreaterEqual(forte["abertura"]["nota"], 4)

    def test_puxar_frase_so_da_frase_inteira_e_nunca_a_ultima(self):
        r, _, _ = self.avaliar([(FRACO, 0.8), (FORTE, 10.0), (FECHO, 20.0)])
        prop = next(p for p in r["propostas"] if p["tipo"] == "puxar_frase")
        textos = [c["texto"] for c in prop["candidatas"]]
        self.assertEqual(textos[0], FORTE)
        self.assertNotIn(FECHO, textos)
        self.assertGreaterEqual(prop["candidatas"][0]["nota"], r["abertura"]["nota_conteudo"] + 2)

    def test_frase_sem_ponto_final_nao_e_candidata(self):
        sem_ponto = FORTE.rstrip("?")
        r, _, _ = self.avaliar([(FRACO, 0.8), (sem_ponto, 10.0), (FECHO, 20.0)])
        self.assertFalse(any(p["tipo"] == "puxar_frase" for p in r["propostas"]))

    def test_comeco_bom_nao_propoe_puxar(self):
        r, _, _ = self.avaliar([(FORTE, 0.1), (FRACO, 10.0), (FECHO, 20.0)])
        self.assertFalse(any(p["tipo"] == "puxar_frase" for p in r["propostas"]))

    def test_saudacao_vira_proposta_de_cortar_abertura(self):
        r, trechos, pal = self.avaliar([("Oi pessoal.", 0.2), (FORTE, 3.0), (FECHO, 12.0)])
        self.assertTrue(any(p["tipo"] == "cortar_abertura" for p in r["propostas"]))
        novos = gancho.cortar_abertura(trechos, pal, gancho.frases_do_corte(trechos, pal))
        self.assertEqual(novos[0]["texto"], FORTE)
        self.assertEqual(len(novos), 2)

    def test_puxar_conserva_o_tempo_e_as_palavras_e_corta_no_silencio(self):
        # uma única tomada com três frases e pausas entre elas
        ws = falar(FRACO, 0.8) + falar(FORTE, 10.0) + falar(FECHO, 20.0)
        trechos, pal = [trecho(ws)], [ws]
        frases = gancho.frases_do_corte(trechos, pal)
        self.assertEqual(len(frases), 3)
        meio = frases[1]
        novos = gancho.puxar_frase(trechos, pal, meio["trecho"], meio["k0"], meio["k1"])
        antes = sum(t["fim"] - t["inicio"] for t in trechos)
        depois = sum(t["fim"] - t["inicio"] for t in novos)
        self.assertAlmostEqual(antes, depois, places=6)
        self.assertEqual(novos[0]["texto"], FORTE)
        palavras_antes = sorted(" ".join(w["p"] for w in ws).split())
        palavras_depois = sorted(" ".join(t["texto"] for t in novos).split())
        self.assertEqual(palavras_antes, palavras_depois)
        # nenhum corte cai dentro de uma palavra
        for t in novos:
            for w in ws:
                self.assertFalse(w["i"] < t["inicio"] < w["f"] or w["i"] < t["fim"] < w["f"])

    def test_puxar_entre_trechos_nao_mexe_nos_outros(self):
        trechos, pal = self.montar([(FRACO, 0.8), (FORTE, 10.0), (FECHO, 20.0)])
        novos = gancho.puxar_frase(trechos, pal, 1, 0, len(pal[1]) - 1)
        self.assertEqual([t["texto"] for t in novos][:1], [FORTE])
        self.assertEqual(len(novos), 3)
        self.assertEqual(novos[1], trechos[0])


def serie_com(trechos_de_desvio: list[tuple[float, float]], total: float = 20.0, inclinacao_normal: float = 0.6,
              extra: float = 0.2):
    """Série de medidas a cada 0,1 s; nos intervalos dados a cabeça fica abaixada."""
    serie = []
    for k in range(int(total / 0.1)):
        t = round(k * 0.1, 3)
        ruido = ((k * 7) % 5 - 2) * 0.004
        baixo = any(a <= t < b for a, b in trechos_de_desvio)
        incl = inclinacao_normal + ruido + (extra if baixo else 0.0)
        # olhos em y=0.40, boca em y=0.60: o nariz fica entre os dois
        serie.append((t, {"olho_d_x": 0.45, "olho_e_x": 0.55, "nariz_x": 0.50, "nariz_y": 0.40 + incl * 0.20,
                          "olhos": 0.40, "boca": 0.60}))
    return serie


class TestOlhar(unittest.TestCase):
    def test_marca_dois_segundos_de_cabeca_baixa(self):
        r = olhar.analisar(serie_com([(5.0, 7.0)]))
        self.assertEqual(len(r["desvios"]), 1)
        d = r["desvios"][0]
        self.assertEqual(d["tipo"], "baixo")
        self.assertAlmostEqual(d["inicio"], 5.0, delta=0.3)
        self.assertAlmostEqual(d["fim"], 7.0, delta=0.3)

    def test_ignora_desvio_curto(self):
        self.assertEqual(olhar.analisar(serie_com([(5.0, 5.8)]))["desvios"], [])

    def test_junta_desvios_separados_por_pouco(self):
        r = olhar.analisar(serie_com([(5.0, 5.9), (6.1, 7.0)]))
        self.assertEqual(len(r["desvios"]), 1)

    def test_nao_junta_desvios_distantes(self):
        r = olhar.analisar(serie_com([(3.0, 4.5), (12.0, 13.5)]))
        self.assertEqual(len(r["desvios"]), 2)

    def test_uma_medida_ruim_nao_marca_nada(self):
        serie = serie_com([])
        serie[50] = (serie[50][0], {**serie[50][1], "nariz_y": 0.70})
        self.assertEqual(olhar.analisar(serie)["desvios"], [])

    def test_cabeca_virada_para_o_lado(self):
        serie = serie_com([])
        for k in range(50, 70):
            t, m = serie[k]
            serie[k] = (t, {**m, "nariz_x": 0.50 + 0.40 * 0.10})   # nariz 40% da distância dos olhos para o lado
        d = olhar.analisar(serie)["desvios"]
        self.assertEqual([x["tipo"] for x in d], ["lado"])

    def test_pouco_rosto_nao_mede(self):
        self.assertIsNone(olhar.analisar(serie_com([], total=1.0))["normal"])


class TestZoomDeDisfarce(unittest.TestCase):
    D = [{"inicio": 5.0, "fim": 7.0, "tipo": "baixo"}]

    def test_cria_bloco_com_o_zoom_pedido(self):
        blocos, usados, pulados = olhar.aplicar_zoom([], self.D, [], 20.0, 1.15)
        self.assertEqual(len(usados), 1)
        self.assertEqual(pulados, [])
        self.assertEqual(blocos[0]["zoom"], 1.15)
        self.assertLessEqual(blocos[0]["inicio"], 5.0)
        self.assertGreaterEqual(blocos[0]["fim"], 7.0)

    def test_pula_trecho_que_cruza_elemento(self):
        blocos, usados, pulados = olhar.aplicar_zoom([], self.D, [(6.0, 8.0)], 20.0, 1.15)
        self.assertEqual((blocos, usados, len(pulados)), ([], [], 1))

    def test_bloco_curto_cresce_ate_o_minimo(self):
        blocos, _, _ = olhar.aplicar_zoom([], [{"inicio": 5.0, "fim": 6.2, "tipo": "baixo"}], [], 20.0, 1.15)
        self.assertGreaterEqual(blocos[0]["fim"] - blocos[0]["inicio"], olhar.BLOCO_MIN - 1e-6)

    def test_corta_o_bloco_vizinho_sem_sobrepor(self):
        antes = [{"inicio": 0.0, "fim": 20.0, "zoom": 1.0, "motivo": "frase"}]
        blocos, _, _ = olhar.aplicar_zoom(antes, self.D, [], 20.0, 1.15)
        for a, b in zip(blocos, blocos[1:]):
            self.assertLessEqual(a["fim"], b["inicio"] + 1e-6)


if __name__ == "__main__":
    unittest.main()
