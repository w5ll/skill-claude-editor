"""Testes da Fase 11 (série, fatos e imagens de apoio). Rodar: .venv/bin/python -m unittest discover -s tests -v"""

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

import elementos  # noqa: E402
import fatos  # noqa: E402
import imagens  # noqa: E402
import serie  # noqa: E402

MODELO = json.loads((Path(__file__).resolve().parent.parent / "series" / "_modelo.json").read_text(encoding="utf-8"))


# ---------- série ----------

class TestSerie(unittest.TestCase):
    def test_modelo_passa_e_erros_sao_recusados(self):
        self.assertEqual(serie.validar(MODELO), [])
        for campo, valor in [("ritmo", "rapido"), ("ruido", "muito"), ("formato", "16:10")]:
            s = {**MODELO, campo: valor}
            self.assertTrue(serie.validar(s), campo)
        for s in [{"camera": {"zoom": "enorme"}}, {"som": {"musica": "jazz"}}, {"som": {"volume": -3}},
                  {"elementos": {"proibidos": ["dragao"]}}, {"elementos": {"intervalo": 1}},
                  {"legenda": {"palavras": 9}}, {"publicacao": {"hashtags_fixas": ["semhash"]}}, {"inventado": 1}]:
            self.assertTrue(serie.validar(s), s)

    def test_cartao_marca_a_origem_e_diz_o_que_falta(self):
        s = {"nome": "Planejamento", "ritmo": "dinamico", "camera": {"zoom": "leve"}}
        linhas = "\n".join(serie.linhas_do_cartao(s))
        self.assertIn("da série Planejamento", linhas)
        self.assertIn("dinâmico", linhas)
        self.assertIn("zoom de ênfase leve", linhas)
        self.assertIn("legenda", serie.abertos(s))
        self.assertNotIn("câmera", serie.abertos(s))

    def test_comandos_trazem_os_parametros(self):
        s = {"ritmo": "dinamico", "formato": "9:16@1080", "camera": {"zoom": "forte"}, "termos": ["Ana", "Beto"],
             "legenda": {"palavras": 2, "maiusculas": True, "destaque": False},
             "som": {"musica": "calmo", "efeitos": True, "volume": -16}, "ruido": "leve"}
        c = "\n".join(serie.comandos(s, "saida/x"))
        for esperado in ["--ritmo dinamico", "--formato 9:16@1080", "--intensidade forte", '--termos "Ana,Beto"',
                         "--palavras 2", "--maiusculas", "--sem-destaque", "--musica calmo", "--efeitos",
                         "--volume -16", "--ruido leve"]:
            self.assertIn(esperado, c)
        sem = "\n".join(serie.comandos({"elementos": {"ligado": False}, "camera": {"zoom": "nenhum"}}, "p"))
        self.assertNotIn("camera.py", sem)
        self.assertNotIn("elementos.py sugerir", sem)
        self.assertIn("--sem-elementos", sem)

    def test_filtra_elementos_proibidos_permitidos_e_gerados(self):
        itens = [{"elemento": "cadeado", "inicio": 1}, {"elemento": "funil", "inicio": 8},
                 {"elemento": "gerado:bussola", "inicio": 15}, {"elemento": "imagem:cafe", "inicio": 22}]
        ficam, saem = serie.filtrar_elementos(itens, {"elementos": {"proibidos": ["cadeado"]}})
        self.assertEqual([i["elemento"] for i in saem], ["cadeado"])
        ficam, saem = serie.filtrar_elementos(itens, {"elementos": {"permitidos": ["funil", "gerado"]}})
        self.assertEqual([i["elemento"] for i in ficam], ["funil", "gerado:bussola"])
        ficam, saem = serie.filtrar_elementos(itens, {"elementos": {"gerados": False, "proibidos": ["imagem"]}})
        self.assertEqual([i["elemento"] for i in ficam], ["cadeado", "funil"])

    def test_texto_exige_hashtags_e_avisos(self):
        s = {"publicacao": {"hashtags_fixas": ["#planejamento"], "avisos_obrigatorios": ["Conteúdo informativo"]}}
        self.assertEqual(serie.faltando_no_texto("Oi. Conteúdo informativo. #Planejamento", s), [])
        falta = serie.faltando_no_texto("Oi, tudo bem?", s)
        self.assertEqual(len(falta), 2)
        self.assertEqual(serie.faltando_no_texto("conteudo   INFORMATIVO #planejamento", s), [])

    def test_nome_da_serie_nao_escapa_da_pasta(self):
        with self.assertRaises(SystemExit):
            serie.caminho("../fora")


# ---------- fatos ----------

