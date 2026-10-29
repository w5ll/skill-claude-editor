"""Testes da Fase 12 (cenas explicativas). Rodar: .venv/bin/python -m unittest discover -s tests -v"""

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "edicao-video-well" / "scripts"))

import cenas  # noqa: E402
import elementos  # noqa: E402
import som  # noqa: E402

MARCA = json.loads((elementos.PASTA_SKILL / "marca.json").read_text())


def fala(texto: str, inicio: float = 0.0, passo: float = 0.3) -> list[dict]:
    return [{"p": p, "i": round(inicio + k * passo, 3), "f": round(inicio + k * passo + passo * 0.8, 3)}
            for k, p in enumerate(texto.split())]


def juntar(*partes):
    return [w for p in partes for w in p]


LISTA = juntar(fala("Primeiro, defina uma meta clara.", 2.0), fala("Segundo, meça toda semana.", 6.0),
               fala("Terceiro, ajuste o plano.", 10.0))


class TestNumerosFalados(unittest.TestCase):
    def valores(self, texto):
        return cenas.valores_falados(fala(texto))

    def test_por_extenso_com_multiplos(self):
        self.assertEqual(self.valores("foram cento e trinta mil reais"), {130000.0, 130.0})
        self.assertEqual(self.valores("quase dois milhões"), {2e6, 2.0})
        self.assertIn(1000.0, self.valores("custa mil"))
        self.assertIn(21.0, self.valores("tenho vinte e um anos"))

    def test_digitos_e_porcentagem(self):
        self.assertIn(30.0, self.valores("cresceu 30% no ano"))
        self.assertIn(2.5, self.valores("são 2,5 por cento"))
        self.assertEqual(self.valores("pago 5.000 reais"), {5000.0})
        self.assertEqual(self.valores("deram 130 mil"), {130000.0, 130.0})

    def test_numero_lido_para_a_cena(self):
        r = cenas.ler_numero(fala("cento e trinta mil reais"), 0)
        self.assertEqual((r["valor"], r["sufixo"], r["prefixo"], r["total"]), (130.0, " mil", "R$ ", 130000.0))
        r = cenas.ler_numero(fala("dois milhões"), 0)
        self.assertEqual((r["valor"], r["sufixo"]), (2.0, " milhões"))
        r = cenas.ler_numero(fala("trinta por cento"), 0)
        self.assertEqual((r["valor"], r["sufixo"]), (30.0, "%"))
        self.assertIsNone(cenas.ler_numero(fala("casa"), 0))


