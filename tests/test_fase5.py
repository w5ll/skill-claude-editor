"""Testes da Fase 5 (painel que executa). Rodar: .venv/bin/python -m unittest discover -s tests -v

Servidor de verdade numa porta livre, com um executor de mentira no lugar dos scripts de edição.
"""

import http.client
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "welldit" / "scripts"))

import editar  # noqa: E402
import fila as modulo_fila  # noqa: E402
import painel as modulo_painel  # noqa: E402
import painel_seguranca  # noqa: E402
from comum import carregar_marca  # noqa: E402
from test_fase4 import INSPECAO, Falso  # noqa: E402

CABECALHOS_OK = {"X-Painel": "1", "Content-Type": "application/json"}


class Bloqueia(Falso):
    """Como o executor de mentira, mas fica esperando numa etapa (para testar fila, cancelar e 409)."""

    def __init__(self, job, onde="transcrever.py", segura: threading.Event | None = None):
        super().__init__()
        self.job, self.onde, self.segura = job, onde, segura
        self.parou = threading.Event()

    def __call__(self, argv, log):
        if argv[0] == self.onde and self.segura is not None:
            self.parou.set()
            while not self.segura.is_set():
                if self.job["cancelar"].is_set():
                    raise editar.Cancelado()
                time.sleep(0.01)
        return super().__call__(argv, log)


class Servidor:
    def __init__(self, fabrica=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)
        self.falso = Falso()
        fabrica = fabrica or (lambda job: self.falso)
        self.fila = modulo_fila.Fila(fabrica_de_executor=fabrica)
        self.abertas: list[Path] = []
        self.painel = modulo_painel.Painel(self.raiz, fila=self.fila, abrir=self.abertas.append)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), modulo_painel.criar_handler(self.painel, carregar_marca()))
        self.porta = self.httpd.server_address[1]
        self.painel.sessao = painel_seguranca.Sessao(self.porta)
        self.codigo = self.painel.sessao.codigo
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.cookie = f"painel={self.codigo}"

    def fechar(self):
        self.fila.parar()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def pedir(self, metodo, caminho, corpo=None, cabecalhos=None, sessao=True, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=15)
        h = {"Host": host or f"localhost:{self.porta}"}
        if sessao:
            h["Cookie"] = self.cookie
        h.update(cabecalhos or {})
        dados = corpo if isinstance(corpo, (bytes, type(None))) else json.dumps(corpo).encode()
        c.request(metodo, caminho, body=dados, headers=h)
        r = c.getresponse()
        bruto = r.read()
        c.close()
        try:
            texto = json.loads(bruto)
        except ValueError:
            texto = bruto.decode("utf-8", "replace")
        return r.status, dict(r.getheaders()), texto

    def post(self, caminho, corpo, **kw):
        return self.pedir("POST", caminho, corpo, {**CABECALHOS_OK, **kw.pop("cabecalhos", {})}, **kw)

    def caminho(self, pasta):
        return (self.raiz / "saida" / pasta).resolve()

    def video(self, nome="a.mov"):
        (self.raiz / "material-bruto" / nome).write_bytes(b"video")
        return nome

    def estado(self):
        return self.pedir("GET", "/api/estado")[2]

    def trabalho(self, nome):
        return next(t for t in self.estado()["trabalhos"] if t["nome"] == nome)


class Base(unittest.TestCase):
    def setUp(self):
        self.s = Servidor()

    def tearDown(self):
        self.s.fechar()

    def novo(self, **kw):
        self.s.video()
        st, _, d = self.s.post("/api/novo", {"videos": ["a.mov"], "tema": kw.get("tema", "teste"), "iniciar": kw.get("iniciar", True)})
        self.assertEqual(st, 200, d)
        self.assertTrue(self.s.fila.esperar_ociosa())
        return d["pasta"]


