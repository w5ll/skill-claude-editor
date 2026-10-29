"""Perfis de marca: cada pessoa edita nas cores e na fonte dela.

Uso:
    python perfil.py listar
    python perfil.py novo NOME           copia o perfil _modelo para perfis/NOME/
    python perfil.py validar [NOME]      confere campos, cores e fonte (padrão: o perfil em uso)

O perfil fica em perfis/NOME/marca.json (veja perfis/LEIA.md). Para usar um perfil numa edição:
    python inspecionar.py VIDEO --pasta saida/... --perfil NOME
A escolha fica gravada na pasta do trabalho e vale para o resto da edição.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys

from comum import (PASTA_PERFIS, PERFIL_PADRAO, erro, ler_json, nome_do_perfil, perfis_disponiveis,
                   problemas_da_marca)


def listar():
    em_uso = nome_do_perfil()
    for nome in perfis_disponiveis():
        marca = ler_json(PASTA_PERFIS / nome / "marca.json")
        etiqueta = " (padrão)" if nome == PERFIL_PADRAO else " (modelo para copiar)" if nome.startswith("_") else ""
        uso = "  <- em uso" if nome == em_uso else ""
        print(f"  {nome}{etiqueta}{uso}")
        print(f"      {marca.get('nome', '')}"
              f"{' · ' + marca['arroba'] if marca.get('arroba') else ''}"
              f" · gatilhos: {', '.join(marca.get('gatilhos', ['geral']))}"
              f"{' · ' + marca['creditos'] if marca.get('creditos') else ''}")


def novo(nome: str):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", nome):
        erro("o nome do perfil deve ter só letras minúsculas sem acento, números e hífen (ex.: minha-marca)")
    destino = PASTA_PERFIS / nome
    if destino.exists():
        erro(f"o perfil {nome} já existe: escolha outro nome ou edite perfis/{nome}/marca.json")
    shutil.copytree(PASTA_PERFIS / "_modelo", destino)
    print(f"ok  perfis/{nome}/marca.json criado a partir do modelo")
    print("    1. edite o nome, o @, as cores e a fonte (campos em perfis/LEIA.md)")
    print(f"    2. confira com: python perfil.py validar {nome}")
    print(f"    3. use com: python inspecionar.py VIDEO --pasta saida/... --perfil {nome}")
    print("    (perfis pessoais não vão para o git; para compartilhar um, use git add -f)")


def validar(nome: str | None):
    nome = nome or nome_do_perfil()
    arq = PASTA_PERFIS / nome / "marca.json"
    if not arq.exists():
        erro(f'não existe o perfil "{nome}". Perfis disponíveis: {", ".join(perfis_disponiveis())}')
    problemas = problemas_da_marca(ler_json(arq), arq.parent)
    if problemas:
        print(f'FALHOU  o perfil "{nome}"')
        for p in problemas:
            print(f"          {p}")
        sys.exit(1)
    print(f'ok  o perfil "{nome}" está certo')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("acao", choices=["listar", "novo", "validar"])
    ap.add_argument("nome", nargs="?")
    a = ap.parse_args()
    if a.acao == "listar":
        listar()
    elif a.acao == "novo":
        if not a.nome:
            erro("diga o nome: python perfil.py novo minha-marca")
        novo(a.nome)
    else:
        validar(a.nome)


if __name__ == "__main__":
    main()