class TestSugerir(unittest.TestCase):
    def tipos(self, palavras):
        return [p["tipo"] for p in cenas.sugerir(palavras)]

    def test_lista_com_o_tempo_de_cada_passo(self):
        props = [p for p in cenas.sugerir(LISTA) if p["tipo"] == "lista"]
        self.assertEqual(len(props), 1)
        c = props[0]["item"]["cena"]
        self.assertEqual([p["texto"] for p in c["passos"]], ["Defina uma meta clara", "Meça toda semana", "Ajuste o plano"])
        self.assertEqual([p["fala_em"] for p in c["passos"]], [2.0, 6.0, 10.0])
        item = props[0]["item"]
        self.assertAlmostEqual(item["inicio"], 2.0 - cenas.ENTRADA, places=2)
        self.assertGreaterEqual(item["duracao"], 10.0 + cenas.LEITURA - item["inicio"] - 1e-6)

    def test_lista_dita_sem_ordinais_pela_abertura_repetida(self):
        p = fala("Vamos supor que o seu objetivo é aposentar seus pais Seu objetivo é comprar uma casa "
                 "Seu objetivo é ter uma vida desprendida de horários e agendas", 1.0)
        props = [x for x in cenas.sugerir(p) if x["tipo"] == "lista"]
        self.assertEqual(len(props), 1)
        passos = props[0]["item"]["cena"]["passos"]
        self.assertEqual([x["texto"] for x in passos], ["Aposentar seus pais", "Comprar uma casa",
                                                          "Ter uma vida desprendida de horários"])
        self.assertEqual(passos[0]["gatilho"], "aposentar")
        self.assertGreater(passos[1]["fala_em"], passos[0]["fala_em"])
        itens = [props[0]["item"]]
        self.assertEqual(cenas.validar(itens, p), [])           # os gatilhos existem na fala

    def test_frase_comum_repetida_nao_vira_lista(self):
        fala_solta = ("a gente tem que entender e ser disciplinado quando a gente tem vontade ou a gente tem que "
                      "seguir os planos e depois a gente tem que ajustar tudo isso com calma")
        self.assertNotIn("lista", [x["tipo"] for x in cenas.sugerir(fala(fala_solta, 1.0))])

    def test_ordem_sozinha_ou_tempo_nao_e_lista(self):
        self.assertEqual(self.tipos(fala("Primeiro eu fui ao mercado e comprei pão.")), [])
        self.assertNotIn("lista", self.tipos(fala("Eu fiz isso em um segundo e depois voltei. Primeiro eu saí.")))
        self.assertNotIn("lista", self.tipos(juntar(fala("Primeiro, defina a meta.", 1.0), fala("Terceiro, ajuste.", 5.0))))

    def test_antes_e_depois(self):
        p = fala("Antes eu perdia muito tempo com planilhas.", 1.0) + fala("Agora eu uso um painel simples.", 5.0)
        props = [x for x in cenas.sugerir(p) if x["tipo"] == "antes-depois"]
        self.assertEqual(len(props), 1)
        c = props[0]["item"]["cena"]
        self.assertEqual(c["antes"]["texto"], "Eu perdia muito tempo com planilhas")
        self.assertEqual(c["depois"]["texto"], "Eu uso um painel simples")
        self.assertEqual((c["antes"]["fala_em"], c["depois"]["fala_em"]), (1.0, 5.0))
        self.assertEqual(self.tipos(fala("Antes de tudo, respire fundo e comece.")), [])

    def test_de_para_e_numero(self):
        p = fala("Saímos de um milhão para cento e trinta mil reais.", 1.0)
        props = cenas.sugerir(p)
        dp = [x for x in props if x["tipo"] == "de-para"]
        self.assertEqual(len(dp), 1)
        c = dp[0]["item"]["cena"]
        self.assertEqual((c["de"]["valor"], c["de"]["sufixo"]), (1.0, " milhão"))
        self.assertEqual((c["para"]["valor"], c["para"]["sufixo"], c["para"]["prefixo"]), (130.0, " mil", "R$ "))
        self.assertNotIn("numero", [x["tipo"] for x in props])       # os números do de-para não viram cena à parte
        n = [x for x in cenas.sugerir(fala("Foram 30% a mais de clientes.", 1.0)) if x["tipo"] == "numero"]
        self.assertEqual(n[0]["item"]["cena"]["sufixo"], "%")
        self.assertEqual(cenas.sugerir(fala("Eu tenho três dicas para você.")), [])    # contagem pequena não é cena

    def test_no_maximo_dois_numeros(self):
        p = fala("Pago 5 mil reais, depois 30% e depois 20% e mais 10 mil reais.")
        self.assertLessEqual(len([x for x in cenas.sugerir(p) if x["tipo"] == "numero"]), 2)


def item_lista(**kw):
    base = cenas.montar_item("lista", copy.deepcopy(cenas.sugerir(LISTA)[0]["item"]["cena"]))
    base["cena"]["titulo"] = "Três passos"
    base.update(kw)
    return base