class TestSessao(unittest.TestCase):
    def test_conferencias_isoladas(self):
        s = painel_seguranca.Sessao(8765, "segredo")
        self.assertTrue(s.host_ok("localhost:8765") and s.host_ok("127.0.0.1:8765") and s.host_ok("LOCALHOST:8765"))
        for ruim in (None, "", "localhost", "localhost:9999", "evil.com:8765", "localhost.evil.com:8765", "localhost:8765.evil.com"):
            self.assertFalse(s.host_ok(ruim), ruim)
        self.assertTrue(s.origem_ok(None) and s.origem_ok("http://localhost:8765"))
        for ruim in ("http://evil.com", "http://localhost:9999", "null", "https://localhost:8765"):
            self.assertFalse(s.origem_ok(ruim), ruim)
        self.assertTrue(s.codigo_ok("segredo"))
        self.assertFalse(s.codigo_ok("segredO") or s.codigo_ok("") or s.codigo_ok(None))
        self.assertTrue(s.cookie_ok("outro=1; painel=segredo"))
        for ruim in (None, "", "painel=errado", "painel", ";;;", "x=y"):
            self.assertFalse(s.cookie_ok(ruim), repr(ruim))
        self.assertTrue(s.cabecalho_ok("1"))
        self.assertFalse(s.cabecalho_ok(None) or s.cabecalho_ok("0") or s.cabecalho_ok("true"))
        cookie = s.set_cookie()
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertNotIn("segredo", s.endereco().replace("?s=segredo", ""))

    def test_o_codigo_muda_a_cada_sessao(self):
        self.assertNotEqual(painel_seguranca.Sessao(1).codigo, painel_seguranca.Sessao(1).codigo)
        self.assertGreaterEqual(len(painel_seguranca.Sessao(1).codigo), 24)


