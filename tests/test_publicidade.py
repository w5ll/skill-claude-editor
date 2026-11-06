"""Testes do modo publicidade (gancho entre todas as frases, roteiro acertado) com fala sintética."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skill" / "welldit" / "scripts"))

import publicidade  # noqa: E402


def falar(texto: str, inicio: float, passo: float = 0.3) -> list[dict]:
    return [{"p": p, "i": round(inicio + k * passo, 3), "f": round(inicio + k * passo + passo * 0.8, 3)}
            for k, p in enumerate(texto.split())]


def um_trecho(frases: list[str], pausa: float = 1.0):
    """Todas as frases num trecho só, com `pausa` segundos de silêncio entre elas."""
    ws, t = [], 1.0
    for f in frases:
        novas = falar(f, t)
        ws += novas
        t = novas[-1]["f"] + pausa
    trecho = {"video": 0, "inicio": 0.5, "fim": round(ws[-1]["f"] + 0.5, 3), "texto": ""}
    return [trecho], [ws]


HOOK = "Se você é advogado e perdeu 5 clientes por mês, a gente resolve isso."
MEIO = "Hoje eu vou falar sobre uma coisa que acontece com a empresa."
FECHO = "Me segue para ver mais."


def ordem(trechos, pal, novos):
    return [t["texto"] for t in novos]


class TestPublicidade(unittest.TestCase):
    def aplicar(self, frases):
        trechos, pal = um_trecho(frases)
        uns = publicidade.unidades(trechos, pal)
        cands = publicidade.candidatas(uns)
        novos = publicidade.puxar(trechos, pal, uns, cands[0]["unidade"])
        return trechos, pal, cands, novos

    def test_o_melhor_gancho_e_a_frase_que_fala_com_a_pessoa_mesmo_no_fim(self):
        trechos, pal, cands, novos = self.aplicar(["Oi pessoal.", MEIO, FECHO, HOOK])
        self.assertEqual(cands[0]["texto"], HOOK)
        self.assertEqual(novos[0]["texto"], HOOK)

    def test_chamada_para_acao_nao_e_gancho_e_fica_no_fim(self):
        trechos, pal, cands, novos = self.aplicar([MEIO, HOOK, FECHO])
        self.assertNotIn(FECHO, [c["texto"] for c in cands])
        self.assertEqual([t["texto"] for t in novos], [HOOK, MEIO, FECHO])

    def test_saudacao_solta_do_comeco_sai_e_nada_fica_repetido(self):
        trechos, pal, cands, novos = self.aplicar(["Oi pessoal.", MEIO, HOOK])
        textos = [t["texto"] for t in novos]
        self.assertEqual(textos, [HOOK, MEIO])
        palavras = " ".join(textos).split()
        self.assertEqual(len(palavras), len(set(range(len(palavras)))))
        self.assertEqual(sorted(palavras), sorted((HOOK + " " + MEIO).split()))

    def test_conectivos_soltos_no_comeco_da_frase_puxada_saem(self):
        trechos, pal, cands, novos = self.aplicar([MEIO, "E, de fato, " + HOOK[0].lower() + HOOK[1:]])
        self.assertTrue(novos[0]["texto"].startswith("se você"), novos[0]["texto"])

    def test_nenhum_corte_cai_dentro_de_uma_palavra(self):
        trechos, pal, cands, novos = self.aplicar(["Oi pessoal.", MEIO, FECHO, HOOK])
        for t in novos:
            for w in pal[0]:
                self.assertFalse(w["i"] < t["inicio"] < w["f"] or w["i"] < t["fim"] < w["f"])

    def test_auto_nao_mexe_quando_o_comeco_ja_prende(self):
        trechos, pal = um_trecho([HOOK, MEIO, FECHO])
        r = publicidade.listar(trechos, pal)
        self.assertTrue(r["candidatas"][0]["e_a_primeira"])

    def test_frase_que_depende_da_anterior_perde_ponto(self):
        trechos, pal = um_trecho([MEIO, "Mas se você é advogado e perdeu 5 clientes, a gente resolve.", HOOK])
        c = publicidade.candidatas(publicidade.unidades(trechos, pal))
        self.assertEqual(c[0]["texto"], HOOK)

    def test_frase_longa_demais_nao_e_candidata(self):
        longa = " ".join(["palavra"] * 150) + "."
        trechos, pal = um_trecho([MEIO, longa, FECHO])
        textos = [c["texto"] for c in publicidade.candidatas(publicidade.unidades(trechos, pal))]
        self.assertNotIn(longa, textos)


class TestOrquestradorPublicidade(unittest.TestCase):
    def test_borda_so_vai_para_o_comando_quando_muda_alguma_coisa(self):
        import editar
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            base = {"escolhas": {"legenda": {"palavras": 3, "posicao": "auto", "tamanho": 0.046}, "formato": "original"}}
            self.assertNotIn("--borda", editar._c_legenda(base, pasta)[0][1])
            limpa = {"escolhas": {**base["escolhas"], "legenda": {**base["escolhas"]["legenda"], "borda": "limpa"}}}
            cmd = editar._c_legenda(limpa, pasta)[0][1]
            self.assertEqual(cmd[cmd.index("--borda") + 1], "limpa")

    def test_publicidade_liga_o_gancho_logo_depois_dos_cortes(self):
        import editar
        t = {"escolhas": {"ritmo": "dinamico", "publicidade": True}}
        self.assertEqual([c[0] for c in editar._c_cortes(t, Path("x"))], ["propor_cortes.py", "publicidade.py"])
        t = {"escolhas": {"ritmo": "dinamico"}}
        self.assertEqual([c[0] for c in editar._c_cortes(t, Path("x"))], ["propor_cortes.py"])


if __name__ == "__main__":
    unittest.main()
