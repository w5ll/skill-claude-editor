"""Testes da Fase 6 (revisão de cortes e legenda). Rodar: .venv/bin/python -m unittest discover -s tests -v

A lógica (revisao.py) é testada sozinha, com transcrições e cortes sintéticos; o áudio das emendas e a prévia da
legenda usam o ffmpeg de verdade num vídeo de teste.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "welldit" / "scripts"))

import revisao  # noqa: E402
from comum import carregar_marca  # noqa: E402


def fala(texto, inicio, passo=0.3, conf=1.0):
    """Palavras com tempo (e confiança) a partir de um texto."""
    return [{"p": p, "i": round(inicio + k * passo, 3), "f": round(inicio + k * passo + passo * 0.8, 3), "conf": conf}
            for k, p in enumerate(texto.split())]


F1 = fala("Primeiro, defina uma meta clara.", 1.0)                 # 1.0 a 2.34
F2 = fala("Depois meça toda semana e ajuste", 4.0)                  # sem ponto final, depois de uma pausa
F3 = fala("Isso funciona sempre.", 8.0)
F4 = fala("Obrigado por assistir.", 12.0)
PALAVRAS = F1 + F2 + F3 + F4


def montar(tmp: Path, trechos=None, removidos=None, conferir=None, palavras=None, duracao=20.0):
    (tmp / "transcricoes").mkdir(exist_ok=True)
    (tmp / "transcricoes" / "a.json").write_text(json.dumps({"palavras": palavras or PALAVRAS}))
    cortes = {"videos": [{"id": 0, "arquivo": str(tmp / "a.mp4"), "duracao": duracao}],
              "trechos": trechos if trechos is not None else [
                  {"video": 0, "inicio": 0.93, "fim": 2.5, "texto": "a"}, {"video": 0, "inicio": 3.93, "fim": 6.0, "texto": "b"},
                  {"video": 0, "inicio": 7.93, "fim": 9.2, "texto": "c"}, {"video": 0, "inicio": 11.93, "fim": 14.0, "texto": "d"}],
              "removidos": removidos or [], "conferir": conferir or [], "duracao_original": duracao, "duracao_final": 0}
    (tmp / "cortes.json").write_text(json.dumps(cortes))
    return cortes


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cortes(self):
        return json.loads((self.dir / "cortes.json").read_text())

    def palavras_que_ficam(self, c=None):
        c = c or self.cortes()
        return [w["p"] for w in PALAVRAS if any(t["inicio"] <= (w["i"] + w["f"]) / 2 < t["fim"] for t in c["trechos"])]


class TestUnidades(Base):
    def test_separam_por_pontuacao_pausa_e_estado(self):
        montar(self.dir, trechos=[{"video": 0, "inicio": 0.93, "fim": 6.0, "texto": ""}])
        cortes = self.cortes()
        uns = revisao.unidades(cortes, revisao.palavras_dos_videos(self.dir, cortes))
        textos = [(u["texto"], u["fica"]) for u in uns]
        self.assertEqual(textos[0], ("Primeiro, defina uma meta clara.", True))
        self.assertEqual(textos[1], ("Depois meça toda semana e ajuste", True))
        self.assertEqual(textos[2], ("Isso funciona sempre.", False))                   # fora dos trechos: sai
        self.assertEqual(textos[3], ("Obrigado por assistir.", False))
        for u in uns:                                                                    # nunca meio a meio
            estados = {revisao.fica(w, cortes["trechos"]) for w in u["palavras"]}
            self.assertEqual(len(estados), 1)

    def test_unidade_comprida_parte_na_maior_pausa(self):
        longa = fala("um dois tres quatro cinco seis sete oito", 1.0) + fala("nove dez onze doze treze quatorze quinze", 6.0, passo=0.3)
        montar(self.dir, trechos=[{"video": 0, "inicio": 0.9, "fim": 12.0, "texto": ""}], palavras=longa)
        cortes = self.cortes()
        uns = revisao.unidades(cortes, revisao.palavras_dos_videos(self.dir, cortes))
        self.assertTrue(all(len(u["palavras"]) <= revisao.MAX_PALAVRAS_UNIDADE for u in uns))
        self.assertGreaterEqual(len(uns), 2)

    def test_motivo_do_que_saiu(self):
        montar(self.dir, trechos=[{"video": 0, "inicio": 0.93, "fim": 6.0, "texto": ""}],
               removidos=[{"video": 0, "inicio": 7.9, "fim": 9.2, "motivo": "frase repetida ou começo errado", "video_": 0}])
        cortes = self.cortes()
        uns = revisao.unidades(cortes, revisao.palavras_dos_videos(self.dir, cortes))
        self.assertEqual(next(u for u in uns if u["texto"].startswith("Isso"))["motivo"], "frase repetida ou começo errado")


class TestTirarEVoltar(Base):
    def unidade(self, comeco):
        cortes = self.cortes()
        return next(u for u in revisao.unidades(cortes, revisao.palavras_dos_videos(self.dir, cortes)) if u["texto"].startswith(comeco))

    def test_tirar_corta_no_silencio_e_nunca_no_meio_de_palavra(self):
        montar(self.dir)
        u = self.unidade("Depois")
        c = revisao.alternar(self.dir, 0, u["k0"], u["k1"], "tirar")
        for t in c["trechos"]:
            for w in PALAVRAS:
                self.assertFalse(w["i"] < t["inicio"] < w["f"] or w["i"] < t["fim"] < w["f"], (t, w))
        self.assertNotIn("Depois", self.palavras_que_ficam(c))
        self.assertIn("Isso", self.palavras_que_ficam(c))
        self.assertEqual(c["duracao_final"], round(sum(t["fim"] - t["inicio"] for t in c["trechos"]), 2))
        self.assertTrue(any(r["motivo"] == "tirado na revisão" for r in c["removidos"]))

    def test_tirar_do_meio_de_um_trecho_divide_o_trecho(self):
        montar(self.dir, trechos=[{"video": 0, "inicio": 0.93, "fim": 14.0, "texto": "", "ganho_db": 3.0}])
        u = self.unidade("Isso")
        c = revisao.alternar(self.dir, 0, u["k0"], u["k1"], "tirar")
        self.assertEqual(len(c["trechos"]), 2)
        self.assertEqual([t.get("ganho_db") for t in c["trechos"]], [3.0, 3.0])          # o ganho vale para os dois pedaços
        self.assertNotIn("Isso", self.palavras_que_ficam(c))
        self.assertEqual(self.palavras_que_ficam(c), [w["p"] for w in PALAVRAS if w not in F3])

    def test_voltar_devolve_as_mesmas_palavras_e_junta_com_o_vizinho(self):
        montar(self.dir, trechos=[{"video": 0, "inicio": 0.93, "fim": 6.0, "texto": ""}, {"video": 0, "inicio": 11.93, "fim": 14.0, "texto": ""}])
        u = self.unidade("Isso")
        c = revisao.alternar(self.dir, 0, u["k0"], u["k1"], "voltar")
        self.assertEqual(self.palavras_que_ficam(c), [w["p"] for w in PALAVRAS])
        self.assertEqual(len(c["trechos"]), 3)                  # o "Isso" ficou longe dos vizinhos (pausa maior que 0,6 s)
        v = self.unidade("Depois")
        c2 = revisao.alternar(self.dir, 0, v["k0"], v["k1"], "tirar")
        c3 = revisao.alternar(self.dir, 0, v["k0"], v["k1"], "voltar")
        self.assertEqual(self.palavras_que_ficam(c3), self.palavras_que_ficam(c))

    def test_voltar_encostado_vira_um_trecho_so(self):
        montar(self.dir, trechos=[{"video": 0, "inicio": 0.93, "fim": 2.5, "texto": ""}, {"video": 0, "inicio": 4.3, "fim": 14.0, "texto": ""}])
        u = self.unidade("Depois")                                # a unidade começa em 4.0, antes do trecho que começa em 4.3
        c = revisao.alternar(self.dir, 0, u["k0"], u["k0"], "voltar")
        self.assertIn("Depois", self.palavras_que_ficam(c))

    def test_mantem_a_ordem_de_um_trecho_puxado_para_o_comeco(self):
        # a frase "Obrigado..." foi puxada para o começo (gancho): a ordem de reprodução não segue o tempo do vídeo
        montar(self.dir, trechos=[{"video": 0, "inicio": 11.93, "fim": 14.0, "texto": ""}, {"video": 0, "inicio": 0.93, "fim": 2.5, "texto": ""}])
        u = self.unidade("Depois")
        c = revisao.alternar(self.dir, 0, u["k0"], u["k1"], "voltar")
        self.assertEqual(c["trechos"][0]["inicio"], 11.93)                         # continua primeiro
        self.assertEqual([round(t["inicio"], 1) for t in c["trechos"]][0], 11.9)

    def test_nao_deixa_os_cortes_vazios_nem_aceita_indice_ruim(self):
        montar(self.dir, trechos=[{"video": 0, "inicio": 0.93, "fim": 2.5, "texto": ""}])
        with self.assertRaises(revisao.Recusado):
            revisao.alternar(self.dir, 0, 0, len(F1) - 1, "tirar")
        for args in ((9, 0, 1, "tirar"), (0, -1, 2, "tirar"), (0, 0, 999, "tirar"), (0, 3, 1, "tirar"), (0, "a", 1, "tirar"), (0, 0, 1, "apagar")):
            with self.assertRaises(revisao.Recusado, msg=str(args)):
                revisao.alternar(self.dir, *args)
        self.assertEqual(revisao.historico(self.dir, "cortes"), [])                       # nada foi gravado

    def test_desfazer_restaura_exatamente_e_varias_vezes(self):
        montar(self.dir)
        original = (self.dir / "cortes.json").read_text()
        u = self.unidade("Depois")
        revisao.alternar(self.dir, 0, u["k0"], u["k1"], "tirar")
        meio = (self.dir / "cortes.json").read_text()
        v = self.unidade("Isso")
        revisao.alternar(self.dir, 0, v["k0"], v["k1"], "tirar")
        self.assertEqual(len(revisao.historico(self.dir, "cortes")), 2)
        self.assertTrue(revisao.desfazer(self.dir, "cortes", self.dir / "cortes.json"))
        self.assertEqual((self.dir / "cortes.json").read_text(), meio)
        self.assertTrue(revisao.desfazer(self.dir, "cortes", self.dir / "cortes.json"))
        self.assertEqual((self.dir / "cortes.json").read_text(), original)
        self.assertFalse(revisao.desfazer(self.dir, "cortes", self.dir / "cortes.json"))   # sem histórico: nada


class TestSuspeitas(Base):
    def tipos(self, **kw):
        montar(self.dir, **kw)
        cortes = self.cortes()
        uns = revisao.unidades(cortes, revisao.palavras_dos_videos(self.dir, cortes))
        return [(s["tipo"], s["motivo"]) for s in revisao.suspeitas(cortes, uns)], uns

    def test_acha_cada_tipo(self):
        duvidosa = [{**w, "conf": 0.2} if w["p"] == "meta" else w for w in PALAVRAS]
        longa = [{**w, "f": w["i"] + 2.0} if w["p"] == "clara." else w for w in duvidosa]
        s, _ = self.tipos(palavras=longa, trechos=[{"video": 0, "inicio": 0.93, "fim": 6.0, "texto": ""}],
                          removidos=[{"video": 0, "inicio": 7.9, "fim": 9.2, "motivo": "frase repetida ou começo errado"}],
                          conferir=[{"video": 0, "tempo": 10.0, "motivo": "som sem palavra transcrita (risada, barulho?)", "texto": ""}])
        tipos = {t for t, _ in s}
        self.assertEqual(tipos, {"duvidosa", "repetida", "sem_palavra", "fim", "nao_termina"})
        self.assertTrue(any("“meta”" in m for t, m in s if t == "duvidosa"))
        self.assertTrue(any("som arrastado" in m for t, m in s))

    def test_palavra_pequena_de_baixa_confianca_nao_e_marcada_a_menos_que_seja_muito_baixa(self):
        fracas = [{**w, "conf": 0.3} if w["p"] in ("uma", "e") else w for w in PALAVRAS]
        s, _ = self.tipos(palavras=fracas)
        self.assertEqual([m for t, m in s if t == "duvidosa"], [])                      # “uma” e “e” são palavras pequenas
        muito = [{**w, "conf": 0.1} if w["p"] == "uma" else w for w in PALAVRAS]
        s, _ = self.tipos(palavras=muito)
        self.assertTrue(any("“uma”" in m for t, m in s if t == "duvidosa"))

    def test_varias_palavras_duvidosas_da_mesma_frase_viram_um_ponto_so_e_ordenadas_no_tempo(self):
        fracas = [{**w, "conf": 0.2} if w["p"] in ("defina", "meta", "clara.") else w for w in PALAVRAS]
        montar(self.dir, palavras=fracas)
        cortes = self.cortes()
        uns = revisao.unidades(cortes, revisao.palavras_dos_videos(self.dir, cortes))
        sus = revisao.suspeitas(cortes, uns)
        duv = [x for x in sus if x["tipo"] == "duvidosa"]
        self.assertEqual(len(duv), 1)
        self.assertIn("“defina”", duv[0]["motivo"])
        self.assertIn("Primeiro", duv[0]["texto"])                                    # o trecho da frase aparece
        self.assertEqual([x["tempo"] for x in sus], sorted(x["tempo"] for x in sus))

    def test_mensagens_da_conferencia_sem_comando_de_terminal(self):
        s, _ = self.tipos(conferir=[{"video": 0, "tempo": 10.0, "motivo": "fala que o Whisper não reconheceu: rode transcrever.py --trecho 9 12 antes de cortar", "texto": ""},
                                    {"video": 0, "tempo": 13.5, "motivo": "FALA NO FIM SEM TRANSCRIÇÃO: pode ser o fecho. Rode transcrever.py --trecho 12 16", "texto": ""}])
        textos = " ".join(m for _, m in s)
        self.assertNotIn("transcrever.py", textos)
        self.assertNotIn("--trecho", textos)
        self.assertIn("ouça", textos)

    def test_frase_cortada_ao_meio(self):
        s, _ = self.tipos(trechos=[{"video": 0, "inicio": 0.93, "fim": 6.0, "texto": ""}])
        self.assertTrue(any(t == "nao_termina" and "ajuste" in m for t, m in s))        # "...e ajuste" e depois um corte

    def test_frase_boa_nao_e_marcada(self):
        s, _ = self.tipos(trechos=[{"video": 0, "inicio": 0.93, "fim": 2.5, "texto": ""}, {"video": 0, "inicio": 7.93, "fim": 14.0, "texto": ""}])
        self.assertEqual([t for t, _ in s if t == "nao_termina"], [])
        self.assertEqual([t for t, _ in s if t == "duvidosa"], [])

    def test_fim_da_gravacao_sempre_aparece(self):
        s, uns = self.tipos()
        self.assertEqual([t for t, _ in s].count("fim"), 1)


class TestPainelDeCortes(Base):
    def test_emendas_duracao_e_meta(self):
        montar(self.dir)
        p = revisao.painel_de_cortes(self.dir, 30.0)
        self.assertEqual(len(p["emendas"]), 3)                        # quatro trechos, três junções
        for e in p["emendas"]:
            self.assertEqual(len(e["pedacos"]), 2)
            self.assertTrue(all(0 < x["fim"] - x["inicio"] <= 1.2 + 1e-6 for x in e["pedacos"]))
        self.assertEqual(p["meta"], 30.0)
        self.assertEqual(p["desfazer"], 0)
        self.assertEqual(p["videos"][0]["nome"], "a.mp4")

    def test_trechos_continuos_nao_tem_emenda(self):
        montar(self.dir, trechos=[{"video": 0, "inicio": 0.93, "fim": 6.0, "texto": ""}, {"video": 0, "inicio": 6.0, "fim": 9.2, "texto": ""}])
        self.assertEqual(revisao.painel_de_cortes(self.dir, None)["emendas"], [])


class TestOuvir(Base):
    def setUp(self):
        super().setUp()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=f=440:d=10", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=10",
                        "-shortest", "-pix_fmt", "yuv420p", str(self.dir / "a.mp4")], check=True)
        montar(self.dir, duracao=10.0)

    def duracao(self, arq):
        saida = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(arq)], capture_output=True, text=True).stdout
        return float(saida.strip())

    def test_audio_com_a_duracao_pedida(self):
        cortes = self.cortes()
        pedacos = revisao.pedacos_validos(cortes, [{"video": 0, "inicio": 1.0, "fim": 2.2}, {"video": 0, "inicio": 5.0, "fim": 6.0}])
        arq = revisao.audio_dos_pedacos(pedacos, self.dir / "ouvir" / "x.m4a")
        self.assertAlmostEqual(self.duracao(arq), 2.2, delta=0.12)

    def test_so_videos_do_cortes_e_dentro_dos_limites(self):
        cortes = self.cortes()
        ruins = ([{"video": 1, "inicio": 0, "fim": 1}], [{"video": 0, "inicio": -1, "fim": 1}], [{"video": 0, "inicio": 2, "fim": 1}],
                 [{"video": 0, "inicio": 0, "fim": 99}], [{"video": 0, "inicio": 0, "fim": 1}] * 7, [], "x", [{"video": "../x", "inicio": 0, "fim": 1}],
                 [{"arquivo": "/etc/passwd", "inicio": 0, "fim": 1}], [{"video": 0, "inicio": "a", "fim": 1}])
        for pedacos in ruins:
            with self.assertRaises(revisao.Recusado, msg=str(pedacos)):
                revisao.pedacos_validos(cortes, pedacos)
        ok = revisao.pedacos_validos(cortes, [{"video": 0, "inicio": 0, "fim": 1, "arquivo": "/etc/passwd"}])
        self.assertEqual(ok[0]["arquivo"], cortes["videos"][0]["arquivo"])                # o caminho vem do cortes.json, não do pedido

    def test_o_mesmo_pedido_usa_o_cache(self):
        pedacos = revisao.pedacos_validos(self.cortes(), [{"video": 0, "inicio": 1.0, "fim": 2.0}])
        a = revisao.chave_do_audio(pedacos)
        self.assertEqual(a, revisao.chave_do_audio(pedacos))
        self.assertNotEqual(a, revisao.chave_do_audio(revisao.pedacos_validos(self.cortes(), [{"video": 0, "inicio": 1.0, "fim": 2.5}])))


def legendas_de_teste(tmp: Path, textos=("Defina uma", "meta clara", "Pague 30", "mil reais")):
    blocos = []
    for k, t in enumerate(textos):
        ws = t.split()
        blocos.append({"texto": t, "inicio": 1.0 + k * 1.0, "fim": 1.9 + k * 1.0,
                       "palavras": [{"p": p, "i": 1.0 + k + j * 0.4, "f": 1.0 + k + j * 0.4 + 0.35} for j, p in enumerate(ws)],
                       "y": 730 if k != 3 else 150, "lugar": "embaixo" if k != 3 else "acima da testa"})
    d = {"estilo": {"palavras": 2, "posicao": "auto", "tamanho": 0.046, "maiusculas": False, "destaque": True, "formato": "original",
                    "largura": 540, "altura": 960}, "blocos": blocos}
    (tmp / "legendas.json").write_text(json.dumps(d))
    return d


class TestLegenda(Base):
    def test_editar_um_bloco_guarda_o_anterior(self):
        legendas_de_teste(self.dir)
        antes = (self.dir / "legendas.json").read_text()
        d = revisao.editar_bloco(self.dir, 1, "  meta   clara!  ")
        self.assertEqual(d["blocos"][1]["texto"], "meta clara!")
        self.assertEqual(len(revisao.historico(self.dir, "legendas")), 1)
        self.assertTrue(revisao.desfazer(self.dir, "legendas", self.dir / "legendas.json"))
        self.assertEqual((self.dir / "legendas.json").read_text(), antes)

    def test_texto_invalido(self):
        legendas_de_teste(self.dir)
        for ruim in ("", "   ", "x" * 81, "a\x00b", 5, None, ["a"]):
            with self.assertRaises(revisao.Recusado, msg=repr(ruim)):
                revisao.editar_bloco(self.dir, 0, ruim)
        for indice in (-1, 99, "a", None, True):
            with self.assertRaises(revisao.Recusado, msg=repr(indice)):
                revisao.editar_bloco(self.dir, indice, "ok")
        self.assertEqual(revisao.historico(self.dir, "legendas"), [])

    def test_mesmo_texto_nao_gera_historico(self):
        legendas_de_teste(self.dir)
        revisao.editar_bloco(self.dir, 0, "Defina uma")
        self.assertEqual(revisao.historico(self.dir, "legendas"), [])

    def test_destaque_some_quando_muda_o_numero_de_palavras(self):
        legendas_de_teste(self.dir)
        self.assertTrue(all(b["destaque"] for b in revisao.painel_de_legenda(self.dir)["blocos"]))
        revisao.editar_bloco(self.dir, 0, "Defina uma coisa")
        blocos = revisao.painel_de_legenda(self.dir)["blocos"]
        self.assertFalse(blocos[0]["destaque"])
        self.assertTrue(blocos[1]["destaque"])

    def test_corrigir_em_todos(self):
        legendas_de_teste(self.dir, textos=("Pague zap", "no Zap agora", "zapzap", "sem nada"))
        n = revisao.substituir(self.dir, "zap", "WhatsApp")
        self.assertEqual(n, 2)                                               # palavra inteira, sem diferenciar maiúscula; "zapzap" não
        d = json.loads((self.dir / "legendas.json").read_text())
        self.assertEqual([b["texto"] for b in d["blocos"]], ["Pague WhatsApp", "no WhatsApp agora", "zapzap", "sem nada"])
        self.assertEqual(d["blocos"][0]["palavras"][1]["p"], "WhatsApp")      # o destaque acompanha a troca
        self.assertEqual(len(revisao.historico(self.dir, "legendas")), 1)
        self.assertEqual(revisao.substituir(self.dir, "inexistente", "x"), 0)
        self.assertEqual(len(revisao.historico(self.dir, "legendas")), 1)    # nada mudou: nada guardado
        for de, para in (("", "x"), ("x", None), ("a" * 41, "b"), ("x", "x")):
            with self.assertRaises(revisao.Recusado, msg=repr((de, para))):
                revisao.substituir(self.dir, de, para)

    def test_marcas(self):
        legendas_de_teste(self.dir, textos=("Defina uma", "meta clara", "Pague 30", "mil WhatsApp"))
        marcas = [b["marcas"] for b in revisao.painel_de_legenda(self.dir)["blocos"]]
        self.assertEqual(marcas[0], [])
        self.assertEqual(marcas[2], ["número"])
        self.assertEqual(marcas[3], ["nome próprio", "movida"])


class TestPreviaDaLegenda(Base):
    def setUp(self):
        super().setUp()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=540x960:r=30:d=8", "-f", "lavfi", "-i", "sine=d=8",
                        "-shortest", "-pix_fmt", "yuv420p", str(self.dir / "a.mp4")], check=True)
        (self.dir / "inspecao.json").write_text(json.dumps({"videos": [{"arquivo": str(self.dir / "a.mp4"), "nome": "a.mp4", "fps": "30/1",
                                                                         "largura": 540, "altura": 960, "hdr": False, "duracao": 8.0}]}))
        montar(self.dir, trechos=[{"video": 0, "inicio": 0.0, "fim": 8.0, "texto": ""}], duracao=8.0)
        legendas_de_teste(self.dir)
        self.marca = carregar_marca()

    def test_a_previa_sai_do_tamanho_certo_com_a_legenda_desenhada(self):
        import cv2
        arq = revisao.previa_legenda(self.dir, 0, self.marca, self.dir / "previas")
        img = cv2.imread(str(arq))
        self.assertEqual(img.shape[:2], (768, 432))
        # o mesmo quadro sem legenda: a diferença está na faixa onde a legenda cai (y = 1459 de 1920 = 76%)
        bruto = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-ss", "1.05", "-i", str(self.dir / "a.mp4"), "-frames:v", "1",
                                "-vf", "scale=540:960:force_original_aspect_ratio=increase,crop=540:960,format=yuv420p,scale=432:-2",
                                "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
        sem = cv2.imdecode(np.frombuffer(bruto, np.uint8), cv2.IMREAD_COLOR)
        diferenca = np.abs(img.astype(int) - sem.astype(int)).sum(axis=2)
        faixa = diferenca[int(768 * 0.66):int(768 * 0.80)]
        fora = diferenca[:int(768 * 0.50)]
        # o JPEG mexe um pouco em todo o quadro; a legenda mexe muito mais na faixa em que ela cai
        self.assertGreater(float(faixa.mean()), 4 * float(fora.mean()), (float(faixa.mean()), float(fora.mean())))

    def test_texto_diferente_gera_previa_diferente_e_o_cache_se_repete(self):
        a = revisao.previa_legenda(self.dir, 0, self.marca, self.dir / "previas")
        self.assertEqual(a, revisao.previa_legenda(self.dir, 0, self.marca, self.dir / "previas"))
        revisao.editar_bloco(self.dir, 0, "Outra coisa")
        b = revisao.previa_legenda(self.dir, 0, self.marca, self.dir / "previas")
        self.assertNotEqual(a, b)
        with self.assertRaises(revisao.Recusado):
            revisao.previa_legenda(self.dir, 99, self.marca, self.dir / "previas")


# ---------- pela API e na tela ----------

import test_fase5  # noqa: E402
import editar  # noqa: E402


def edicao_de_teste(servidor, nome="teste"):
    """Uma edição orquestrada com cortes, legenda e um vídeo de verdade, pronta para revisar."""
    video = servidor.raiz / "material-bruto" / "a.mov"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=s=540x960:r=30:d=16", "-f", "lavfi", "-i", "sine=f=330:d=16",
                    "-shortest", "-pix_fmt", "yuv420p", str(video)], check=True)
    pasta = editar.novo([video], None, None, nome, base=servidor.raiz / "saida")
    (pasta / "transcricoes").mkdir(exist_ok=True)
    (pasta / "transcricoes" / "a.json").write_text(json.dumps({"palavras": PALAVRAS}))
    cortes = {"videos": [{"id": 0, "arquivo": str(video), "duracao": 16.0}],
              "trechos": [{"video": 0, "inicio": 0.93, "fim": 2.5, "texto": ""}, {"video": 0, "inicio": 3.93, "fim": 6.0, "texto": ""},
                          {"video": 0, "inicio": 7.93, "fim": 9.2, "texto": ""}, {"video": 0, "inicio": 11.93, "fim": 14.0, "texto": ""}],
              "removidos": [], "conferir": [], "duracao_original": 16.0, "duracao_final": 7.05}
    (pasta / "cortes.json").write_text(json.dumps(cortes))
    (pasta / "inspecao.json").write_text(json.dumps({"videos": [{"arquivo": str(video), "nome": "a.mov", "fps": "30/1", "largura": 540,
                                                                  "altura": 960, "hdr": False, "duracao": 16.0}]}))
    legendas_de_teste(pasta)
    return pasta


class TestApi(unittest.TestCase):
    def setUp(self):
        self.s = test_fase5.Servidor()
        self.pasta = edicao_de_teste(self.s)
        self.nome = self.pasta.name

    def tearDown(self):
        self.s.fechar()

    def ler(self, caminho, **kw):
        return self.s.pedir("GET", caminho, **kw)

    def test_leituras_exigem_sessao(self):
        for caminho in (f"/api/cortes?pasta={self.nome}", f"/api/legenda?pasta={self.nome}", f"/api/ouvir?pasta={self.nome}&p=0:1:2",
                        f"/api/legenda/previa?pasta={self.nome}&i=0"):
            self.assertEqual(self.ler(caminho, sessao=False)[0], 401, caminho)
        for rota in ("/api/cortes/alternar", "/api/cortes/desfazer", "/api/legenda/editar", "/api/legenda/substituir", "/api/legenda/desfazer"):
            self.assertEqual(self.s.post(rota, {"pasta": self.nome}, sessao=False)[0], 401, rota)

    def test_cortes_tirar_desfazer_e_meta(self):
        st, _, d = self.ler(f"/api/cortes?pasta={self.nome}")
        self.assertEqual(st, 200)
        u = next(x for x in d["unidades"] if x["texto"].startswith("Isso"))
        self.assertTrue(u["fica"])
        antes = d["duracao_final"]
        st, _, r = self.s.post("/api/cortes/alternar", {"pasta": self.nome, "video": 0, "k0": u["k0"], "k1": u["k1"], "acao": "tirar"})
        self.assertEqual(st, 200, r)
        p = r["painel"]
        self.assertLess(p["duracao_final"], antes)
        self.assertEqual(p["desfazer"], 1)
        self.assertFalse(next(x for x in p["unidades"] if x["id"] == u["id"])["fica"])
        st, _, r = self.s.post("/api/cortes/desfazer", {"pasta": self.nome})
        self.assertEqual((st, r["painel"]["desfazer"]), (200, 0))
        self.assertAlmostEqual(r["painel"]["duracao_final"], antes, places=2)
        self.assertEqual(self.s.post("/api/cortes/desfazer", {"pasta": self.nome})[0], 409)             # nada para desfazer
        self.assertEqual(self.s.post("/api/ajustar", {"pasta": self.nome, "chave": "meta_duracao", "valor": 60})[0], 200)
        self.assertEqual(self.ler(f"/api/cortes?pasta={self.nome}")[2]["meta"], 60)
        self.assertEqual(self.s.post("/api/ajustar", {"pasta": self.nome, "chave": "meta_duracao", "valor": 5})[0], 400)
        self.assertEqual(self.s.post("/api/ajustar", {"pasta": self.nome, "chave": "meta_duracao", "valor": None})[0], 200)
        self.assertIsNone(self.ler(f"/api/cortes?pasta={self.nome}")[2]["meta"])

    def test_pedidos_ruins_sao_recusados_sem_mexer_nos_cortes(self):
        original = (self.pasta / "cortes.json").read_text()
        for corpo in ({"video": 9, "k0": 0, "k1": 1, "acao": "tirar"}, {"video": 0, "k0": -1, "k1": 1, "acao": "tirar"},
                      {"video": 0, "k0": 0, "k1": 9999, "acao": "tirar"}, {"video": 0, "k0": "x", "k1": 1, "acao": "tirar"},
                      {"video": 0, "k0": 0, "k1": 1, "acao": "apagar"}, {"video": 0, "k0": 0, "k1": 1}):
            self.assertEqual(self.s.post("/api/cortes/alternar", {"pasta": self.nome, **corpo})[0], 400, corpo)
        self.assertEqual((self.pasta / "cortes.json").read_text(), original)
        for pasta in ("../x", "..", "nao-existe", None):
            self.assertIn(self.ler(f"/api/cortes?pasta={pasta}")[0], (400, 404))

    def test_edicao_ocupada_recebe_409_mas_a_leitura_continua(self):
        self.s.fila.ocupada = lambda p: True
        self.assertEqual(self.s.post("/api/cortes/alternar", {"pasta": self.nome, "video": 0, "k0": 0, "k1": 1, "acao": "tirar"})[0], 409)
        self.assertEqual(self.s.post("/api/legenda/editar", {"pasta": self.nome, "indice": 0, "texto": "x"})[0], 409)
        self.assertEqual(self.ler(f"/api/cortes?pasta={self.nome}")[0], 200)

    def test_ouvir_so_do_que_esta_nos_cortes(self):
        st, h, corpo = self.ler(f"/api/ouvir?pasta={self.nome}&p=0:1.0:2.0&p=0:5.0:5.8")
        self.assertEqual((st, h["Content-Type"]), (200, "audio/mp4"))
        for ruim in ("p=1:0:1", "p=0:-1:1", "p=0:2:1", "p=0:0:99", "p=../etc:0:1", "p=0:0", "p=0:a:b", "p=/etc/passwd:0:1", ""):
            self.assertIn(self.ler(f"/api/ouvir?pasta={self.nome}&{ruim}")[0], (400, 404), ruim)
        mais = "&".join("p=0:0:1" for _ in range(7))
        self.assertEqual(self.ler(f"/api/ouvir?pasta={self.nome}&{mais}")[0], 400)

    def test_legenda_editar_atualiza_o_srt_e_desfaz(self):
        st, _, r = self.s.post("/api/legenda/editar", {"pasta": self.nome, "indice": 1, "texto": "meta bem clara"})
        self.assertEqual(st, 200, r)
        self.assertEqual(r["painel"]["blocos"][1]["texto"], "meta bem clara")
        self.assertIn("meta bem clara", (self.pasta / "legendas.srt").read_text(encoding="utf-8"))        # o legendas.py de verdade rodou
        self.assertIn("meta bem clara", (self.pasta / "legendas.ass").read_text(encoding="utf-8").replace("\\N", " "))
        self.assertEqual(r["painel"]["desfazer"], 1)
        st, _, r = self.s.post("/api/legenda/desfazer", {"pasta": self.nome})
        self.assertEqual(st, 200)
        self.assertEqual(r["painel"]["blocos"][1]["texto"], "meta clara")
        self.assertNotIn("meta bem clara", (self.pasta / "legendas.srt").read_text(encoding="utf-8"))
        for corpo in ({"indice": 99, "texto": "x"}, {"indice": 0, "texto": ""}, {"indice": 0, "texto": "x" * 200}, {"indice": "a", "texto": "x"}):
            self.assertEqual(self.s.post("/api/legenda/editar", {"pasta": self.nome, **corpo})[0], 400, corpo)

    def test_legenda_corrigir_em_todos_e_previa(self):
        st, _, r = self.s.post("/api/legenda/substituir", {"pasta": self.nome, "de": "meta", "para": "objetivo"})
        self.assertEqual((st, r["mudou"]), (200, 1))
        self.assertEqual(self.s.post("/api/legenda/substituir", {"pasta": self.nome, "de": "nada", "para": "x"})[2]["mudou"], 0)
        st, h, corpo = self.s.pedir("GET", f"/api/legenda/previa?pasta={self.nome}&i=0")
        self.assertEqual((st, h["Content-Type"]), (200, "image/jpeg"))
        self.assertEqual(self.s.pedir("GET", f"/api/legenda/previa?pasta={self.nome}&i=99")[0], 400)
        self.assertEqual(self.s.pedir("GET", f"/api/legenda/previa?pasta={self.nome}&i=abc")[0], 400)

    def test_nada_do_navegador_vira_caminho_de_arquivo(self):
        for parametro in ("arquivo=/etc/passwd", "video=/etc/passwd", "caminho=../../x", "c=../../x"):
            st, h, _ = self.ler(f"/api/ouvir?pasta={self.nome}&{parametro}&p=0:0:1")
            self.assertEqual(st, 200)                              # o parâmetro desconhecido é ignorado; o vídeo vem do cortes.json
        self.assertFalse((self.s.raiz / ".painel" / "ouvir").exists() and any("passwd" in p.name for p in (self.s.raiz / ".painel" / "ouvir").iterdir()))


class TestTelaDeRevisao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright
            from elementos import abrir_navegador
        except ImportError:
            raise unittest.SkipTest("sem playwright")
        cls.pw = sync_playwright().start()
        try:
            cls.nav = abrir_navegador(cls.pw)
        except SystemExit:
            cls.pw.stop()
            raise unittest.SkipTest("sem navegador")

    @classmethod
    def tearDownClass(cls):
        cls.nav.close()
        cls.pw.stop()

    def abrir(self, s):
        ctx = self.nav.new_context(viewport={"width": 1100, "height": 900})
        ctx.add_cookies([{"name": "painel", "value": s.codigo, "domain": "localhost", "path": "/"}])
        pg = ctx.new_page()
        pg.goto(f"http://localhost:{s.porta}/")
        return ctx, pg

    def test_cortes_clicar_tira_e_a_duracao_muda_ao_vivo(self):
        s = test_fase5.Servidor()
        try:
            pasta = edicao_de_teste(s)
            ctx, pg = self.abrir(s)
            pg.wait_for_selector("button[data-acao='revisar'][data-tipo='cortes']", timeout=10000)
            pg.click("button[data-acao='revisar'][data-tipo='cortes']")
            pg.wait_for_selector(".un", timeout=8000)
            antes = pg.inner_text("#rev-duracao")
            self.assertIn("Duração", antes)
            self.assertEqual(pg.locator(".un.sai").count(), 0)
            self.assertTrue(pg.is_disabled("#rev-desfazer"))
            pg.click(".un:has-text('Isso funciona')")
            pg.wait_for_selector(".un.sai", timeout=8000)
            self.assertNotEqual(pg.inner_text("#rev-duracao"), antes)
            self.assertFalse(pg.is_disabled("#rev-desfazer"))
            self.assertTrue(pg.locator("button.emenda").count() >= 1)                # as junções aparecem
            pg.click("#rev-desfazer")
            pg.wait_for_function("document.querySelectorAll('.un.sai').length === 0", timeout=8000)
            self.assertEqual(pg.inner_text("#rev-duracao"), antes)
            pg.check("#rev-so")                                                       # só suspeitas: sobra a unidade do fim da gravação
            self.assertGreaterEqual(pg.locator(".un").count(), 1)
            self.assertLess(pg.locator(".un").count(), 6)
            pg.fill("#rev-meta", "10")
            pg.dispatch_event("#rev-meta", "change")
            pg.wait_for_function("document.querySelector('#rev-duracao').innerText.includes('meta')", timeout=8000)
            self.assertIn("cabe, sobram", pg.inner_text("#rev-duracao"))               # 0:07 de 0:10
            pg.fill("#rev-meta", "5")                                                  # abaixo do mínimo: o servidor recusa e a tela avisa
            pg.dispatch_event("#rev-meta", "change")
            pg.wait_for_function("document.querySelector('#copiado').innerText.includes('de 10 a 600')", timeout=8000)
            ctx.close()
        finally:
            s.fechar()

    def test_legenda_editar_atualiza_a_previa(self):
        s = test_fase5.Servidor()
        try:
            pasta = edicao_de_teste(s)
            ctx, pg = self.abrir(s)
            pg.wait_for_selector("button[data-acao='revisar'][data-tipo='legenda']", timeout=10000)
            pg.click("button[data-acao='revisar'][data-tipo='legenda']")
            pg.wait_for_selector("input[data-texto='1']", timeout=8000)
            src = pg.get_attribute(".leg-linha[data-bloco='1'] img", "src")
            pg.fill("input[data-texto='1']", "meta bem clara")
            pg.press("input[data-texto='1']", "Enter")
            pg.wait_for_function("document.querySelector(\".leg-linha[data-bloco='1'] img\").src !== arguments[0]", arg=src if False else None, timeout=1) if False else None
            pg.wait_for_function("(v) => document.querySelector(\".leg-linha[data-bloco='1'] img\").getAttribute('src') !== v", arg=src, timeout=10000)
            self.assertIn("meta bem clara", (pasta / "legendas.srt").read_text(encoding="utf-8"))
            self.assertIn("número", pg.inner_text(".leg-linha[data-bloco='2']"))
            self.assertIn("movida", pg.inner_text(".leg-linha[data-bloco='3']"))
            self.assertEqual(pg.input_value("input[data-texto='1']"), "meta bem clara")
            pg.fill("#troca-de", "meta")
            pg.fill("#troca-para", "objetivo")
            pg.click("#troca-ir")
            pg.wait_for_function("document.querySelector(\"input[data-texto='1']\").value.includes('objetivo')", timeout=10000)
            pg.click("#rev-desfazer")
            pg.wait_for_function("!document.querySelector(\"input[data-texto='1']\").value.includes('objetivo')", timeout=10000)
            ctx.close()
        finally:
            s.fechar()


if __name__ == "__main__":
    unittest.main()
