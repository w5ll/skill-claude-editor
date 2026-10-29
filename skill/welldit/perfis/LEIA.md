# Perfis de marca

Cada pasta aqui é um perfil: o visual e as regras de quem edita. O perfil padrão é o `arven` (elementos base ARVEN).

Para criar o seu: `python scripts/perfil.py novo minha-marca`, e edite `perfis/minha-marca/marca.json`. Para usar: `python scripts/inspecionar.py VIDEO --pasta saida/... --perfil minha-marca`. A escolha fica gravada na pasta do trabalho e vale para o resto da edição.

Campos do `marca.json`:

| Campo | O que é |
| --- | --- |
| `nome` | nome da marca, mostrado no título do painel |
| `arroba` | aparece no alto da tela cheia dos elementos; vazio, não aparece nada |
| `creditos` | aviso fixo no rodapé do painel (por exemplo, a origem do visual) |
| `cores` | as nove cores da marca, em `#rrggbb` (`fundo`, `fundo_profundo`, `cartao`, `linha`, `elemento_3d`, `destaque`, `texto`, `apoio`, `rotulo`) |
| `legenda` | `fonte` (nome da família), `arquivo_fonte` (procurado nesta pasta e depois na pasta da skill) e quais cores a legenda usa |
| `gatilhos` | pacotes de palavras que chamam elementos: `geral`, `marketing`, `juridico` |
| `avisos_obrigatorios` | frases que nunca podem ser cortadas; o `propor_cortes.py` avisa se um corte as atingir |
| `termos` | grafia certa de marcas e termos (a legenda corrige só a caixa e a acentuação) |

Perfis pessoais não vão para o git (só `arven` e `_modelo`). Para compartilhar um, use `git add -f`.