class TestSeguranca(Base):
    def test_sem_sessao_nada_responde(self):
        for caminho in ("/api/estado", "/arquivo?c=material-bruto/a.mov", "/miniatura?c=x"):
            self.assertEqual(self.s.pedir("GET", caminho, sessao=False)[0], 401, caminho)
        st, _, corpo = self.s.pedir("GET", "/", sessao=False)
        self.assertEqual(st, 401)
        self.assertIn("sessão", corpo)
        self.assertNotIn("Nova edição", corpo)
        self.assertEqual(self.s.pedir("PUT", "/api/enviar?nome=x.mov", b"abc", CABECALHOS_OK, sessao=False)[0], 401)
        self.assertEqual(self.s.post("/api/novo", {"videos": ["a.mov"]}, sessao=False)[0], 401)
        self.assertEqual(self.s.pedir("GET", "/marca.json", sessao=False)[0], 200)        # só a aparência

    def test_codigo_certo_vira_cookie_e_some_do_endereco(self):
        st, h, _ = self.s.pedir("GET", "/?s=errado", sessao=False)
        self.assertEqual(st, 401)
        self.assertNotIn("Set-Cookie", h)
        st, h, _ = self.s.pedir("GET", f"/?s={self.s.codigo}", sessao=False)
        self.assertEqual(st, 302)
        self.assertEqual(h["Location"], "/")
        self.assertIn("HttpOnly", h["Set-Cookie"])
        self.assertIn("SameSite=Strict", h["Set-Cookie"])
        st, _, corpo = self.s.pedir("GET", "/")
        self.assertEqual(st, 200)
        self.assertIn("Nova edição", corpo)

    def test_host_trocado_e_recusado_mesmo_com_sessao(self):
        for host in ("evil.example:%d" % self.s.porta, "localhost.evil.com:%d" % self.s.porta, "localhost:1"):
            self.assertEqual(self.s.pedir("GET", "/api/estado", host=host)[0], 403, host)
            self.assertEqual(self.s.pedir("GET", "/", host=host, sessao=False)[0], 403, host)

    def test_pedido_que_muda_algo_exige_cabecalho_e_origem(self):
        corpo = {"pasta": "nada"}
        self.assertEqual(self.s.pedir("POST", "/api/cancelar", corpo, {"Content-Type": "application/json"})[0], 403)     # sem X-Painel
        self.assertEqual(self.s.post("/api/cancelar", corpo, cabecalhos={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.s.post("/api/cancelar", corpo, cabecalhos={"Origin": "null"})[0], 403)
        st = self.s.post("/api/cancelar", corpo, cabecalhos={"Origin": f"http://localhost:{self.s.porta}"})[0]
        self.assertEqual(st, 404)                          # passou nas conferências; recusado pelo conteúdo (a edição não existe)

    def test_nao_existe_comando_livre(self):
        for rota in ("/api/executar", "/api/comando", "/api/shell", "/api/rodar", "/api/proximo", "/api"):
            self.assertEqual(self.s.post(rota, {"comando": "ls", "args": ["-la"]})[0], 404, rota)
        self.assertEqual(self.s.pedir("OPTIONS", "/api/novo")[0], 501)                 # sem CORS: nada de outros sites
        self.assertEqual(sorted(modulo_painel.Acoes.ROTAS.values()),
                         sorted(["novo", "aprovar", "iniciar", "cancelar", "ajustar", "refazer", "aprovar_entrega", "abrir_pasta",
                                 "cortes_alternar", "cortes_desfazer", "legenda_editar", "legenda_substituir", "legenda_desfazer",
                                 # Fase 7: elementos, zoom, som e conferência
                                 "elementos_tirar", "elementos_trocar", "elementos_rotulo", "elementos_tempo", "elementos_modo",
                                 "elementos_adicionar", "elementos_promover", "elementos_desfazer", "zoom_nivel", "zoom_tirar_enfase",
                                 "zoom_desfazer", "som_musica", "som_ganho", "som_trocar", "som_tirar", "som_desfazer",
                                 "conferencia_aceitar_pausa", "conferencia_aplicar_ganho",
                                 # Fase 8: Claude por trás
                                 "claude_pedir", "claude_cancelar", "claude_aplicar", "claude_descartar", "claude_ligar"]))

    def test_corpo_invalido_ou_grande(self):
        self.assertEqual(self.s.pedir("POST", "/api/novo", b"{nao json", CABECALHOS_OK)[0], 400)
        self.assertEqual(self.s.pedir("POST", "/api/novo", b"[1, 2]", CABECALHOS_OK)[0], 400)
        grande = {**CABECALHOS_OK, "Content-Length": "70000"}               # só o cabeçalho: o servidor recusa sem ler o corpo
        self.assertEqual(self.s.pedir("POST", "/api/novo", b"", grande)[0], 413)


class TestValidacao(Base):
    def test_videos_e_nomes_perigosos(self):
        self.s.video()
        for videos in (["../a.mov"], ["a.mov/../../x"], [""], [123], "a.mov", [], ["nao-existe.mov"], ["a.mov"] * 9, ["a.txt"]):
            st, _, d = self.s.post("/api/novo", {"videos": videos})
            self.assertIn(st, (400, 404), (videos, d))
        (self.s.raiz / "material-bruto" / "a.txt").write_text("x")
        self.assertEqual(self.s.post("/api/novo", {"videos": ["a.txt"]})[0], 404)
        self.assertEqual(self.s.post("/api/novo", {"videos": ["a.mov"], "serie": "../../etc"})[0], 400)
        self.assertEqual(self.s.post("/api/novo", {"videos": ["a.mov"], "perfil": "nao-existe"})[0], 400)
        self.assertEqual(self.s.post("/api/novo", {"videos": ["a.mov"], "tema": "x" * 100})[0], 400)
        self.assertEqual(list((self.s.raiz / "saida").iterdir()), [])                 # nada foi criado

    def test_nome_de_edicao_nao_sai_da_pasta(self):
        for nome in ("..", "../material-bruto", "a/b", "", None, "x" * 200, "..\\x", "%2e%2e"):
            for rota in ("/api/aprovar", "/api/iniciar", "/api/cancelar", "/api/refazer", "/api/abrir-pasta"):
                st = self.s.post(rota, {"pasta": nome, "etapa": "rosto"})[0]
                self.assertIn(st, (400, 404), (rota, nome))
        self.assertEqual(self.s.abertas, [])

    def test_escolhas_so_da_lista(self):
        pasta = self.novo()
        for chave, valor in (("camera", "enorme"), ("ritmo", "rapido"), ("formato", "9:16; rm -rf"), ("legenda.palavras", 99),
                             ("legenda.palavras", True), ("som.efeitos", "sim"), ("som.musica", "../x"), ("volume", -3),
                             ("perfil", "x"), ("videos", []), ("etapas", {})):
            st, _, d = self.s.post("/api/ajustar", {"pasta": pasta, "chave": chave, "valor": valor})
            self.assertEqual(st, 400, (chave, valor, d))
        st, _, d = self.s.post("/api/ajustar", {"pasta": pasta, "chave": "camera", "valor": "leve"})
        self.assertEqual(st, 200, d)
        self.assertEqual(editar.carregar(self.s.caminho(pasta))["escolhas"]["camera"], "leve")

    def test_refazer_so_etapa_conhecida(self):
        pasta = self.novo()
        self.assertEqual(self.s.post("/api/refazer", {"pasta": pasta, "etapa": "rm -rf"})[0], 400)
        self.assertEqual(self.s.post("/api/refazer", {"pasta": pasta, "etapa": "rosto"})[0], 200)

    def test_entrega_so_versao_do_video_inteiro(self):
        pasta = self.novo()
        for arq in ("../x.mp4", "amostra-v001.mp4", "qualquer.txt", "x-v001.mp4", 5, None):
            self.assertIn(self.s.post("/api/aprovar-entrega", {"pasta": pasta, "arquivo": arq})[0], (400, 404), arq)

    def test_edicao_feita_so_na_conversa_nao_tem_acoes(self):
        antiga = self.s.raiz / "saida" / "2026-01-01_antiga"
        antiga.mkdir()
        (antiga / "inspecao.json").write_text(json.dumps(INSPECAO))
        self.assertEqual(self.s.post("/api/iniciar", {"pasta": "2026-01-01_antiga"})[0], 400)
        t = self.s.trabalho("2026-01-01_antiga")
        self.assertIsNone(t["orq"])                       # o painel antigo continua mostrando
        self.assertEqual(t["videos"], ["a.mov"])


class TestFluxo(Base):
    def test_do_bruto_ate_a_entrega_so_pela_api(self):
        pasta = self.novo()
        t = self.s.trabalho(pasta)
        g = t["orq"]["portao"]
        self.assertEqual(g["nome"], "cartao")
        pend = g["cartao"]["pendencias"]
        self.assertEqual([p["id"] for p in pend], ["hdr", "ruido"])
        self.assertTrue(all(sum(o["recomendada"] for o in p["opcoes"]) == 1 for p in pend))      # tem recomendado
        self.assertEqual(t["orq"]["posicao"], None)
        # resposta incompleta: recusada e nada muda
        st, _, d = self.s.post("/api/aprovar", {"pasta": pasta, "portao": "cartao", "resposta": "A"})
        self.assertEqual(st, 400)
        self.assertIn("faltam respostas", d["erro"])
        self.assertEqual(self.s.trabalho(pasta)["orq"]["portao"]["nome"], "cartao")
        # com ajustes rápidos junto
        st, _, d = self.s.post("/api/aprovar", {"pasta": pasta, "portao": "cartao", "resposta": "A,C",
                                                "escolhas": [{"chave": "camera", "valor": "leve"}]})
        self.assertEqual(st, 200, d)
        self.assertTrue(self.s.fila.esperar_ociosa())
        t = self.s.trabalho(pasta)
        self.assertEqual(t["orq"]["portao"]["nome"], "cortes")
        self.assertEqual(t["orq"]["escolhas"]["camera"], "leve")
        self.assertEqual(t["orq"]["escolhas"]["hdr"], "sdr")
        for _ in range(8):
            g = self.s.trabalho(pasta)["orq"]["portao"]
            if not g:
                break
            self.assertEqual(self.s.post("/api/aprovar", {"pasta": pasta, "portao": g["nome"]})[0], 200)
            self.assertTrue(self.s.fila.esperar_ociosa())
        t = self.s.trabalho(pasta)
        self.assertEqual(t["orq"]["etapas"]["entrega"]["situacao"], "feita")
        versao = next(v["nome"] for v in t["versoes"] if not v["amostra"])
        st, _, d = self.s.post("/api/aprovar-entrega", {"pasta": pasta, "arquivo": versao})
        self.assertEqual(st, 200, d)
        self.assertEqual(self.s.trabalho(pasta)["orq"]["entrega_aprovada"]["arquivo"], versao)

    def test_portao_errado_ou_inexistente(self):
        pasta = self.novo()
        st, _, d = self.s.post("/api/aprovar", {"pasta": pasta, "portao": "cortes", "resposta": "A,C"})
        self.assertEqual(st, 400)
        self.assertIn("cartao", d["erro"])

    def test_abrir_pasta_so_de_edicao_valida(self):
        pasta = self.novo()
        self.assertEqual(self.s.post("/api/abrir-pasta", {"pasta": pasta})[0], 200)
        self.assertEqual([p.resolve() for p in self.s.abertas], [self.s.caminho(pasta)])


class TestFilaEConcorrencia(unittest.TestCase):
    def test_uma_edicao_por_vez_na_ordem_de_chegada(self):
        eventos = []
        trava = threading.Event()

        def proximo(pasta, executor, saida):
            eventos.append(("inicio", pasta.name))
            trava.wait(5)
            eventos.append(("fim", pasta.name))
            return "fim"

        f = modulo_fila.Fila(proximo=proximo)
        try:
            p = [Path(f"/x/{n}") for n in "abc"]
            self.assertEqual(f.enfileirar(p[0]), "rodando")
            time.sleep(0.1)
            self.assertEqual(f.enfileirar(p[1]), "na_fila")
            self.assertEqual(f.enfileirar(p[2]), "na_fila")
            self.assertEqual(f.enfileirar(p[1]), "ja_esta")                       # não duplica
            self.assertEqual([f.posicao(x) for x in p], [0, 1, 2])
            self.assertEqual(eventos, [("inicio", "a")])                         # as outras esperam
            self.assertTrue(f.cancelar(p[1]))                                    # tirar da fila
            trava.set()
            self.assertTrue(f.esperar_ociosa())
            self.assertEqual(eventos, [("inicio", "a"), ("fim", "a"), ("inicio", "c"), ("fim", "c")])
        finally:
            f.parar()

    def test_acao_na_edicao_ocupada_recebe_409(self):
        segura = threading.Event()
        s = Servidor(lambda job: Bloqueia(job, segura=segura))
        try:
            s.video()
            st, _, d = s.post("/api/novo", {"videos": ["a.mov"], "tema": "ocupada"})
            pasta = d["pasta"]
            time.sleep(0.3)                                  # a inspeção roda e abre o cartão; aprovar começa a transcrever
            self.assertTrue(s.fila.esperar_ociosa())
            self.assertEqual(s.post("/api/aprovar", {"pasta": pasta, "portao": "cartao", "resposta": "A,C"})[0], 200)
            time.sleep(0.3)                                  # parada na transcrição
            self.assertEqual(s.fila.posicao(s.caminho(pasta)), 0)
            for rota, corpo in (("/api/iniciar", {}), ("/api/aprovar", {}), ("/api/ajustar", {"chave": "camera", "valor": "leve"}),
                                ("/api/refazer", {"etapa": "rosto"}), ("/api/aprovar-entrega", {"arquivo": "x-v001.mp4"})):
                self.assertEqual(s.post(rota, {"pasta": pasta, **corpo})[0], 409, rota)
            t = s.trabalho(pasta)
            self.assertEqual(t["orq"]["posicao"], 0)
            self.assertEqual(s.post("/api/cancelar", {"pasta": pasta})[0], 200)       # cancelar deixa a etapa interrompida
            self.assertTrue(s.fila.esperar_ociosa())
            t = s.trabalho(pasta)
            self.assertEqual(t["orq"]["etapas"]["transcrever"]["situacao"], "interrompida")
            self.assertEqual(s.post("/api/cancelar", {"pasta": pasta})[0], 409)       # nada para cancelar
            segura.set()
            self.assertEqual(s.post("/api/iniciar", {"pasta": pasta})[0], 200)       # retomar continua de onde parou
            self.assertTrue(s.fila.esperar_ociosa())
            self.assertEqual(s.trabalho(pasta)["orq"]["portao"]["nome"], "cortes")
        finally:
            segura.set()
            s.fechar()

    def test_cancelar_mata_o_grupo_de_processos_de_verdade(self):
        with tempfile.TemporaryDirectory() as d:
            scripts = Path(d)
            (scripts / "dorme.py").write_text(
                "import subprocess, sys, time\n"
                "filho = subprocess.Popen(['sleep', '60'])\n"
                "open(sys.argv[1], 'w').write(str(filho.pid))\n"
                "time.sleep(60)\n")
            job = {"cancelar": threading.Event(), "processo": None}
            executar = modulo_fila.executor_cancelavel(job, scripts)
            resultado = {}

            def roda():
                try:
                    executar(["dorme.py", str(scripts / "filho.pid")], scripts / "log.txt")
                except editar.Cancelado:
                    resultado["cancelado"] = True

            t = threading.Thread(target=roda)
            t.start()
            for _ in range(100):
                if (scripts / "filho.pid").exists() and job["processo"] is not None:
                    break
                time.sleep(0.05)
            pid_filho = int((scripts / "filho.pid").read_text())
            job["cancelar"].set()
            modulo_fila.matar(job["processo"])
            t.join(10)
            self.assertTrue(resultado.get("cancelado"))
            time.sleep(0.3)
            with self.assertRaises(OSError):
                os.kill(pid_filho, 0)                          # o processo filho também morreu


class TestTela(unittest.TestCase):
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
        ctx = self.nav.new_context()
        ctx.add_cookies([{"name": "painel", "value": s.codigo, "domain": "localhost", "path": "/"}])
        pagina = ctx.new_page()
        pagina.goto(f"http://localhost:{s.porta}/")
        return ctx, pagina

    def test_cartao_com_o_recomendado_e_aprovar(self):
        s = Servidor()
        try:
            s.video()
            st, _, d = s.post("/api/novo", {"videos": ["a.mov"], "tema": "tela"})
            self.assertTrue(s.fila.esperar_ociosa())
            ctx, pg = self.abrir(s)
            pg.wait_for_selector(".portao input[type=radio]", timeout=8000)
            marcados = pg.eval_on_selector_all(".portao input[type=radio]:checked", "els => els.map(e => e.value)")
            self.assertEqual(marcados, ["A", "C"])                                 # o recomendado já vem marcado
            self.assertIn("Aprovar e começar", pg.inner_text(".portao"))
            pedidos = []
            pg.on("request", lambda r: pedidos.append(r) if r.method == "POST" else None)
            pg.click("details.rapido summary")                                      # "Ajustes rápidos" começa fechado
            pg.select_option("select[data-escolha='camera']", "leve")
            pg.click("button[data-acao='aprovar-cartao']")
            pg.wait_for_function("document.body.innerText.includes('Revisar os cortes')", timeout=10000)
            self.assertEqual(len(pedidos), 1)
            corpo = json.loads(pedidos[0].post_data)
            self.assertEqual((corpo["resposta"], corpo["portao"]), ("A,C", "cartao"))
            self.assertEqual(corpo["escolhas"], [{"chave": "camera", "valor": "leve"}])
            self.assertEqual(pedidos[0].headers.get("x-painel"), "1")
            ctx.close()
        finally:
            s.fechar()

    def test_escolher_videos_e_comecar(self):
        s = Servidor()
        try:
            s.video("um.mov")
            ctx, pg = self.abrir(s)
            pg.wait_for_selector("input[data-usar]", timeout=8000)
            self.assertTrue(pg.is_disabled("#nova-comecar"))
            pg.check("input[data-usar='um.mov']")
            self.assertFalse(pg.is_disabled("#nova-comecar"))
            pg.fill("#nova-tema", "primeira")
            pg.click("#nova-comecar")
            pg.wait_for_selector(".portao", timeout=10000)                       # a inspeção rodou e abriu o cartão
            self.assertIn("primeira", pg.inner_text("#trabalhos"))
            ctx.close()
        finally:
            s.fechar()

    def test_sem_sessao_a_tela_pede_o_codigo(self):
        s = Servidor()
        try:
            ctx = self.nav.new_context()
            pg = ctx.new_page()
            pg.goto(f"http://localhost:{s.porta}/")
            self.assertIn("Código da sessão", pg.inner_text("body"))
            pg.fill("#codigo", s.codigo)
            pg.click("#entrar")
            pg.wait_for_selector("text=Nova edição", timeout=8000)
            ctx.close()
        finally:
            s.fechar()


if __name__ == "__main__":
    unittest.main()
