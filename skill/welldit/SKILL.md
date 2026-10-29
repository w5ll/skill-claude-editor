---
name: welldit
description: "Edita os vídeos que uma pessoa grava para o Instagram (vídeo vertical, Reels): corta pausas, respirações, erros e repetições, junta tomadas, coloca legenda no padrão do perfil de marca fora do rosto, faz elementos 3D da marca entrarem quando a pessoa fala a palavra certa (e desenha elementos novos para as ideias que nenhum elemento pronto representa), dá zoom de ênfase, tira ruído, põe música e efeitos quando pedido, iguala o volume e entrega o MP4 pronto para postar. Use quando a pessoa mandar um vídeo bruto, pedir para editar, cortar, legendar, pôr elementos 3D, zoom, música ou ajustar um vídeo já editado."
---

# welldit: edição de vídeo

Edita no próprio computador os vídeos que a pessoa grava (normalmente celular na vertical, a partir de um roteiro, se houver). O objetivo é um vídeo com ritmo, sem pausa morta nem erro, com a fala da pessoa intacta e legenda legível.

O visual (cores, fonte, nome, @) vem do **perfil de marca** escolhido: pasta `perfis/NOME/` (veja `perfis/LEIA.md`). O padrão é o `arven` (elementos base ARVEN). Quem quiser as próprias cores cria um perfil com `python scripts/perfil.py novo NOME` e usa `--perfil NOME` na inspeção.

Sempre em português, com acentuação, sem travessão e sem termo em inglês sem tradução. A pessoa pode não ler inglês: nada de comando, caminho interno, código ou registro do ffmpeg na conversa.

## Arquivos de apoio

Leia só o que a etapa pede. Em `referencias/`: `fluxo-manual.md` (cada etapa, o cartão, a entrega), `cortes.md`, `legendas.md`, `elementos-3d.md`, `rosto-e-camera.md`, `gancho-e-olhar.md`, `som-e-imagem.md` (volume, ruído, HDR, formato, música), `fatos.md`, `imagens.md`, `cenas.md`, `series.md` (jeito de editar de um conjunto de vídeos), `publicacao.md` (capa, texto do post, limites do Instagram), `orquestrador.md` (o `editar.py` por dentro), `painel.md` (o painel que executa), `gravacao.md` (dicas para a pessoa), `instalacao.md`. O perfil de marca está em `perfis/NOME/marca.json`. Scripts em `scripts/`; todos aceitam `--help`.

## O fluxo

**Inspecionar → cartão de ajustes → "ok" da pessoa → editar → amostra → vídeo inteiro → conferir → entregar.** O `editar.py` roda as etapas e para nos portões de aprovação; você decide só o que é julgamento. O "ok" tem que vir numa mensagem da pessoa depois do cartão (mesmo que o pedido venha detalhado ou diga "decide tudo"); nunca invente a resposta.

```bash
python scripts/editar.py novo BRUTO1.mov [BRUTO2.mov] [--serie NOME] [--perfil NOME] [--tema curto]
python scripts/editar.py proximo --pasta saida/AAAA-MM-DD_tema      # roda até o próximo portão
python scripts/editar.py estado  --pasta ...                         # onde está (curto)
python scripts/editar.py aprovar --pasta ... [PORTAO] [--resposta "A,C"] [--seguir]   # --seguir: aprova e já roda até o próximo portão
python scripts/editar.py ajustar --pasta ... --escolha camera=leve   # muda uma escolha e refaz só o que depende dela
```

Cada etapa imprime uma linha; o texto completo fica em `etapas/<nome>.log` (só abra se algo falhar). O estado fica em `trabalho.json`.

| Portão | O que fazer |
| --- | --- |
| `cartao` | `editar.py cartao`: mande o texto **como mensagem normal** (não em bloco de código) e espere a resposta com as letras das pendências. `aprovar --resposta "A,C" --seguir`. Mudança pedida: `ajustar` e mostre o cartão de novo com ✏️. |
| `cortes` | Leia `referencias/cortes.md` e revise o `cortes.json` (tomada certa, fim da gravação, o que nunca sai). Fala não reconhecida: `transcrever.py --trecho` antes de cortar. |
| `fatos` | `fatos.py mostrar`, pergunte à pessoa, `fatos.py responder`. Só segue com tudo respondido (`referencias/fatos.md`). |
| `gancho_olhar` | Mostre a nota e as propostas (`referencias/gancho-e-olhar.md`); só aplique com o "ok". |
| `elementos` | `elementos.py previa`, cenas e imagens sugeridas (`referencias/elementos-3d.md`, `cenas.md`, `imagens.md`); gerado, cena e imagem só com a prévia aprovada. |
| `legenda` | Corrija a grafia em `legendas.json` (`referencias/legendas.md`) e rode `legendas.py --reaproveitar`. |
| `amostra` | Só se a pessoa pediu para aprovar a amostra; senão, a conferência da amostra basta. |
| `problemas` | Falha da conferência: corrija (ganho, pausa, corte) ou explique como limite. Nunca entregue com "FALHOU" sem dizer. |