class TestValidar(unittest.TestCase):
    def problemas(self, itens, palavras=None):
        return cenas.validar(itens, palavras if palavras is not None else LISTA)

    def test_cena_boa_passa(self):
        self.assertEqual(self.problemas([item_lista()]), [])

    def test_numero_que_nao_foi_falado(self):
        it = cenas.montar_item("numero", {"valor": 50, "prefixo": "", "sufixo": "%", "rotulo": "a mais", "decimais": 0, "fala_em": 3.0})
        falas = fala("cresceu 30% no ano", 2.5)
        self.assertTrue(any("não foi falado" in p for p in self.problemas([it], falas)))
        it["cena"]["valor"] = 30
        self.assertEqual(self.problemas([it], falas), [])

    def test_130_mil_dito_por_extenso(self):
        it = cenas.montar_item("numero", {"valor": 130, "prefixo": "R$ ", "sufixo": " mil", "rotulo": "", "decimais": 0, "fala_em": 3.0})
        self.assertEqual(self.problemas([it], fala("foram cento e trinta mil reais", 2.5)), [])

    def test_gatilho_que_nao_existe(self):
        it = item_lista()
        it["cena"]["passos"][1]["gatilho"] = "quarto"
        self.assertTrue(any("não achei \"quarto\"" in p for p in self.problemas([it])))

    def test_sincronia_e_duracao(self):
        it = item_lista(duracao=5.0)
        self.assertTrue(self.problemas([it]))               # o último passo fica fora da cena
        it = item_lista()
        it["cena"]["passos"][0]["fala_em"] = 1.0
        self.assertTrue(any("ordem" in p for p in self.problemas([it])) or any("fora da cena" in p for p in self.problemas([it])))

    def test_limites(self):
        it = item_lista()
        it["cena"]["passos"] += [{"texto": "x", "gatilho": "", "fala_em": 11.0}] * 3
        self.assertTrue(any("passos" in p for p in self.problemas([it])))
        it = item_lista()
        it["cena"]["passos"][0]["texto"] = "uma frase com mais de seis palavras aqui"
        self.assertTrue(any("mais de 6 palavras" in p for p in self.problemas([it])))
        it = item_lista(modo="tela", duracao=8.0)
        self.assertTrue(any("2 a 6 s" in p for p in self.problemas([it])))

    def test_sobreposicao_com_outro_elemento(self):
        it = item_lista()
        outro = {"elemento": "funil", "inicio": it["inicio"] + 1, "duracao": 2.0, "modo": "sobreposto"}
        self.assertTrue(any("encosta em outro elemento" in p for p in self.problemas([it, outro])))
        longe = {**outro, "inicio": it["inicio"] + it["duracao"] + 2.0}
        self.assertEqual(self.problemas([it, longe]), [])


class TestAplicarEPainel(unittest.TestCase):
    def test_mover_o_inicio_nao_muda_a_sincronia(self):
        it = item_lista()
        a = cenas.cfg_da_cena(it, 950, 500, MARCA)["cena"]["passos"]
        it2 = {**it, "inicio": it["inicio"] - 0.5, "duracao": it["duracao"] + 0.5}
        b = cenas.cfg_da_cena(it2, 950, 500, MARCA)["cena"]["passos"]
        for x, y, p in zip(a, b, it["cena"]["passos"]):
            self.assertAlmostEqual(x["em"] + it["inicio"], p["fala_em"] - cenas.ANTES_DA_FALA, places=2)
            self.assertAlmostEqual(y["em"] + it2["inicio"], p["fala_em"] - cenas.ANTES_DA_FALA, places=2)

    def test_painel_fora_do_rosto(self):
        class Rostos:
            def __init__(self, cy):
                self.cy = cy

            def amostras(self, a, b):
                return [(a, {"cx": 540, "cy": self.cy, "w": 300, "h": 400, "olhos": self.cy - 40, "boca": self.cy + 80})]

        from rosto import zona_protegida
        alto = item_lista()
        self.assertIsNone(cenas.resolver_caixa(alto, 1080, 1920, Rostos(500), None))
        x, y, w, h = alto["caixa_usada"]
        zona = zona_protegida({"cx": 540, "cy": 500, "w": 300, "h": 400})
        self.assertGreater(y, zona[3])
        self.assertLessEqual(y + h, 1920 * cenas.SEGURO_BASE)
        self.assertGreaterEqual(x, 0)
        self.assertLessEqual(x + w, 1080)
        baixo = item_lista()
        self.assertIsNone(cenas.resolver_caixa(baixo, 1080, 1920, Rostos(1200), None))
        self.assertLess(baixo["caixa_usada"][1] + baixo["caixa_usada"][3], zona_protegida({"cx": 540, "cy": 1200, "w": 300, "h": 400})[1])
        grande = item_lista()
        self.assertIn("modo tela", cenas.resolver_caixa(grande, 1080, 1920, Rostos(900), None))
        tela = item_lista(modo="tela", duracao=5.0)
        self.assertIsNone(cenas.resolver_caixa(tela, 1080, 1920, Rostos(900), None))
        self.assertNotIn("caixa_usada", tela)

    def test_altura_do_painel_cresce_com_o_conteudo(self):
        a = item_lista()
        b = copy.deepcopy(a)
        b["cena"]["passos"] = b["cena"]["passos"][:2]
        self.assertGreater(cenas.altura_do_painel(a, 1080), cenas.altura_do_painel(b, 1080))


