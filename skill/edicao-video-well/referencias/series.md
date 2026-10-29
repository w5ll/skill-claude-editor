# Séries

Uma série é um conjunto de vídeos que se editam do mesmo jeito (por exemplo, "planejamento", "bastidores", "anúncio"). O jeito fica num arquivo em `series/<nome>.json`, **na raiz do projeto, fora da skill**: é da pessoa e não vai para o `.skill`. Copie `series/_modelo.json` para começar.

## Campos (todos opcionais)

| Campo | Valores | O que muda |
| --- | --- | --- |
| `ritmo` | `natural`, `dinamico` | `propor_cortes.py --ritmo` |
| `formato` | `original`, `9:16`, `4:5`, `1:1`, `16:9`, com `@1080` se quiser reduzir | `--formato` em todos os scripts |
| `legenda` | `ligada`, `palavras` (1 a 6), `posicao` (`auto`, `baixo`, `meio`, `alto`), `tamanho` (0,02 a 0,09), `maiusculas`, `destaque` | `legendas.py` |
| `elementos` | `ligado`, `modo` (`sobreposto`, `tela`), `intervalo` (mínimo 3 s), `permitidos`, `proibidos`, `gerados` | `elementos.py sugerir` e `serie.py elementos` |
| `camera` | `zoom`: `nenhum`, `leve`, `normal`, `forte` | `camera.py planejar --intensidade` |
| `som` | `musica` (`nenhuma`, `calmo`, `animado`, `batida`), `efeitos`, `volume` (-23 a -9 LUFS) | `som.py planejar` e `renderizar.py --volume` |
| `ruido` | `auto`, `nao`, `leve`, `forte` | `renderizar.py --ruido` (`auto` segue a sugestão da inspeção) |
| `termos` | lista de nomes e palavras difíceis | `transcrever.py --termos` |
| `publicacao` | `hashtags_fixas`, `avisos_obrigatorios`, `chamada` | `serie.py texto` |

`permitidos` vazio quer dizer "todos"; `proibidos` ganha de `permitidos`. Em ambos, além dos 12 nomes de elemento, valem `gerado` (os desenhados para o vídeo) e `imagem` (as imagens de apoio).

## Como usar

1. Descubra a série: o Well disse o nome, ou `python scripts/serie.py listar` mostra uma que combina. Se houver dúvida, pergunte uma vez.
2. `python scripts/serie.py validar NOME` (diz em português o que está errado).
3. `python scripts/serie.py cartao NOME`: as linhas do cartão que a série preenche, já com "_(da série X)_". Use-as no cartão de ajustes. O que a série não define aparece na última linha da saída e vale o padrão da skill.
4. Depois do "ok" do Well, `python scripts/serie.py aplicar NOME --pasta saida/...`. Isso guarda uma **cópia** (`serie.json`) na pasta do trabalho (mudar a série depois não altera uma edição antiga) e imprime os comandos de cada etapa com os parâmetros da série. Siga-os na ordem do SKILL.md.
5. Depois de `elementos.py sugerir`, rode `serie.py elementos --pasta ...` se a série proíbe ou limita elementos.
6. No fim, ao escrever o texto do post, `serie.py texto --pasta ... --arquivo texto-do-post.md` confere as hashtags fixas e os avisos obrigatórios.

O Well manda: ele pode mudar qualquer linha do cartão. Se a mudança for permanente, edite o arquivo da série (e diga a ele que fez).

## O que não pôr numa série

Nada de nome de cliente, número real ou método interno de empresa: o repositório pode ser público. Termos de transcrição são nomes que aparecem na fala (do próprio Well, de marcas dele), nunca de cliente.

## Relação com a Fase 4

O formato é o mesmo que os modelos de edição da Fase 4 vão usar: a série já é o modelo.
