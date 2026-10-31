"""Testes da Fase 7 (elementos, zoom e som no painel). Rodar: .venv/bin/python -m unittest discover -s tests -v

A lógica (ajustes.py) é testada sozinha, com arquivos sintéticos; o orquestrador usa o executor de mentira da Fase 4;
a conferência roda de verdade num vídeo de teste (ffmpeg); a API usa o servidor da Fase 5; as prévias usam o
navegador e o ffmpeg de verdade.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
SCRIPTS = Path(__file__).resolve().parent.parent / "skill" / "welldit" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import ambiente  # noqa: E402

import ajustes  # noqa: E402
import editar  # noqa: E402
import elementos  # noqa: E402
import test_fase4  # noqa: E402
import test_fase5  # noqa: E402
import test_fase6  # noqa: E402
from comum import assinatura_dos_cortes  # noqa: E402

BUSSOLA = Path(__file__).resolve().parent.parent / "skill" / "welldit" / "templates" / "exemplos-gerados" / "bussola.svg"


def itens_de_teste():
    return [
        {"elemento": "relogio", "inicio": 0.5, "duracao": 2.0, "modo": "sobreposto", "posicao": "auto", "texto": "*5 minutos*",
         "gatilho": "cinco minutos", "fala_em": 0.6},
        {"elemento": "funil", "inicio": 3.0, "duracao": 2.0, "modo": "sobreposto", "posicao": "auto", "texto": "",
         "gatilho": "funil", "fala_em": 3.1},
    ]


def montar(dir_: Path, itens=None, total=7.05):
    (dir_ / "cortes.json").write_text(json.dumps({"videos": [], "trechos": [], "duracao_final": total}))
    (dir_ / "elementos.json").write_text(json.dumps({"itens": itens if itens is not None else itens_de_teste()}))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def itens(self):
        return json.loads((self.dir / "elementos.json").read_text())["itens"]

    def bytes_(self, nome):
        return (self.dir / nome).read_bytes()

    def historico(self, nome):
        return len(ajustes.historico(self.dir, nome))

    def id(self, k=0):
        return ajustes.id_do_item(self.itens()[k])


# ---------- elementos ----------

class TestElementos(Base):
    def setUp(self):
        super().setUp()
        montar(self.dir)

    def test_o_painel_descreve_cada_item(self):
        d = ajustes.painel_de_elementos(self.dir)
        self.assertEqual([i["nome"] for i in d["itens"]], ["relogio", "funil"])
        self.assertTrue(all(i["editavel"] and i["previa"] for i in d["itens"]))
        self.assertEqual(d["itens"][0]["texto"], "*5 minutos*")
        self.assertIn("furo", d["prontos"])
        self.assertEqual(d["desfazer"], 0)

    def test_tirar_e_desfazer_devolvem_o_arquivo_exato(self):
        antes = self.bytes_("elementos.json")
        ajustes.tirar_elemento(self.dir, self.id(0))
        self.assertEqual([i["elemento"] for i in self.itens()], ["funil"])
        ajustes.tirar_elemento(self.dir, self.id(0))
        self.assertEqual(self.itens(), [])
        self.assertTrue(ajustes.desfazer_elementos(self.dir))
        self.assertTrue(ajustes.desfazer_elementos(self.dir))
        self.assertEqual(self.bytes_("elementos.json"), antes)
        self.assertFalse(ajustes.desfazer_elementos(self.dir))

    def test_trocar_mantem_o_resto_do_item(self):
        ajustes.trocar_elemento(self.dir, self.id(0), "lupa")
        it = self.itens()[0]
        self.assertEqual((it["elemento"], it["inicio"], it["texto"], it["gatilho"]), ("lupa", 0.5, "*5 minutos*", "cinco minutos"))
        self.assertEqual(len(self.itens()), 2)

    def test_pedidos_ruins_nao_mexem_em_nada_nem_deixam_historico(self):
        antes = self.bytes_("elementos.json")
        ruins = [(ajustes.trocar_elemento, (self.id(0), "elemento-que-nao-existe")), (ajustes.trocar_elemento, (self.id(0), "../../x")),
                 (ajustes.trocar_elemento, (self.id(0), 7)), (ajustes.trocar_elemento, (self.id(0), "gerado:nao-esta-no-catalogo")),
                 (ajustes.mudar_rotulo, (self.id(0), "x" * 41)), (ajustes.mudar_rotulo, (self.id(0), "<script>")),
                 (ajustes.mudar_rotulo, (self.id(0), 5)), (ajustes.mudar_tempo, (self.id(0), -1, 2.0)),
                 (ajustes.mudar_tempo, (self.id(0), "a", 2.0)), (ajustes.mudar_tempo, (self.id(0), float("nan"), 2.0)),
                 (ajustes.mudar_tempo, (self.id(0), True, 2.0)), (ajustes.mudar_tempo, (self.id(0), 1.0, 0.5)),
                 (ajustes.mudar_tempo, (self.id(0), 1.0, 9.0)), (ajustes.mudar_tempo, (self.id(0), 2.9, 2.0)),          # bate no funil
                 (ajustes.mudar_tempo, (self.id(0), 6.5, 2.0)),                                                       # passa do fim
                 (ajustes.mudar_modo, (self.id(0), "voando")), (ajustes.mudar_modo, (self.id(0), "sobreposto", "cima")),
                 (ajustes.adicionar_elemento, ("furo", 3.5)), (ajustes.adicionar_elemento, ("furo", 5.5)),
                 (ajustes.adicionar_elemento, ("furo", 0.0, "x")),
                 (ajustes.tirar_elemento, ("furo@9.000",)), (ajustes.tirar_elemento, (None,))]
        for f, args in ruins:
            with self.assertRaises(ajustes.Recusado, msg=f"{f.__name__}{args}"):
                f(self.dir, *args)
        self.assertEqual(self.bytes_("elementos.json"), antes)
        self.assertEqual(self.historico("elementos"), 0)

    def test_rotulo_tempo_e_modo(self):
        ajustes.mudar_rotulo(self.dir, self.id(0), "  *10 minutos*  ")
        self.assertEqual(self.itens()[0]["texto"], "*10 minutos*")
        ajustes.mudar_tempo(self.dir, self.id(0), 0.2, 2.5)
        it = self.itens()[0]
        self.assertEqual((it["inicio"], it["duracao"]), (0.2, 2.5))
        ajustes.mudar_modo(self.dir, ajustes.id_do_item(self.itens()[0]), "tela", "meio")
        it = self.itens()[0]
        self.assertEqual((it["modo"], it["duracao"], it["posicao"]), ("tela", 2.5, "meio"))
        ajustes.mudar_tempo(self.dir, ajustes.id_do_item(it), 0.2, 2.8)
        with self.assertRaises(ajustes.Recusado):                       # tela cheia dura no máximo 3 s
            ajustes.mudar_tempo(self.dir, ajustes.id_do_item(self.itens()[0]), 0.2, 3.5)

    def test_tela_cheia_encurta_o_que_passa_de_3_s(self):
        ajustes.tirar_elemento(self.dir, self.id(1))
        ajustes.mudar_tempo(self.dir, self.id(0), 0.5, 3.8)
        ajustes.mudar_modo(self.dir, self.id(0), "tela")
        self.assertEqual(self.itens()[0]["duracao"], 3.0)

    def test_adicionar_mantem_a_ordem_do_tempo(self):
        montar(self.dir, total=20.0)
        ajustes.adicionar_elemento(self.dir, "furo", 12.0)
        ajustes.adicionar_elemento(self.dir, "alvo", 6.0, "tela")
        self.assertEqual([i["elemento"] for i in self.itens()], ["relogio", "funil", "alvo", "furo"])
        self.assertEqual((self.itens()[2]["modo"], self.itens()[2]["duracao"], self.itens()[3]["posicao"]), ("tela", 1.8, "auto"))
        with self.assertRaises(ajustes.Recusado):
            ajustes.adicionar_elemento(self.dir, "lupa", 19.0)         # 19 + 2 passa de 20
        self.assertEqual(self.historico("elementos"), 2)

    def test_id_velho_e_recusado(self):
        antigo = self.id(0)
        ajustes.mudar_tempo(self.dir, antigo, 1.0, 2.0)
        with self.assertRaises(ajustes.Recusado):
            ajustes.tirar_elemento(self.dir, antigo)
        self.assertEqual(len(self.itens()), 2)

    def test_cena_e_imagem_so_tiram_ou_mudam_de_momento(self):
        itens = itens_de_teste() + [{"elemento": "cena:lista", "inicio": 5.5, "duracao": 1.5, "modo": "sobreposto", "posicao": "auto",
                                     "texto": "", "gatilho": "x", "fala_em": 5.5}]
        montar(self.dir, itens)
        d = ajustes.painel_de_elementos(self.dir)
        cena = d["itens"][2]
        self.assertEqual((cena["tipo"], cena["editavel"], cena["previa"]), ("cena", False, False))
        for f, args in [(ajustes.trocar_elemento, (cena["id"], "furo")), (ajustes.mudar_rotulo, (cena["id"], "x")),
                        (ajustes.mudar_modo, (cena["id"], "tela"))]:
            with self.assertRaises(ajustes.Recusado):
                f(self.dir, *args)
        ajustes.mudar_tempo(self.dir, cena["id"], 5.4, 1.5)
        ajustes.tirar_elemento(self.dir, ajustes.id_do_item(self.itens()[2]))
        self.assertEqual(len(self.itens()), 2)

    def test_desenho_invalido_aparece_com_o_motivo(self):
        (self.dir / "elementos-gerados").mkdir()
        (self.dir / "elementos-gerados" / "ruim.svg").write_text("<text>oi</text>")
        itens = itens_de_teste() + [{"elemento": "gerado:ruim", "svg": "elementos-gerados/ruim.svg", "animacao": "girar", "inicio": 5.5,
                                     "duracao": 1.5, "modo": "sobreposto", "texto": "", "gatilho": "x", "fala_em": 5.5}]
        montar(self.dir, itens)
        g = ajustes.painel_de_elementos(self.dir)["itens"][2]
        self.assertEqual(g["tipo"], "gerado")
        self.assertIn("texto", g["problema"])
        with self.assertRaises(ajustes.Recusado):
            ajustes.promover_elemento(self.dir, g["id"], ["ruim"])

    def test_catalogo_e_promover(self):
        gerados = self.dir / "catalogo-teste"
        gerados.mkdir()
        original = elementos.PASTA_GERADOS
        elementos.PASTA_GERADOS = gerados
        try:
            (self.dir / "elementos-gerados").mkdir()
            shutil.copy(BUSSOLA, self.dir / "elementos-gerados" / "bussola.svg")
            itens = itens_de_teste() + [{"elemento": "gerado:bussola", "svg": "elementos-gerados/bussola.svg", "animacao": "girar",
                                         "parar": True, "ideia": "uma bússola", "inicio": 5.5, "duracao": 1.5, "modo": "sobreposto",
                                         "texto": "", "gatilho": "rumo", "fala_em": 5.5}]
            montar(self.dir, itens)
            g = ajustes.painel_de_elementos(self.dir)["itens"][2]
            self.assertIsNone(g["problema"])
            self.assertFalse(g["no_catalogo"])
            for ruim in ([], ["a"], ["bússola bonita"], "bussol", ["x" * 30], ["ok"] * 9):
                with self.assertRaises(ajustes.Recusado, msg=str(ruim)):
                    ajustes.promover_elemento(self.dir, g["id"], ruim)
            with self.assertRaises(ajustes.Recusado):
                ajustes.promover_elemento(self.dir, self.id(0), ["relogio"])        # elemento pronto não vai para o catálogo
            entrada = ajustes.promover_elemento(self.dir, g["id"], ["bussol", "rumo"])
            self.assertEqual(entrada["nome"], "bussola")
            self.assertTrue((gerados / "bussola.svg").exists())
            self.assertTrue(ajustes.painel_de_elementos(self.dir)["itens"][2]["no_catalogo"])
            # agora dá para trocar um elemento pronto pelo do catálogo, e o desenho vem para a pasta do trabalho
            (self.dir / "elementos-gerados" / "bussola.svg").unlink()
            ajustes.trocar_elemento(self.dir, self.id(0), "gerado:bussola")
            novo = self.itens()[0]
            self.assertEqual((novo["elemento"], novo["animacao"], novo["svg"]), ("gerado:bussola", "girar", "elementos-gerados/bussola.svg"))
            self.assertTrue((self.dir / "elementos-gerados" / "bussola.svg").exists())
            ajustes.trocar_elemento(self.dir, ajustes.id_do_item(novo), "furo")
            self.assertNotIn("svg", self.itens()[0])
        finally:
            elementos.PASTA_GERADOS = original


# ---------- zoom ----------

def camera_de_teste(dir_: Path, blocos=None, inten="normal"):
    blocos = blocos or [{"inicio": 0.0, "fim": 2.9, "zoom": 1.0, "motivo": "frase"},
                        {"inicio": 2.9, "fim": 5.1, "zoom": 1.12, "motivo": "frase"},
                        {"inicio": 5.1, "fim": 7.05, "zoom": 1.25, "motivo": "ênfase: meta"}]
    (dir_ / "camera.json").write_text(json.dumps({"intensidade": inten, "duracao": 7.05, "blocos": blocos}))


class TestZoom(Base):
    def setUp(self):
        super().setUp()
        montar(self.dir)
        camera_de_teste(self.dir)

    def blocos(self):
        return json.loads((self.dir / "camera.json").read_text())["blocos"]

    def test_o_painel_diz_o_nivel_de_cada_bloco(self):
        d = ajustes.painel_de_zoom(self.dir)
        self.assertEqual([b["nivel"] for b in d["blocos"]], ["aberto", "perto", "enfase"])
        self.assertEqual([b["enfase"] for b in d["blocos"]], [False, False, True])
        self.assertTrue(d["planejado"])

    def test_sem_camera_o_painel_diz_que_nao_foi_planejado(self):
        (self.dir / "camera.json").unlink()
        self.assertFalse(ajustes.painel_de_zoom(self.dir)["planejado"])

    def test_mudar_o_nivel_e_desfazer(self):
        antes = self.bytes_("camera.json")
        ajustes.definir_nivel_do_zoom(self.dir, 2, "perto")
        self.assertEqual(self.blocos()[2]["zoom"], 1.12)
        self.assertEqual(self.blocos()[2]["motivo"], "manual: perto")
        self.assertTrue(ajustes.desfazer_zoom(self.dir))
        self.assertEqual(self.bytes_("camera.json"), antes)
        self.assertFalse(ajustes.desfazer_zoom(self.dir))

    def test_tirar_enfase_vira_o_enquadramento_do_vizinho(self):
        ajustes.tirar_enfase(self.dir, 2)
        self.assertEqual(self.blocos()[2]["zoom"], 1.12)
        with self.assertRaises(ajustes.Recusado):
            ajustes.tirar_enfase(self.dir, 0)                           # não é uma ênfase

    def test_pedidos_ruins_nao_mexem_em_nada(self):
        antes = self.bytes_("camera.json")
        for f, args in [(ajustes.definir_nivel_do_zoom, (9, "perto")), (ajustes.definir_nivel_do_zoom, (-1, "perto")),
                        (ajustes.definir_nivel_do_zoom, ("0", "perto")), (ajustes.definir_nivel_do_zoom, (True, "perto")),
                        (ajustes.definir_nivel_do_zoom, (0, "enorme")), (ajustes.definir_nivel_do_zoom, (0, "aberto")),
                        (ajustes.tirar_enfase, (5,))]:
            with self.assertRaises(ajustes.Recusado, msg=f"{f.__name__}{args}"):
                f(self.dir, *args)
        self.assertEqual(self.bytes_("camera.json"), antes)
        self.assertEqual(self.historico("camera"), 0)

    def test_nunca_muda_o_zoom_com_elemento_na_tela(self):
        camera_de_teste(self.dir, [{"inicio": 0.0, "fim": 1.5, "zoom": 1.0, "motivo": "frase"},
                                   {"inicio": 1.5, "fim": 7.05, "zoom": 1.0, "motivo": "frase"}])
        with self.assertRaises(ajustes.Recusado) as e:
            ajustes.definir_nivel_do_zoom(self.dir, 1, "perto")         # o relógio fica na tela de 0,5 s a 2,5 s
        self.assertIn("elemento 3D", str(e.exception))
        self.assertEqual(self.historico("camera"), 0)

    def test_em_cima_de_um_elemento_o_bloco_inteiro_pode_mudar(self):
        ajustes.definir_nivel_do_zoom(self.dir, 0, "perto")             # só o relógio está nesse bloco
        self.assertEqual(self.blocos()[0]["zoom"], 1.12)


# ---------- som ----------

def som_de_teste(dir_: Path):
    (dir_ / "som.json").write_text(json.dumps({
        "musica": {"arquivo": "musica/calmo.mp3", "abaixo_da_voz_db": 22.0, "sobe_na_pausa_db": 6.0, "inicio_na_musica": 0.0,
                   "entra_em": 0.0, "saida_s": 1.5},
        "efeitos": [{"som": "tique-taque", "tempo": 0.65, "ganho_db": 0, "elemento": "relogio", "duracao_max": 2.0},
                    {"som": "passagem", "tempo": 3.15, "ganho_db": 0, "elemento": "funil"}]}))


class TestSom(Base):
    def setUp(self):
        super().setUp()
        som_de_teste(self.dir)

    def plano(self):
        return json.loads((self.dir / "som.json").read_text())

    def test_o_painel_descreve_a_musica_e_os_efeitos(self):
        d = ajustes.painel_de_som(self.dir)
        self.assertEqual(d["musica"]["nome"], "calmo")
        self.assertEqual([e["som"] for e in d["efeitos"]], ["tique-taque", "passagem"])
        self.assertEqual({m["nome"] for m in d["musicas"]}, {"calmo", "animado", "batida"})
        self.assertEqual(len(d["sons"]), 10)

    def test_niveis_ganho_troca_e_remocao(self):
        ajustes.nivel_da_musica(self.dir, 18, 3)
        self.assertEqual((self.plano()["musica"]["abaixo_da_voz_db"], self.plano()["musica"]["sobe_na_pausa_db"]), (18.0, 3.0))
        ajustes.ganho_do_efeito(self.dir, 1, -4.5)
        self.assertEqual(self.plano()["efeitos"][1]["ganho_db"], -4.5)
        ajustes.trocar_som_do_efeito(self.dir, 0, "acerto")
        self.assertNotIn("duracao_max", self.plano()["efeitos"][0])
        ajustes.trocar_som_do_efeito(self.dir, 0, "tique-taque")
        self.assertEqual(self.plano()["efeitos"][0]["duracao_max"], 2.0)
        ajustes.tirar_efeito(self.dir, 0)
        self.assertEqual([e["som"] for e in self.plano()["efeitos"]], ["passagem"])
        for _ in range(5):
            ajustes.desfazer_som(self.dir)
        self.assertFalse(ajustes.desfazer_som(self.dir))
        self.assertEqual(self.plano()["efeitos"][0]["som"], "tique-taque")
        self.assertEqual(self.plano()["musica"]["abaixo_da_voz_db"], 22.0)

    def test_valores_fora_do_limite_ou_fora_do_catalogo_sao_recusados(self):
        antes = self.bytes_("som.json")
        ruins = [(ajustes.nivel_da_musica, (5, 3)), (ajustes.nivel_da_musica, (18, 40)), (ajustes.nivel_da_musica, ("a", 3)),
                 (ajustes.ganho_do_efeito, (0, 20)), (ajustes.ganho_do_efeito, (0, -20)), (ajustes.ganho_do_efeito, (9, 0)),
                 (ajustes.ganho_do_efeito, (True, 0)), (ajustes.ganho_do_efeito, (0, float("inf"))),
                 (ajustes.trocar_som_do_efeito, (0, "../../etc/passwd")), (ajustes.trocar_som_do_efeito, (0, "buzina")),
                 (ajustes.tirar_efeito, (7,)), (ajustes.tirar_efeito, (-1,))]
        for f, args in ruins:
            with self.assertRaises(ajustes.Recusado, msg=f"{f.__name__}{args}"):
                f(self.dir, *args)
        self.assertEqual(self.bytes_("som.json"), antes)
        self.assertEqual(self.historico("som"), 0)

    def test_sem_musica_nao_ha_nivel_para_mexer(self):
        plano = self.plano()
        plano["musica"] = None
        (self.dir / "som.json").write_text(json.dumps(plano))
        with self.assertRaises(ajustes.Recusado):
            ajustes.nivel_da_musica(self.dir, 18, 3)
        self.assertIsNone(ajustes.painel_de_som(self.dir)["musica"])

    def test_ouvir_so_serve_o_que_esta_no_catalogo(self):
        cache = self.dir / "cache"
        self.assertTrue(ajustes.som_para_ouvir("efeito", "acerto", cache).is_file())
        trecho = ajustes.som_para_ouvir("musica", "calmo", cache)
        self.assertTrue(trecho.is_file())
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(trecho)],
                                   capture_output=True, text=True).stdout)
        self.assertAlmostEqual(dur, 30.0, delta=0.6)
        self.assertEqual(ajustes.som_para_ouvir("musica", "calmo", cache), trecho)        # a segunda vez vem do cache
        for tipo, nome in [("efeito", "../musica/calmo"), ("musica", "/etc/passwd"), ("musica", "calmo.mp3"), ("arquivo", "calmo"),
                           ("efeito", ""), ("musica", "..")]:
            with self.assertRaises(ajustes.Recusado, msg=f"{tipo} {nome}"):
                ajustes.som_para_ouvir(tipo, nome, cache)


# ---------- conferência ----------

def conferencia_de_teste(dir_: Path, correcoes, aprovado=False):
    video = dir_ / f"{dir_.name}-v001.mp4"
    video.write_bytes(b"x")
    video.with_suffix(".conferencia.json").write_text(json.dumps({"video": str(video), "aprovado": aprovado, "checks": [], "correcoes": correcoes}))
    return video


class TestConferencia(Base):
    def test_sem_conferencia_o_painel_recusa(self):
        with self.assertRaises(ajustes.Recusado):
            ajustes.painel_de_conferencia(self.dir)

    def test_aceitar_pausa_so_vale_para_pausa_achada(self):
        conferencia_de_teste(self.dir, [{"tipo": "pausa", "inicio": 3.2, "fim": 4.4, "texto": "silêncio"}])
        self.assertEqual(ajustes.pausa_aceitavel(self.dir, 3.2), 3.2)
        self.assertEqual(ajustes.pausa_aceitavel(self.dir, 3.205), 3.2)
        for ruim in (9.0, "x", None, True, -1):
            with self.assertRaises(ajustes.Recusado, msg=str(ruim)):
                ajustes.pausa_aceitavel(self.dir, ruim)

    def test_aplicar_ganho_grava_no_trecho_e_guarda_o_anterior(self):
        (self.dir / "cortes.json").write_text(json.dumps({"trechos": [{"video": 0, "inicio": 0, "fim": 2}, {"video": 0, "inicio": 3, "fim": 5, "ganho_db": 1.0}],
                                                          "duracao_final": 4}))
        conferencia_de_teste(self.dir, [{"tipo": "ganho", "trecho": 1, "ganho_db": 3.5, "atual": 1.0}])
        antes = self.bytes_("cortes.json")
        with self.assertRaises(ajustes.Recusado):
            ajustes.aplicar_ganho(self.dir, 1, 4.0)               # não é o ganho sugerido
        with self.assertRaises(ajustes.Recusado):
            ajustes.aplicar_ganho(self.dir, 0, 3.5)               # não é o trecho com problema
        with self.assertRaises(ajustes.Recusado):
            ajustes.aplicar_ganho(self.dir, 1, 99)
        self.assertEqual(self.bytes_("cortes.json"), antes)
        ajustes.aplicar_ganho(self.dir, 1, 3.5)
        self.assertEqual(json.loads(self.bytes_("cortes.json"))["trechos"][1]["ganho_db"], 3.5)
        self.assertTrue(ajustes.desfazer(self.dir, "cortes", self.dir / "cortes.json"))       # o Desfazer da revisão dos cortes
        self.assertEqual(self.bytes_("cortes.json"), antes)

    def test_o_conferir_de_verdade_grava_as_correcoes(self):
        """Um vídeo de 10 s com uma pausa de 3 s sem fala: o conferir.py acha o silêncio e diz o que consertar."""
        video = self.dir / "a.mov"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=270x480:r=30:d=10", "-f", "lavfi", "-i",
                        "sine=f=330:d=10", "-shortest", "-pix_fmt", "yuv420p", str(video)], check=True)
        (self.dir / "transcricoes").mkdir()
        palavras = [{"p": "Primeira", "i": 0.5, "f": 1.0}, {"p": "frase", "i": 1.1, "f": 1.6},
                    {"p": "Segunda", "i": 5.0, "f": 5.5}, {"p": "frase.", "i": 5.6, "f": 6.1}]
        (self.dir / "transcricoes" / "a.json").write_text(json.dumps({"palavras": palavras}))
        (self.dir / "cortes.json").write_text(json.dumps({"videos": [{"id": 0, "arquivo": str(video), "duracao": 10.0}],
                                                          "trechos": [{"video": 0, "inicio": 0.0, "fim": 10.0, "texto": "x"}],
                                                          "duracao_final": 10.0, "duracao_original": 10.0}))
        (self.dir / "inspecao.json").write_text(json.dumps({"videos": [{"arquivo": str(video), "nome": "a.mov", "fps": "30/1", "largura": 270,
                                                                         "altura": 480, "hdr": False, "duracao": 10.0}]}))
        saida = self.dir / "edicao-v001.mp4"
        shutil.copy(video, saida)
        r = subprocess.run([sys.executable, str(SCRIPTS / "conferir.py"), "--pasta", str(self.dir), "--video", str(saida)],
                           capture_output=True, text=True)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        c = json.loads(saida.with_suffix(".conferencia.json").read_text())
        pausas = [x for x in c["correcoes"] if x["tipo"] == "pausa"]
        self.assertTrue(pausas, c["correcoes"])
        self.assertAlmostEqual(pausas[0]["inicio"], 1.6, delta=0.1)
        self.assertGreater(pausas[0]["fim"] - pausas[0]["inicio"], 3.0)
        # a pausa aceita some da lista na conferência seguinte (o --pausas-ok que o orquestrador repassa)
        r = subprocess.run([sys.executable, str(SCRIPTS / "conferir.py"), "--pasta", str(self.dir), "--video", str(saida),
                            "--pausas-ok", str(pausas[0]["inicio"])], capture_output=True, text=True)
        c2 = json.loads(saida.with_suffix(".conferencia.json").read_text())
        self.assertFalse([x for x in c2["correcoes"] if x["tipo"] == "pausa" and x["inicio"] == pausas[0]["inicio"]])


# ---------- orquestrador ----------

class FalsoComTrecho(test_fase4.Falso):
    def __call__(self, argv, log):
        r = super().__call__(argv, log)
        if argv[0] == "propor_cortes.py":
            (self.pasta(argv) / "cortes.json").write_text(json.dumps({"videos": [], "duracao_final": 40.0, "trechos": [
                {"video": 0, "inicio": 0.0, "fim": 5.0, "texto": "a"}, {"video": 0, "inicio": 6.0, "fim": 9.0, "texto": "b"}]}))
        return r


class TestOrquestrador(test_fase4.Base):
    def completo(self):
        pasta, falso = self.novo(), FalsoComTrecho()
        self.assertEqual(self.aprovar_tudo_ate(pasta, falso, "nunca"), "fim")
        return pasta, falso

    def situacoes(self, pasta):
        t = editar.carregar(pasta)
        return {e.nome: editar.situacao(t, e, pasta) for e in editar.ETAPAS}

    def test_mudar_so_o_ganho_refaz_a_amostra_e_o_video_e_nada_antes(self):
        pasta, falso = self.completo()
        cortes = json.loads((pasta / "cortes.json").read_text())
        cortes["trechos"][1]["ganho_db"] = 3.0
        (pasta / "cortes.json").write_text(json.dumps(cortes))
        s = self.situacoes(pasta)
        for nome in ("fatos", "rosto", "gancho_olhar", "elementos", "camera", "legenda", "som"):
            self.assertIn(s[nome], ("feita", "pulada"), nome)
        self.assertEqual((s["amostra"], s["video"]), ("desatualizada", "desatualizada"))
        antes = len(falso.chamadas)
        self.assertEqual(self.aprovar_tudo_ate(pasta, falso, "nunca"), "fim")
        refeitos = [c[0] for c in falso.chamadas[antes:]]
        self.assertEqual(refeitos, ["renderizar.py", "renderizar.py", "conferir.py"])

    def test_mudar_um_tempo_dos_cortes_refaz_tudo_que_depende_deles(self):
        pasta, falso = self.completo()
        cortes = json.loads((pasta / "cortes.json").read_text())
        cortes["trechos"][1]["fim"] = 9.5
        (pasta / "cortes.json").write_text(json.dumps(cortes))
        s = self.situacoes(pasta)
        for nome in ("rosto", "elementos", "legenda", "amostra", "video"):
            self.assertEqual(s[nome], "desatualizada", nome)

    def estilo_igual(self, pasta, **mudancas):
        t = editar.carregar(pasta)
        leg = {"palavras": 3, "posicao": "auto", "tamanho": 0.046, "maiusculas": False, "destaque": True}
        leg.update(mudancas)
        (pasta / "legendas.json").write_text(json.dumps({"blocos": [{"texto": "revisado"}], "estilo": {
            **leg, "formato": "original", "cortes": assinatura_dos_cortes(json.loads((pasta / "cortes.json").read_text()))}}))
        return t

    def test_mudar_a_camera_mantem_o_texto_da_legenda(self):
        pasta, falso = self.completo()
        t = self.estilo_igual(pasta)
        self.assertTrue(editar._legenda_reaproveitavel(t, pasta))
        self.assertEqual(editar._c_legenda(t, pasta), [("legendas.py", ["--pasta", str(pasta), "--reaproveitar"], False)])

    def test_mudar_os_cortes_ou_o_estilo_refaz_a_legenda_do_zero(self):
        pasta, falso = self.completo()
        t = self.estilo_igual(pasta)
        self.assertNotIn("--reaproveitar", editar._c_legenda({**t, "escolhas": {**t["escolhas"], "legenda": {**t["escolhas"]["legenda"], "palavras": 2}}}, pasta)[0][1])
        cortes = json.loads((pasta / "cortes.json").read_text())
        cortes["trechos"][0]["fim"] = 4.0
        (pasta / "cortes.json").write_text(json.dumps(cortes))
        self.assertFalse(editar._legenda_reaproveitavel(t, pasta))
        self.assertNotIn("--reaproveitar", editar._c_legenda(t, pasta)[0][1])
        (pasta / "legendas.json").unlink()
        self.assertFalse(editar._legenda_reaproveitavel(t, pasta))

    def test_so_o_ganho_diferente_nao_muda_a_assinatura_dos_cortes(self):
        a = {"trechos": [{"inicio": 0, "fim": 1}], "duracao_final": 1}
        b = {"trechos": [{"inicio": 0, "fim": 1, "ganho_db": 2.5}], "duracao_final": 1}
        c = {"trechos": [{"inicio": 0, "fim": 1.5}], "duracao_final": 1}
        self.assertEqual(assinatura_dos_cortes(a), assinatura_dos_cortes(b))
        self.assertNotEqual(assinatura_dos_cortes(a), assinatura_dos_cortes(c))

    def test_pausas_aceitas_chegam_ao_conferir(self):
        pasta, falso = self.completo()
        self.assertNotIn("--pausas-ok", falso.chamadas[-1])
        editar.ajustar(pasta, "pausas_ok=[3.5, 7.25]")
        self.assertEqual(self.situacoes(pasta)["conferir"], "desatualizada")
        editar.refazer(pasta, "conferir")
        self.rodar(pasta, falso)
        chamada = falso.chamadas[-1]
        self.assertEqual(chamada[0], "conferir.py")
        i = chamada.index("--pausas-ok")
        self.assertEqual(chamada[i + 1:], ["3.5", "7.25"])


# ---------- API ----------

def edicao_com_ajustes(servidor, nome="teste"):
    pasta = test_fase6.edicao_de_teste(servidor, nome)
    montar(pasta, [{"elemento": "relogio", "inicio": 0.5, "duracao": 2.0, "modo": "sobreposto", "posicao": "auto", "texto": "*5 min*",
                    "gatilho": "cinco minutos", "fala_em": 0.6},
                   {"elemento": "funil", "inicio": 3.0, "duracao": 2.0, "modo": "sobreposto", "posicao": "auto", "texto": "",
                    "gatilho": "funil", "fala_em": 3.1}])
    cortes = json.loads((pasta / "cortes.json").read_text())
    cortes["duracao_final"] = 7.05
    # a montar() acima trocou o cortes.json: refaz com o vídeo de verdade
    cortes = {"videos": [{"id": 0, "arquivo": str(servidor.raiz / "material-bruto" / "a.mov"), "duracao": 16.0}],
              "trechos": [{"video": 0, "inicio": 0.93, "fim": 2.5, "texto": ""}, {"video": 0, "inicio": 3.93, "fim": 6.0, "texto": ""},
                          {"video": 0, "inicio": 7.93, "fim": 9.2, "texto": ""}, {"video": 0, "inicio": 11.93, "fim": 14.0, "texto": ""}],
              "removidos": [], "conferir": [], "duracao_original": 16.0, "duracao_final": 7.05}
    (pasta / "cortes.json").write_text(json.dumps(cortes))
    camera_de_teste(pasta)
    som_de_teste(pasta)
    return pasta


class TestApi(unittest.TestCase):
    def setUp(self):
        self.s = test_fase5.Servidor()
        self.pasta = edicao_com_ajustes(self.s)
        self.nome = self.pasta.name
        self.s.fila.enfileirar = lambda p: "rodando"          # a edição de teste não tem estado de etapas para rodar de verdade

    def tearDown(self):
        self.s.fechar()

    def ler(self, caminho, **kw):
        return self.s.pedir("GET", caminho, **kw)

    def post(self, rota, corpo=None, **kw):
        return self.s.post(rota, {"pasta": self.nome, **(corpo or {})}, **kw)

    def test_leituras_e_escritas_exigem_a_sessao(self):
        leituras = ["/api/elementos", "/api/zoom", "/api/som", "/api/conferencia", "/api/elementos/previa?id=x", "/api/zoom/previa?i=0",
                    "/api/som/ouvir?tipo=efeito&nome=acerto"]
        for caminho in leituras:
            sep = "&" if "?" in caminho else "?"
            self.assertEqual(self.ler(f"{caminho}{sep}pasta={self.nome}", sessao=False)[0], 401, caminho)
        for rota in [r for r in __import__("painel").Acoes.ROTAS if r.split("/")[2] in ("elementos", "zoom", "som", "conferencia")]:
            self.assertEqual(self.s.post(rota, {"pasta": self.nome}, sessao=False)[0], 401, rota)

    def test_elementos_pela_api(self):
        st, _, d = self.ler(f"/api/elementos?pasta={self.nome}")
        self.assertEqual((st, [i["nome"] for i in d["itens"]]), (200, ["relogio", "funil"]))
        id_ = d["itens"][0]["id"]
        st, _, r = self.post("/api/elementos/rotulo", {"id": id_, "texto": "*10 min*"})
        self.assertEqual((st, r["painel"]["itens"][0]["texto"]), (200, "*10 min*"))
        st, _, r = self.post("/api/elementos/tirar", {"id": id_})
        self.assertEqual((st, len(r["painel"]["itens"]), r["painel"]["desfazer"]), (200, 1, 2))
        st, _, r = self.post("/api/elementos/desfazer")
        self.assertEqual((st, len(r["painel"]["itens"])), (200, 2))
        self.assertEqual(self.post("/api/elementos/trocar", {"id": id_, "elemento": "lupa"})[0], 200)
        self.assertEqual(self.post("/api/elementos/trocar", {"id": id_, "elemento": "lupa"})[0], 400)      # o id mudou
        for corpo in ({"id": "x", "elemento": "furo"}, {"id": 5, "elemento": "furo"}, {"elemento": "furo"}):
            self.assertEqual(self.post("/api/elementos/trocar", corpo)[0], 400, corpo)

    def test_zoom_pela_api(self):
        st, _, d = self.ler(f"/api/zoom?pasta={self.nome}")
        self.assertEqual((st, d["escolha"], len(d["blocos"])), (200, "nenhum", 3))
        st, _, r = self.post("/api/zoom/nivel", {"indice": 2, "nivel": "aberto"})
        self.assertEqual((st, r["painel"]["blocos"][2]["nivel"]), (200, "aberto"))
        self.assertEqual(self.post("/api/zoom/nivel", {"indice": 2, "nivel": "gigante"})[0], 400)
        self.assertEqual(self.post("/api/zoom/tirar-enfase", {"indice": 2})[0], 400)         # já não é ênfase
        self.assertEqual(self.post("/api/zoom/desfazer")[0], 200)
        self.assertEqual(self.post("/api/zoom/desfazer")[0], 409)

    def test_som_pela_api(self):
        st, _, d = self.ler(f"/api/som?pasta={self.nome}")
        self.assertEqual((st, d["escolha"], len(d["efeitos"])), (200, {"musica": "nenhuma", "efeitos": False}, 2))
        st, _, r = self.post("/api/som/ganho", {"indice": 1, "ganho_db": -3})
        self.assertEqual((st, r["painel"]["efeitos"][1]["ganho_db"]), (200, -3))
        self.assertEqual(self.post("/api/som/ganho", {"indice": 1, "ganho_db": 30})[0], 400)
        self.assertEqual(self.post("/api/som/trocar", {"indice": 0, "som": "../x"})[0], 400)
        self.assertEqual(self.post("/api/som/musica", {"abaixo": 15, "sobe": 4})[0], 200)

    def test_ouvir_serve_so_o_catalogo(self):
        st, h, corpo = self.ler(f"/api/som/ouvir?pasta={self.nome}&tipo=efeito&nome=acerto")
        self.assertEqual((st, h["Content-Type"]), (200, "audio/wav"))
        st, h, _ = self.ler(f"/api/som/ouvir?pasta={self.nome}&tipo=musica&nome=calmo")
        self.assertEqual((st, h["Content-Type"]), (200, "audio/mp4"))
        for nome in ("../../x", "..%2F..%2Fx", "calmo.mp3", "%2Fetc%2Fpasswd"):
            self.assertEqual(self.ler(f"/api/som/ouvir?pasta={self.nome}&tipo=musica&nome={nome}")[0], 400, nome)
        self.assertEqual(self.ler("/api/som/ouvir?tipo=efeito&nome=acerto")[0], 400)        # sem edição não serve nada

    def test_conferencia_aceitar_pausa_e_aplicar_ganho(self):
        conferencia_de_teste(self.pasta, [{"tipo": "pausa", "inicio": 3.2, "fim": 4.4, "texto": "silêncio"},
                                          {"tipo": "ganho", "trecho": 1, "ganho_db": 2.5, "atual": 0.0, "texto": "baixo"}])
        st, _, d = self.ler(f"/api/conferencia?pasta={self.nome}")
        self.assertEqual((st, len(d["correcoes"]), d["pausas_ok"]), (200, 2, []))
        self.assertEqual(self.post("/api/conferencia/aceitar-pausa", {"inicio": 9.9})[0], 400)
        st, _, r = self.post("/api/conferencia/aceitar-pausa", {"inicio": 3.2})
        self.assertEqual((st, r["fila"]), (200, "rodando"))
        self.assertEqual(editar.carregar(self.pasta)["escolhas"]["pausas_ok"], [3.2])
        self.assertEqual(self.ler(f"/api/conferencia?pasta={self.nome}")[2]["pausas_ok"], [3.2])
        self.assertEqual(self.post("/api/conferencia/aplicar-ganho", {"trecho": 1, "ganho_db": 9})[0], 400)
        st, _, r = self.post("/api/conferencia/aplicar-ganho", {"trecho": 1, "ganho_db": 2.5})
        self.assertEqual(st, 200, r)
        self.assertEqual(json.loads((self.pasta / "cortes.json").read_text())["trechos"][1]["ganho_db"], 2.5)
        self.assertNotIn("video", editar.carregar(self.pasta)["etapas"])

    def test_edicao_ocupada_recebe_409_mas_a_leitura_continua(self):
        self.s.fila.ocupada = lambda p: True
        for rota, corpo in [("/api/elementos/tirar", {"id": "x"}), ("/api/zoom/nivel", {"indice": 0, "nivel": "perto"}),
                            ("/api/som/ganho", {"indice": 0, "ganho_db": 0}), ("/api/elementos/desfazer", {}),
                            ("/api/conferencia/aceitar-pausa", {"inicio": 1}), ("/api/conferencia/aplicar-ganho", {"trecho": 0, "ganho_db": 1})]:
            self.assertEqual(self.post(rota, corpo)[0], 409, rota)
        self.assertEqual(self.ler(f"/api/elementos?pasta={self.nome}")[0], 200)

    def test_nomes_de_edicao_ruins(self):
        for pasta in ("../x", "..", "nao-existe", "", None):
            self.assertIn(self.ler(f"/api/elementos?pasta={pasta}")[0], (400, 404))
            self.assertIn(self.s.post("/api/elementos/tirar", {"pasta": pasta, "id": "x"})[0], (400, 404))

    def test_o_estado_diz_o_que_ha_para_ajustar(self):
        base = self.ler("/api/estado")[2]["trabalhos"][0]["orq"]
        self.assertEqual(base["ajustar"], {"elementos": True, "zoom": True, "som": True, "conferencia": False})
        conferencia_de_teste(self.pasta, [])
        self.assertTrue(self.ler("/api/estado")[2]["trabalhos"][0]["orq"]["ajustar"]["conferencia"])


# ---------- prévias ----------

class TestPrevias(unittest.TestCase):
    def setUp(self):
        self.s = test_fase5.Servidor()
        self.pasta = edicao_com_ajustes(self.s)
        self.nome = self.pasta.name

    def tearDown(self):
        self.s.fechar()

    def test_previa_de_um_elemento_e_do_zoom(self):
        d = self.s.pedir("GET", f"/api/elementos?pasta={self.nome}")[2]
        st, h, corpo = self.s.pedir("GET", f"/api/elementos/previa?pasta={self.nome}&id={d['itens'][1]['id']}")
        self.assertEqual((st, h["Content-Type"]), (200, "image/jpeg"), corpo[:200])
        self.assertGreater(int(h["Content-Length"]), 3000)
        again = self.s.pedir("GET", f"/api/elementos/previa?pasta={self.nome}&id={d['itens'][1]['id']}")
        self.assertEqual(again[2], corpo)                                           # a segunda vem do cache
        self.assertEqual(self.s.pedir("GET", f"/api/elementos/previa?pasta={self.nome}&id=funil@99.000")[0], 400)
        for i in (0, 2):
            st, h, corpo = self.s.pedir("GET", f"/api/zoom/previa?pasta={self.nome}&i={i}")
            self.assertEqual((st, h["Content-Type"]), (200, "image/jpeg"), corpo[:200])
        for i in ("9", "x", "-1", ""):
            self.assertEqual(self.s.pedir("GET", f"/api/zoom/previa?pasta={self.nome}&i={i}")[0], 400, i)


# ---------- na tela, num navegador de verdade ----------

class TestTela(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
            from elementos import abrir_navegador
        except ImportError:
            ambiente.indisponivel("sem o Playwright instalado")
        cls.pw = sync_playwright().start()
        try:
            cls.nav = abrir_navegador(cls.pw)
        except SystemExit:
            cls.pw.stop()
            ambiente.indisponivel("sem o Chromium do Playwright (python -m playwright install chromium)")

    @classmethod
    def tearDownClass(cls):
        cls.nav.close()
        cls.pw.stop()

    def abrir(self, s):
        ctx = self.nav.new_context(viewport={"width": 1200, "height": 900})
        ctx.add_cookies([{"name": "painel", "value": s.codigo, "domain": "localhost", "path": "/"}])
        pg = ctx.new_page()
        self.erros = []
        pg.on("pageerror", lambda e: self.erros.append(str(e)))
        pg.goto(f"http://localhost:{s.porta}/")
        return ctx, pg

    def test_elementos_tirar_desfazer_rotulo_e_adicionar(self):
        s = test_fase5.Servidor()
        try:
            pasta = edicao_com_ajustes(s)
            ctx, pg = self.abrir(s)
            pg.wait_for_selector("button[data-aba='elementos']", timeout=10000)
            pg.click("button[data-aba='elementos'][data-acao='ajustar']")
            pg.wait_for_selector(".aj-linha", timeout=8000)
            self.assertEqual(pg.locator(".aj-linha").count(), 2)
            self.assertTrue(pg.is_disabled("#aj-desfazer"))
            pg.wait_for_function("[...document.querySelectorAll('.aj-linha img')].every(i => i.complete && i.naturalWidth > 100)", timeout=40000)
            linha = lambda n: pg.locator(".aj-linha").nth(n)
            linha(0).locator("[data-el=rotulo]").fill("*10 min*")
            linha(0).locator("[data-el=rotulo]").dispatch_event("change")
            pg.wait_for_function("!document.querySelector('#aj-desfazer').disabled", timeout=8000)
            self.assertEqual(json.loads((pasta / "elementos.json").read_text())["itens"][0]["texto"], "*10 min*")
            linha(1).locator("button[data-aj=tirar]").click()
            pg.wait_for_function("document.querySelectorAll('.aj-linha').length === 1", timeout=8000)
            self.assertEqual(len(json.loads((pasta / "elementos.json").read_text())["itens"]), 1)
            pg.click("#aj-desfazer")
            pg.wait_for_function("document.querySelectorAll('.aj-linha').length === 2", timeout=8000)
            linha(0).locator("[data-campo=duracao]").fill("9")                    # acima do máximo: o servidor recusa e a tela avisa
            linha(0).locator("[data-campo=duracao]").dispatch_event("change")
            pg.wait_for_function("document.querySelector('#copiado').innerText.includes('de 1 a 4')", timeout=8000)
            self.assertEqual(json.loads((pasta / "elementos.json").read_text())["itens"][0]["duracao"], 2.0)
            pg.select_option("#aj-novo-el", "furo")
            pg.fill("#aj-novo-t", "5.0")
            pg.click("#aj-novo-ir")
            pg.wait_for_function("document.querySelectorAll('.aj-linha').length === 3", timeout=8000)
            self.assertEqual([i["elemento"] for i in json.loads((pasta / "elementos.json").read_text())["itens"]], ["relogio", "funil", "furo"])
            self.assertEqual(self.erros, [])
            ctx.close()
        finally:
            s.fechar()

    def test_conferencia_aceitar_pausa_pela_tela(self):
        s = test_fase5.Servidor()
        try:
            pasta = edicao_com_ajustes(s)
            s.fila.enfileirar = lambda p: "rodando"
            conferencia_de_teste(pasta, [{"tipo": "pausa", "inicio": 3.2, "fim": 4.4, "texto": "silêncio de 1,2 s em 0:03"},
                                         {"tipo": "ganho", "trecho": 1, "ganho_db": 2.5, "atual": 0.0, "texto": "o trecho 2 está baixo"}])
            ctx, pg = self.abrir(s)
            pg.wait_for_selector("button[data-aba='conferencia']", timeout=10000)
            pg.click("button[data-aba='conferencia'][data-acao='ajustar']")
            pg.wait_for_selector(".correcao", timeout=8000)
            self.assertEqual(pg.locator(".correcao").count(), 2)
            self.assertIn("2,5 dB", pg.inner_text("button[data-aj=aplicar-ganho]"))
            pg.click("button[data-aj=aceitar-pausa]")
            pg.wait_for_function("!document.querySelector('#ajustes').classList.contains('aberto')", timeout=8000)
            self.assertEqual(editar.carregar(pasta)["escolhas"]["pausas_ok"], [3.2])
            self.assertEqual(self.erros, [])
            ctx.close()
        finally:
            s.fechar()

    def test_zoom_e_som_pela_tela(self):
        s = test_fase5.Servidor()
        try:
            pasta = edicao_com_ajustes(s)
            ctx, pg = self.abrir(s)
            pg.wait_for_selector("button[data-aba='zoom']", timeout=10000)
            pg.click("button[data-aba='zoom'][data-acao='ajustar']")
            pg.wait_for_selector(".zoom-bloco", timeout=8000)
            self.assertEqual(pg.locator(".zoom-bloco").count(), 3)
            pg.select_option("[data-aj-zoom='2']", "aberto")
            pg.wait_for_function("!document.querySelector('#aj-desfazer').disabled", timeout=8000)
            self.assertEqual(json.loads((pasta / "camera.json").read_text())["blocos"][2]["zoom"], 1.0)
            pg.click("#aj-abas button[data-aba='som']")
            pg.wait_for_selector("[data-aj-ganho]", timeout=8000)
            pg.fill("[data-aj-ganho='1']", "-4")
            pg.dispatch_event("[data-aj-ganho='1']", "change")
            pg.wait_for_function("!document.querySelector('#aj-desfazer').disabled", timeout=8000)
            self.assertEqual(json.loads((pasta / "som.json").read_text())["efeitos"][1]["ganho_db"], -4.0)
            pg.click("[data-aj-musica='animado']")                                          # é só uma escolha: o som é planejado depois
            pg.wait_for_function("document.querySelector('.musica.escolhida .nome')?.innerText.includes('Blue Skies')", timeout=8000)
            self.assertEqual(editar.carregar(pasta)["escolhas"]["som"]["musica"], "animado")
            self.assertEqual(self.erros, [])
            ctx.close()
        finally:
            s.fechar()


if __name__ == "__main__":
    unittest.main()