def frase(texto, inicio=0.0, passo=0.3):
    return [{"p": p, "i": round(inicio + k * passo, 3), "f": round(inicio + k * passo + passo * 0.8, 3)}
            for k, p in enumerate(texto.split())]


def achar(texto):
    return fatos.achar_na_frase(frase(texto))


def tipos(texto):
    return [(m["tipo"], m["gravidade"]) for m in achar(texto)]


class TestFatos(unittest.TestCase):
    def test_achados_principais(self):
        self.assertIn(("numero", "alta"), tipos("Eu pago cinco mil reais por mês"))
        self.assertIn(("numero", "alta"), tipos("O ganho foi de 30% no ano"))
        self.assertIn(("numero", "alta"), tipos("Foram cento e vinte mil reais"))
        self.assertIn(("data", "alta"), tipos("Isso foi em 2024 mesmo"))
        self.assertIn(("data", "alta"), tipos("Abri em 10 de março de 2023"))
        self.assertIn(("fonte", "alta"), tipos("Segundo uma pesquisa recente, isso funciona"))
        self.assertIn(("fonte", "alta"), tipos("Eu li num estudo que isso muda tudo"))
        self.assertIn(("norma", "alta"), tipos("A lei 13.709 trata disso"))
        self.assertIn(("absoluto", "média"), tipos("Isso sempre funciona"))
        self.assertIn(("comparacao", "média"), tipos("Dobrou o resultado, foi o dobro"))

    def test_o_trecho_marcado_inclui_valor_e_unidade(self):
        m = [x for x in achar("Eu pago cinco mil reais por mês") if x["tipo"] == "numero"][0]
        self.assertEqual(m["trecho"], "cinco mil reais")
        m = [x for x in achar("A lei 13.709 trata disso") if x["tipo"] == "norma"][0]
        self.assertEqual(m["trecho"], "lei 13.709")
        m = [x for x in achar("Foram R$ 5.000 por mês") if x["tipo"] == "numero"][0]
        self.assertTrue(m["trecho"].startswith("R$"))

    def test_nao_marca_o_que_nao_e_fato(self):
        self.assertEqual([t for t in tipos("É o segundo passo do processo") if t[0] == "fonte"], [])
        self.assertEqual([t for t in tipos("Um dia eu comecei") if t[0] == "numero"], [])
        self.assertEqual(tipos("Eu tenho três dicas para você"), [("numero", "baixa")])

    def test_contagem_pequena_e_nome_so_com_tudo(self):
        videos = {0: frase("Eu uso o Instagram e tenho três dicas.")}
        self.assertEqual(fatos.marcar_transcricoes(videos), [])
        tipos_tudo = {i["tipo"] for i in fatos.marcar_transcricoes(videos, tudo=True)}
        self.assertEqual(tipos_tudo, {"numero", "nome"})

    def test_status_fora_do_corte_e_pendentes(self):
        videos = {0: frase("Pago cinco mil reais.", 1.0) + frase("Depois foram 2024 anos.", 20.0)}
        itens = fatos.mesclar(fatos.marcar_transcricoes(videos), [])
        fatos.definir_status(itens, [{"video": 0, "inicio": 0.0, "fim": 10.0}])
        por_status = {i["status"] for i in itens}
        self.assertEqual(por_status, {"pendente", "fora_do_corte"})
        self.assertTrue(all(i["tempo"] < 10 for i in fatos.pendentes(itens)))
        self.assertGreaterEqual(len(fatos.pendentes(itens)), 1)

    def test_marcar_de_novo_conserva_respostas_e_marcas_manuais(self):
        videos = {0: frase("Pago cinco mil reais por mês.", 1.0)}
        itens = fatos.mesclar(fatos.marcar_transcricoes(videos), [])
        fatos.definir_status(itens, None)
        itens[0]["status"], itens[0]["nota"] = "corrigir", "50 mil"
        manual = {"tipo": "manual", "gravidade": "alta", "video": 0, "tempo": 9.0, "frase": "x", "trecho": "x",
                  "motivo": "m", "pergunta": "p", "status": "pendente", "fica": True}
        novos = fatos.mesclar(fatos.marcar_transcricoes(videos), itens + [manual])
        fatos.definir_status(novos, None)
        self.assertEqual(novos[0]["status"], "corrigir")
        self.assertEqual(novos[0]["nota"], "50 mil")
        self.assertTrue(any(i["tipo"] == "manual" for i in novos))
        self.assertEqual([i["id"] for i in novos], list(range(1, len(novos) + 1)))
        self.assertEqual([i["tipo"] for i in fatos.pendentes(novos)], ["manual"])

    def test_bloco_do_cartao_em_portugues(self):
        videos = {0: frase("Pago cinco mil reais por mês. Isso sempre funciona.", 1.0)}
        itens = fatos.mesclar(fatos.marcar_transcricoes(videos), [])
        fatos.definir_status(itens, None)
        texto = fatos.bloco_do_cartao(itens)
        self.assertIn("Conferir antes de editar", texto)
        self.assertIn("confirmo", texto)
        self.assertIn("cinco mil reais", texto)
        self.assertIn("Para olhar", texto)
        self.assertIn("Nada para confirmar", fatos.bloco_do_cartao([]))