class TestChaveDoCache(unittest.TestCase):
    def test_elementos_antigos_nao_mudaram(self):
        item = {"elemento": "funil", "modo": "sobreposto", "texto": "", "duracao": 2.0}
        partes = ["funil", "sobreposto", "", 2.0, 1.0, 540, 960, str(Fraction(30, 1)), MARCA["cores"]]
        antigo = hashlib.sha1(json.dumps(partes, sort_keys=True).encode()).hexdigest()[:8]
        self.assertEqual(elementos.pasta_do_item(Path("/x"), 3, item, 540, 960, Fraction(30, 1)).name, f"03_funil_{antigo}")

    def test_cena_muda_a_chave_quando_o_conteudo_ou_o_tempo_mudam(self):
        a = {**item_lista(), "caixa_usada": [0, 0, 950, 500]}
        k = lambda it: elementos.pasta_do_item(Path("/x"), 0, it, 1080, 1920, Fraction(30, 1)).name
        b = copy.deepcopy(a)
        b["cena"]["passos"][0]["texto"] = "Outro texto"
        c = {**a, "inicio": a["inicio"] + 1}
        self.assertEqual(k(a), k(copy.deepcopy(a)))
        self.assertNotEqual(k(a), k(b))
        self.assertNotEqual(k(a), k(c))