Aprovar um portão é gravar a decisão: **nunca aprove no lugar da pessoa** os portões de cartão, fatos, elementos gerados e amostra aprovada por ela. Os de julgamento (cortes, legenda) são seus, mas a pessoa pode pedir para revisar.

Entrega, publicação (capa, texto do post, pacote) e o passo a passo sem o orquestrador: `referencias/fluxo-manual.md` e `referencias/publicacao.md`. O formato do cartão e da entrega está lá.

## Ajustes depois da entrega

Mudança pontual ("legenda maior", "volta a frase do 0:30") mexe só no que foi pedido: edite `legendas.json` ou `cortes.json` e renderize de novo. A saída nova ganha o próximo número (v002), a anterior fica guardada. Nunca recorte o vídeo inteiro de novo por causa de um ajuste de legenda.

## Regras que não mudam

- Nunca mexa nos arquivos originais. Tudo novo fica na pasta do trabalho.
- Nunca sobrescreva uma entrega anterior.
- A fala é da pessoa: não corte ressalva, negação ou condição que muda o sentido, nem os **avisos obrigatórios do perfil** (campo `avisos_obrigatorios` do `marca.json`, por exemplo o aviso que um órgão de classe exige; o `propor_cortes.py` avisa se um corte os atingir, veja `referencias/cortes.md`). Não junte pedaços de frases diferentes para criar uma frase que a pessoa não disse.
- Corte medido no áudio, não estimado pelo roteiro. O roteiro serve para grafia e ordem.
- Sem elemento 3D, zoom, música, efeito, filtro de cor, conversão de HDR ou redução de ruído sem a pessoa escolher no cartão.
- Cena explicativa só entra com a prévia aprovada pela pessoa e depois de passar no `cenas.py validar`: todo número e todo gatilho têm que estar na fala, e o texto só resume o que ela disse.
- Elemento 3D gerado só entra com a prévia aprovada pela pessoa e depois de passar no `validar` (sem texto, pessoa, rosto, mão, logotipo ou marca de terceiros).
- Música e efeitos só da biblioteca da skill (domínio público) ou que a pessoa mandar. Nunca baixe música da internet.
- Imagem de apoio só da biblioteca `imagens/`, com licença registrada (`referencias/imagens.md`). Nunca use imagem sem origem, de cliente ou com direitos reservados, e só baixe imagem da internet se a pessoa pedir. O crédito obrigatório vai no texto do post.
- Fato (número, data, fonte, norma) marcado como pendente trava o render do vídeo inteiro até a pessoa responder.
- Nada é enviado para fora do computador. A transcrição é local.
- Nunca publique. Postar é com a skill de conteúdo, e só com "pode postar". A capa e o texto do post só entram no pacote com o "ok" da pessoa, e título e texto só trazem número, nome e afirmação que ela falou.

## Painel no navegador

A pessoa pode editar e acompanhar pelo painel (`python scripts/painel.py [--perfil NOME]`): ela envia os vídeos, preenche o cartão e aprova os portões com cliques, e o painel roda o `editar.py`. Conversa e painel leem o mesmo `trabalho.json`: dá para começar num e terminar no outro. Nunca abra o painel por conta própria. Se perguntarem "em que pé está", rode `editar.py estado`. Se a pessoa pedir "revisar na conversa" um portão do painel, ele já deixou `pedidos/<portao>.json`: leia, revise e aprove com `editar.py aprovar --seguir`. Veja `referencias/painel.md`.

## Quando um script falha

Erro de script é problema seu, não da pessoa. Não mostre a mensagem de erro nem peça para consertar. Tente outro caminho (por exemplo, rodar o passo direto no ffmpeg dentro da pasta do trabalho), e conte na entrega, em uma linha simples, o que foi feito diferente. Se não houver caminho, explique o limite em palavras simples e ofereça opções concretas (por exemplo, a versão sem legenda). Nunca desligue um ajuste aprovado em silêncio.

## Inspiração

A forma de trabalhar (cartão antes de editar, corte medido no áudio, amostra, conferência real) veio do projeto aberto editonny, de Matheus Gomes (licença MIT); o código aqui é próprio. Veja `docs/comparacao-editonny.md`.