# ---------- imagens ----------

def foto(caminho: Path, largura=3000, altura=2000, cor=(60, 120, 180)):
    import cv2
    img = np.zeros((altura, largura, 3), np.uint8)
    img[:] = cor
    cv2.circle(img, (largura // 2, altura // 2), altura // 4, (230, 230, 240), -1)
    cv2.imwrite(str(caminho), img)


class TestImagens(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.lib = self.dir / "imagens"
        self.original = self.dir / "foto.png"
        foto(self.original)

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, **kw):
        base = dict(arquivo=self.original, titulo="Café na mesa", palavras=["cafe", "reunião"], autor="Fulana",
                    licenca="cc0", origem="https://exemplo.org/foto/1", pessoa=False, marca=False, pasta=self.lib)
        base.update(kw)
        return imagens.adicionar(**base)

    def test_adiciona_reduz_e_nao_toca_no_original(self):
        antes = hashlib.sha256(self.original.read_bytes()).hexdigest()
        e = self.add()
        self.assertEqual(max(e["largura"], e["altura"]), imagens.LADO_MAXIMO)
        self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(), antes)
        self.assertTrue((self.lib / e["arquivo"]).exists())
        self.assertEqual(e["sha256"], hashlib.sha256((self.lib / e["arquivo"]).read_bytes()).hexdigest())
        self.assertEqual(e["palavras"], ["cafe", "reuniao"])
        self.assertEqual(self.add()["id"], "cafe-na-mesa-2")

    def test_recusa_licenca_ruim_e_campos_que_faltam(self):
        for lic in ["cc-by-sa", "cc-by-nc", "cc-by-nd", "todos-os-direitos-reservados", "inventada"]:
            with self.assertRaises(SystemExit, msg=lic):
                self.add(licenca=lic)
        with self.assertRaises(SystemExit):
            self.add(licenca="cc-by")                        # sem crédito
        self.add(licenca="cc-by", credito="Foto: Fulana, CC BY 4.0")
        with self.assertRaises(SystemExit):
            self.add(origem="")                              # sem origem
        with self.assertRaises(SystemExit):
            self.add(palavras=[])
        self.add(licenca="propria", origem="", autor="")     # a própria pessoa não precisa de origem
        with self.assertRaises(SystemExit):
            imagens.adicionar(self.dir / "nao-existe.jpg", "x", ["x"], "a", "cc0", "https://a", False, False, pasta=self.lib)
        texto = self.dir / "nota.txt"
        texto.write_text("não sou imagem")
        with self.assertRaises(SystemExit):
            self.add(arquivo=texto)

    def test_verificar_pega_arquivo_trocado_e_avisa_pessoa(self):
        e = self.add(pessoa=True)
        r = imagens.verificar(self.lib)
        self.assertEqual([(n) for _, n, _ in r], ["aviso"])
        foto(self.lib / e["arquivo"], 400, 300, (1, 2, 3))
        self.assertIn("FALHOU", [n for _, n, _ in imagens.verificar(self.lib)])
        with self.assertRaises(SystemExit):
            imagens.carregar_imagem(e["id"], self.lib)      # imagem trocada não pode ser usada

    def test_buscar(self):
        self.add()
        reg = imagens.carregar_registro(self.lib)
        self.assertEqual([i for i, _ in imagens.buscar(reg, ["café"])], ["cafe-na-mesa"])
        self.assertEqual(imagens.buscar(reg, ["foguete"]), [])

    def test_sugerir_respeita_intervalo_e_outros_elementos(self):
        self.add()
        reg = imagens.carregar_registro(self.lib)
        pal = frase("tomo um café agora e depois outro café bem forte e mais um café")
        pal = [{**w, "i": w["i"] * 3, "f": w["f"] * 3} for w in pal]            # espalha no tempo
        todas = imagens.sugerir(pal, reg, [], 60.0)
        tempos = [p["inicio"] for p in todas]
        self.assertTrue(all(b - a >= imagens.INTERVALO - 0.2 for a, b in zip(tempos, tempos[1:])))
        livre = imagens.sugerir(pal, reg, [(tempos[0] - 0.5, tempos[0] + 2.0)], 60.0)
        self.assertTrue(all(abs(p["inicio"] - tempos[0]) >= imagens.INTERVALO for p in livre))
        self.assertEqual(imagens.sugerir(pal, reg, [], 1.0), [])               # não cabe no vídeo

    def test_usar_escreve_o_item_e_recusa_conflito(self):
        e = self.add()
        trabalho = self.dir / "saida"
        trabalho.mkdir()
        item = imagens.usar(trabalho, e["id"], 5.0, 2.0, "sobreposto", "Café", self.lib)
        self.assertEqual(item["elemento"], f"imagem:{e['id']}")
        dados = json.loads((trabalho / "elementos.json").read_text())
        self.assertEqual(len(dados["itens"]), 1)
        with self.assertRaises(SystemExit):
            imagens.usar(trabalho, e["id"], 8.0, 2.0, "tela", "", self.lib)    # a menos de 6 s do outro
        with self.assertRaises(SystemExit):
            imagens.usar(trabalho, e["id"], 30.0, 5.0, "tela", "", self.lib)   # tela fica até 3 s
        imagens.usar(trabalho, e["id"], 30.0, 2.0, "tela", "", self.lib)
        self.assertEqual(len(json.loads((trabalho / "elementos.json").read_text())["itens"]), 2)

    def test_creditos_so_das_usadas(self):
        a = self.add(licenca="cc-by", credito="Foto: Fulana, CC BY 4.0")
        b = self.add(titulo="Outra", palavras=["outra"])
        self.add(titulo="Não usada", palavras=["nada"])
        trabalho = self.dir / "saida"
        trabalho.mkdir()
        (trabalho / "elementos.json").write_text(json.dumps({"itens": [
            {"elemento": f"imagem:{a['id']}", "inicio": 1, "duracao": 2, "modo": "tela"},
            {"elemento": f"imagem:{b['id']}", "inicio": 9, "duracao": 2, "modo": "tela"},
            {"elemento": "funil", "inicio": 20, "duracao": 2, "modo": "sobreposto"}]}))
        registro, obrigatorios = imagens.creditos(trabalho, self.lib)
        self.assertEqual(len(registro), 2)
        self.assertEqual(obrigatorios, ["Foto: Fulana, CC BY 4.0"])
        self.assertFalse(any("Não usada" in r for r in registro))

    def test_chave_do_cache_dos_elementos_antigos_nao_mudou(self):
        pasta, fps = Path("/x"), Fraction(30, 1)
        item = {"elemento": "funil", "modo": "sobreposto", "texto": "", "duracao": 2.0}
        marca = json.loads((elementos.PASTA_SKILL / "marca.json").read_text())["cores"]
        partes = ["funil", "sobreposto", "", 2.0, 1.0, 540, 960, str(fps), marca]
        antigo = hashlib.sha1(json.dumps(partes, sort_keys=True).encode()).hexdigest()[:8]
        self.assertEqual(elementos.pasta_do_item(pasta, 3, item, 540, 960, fps).name, f"03_funil_{antigo}")
        novo = {**item, "elemento": "imagem:cafe"}
        a = elementos.pasta_do_item(pasta, 0, novo, 540, 960, fps, None, "aaa")
        b = elementos.pasta_do_item(pasta, 0, novo, 540, 960, fps, None, "bbb")
        self.assertNotEqual(a, b)

    def test_imagem_vira_video_nos_dois_modos(self):
        e = self.add()
        trabalho = self.dir / "saida"
        trabalho.mkdir()
        (trabalho / "elementos.json").write_text(json.dumps({"itens": [
            {"elemento": f"imagem:{e['id']}", "inicio": 1, "duracao": 1.0, "modo": "sobreposto", "texto": "Um *café*",
             "posicao": "auto"},
            {"elemento": f"imagem:{e['id']}", "inicio": 9, "duracao": 1.0, "modo": "tela", "texto": "", "posicao": "auto"}]}))
        original = imagens.PASTA_IMAGENS
        imagens.PASTA_IMAGENS = self.lib
        try:
            try:
                itens = elementos.desenhar(trabalho, 540, 960, Fraction(30, 1))
            except SystemExit:
                self.skipTest("sem navegador para desenhar")
        finally:
            imagens.PASTA_IMAGENS = original
        for it in itens:
            self.assertTrue(Path(it["video"]).exists(), it["modo"])
        self.assertNotEqual(itens[0]["video"], itens[1]["video"])


if __name__ == "__main__":
    unittest.main()