class TestSom(unittest.TestCase):
    def test_efeito_na_entrada_e_clique_em_cada_parte(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            (pasta / "elementos.json").write_text(json.dumps({"itens": [item_lista()]}))
            plano = som.planejar(pasta, None, True, 22.0, 6.0, 0.0)
        efs = plano["efeitos"]
        self.assertEqual(efs[0]["som"], "passagem-curta")
        self.assertEqual([e["som"] for e in efs[1:]], ["clique", "clique"])
        self.assertEqual([e["tempo"] for e in efs[1:]], [6.0, 10.0])
        tempos = [e["tempo"] for e in efs]
        self.assertTrue(all(b - a >= som.ESPACO_EFEITOS - 1e-6 for a, b in zip(tempos, tempos[1:])))

    def test_partes_coladas_respeitam_o_espaco_minimo(self):
        it = item_lista()
        it["cena"]["passos"][1]["fala_em"] = it["cena"]["passos"][0]["fala_em"] + 0.5
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            (pasta / "elementos.json").write_text(json.dumps({"itens": [it]}))
            efs = som.planejar(pasta, None, True, 22.0, 6.0, 0.0)["efeitos"]
        tempos = [e["tempo"] for e in efs]
        self.assertTrue(all(b - a >= som.ESPACO_EFEITOS - 1e-6 for a, b in zip(tempos, tempos[1:])))


# ---------- no navegador ----------

def exemplos():
    return {
        "lista": cenas.montar_item("lista", {"titulo": "Três passos", "passos": [
            {"texto": "Defina uma meta clara", "gatilho": "", "fala_em": 1.0},
            {"texto": "Meça toda semana", "gatilho": "", "fala_em": 2.5},
            {"texto": "Ajuste o plano", "gatilho": "", "fala_em": 4.0}]}),
        "antes-depois": cenas.montar_item("antes-depois", {
            "antes": {"texto": "Perdia tempo com planilhas", "fala_em": 1.0},
            "depois": {"texto": "Um painel simples", "fala_em": 3.0}}),
        "numero": cenas.montar_item("numero", {"valor": 1250, "prefixo": "R$ ", "sufixo": "", "rotulo": "por mês",
                                                "decimais": 0, "fala_em": 1.0}),
        "de-para": cenas.montar_item("de-para", {
            "de": {"valor": 1, "prefixo": "R$ ", "sufixo": " milhão", "fala_em": 1.0},
            "para": {"valor": 130, "prefixo": "R$ ", "sufixo": " mil", "fala_em": 2.5}, "rotulo": "de custo", "decimais": 0}),
    }


class TestNoNavegador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.pw = sync_playwright().start()
        try:
            cls.nav = elementos.abrir_navegador(cls.pw)
        except SystemExit:
            cls.pw.stop()
            raise unittest.SkipTest("sem navegador para desenhar as cenas")

    @classmethod
    def tearDownClass(cls):
        cls.nav.close()
        cls.pw.stop()

    def quadro(self, item, modo, t_list):
        import cv2
        item = {**item, "modo": "tela" if modo == "tela" else "sobreposto"}
        largura, altura = 540, 960
        if modo == "tela":
            w, h = largura, altura
        else:
            item["caixa_usada"] = [0, 0, round(largura * 0.88 / 2) * 2, cenas.altura_do_painel(item, largura)]
            w, h = item["caixa_usada"][2], item["caixa_usada"][3]
        pg = self.nav.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        pg.goto((elementos.PASTA_SKILL / "templates" / "cenas.html").resolve().as_uri())
        r = pg.evaluate("cfg => montar(cfg)", cenas.cfg_da_cena(item, w, h, MARCA))
        self.assertFalse(r["estoura"], f"{item['elemento']} {modo}: o conteúdo passa do painel")
        saida = []
        for t in t_list:
            pg.evaluate(f"desenhar({t})")
            png = pg.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": w, "height": h})
            img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED).astype(np.float32)
            saida.append(img)
        pg.close()
        return saida

    def test_cada_parte_so_aparece_depois_do_gatilho(self):
        for tipo, item in exemplos().items():
            for modo in ("painel", "tela"):
                c = cenas.cfg_da_cena({**item, "modo": "sobreposto"}, 100, 100, MARCA)["cena"]
                if tipo == "lista":
                    antes, depois = c["passos"][2]["em"] - 0.15, c["passos"][2]["em"] + 0.6
                elif tipo == "antes-depois":
                    antes, depois = c["depois"]["em"] - 0.3, c["depois"]["em"] + 0.7
                else:
                    antes, depois = c["em"] - 0.15, c["em"] + 1.5
                a, b = self.quadro(item, modo, [antes, depois])
                diferenca = float(np.abs(a - b).mean())
                self.assertGreater(diferenca, 0.4, f"{tipo} em {modo}: nada mudou depois do gatilho")

    def test_o_numero_sobe_ate_o_valor(self):
        import cv2
        item = exemplos()["numero"]
        cfg = cenas.cfg_da_cena({**item, "modo": "sobreposto"}, 100, 100, MARCA)["cena"]
        meio, fim = self.quadro(item, "painel", [cfg["em"] + 0.5, cfg["em"] + 1.6])
        self.assertGreater(float((fim[:, :, 3] > 40).sum()), float((meio[:, :, 3] > 40).sum()) * 0.9)


class TestDesenhar(unittest.TestCase):
    def test_desenhar_gera_o_video_da_cena(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            lista = exemplos()["numero"]
            tela = {**exemplos()["lista"], "modo": "tela", "duracao": 2.0}
            (pasta / "elementos.json").write_text(json.dumps({"itens": [lista, {**tela, "inicio": lista["inicio"] + 20}]}))
            itens = elementos.desenhar(pasta, 540, 960, Fraction(30, 1))
            for it in itens:
                self.assertTrue(Path(it["video"]).exists(), it["elemento"])
            self.assertEqual(itens[1]["modo"], "tela")
            self.assertTrue(itens[0].get("caixa_usada"))


if __name__ == "__main__":
    unittest.main()
