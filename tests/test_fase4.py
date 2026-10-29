"""Testes da Fase 4 (orquestrador). Rodar: .venv/bin/python -m unittest discover -s tests -v

Os scripts reais são trocados por um executor de mentira que só cria os arquivos que cada etapa produziria:
assim os testes cobrem a ordem, os portões, a retomada e a invalidação sem transcrever nem renderizar.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "welldit" / "scripts"))

import editar  # noqa: E402
import serie  # noqa: E402

INSPECAO = {"videos": [{"arquivo": "/x/a.mov", "nome": "a.mov", "duracao": 65.0, "largura": 2160, "altura": 3840, "hdr": True,
                        "audio": {"ruido": {"sugestao": "leve", "diferenca_db": 24.0}, "estouro": {"estouro": "nao"},
                                  "eco": {"eco": "nao"}, "faixas_de_audio": 1}}]}


class Falso:
    """O executor de mentira. Guarda as chamadas e cria os arquivos de cada script."""

    def __init__(self, fatos_pendentes: int = 0, falha: str | None = None):
        self.chamadas: list[list[str]] = []
        self.fatos_pendentes = fatos_pendentes
        self.falha = falha

    def pasta(self, argv):
        return Path(argv[argv.index("--pasta") + 1])

    def __call__(self, argv, log):
        self.chamadas.append(argv)
        script, p = argv[0], self.pasta(argv)
        if script == self.falha:
            return 1, "erro: de mentira"
        escreve = lambda nome, dados: (p / nome).write_text(json.dumps(dados), encoding="utf-8")
        if script == "inspecionar.py":
            escreve("inspecao.json", INSPECAO)
            escreve("perfil.json", {"perfil": "arven"})
        elif script == "transcrever.py":
            (p / "transcricoes").mkdir(exist_ok=True)
        elif script == "propor_cortes.py":
            escreve("cortes.json", {"duracao_final": 40.0, "trechos": [], "videos": []})
        elif script == "fatos.py":
            itens = [{"gravidade": "alta", "status": "pendente", "id": k} for k in range(self.fatos_pendentes)]
            escreve("fatos.json", {"itens": itens})
        elif script == "rosto.py":
            escreve("rosto.json", {})
        elif script == "gancho.py":
            escreve("gancho.json", {"propostas": []})
        elif script == "olhar.py":
            escreve("olhar.json", {"desvios": []})
        elif script == "elementos.py" and argv[1] == "sugerir":
            escreve("elementos.json", {"itens": []})
        elif script == "cenas.py":
            escreve("cenas-sugeridas.json", {"propostas": []})
        elif script == "camera.py":
            escreve("camera.json", {"blocos": []})
        elif script == "legendas.py":
            escreve("legendas.json", {"blocos": []})
        elif script == "som.py":
            escreve("som.json", {"efeitos": []})
        elif script == "renderizar.py":
            nome = "amostra-v001.mp4" if "--amostra" in argv else f"{p.name}-v001.mp4"
            (p / nome).write_bytes(b"x")
        elif script == "conferir.py":
            escreve(Path(argv[argv.index("--video") + 1]).with_suffix(".conferencia.json").name, {"aprovado": True})
        return 0, "ok  feito (de mentira)"

    def scripts(self):
        return [c[0] for c in self.chamadas]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.video = self.dir / "a.mov"
        self.video.write_bytes(b"video")
        self.saida = []

    def tearDown(self):
        self.tmp.cleanup()

    def novo(self, **kw):
        return editar.novo([self.video], kw.get("serie"), None, kw.get("tema", "teste"), base=self.dir / "saida")

    def rodar(self, pasta, falso):
        return editar.proximo(pasta, falso, self.saida.append)

    def aprovar_tudo_ate(self, pasta, falso, ate: str):
        """Roda e aprova cada portão até chegar no portão `ate` (que fica aberto)."""
        for _ in range(12):
            r = self.rodar(pasta, falso)
            t = editar.carregar(pasta)
            if r != "portao" or t["portao"]["nome"] == ate:
                return r
            editar.aprovar(pasta, None, "A,C" if t["portao"]["nome"] == "cartao" else None)
        self.fail("portões demais")


class TestGrafo(unittest.TestCase):
    def test_dependencias_vem_antes(self):
        vistos = set()
        for e in editar.ETAPAS:
            self.assertTrue(set(e.depende) <= vistos, e.nome)
            vistos.add(e.nome)
        self.assertEqual(len(editar.POR_NOME), len(editar.ETAPAS))

    def test_novo_nunca_sobrescreve(self):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "a.mov"
            v.write_bytes(b"x")
            a = editar.novo([v], None, None, "tema", base=Path(d) / "saida")
            b = editar.novo([v], None, None, "tema", base=Path(d) / "saida")
            self.assertNotEqual(a, b)
            self.assertTrue(b.name.endswith("-2"))


class TestPortoes(Base):
    def test_para_no_cartao_e_so_roda_a_inspecao(self):
        pasta, falso = self.novo(), Falso()
        self.assertEqual(self.rodar(pasta, falso), "portao")
        self.assertEqual(falso.scripts(), ["inspecionar.py"])
        self.assertEqual(editar.carregar(pasta)["portao"]["nome"], "cartao")
        self.rodar(pasta, falso)                       # com o portão aberto, não passa
        self.assertEqual(falso.scripts(), ["inspecionar.py"])

    def test_aprovar_recusa_pendencia_sem_resposta(self):
        pasta, falso = self.novo(), Falso()
        self.rodar(pasta, falso)
        antes = editar.texto_do_cartao(editar.carregar(pasta), INSPECAO)
        for resposta in ("", "A", "A,B", "C"):
            with self.assertRaises(SystemExit, msg=resposta):
                editar.aprovar(pasta, None, resposta)
        self.assertEqual(editar.carregar(pasta)["portao"]["nome"], "cartao")
        self.assertEqual(editar.texto_do_cartao(editar.carregar(pasta), INSPECAO), antes)    # tentativa incompleta não muda o cartão
        editar.aprovar(pasta, None, "A,C")
        t = editar.carregar(pasta)
        self.assertEqual((t["escolhas"]["hdr"], t["escolhas"]["ruido"]), ("sdr", "leve"))
        self.assertIsNone(t["portao"])
        self.assertEqual(t["aprovacoes"][0]["portao"], "cartao")

    def test_hdr_mantido_nao_combina_com_zoom(self):
        pasta, falso = self.novo(), Falso()
        self.rodar(pasta, falso)
        editar.ajustar(pasta, "camera=leve")
        with self.assertRaises(SystemExit):
            editar.aprovar(pasta, None, "B,C")

    def test_pedido_do_portao_de_julgamento(self):
        pasta, falso = self.novo(), Falso()
        self.aprovar_tudo_ate(pasta, falso, "cortes")
        pedido = json.loads((pasta / "pedidos" / "cortes.json").read_text())
        self.assertEqual(pedido["tipo"], "julgamento")
        self.assertIn("cortes.json", pedido["arquivos"])
        self.assertIn("respostas/cortes.json", pedido["resposta_esperada"]["arquivo"])

    def test_resposta_que_nao_aprova_trava(self):
        pasta, falso = self.novo(), Falso()
        self.aprovar_tudo_ate(pasta, falso, "cortes")
        (pasta / "respostas").mkdir()
        (pasta / "respostas" / "cortes.json").write_text(json.dumps({"aprovado": False, "notas": "falta o fecho"}))
        with self.assertRaises(SystemExit):
            editar.aprovar(pasta, "cortes", None)
        (pasta / "respostas" / "cortes.json").write_text(json.dumps({"aprovado": True}))
        self.assertEqual(editar.aprovar(pasta, "cortes", None), "cortes")

    def test_portao_de_fatos_so_com_ponto_alto_pendente(self):
        pasta, falso = self.novo(), Falso(fatos_pendentes=2)
        self.assertEqual(self.aprovar_tudo_ate(pasta, falso, "fatos"), "portao")
        self.assertEqual(editar.carregar(pasta)["portao"]["nome"], "fatos")
        limpa, falso2 = self.novo(tema="outro"), Falso(fatos_pendentes=0)
        self.aprovar_tudo_ate(limpa, falso2, "elementos")
        self.assertEqual(editar.carregar(limpa)["portao"]["nome"], "elementos")     # passou direto pelos fatos


class TestFluxoCompleto(Base):
    def completo(self):
        pasta, falso = self.novo(), Falso()
        self.assertEqual(self.aprovar_tudo_ate(pasta, falso, "nenhum"), "fim")
        return pasta, falso

    def test_vai_do_bruto_ate_o_fim_na_ordem(self):
        pasta, falso = self.completo()
        ordem = [s for s in falso.scripts()]
        esperado = ["inspecionar.py", "transcrever.py", "propor_cortes.py", "fatos.py", "rosto.py", "gancho.py", "olhar.py",
                    "elementos.py", "cenas.py", "legendas.py", "renderizar.py", "renderizar.py", "conferir.py"]
        self.assertEqual(ordem, esperado)         # câmera e som pulados (padrão: sem zoom, sem música)
        t = editar.carregar(pasta)
        self.assertEqual(editar.estado_json(t, pasta)["etapas"]["camera"], "pulada")
        self.assertEqual(editar.estado_json(t, pasta)["etapas"]["entrega"], "feita")

    def test_a_amostra_leva_as_escolhas_do_cartao(self):
        pasta, falso = self.completo()
        amostra = next(c for c in falso.chamadas if c[0] == "renderizar.py" and "--amostra" in c)
        for esperado in ("--hdr", "sdr", "--ruido", "leve", "--volume", "-14.0"):
            self.assertIn(esperado, amostra)
        i = amostra.index("--amostra")
        self.assertLessEqual(float(amostra[i + 2]) - float(amostra[i + 1]), 12.0)

    def test_nada_a_fazer_quando_nada_mudou(self):
        pasta, falso = self.completo()
        antes = len(falso.chamadas)
        self.assertEqual(self.rodar(pasta, falso), "fim")
        self.assertEqual(len(falso.chamadas), antes)

    def test_amostra_aprovada_pela_pessoa_abre_portao(self):
        pasta, falso = self.novo(), Falso()
        self.rodar(pasta, falso)
        editar.ajustar(pasta, "amostra=aprovar")
        self.assertEqual(self.aprovar_tudo_ate(pasta, falso, "amostra"), "portao")
        self.assertNotIn("conferir.py", falso.scripts())          # espera a aprovação da amostra antes do vídeo inteiro
        editar.aprovar(pasta, "amostra", None)
        self.assertEqual(self.rodar(pasta, falso), "fim")

    def test_falha_para_e_mostra_o_motivo(self):
        pasta, falso = self.novo(), Falso(falha="rosto.py")
        self.assertEqual(self.aprovar_tudo_ate(pasta, falso, "nenhum"), "falhou")
        t = editar.carregar(pasta)
        self.assertEqual(t["etapas"]["rosto"]["estado"], "falhou")
        self.assertTrue(any("rosto" in l and "falhou" in l for l in self.saida))
        melhor = Falso()
        self.assertEqual(self.aprovar_tudo_ate(pasta, melhor, "nenhum"), "fim")
        self.assertEqual(melhor.scripts()[0], "rosto.py")           # retoma da que falhou


class TestRetomadaEInvalidacao(Base):
    def test_etapa_interrompida_e_refeita_e_so_ela(self):
        pasta, falso = self.novo(), Falso()
        self.aprovar_tudo_ate(pasta, falso, "nenhum")
        t = editar.carregar(pasta)
        t["etapas"]["rosto"] = {"estado": "rodando", "pid": 99999999}
        editar.salvar(pasta, t)
        self.assertEqual(editar.situacao(editar.carregar(pasta), editar.POR_NOME["rosto"], pasta), "interrompida")
        novo = Falso()
        self.rodar(pasta, novo)
        self.assertEqual(novo.scripts()[0], "rosto.py")

    def test_ajustar_refaz_so_o_que_depende(self):
        pasta, falso = self.novo(), Falso()
        self.aprovar_tudo_ate(pasta, falso, "nenhum")
        refeitas = editar.ajustar(pasta, "legenda.palavras=2")
        self.assertEqual(refeitas, ["legenda", "amostra"])
        novo = Falso()
        self.assertEqual(self.aprovar_tudo_ate(pasta, novo, "nenhum"), "fim")
        self.assertEqual(novo.scripts(), ["legendas.py", "renderizar.py", "renderizar.py", "conferir.py"])
        self.assertIn("2", novo.chamadas[0])                         # --palavras 2

    def test_mudar_os_cortes_refaz_tudo_que_vem_depois(self):
        pasta, falso = self.novo(), Falso()
        self.aprovar_tudo_ate(pasta, falso, "nenhum")
        (pasta / "cortes.json").write_text(json.dumps({"duracao_final": 35.0, "trechos": [], "videos": []}))   # revisão manual
        t = editar.carregar(pasta)
        situacoes = editar.estado_json(t, pasta)["etapas"]
        self.assertEqual(situacoes["transcrever"], "feita")
        self.assertEqual(situacoes["cortes"], "feita")               # a revisão é entrada das seguintes, não invalida a própria etapa
        for nome in ("fatos", "rosto", "gancho_olhar", "elementos", "legenda", "amostra"):
            self.assertEqual(situacoes[nome], "desatualizada", nome)

    def test_refazer_uma_etapa_refaz_as_seguintes(self):
        pasta, falso = self.novo(), Falso()
        self.aprovar_tudo_ate(pasta, falso, "nenhum")
        editar.refazer(pasta, "rosto")
        novo = Falso()
        self.aprovar_tudo_ate(pasta, novo, "nenhum")
        self.assertEqual(novo.scripts()[:2], ["rosto.py", "gancho.py"])
        self.assertNotIn("transcrever.py", novo.scripts())
        self.assertNotIn("propor_cortes.py", novo.scripts())

    def test_etapa_pulada_volta_quando_a_escolha_muda(self):
        pasta, falso = self.novo(), Falso()
        self.aprovar_tudo_ate(pasta, falso, "nenhum")
        editar.ajustar(pasta, "camera=leve")
        t = editar.carregar(pasta)
        self.assertEqual(editar.situacao(t, editar.POR_NOME["camera"], pasta), "pendente")
        novo = Falso()
        self.aprovar_tudo_ate(pasta, novo, "nenhum")
        self.assertIn("camera.py", novo.scripts())
        self.assertIn("leve", next(c for c in novo.chamadas if c[0] == "camera.py"))

    def test_ajustar_escolha_desconhecida_recusa(self):
        pasta = self.novo()
        with self.assertRaises(SystemExit):
            editar.ajustar(pasta, "inventada=1")
        with self.assertRaises(SystemExit):
            editar.ajustar(pasta, "semigual")


class TestSaidaCurta(Base):
    def test_cada_etapa_imprime_uma_linha_curta(self):
        pasta, falso = self.novo(), Falso()
        self.aprovar_tudo_ate(pasta, falso, "nenhum")
        self.assertTrue(all(len(l) <= 300 and "\n" not in l for l in self.saida))
        self.saida.clear()
        pasta2, falso2 = self.novo(tema="outra"), Falso()
        self.rodar(pasta2, falso2)
        self.assertLessEqual(len(self.saida), 2)           # a inspeção e o portão do cartão

    def test_estado_cabe_em_20_linhas(self):
        pasta, falso = self.novo(), Falso()
        self.aprovar_tudo_ate(pasta, falso, "cortes")
        linhas = editar.linhas_do_estado(editar.carregar(pasta), pasta)
        self.assertLessEqual(len(linhas), 20)
        self.assertTrue(any("⏸" in l for l in linhas))
        j = editar.estado_json(editar.carregar(pasta), pasta)
        self.assertLess(len(json.dumps(j)), 1500)
        self.assertEqual(j["portao"]["nome"], "cortes")

    def test_estado_nao_deixa_arquivo_temporario(self):
        pasta, falso = self.novo(), Falso()
        self.rodar(pasta, falso)
        self.assertEqual([p.name for p in pasta.glob(".*.tmp")], [])


class TestSkillCurto(unittest.TestCase):
    RAIZ = Path(__file__).resolve().parent.parent / "skill" / "welldit"

    def test_skill_md_nao_volta_a_crescer(self):
        tamanho = (self.RAIZ / "SKILL.md").stat().st_size
        self.assertLess(tamanho, 10_000, f"SKILL.md com {tamanho} bytes: mova o detalhe para referencias/")

    def test_referencias_citadas_existem(self):
        import re
        texto = (self.RAIZ / "SKILL.md").read_text(encoding="utf-8")
        for nome in set(re.findall(r"`([a-z0-9-]+\.md)`", texto)):
            achou = list((self.RAIZ / "referencias").glob(nome)) or list((self.RAIZ / "perfis").glob(nome))
            self.assertTrue(achou, f"{nome} está no SKILL.md mas não existe")
        for script in set(re.findall(r"scripts/([a-z_]+\.py)", texto)):
            self.assertTrue((self.RAIZ / "scripts" / script).exists(), script)

    def test_modelo_reels_padrao_e_valido(self):
        s = serie.carregar.__globals__["ler_json"](self.RAIZ.parent.parent / "series" / "reels-padrao.json")
        self.assertEqual(serie.validar(s), [])
        esc, org = editar.escolhas_da_serie(s)
        self.assertEqual((esc["ritmo"], esc["camera"], esc["formato"]), ("dinamico", "leve", "9:16@1080"))


class TestCartaoESerie(Base):
    def setUp(self):
        super().setUp()
        self.series = self.dir / "series"
        self.series.mkdir()
        (self.series / "calma.json").write_text(json.dumps({
            "nome": "Calma", "ritmo": "dinamico", "formato": "9:16@1080", "camera": {"zoom": "leve"},
            "som": {"musica": "calmo", "efeitos": True, "volume": -16},
            "elementos": {"proibidos": ["cadeado"], "intervalo": 8}, "ruido": "leve"}))
        self.original = serie.PASTA_SERIES
        serie.PASTA_SERIES = self.series

    def tearDown(self):
        serie.PASTA_SERIES = self.original
        super().tearDown()

    def test_escolhas_vem_da_serie_e_o_resto_do_padrao(self):
        pasta = self.novo(serie="calma")
        t = editar.carregar(pasta)
        e = t["escolhas"]
        self.assertEqual((e["ritmo"], e["formato"], e["camera"], e["volume"], e["ruido"]), ("dinamico", "9:16@1080", "leve", -16, "leve"))
        self.assertEqual(e["som"]["musica"], "calmo")
        self.assertEqual(e["legenda"]["palavras"], 3)               # padrão
        self.assertEqual(t["origens"]["ritmo"], "serie")
        self.assertTrue((pasta / "serie.json").exists())

    def test_cartao_mostra_origem_pendencias_e_letras(self):
        pasta = self.novo(serie="calma")
        texto = editar.texto_do_cartao(editar.carregar(pasta), INSPECAO)
        self.assertIn("da série", texto)
        self.assertIn("**A)**", texto)
        self.assertIn("recomendado", texto)
        self.assertNotIn("redução de ruído", texto)                 # a série já definiu o ruído: sem pendência
        self.assertIn("zoom de ênfase leve", texto)
        self.assertIn("reduzido de 2160 para 1080", editar.texto_do_cartao({**editar.carregar(pasta), "escolhas": {**editar.carregar(pasta)["escolhas"], "formato": "original"}}, INSPECAO))

    def test_comandos_levam_os_parametros_da_serie(self):
        pasta, falso = self.novo(serie="calma"), Falso()
        self.aprovar_tudo_ate(pasta, falso, "nenhum")
        por = {c[0]: c for c in falso.chamadas}
        self.assertIn("dinamico", por["propor_cortes.py"])
        self.assertIn("calmo", por["som.py"])
        self.assertIn("--efeitos", por["som.py"])
        self.assertIn("serie.py", falso.scripts())                  # filtra os elementos proibidos
        self.assertIn("8", next(c for c in falso.chamadas if c[0] == "elementos.py"))

    def test_serie_invalida_recusa(self):
        (self.series / "ruim.json").write_text(json.dumps({"ritmo": "rapido"}))
        with self.assertRaises(SystemExit):
            self.novo(serie="ruim")


if __name__ == "__main__":
    unittest.main()
