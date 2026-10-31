"""Regrava as referências dos testes (legenda e quadros dos elementos).

Use só quando uma mudança de visual foi de propósito; depois, confira a diferença com `git diff` e `git status`
e explique no pedido de revisão. Uso: python tests/atualizar_referencias.py [legenda] [quadros]
"""

import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))


def legenda():
    import test_legenda
    test_legenda.REFERENCIA.parent.mkdir(exist_ok=True)
    test_legenda.REFERENCIA.write_bytes(test_legenda.ass_do_perfil().encode("utf-8"))
    print("ok  tests/referencias/legenda-arven.ass")


def quadros():
    import test_elementos_quadros
    test_elementos_quadros.regravar()


if __name__ == "__main__":
    pedidos = sys.argv[1:] or ["legenda", "quadros"]
    for p in pedidos:
        {"legenda": legenda, "quadros": quadros}[p]()
