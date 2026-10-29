# Fase 7. Elementos, zoom e som no painel

> **Status: implementada** (29/10/2026), com 46 testes novos em `tests/test_fase7.py` (lógica, orquestrador, conferência de verdade, API, prévias e a tela num navegador). As decisões que mudaram estão em [Como ficou](#como-ficou). Quarta fase da trilha A. Usa o painel que executa (Fase 5) e a tela de revisão (Fase 6). Nenhuma etapa nova de edição: a tela mexe nos mesmos arquivos que a conversa já edita à mão (`elementos.json`, `camera.json`, `som.json`, `cortes.json`).

## Objetivo

1. **Ajustar sem abrir o arquivo.** Hoje, para tirar um elemento, mudar o rótulo, suavizar um zoom ou baixar um efeito, a pessoa precisa pedir na conversa ou editar JSON. A Fase 7 põe isso em cliques, com prévia e escuta.
2. **Consertar o que a conferência achou.** A conferência já diz o que está errado e sugere o conserto, mas em texto. Agora cada problema que tem conserto automático ganha um botão.
3. **Nada de perder trabalho.** Todo ajuste guarda a versão anterior (desfazer), como na Fase 6, e mexer num ajuste não refaz o que não depende dele.

## Regras que não mudam

- O painel só faz **ações conhecidas**, com valores dentro de uma lista ou de um limite. Nenhum campo recebe caminho, comando ou desenho livre. Os arquivos que a tela lê para mostrar (prévias, sons) vêm de nomes do catálogo, nunca de um caminho do navegador.
- Só com a edição parada (nem rodando, nem na fila): senão 409, como na Fase 6. Leituras exigem a sessão.
- Nunca mexe nos originais nem apaga entrega. Os sons e músicas da skill são de domínio público; a tela não aceita arquivo de áudio de fora (isso continua sendo pedido na conversa, com a responsabilidade de uso da pessoa).
- O "ok" continua sendo um clique da pessoa, gravado no estado.

## O que a pessoa faz na tela

Um painel de **ajustes** abre por cima da edição, com quatro abas. Abre pelo portão (elementos, problemas) ou pelos botões **Ajustar elementos / zoom / som / Ver a conferência**, que aparecem quando o arquivo correspondente existe.

### Elementos

- Lista em ordem de tempo: nome, momento no vídeo, duração, palavra que chamou, rótulo, modo (sobreposto ou tela cheia), posição. Cada linha tem **prévia** (o elemento sobre o fundo da marca e sobre o quadro do vídeo, nos instantes de entrada, meio e saída), gerada pelo mesmo código da folha `elementos-previa.jpg`.
- **Tirar** (e **Desfazer**), **Trocar** por outro elemento pronto ou do catálogo, **mudar o rótulo** (até 40 letras, `*asterisco*` destaca), **mudar o momento e a duração**, **sobreposto/tela cheia**, **posição** (automática, topo, esquerda, direita, meio) e **Adicionar** um elemento em um momento que a pessoa escolher.
- Elementos desenhados na hora (gerados), cenas e imagens de apoio aparecem na lista. Cena e imagem só podem ser tiradas ou mudar de momento (o texto delas vem da fala e das regras da Fase 12 e 11). Um desenho gerado que não passa na validação aparece com o motivo, em português.
- **Catálogo**: nos gerados, **Guardar no catálogo** (`elementos.py promover`) com as palavras que o chamam; o próximo vídeo já o acha pela palavra.
- Ao salvar, a câmera, o som e a amostra ficam desatualizados e são refeitos no próximo passo. A tela avisa: **o zoom e os efeitos são planejados de novo** (o zoom nunca muda no meio de um elemento). Por isso a ordem recomendada é elementos, depois zoom, depois som.

### Zoom

- **Intensidade** (parado, leve, normal, forte): usa o `ajustar` que já existe e planeja o zoom de novo.
- Lista dos blocos de câmera: momento, nível (aberto, perto, ênfase), motivo (a frase ou a palavra forte) e **prévia** do enquadramento no meio do bloco, com o mesmo cálculo do render (ancorado no rosto).
- **Mudar o nível de um bloco** para aberto, perto ou ênfase (os valores da intensidade escolhida) e **tirar uma ênfase** (vira o enquadramento do bloco vizinho). Desfazer.
- **Regra de segurança**: um ajuste que faria o zoom mudar com um elemento 3D na tela é recusado, com o momento do elemento na mensagem.

### Som

- **Música**: escolher entre as da skill (calmo, animado, batida) ou nenhuma, com **ouvir** (os primeiros 30 s), e os dois níveis (quanto abaixo da voz na fala, quanto sobe nas pausas). A escolha da música usa o `ajustar`; os níveis mexem no `som.json`.
- **Efeitos**: um por elemento, em ordem de tempo, com **ouvir**, **trocar o som** (entre os 10 efeitos da skill), **ganho** (de −12 a +6 dB) e **tirar**. Desfazer.
- A mistura final (voz, música e efeitos juntos) se confere na amostra: a tela não monta a mistura.

### Conferência com botões de correção

A conferência passa a gravar, no `.conferencia.json`, uma lista de **correções** com o tipo e os dados do problema. A tela mostra cada uma com o botão certo:

| Problema | Botão | O que faz |
| --- | --- | --- |
| Silêncio morto de X a Y | **Aceitar essa pausa** | Grava a pausa em `pausas_ok` (escolha da edição) e a conferência é refeita aceitando-a. |
| Trecho N com volume diferente | **Aplicar o ganho sugerido** | Grava `ganho_db` no trecho do `cortes.json` (com histórico) e o vídeo é refeito. Só o vídeo: rosto, elementos, câmera e legenda **não** são refeitos. |
| Palavra cortada ou trecho repetido | **Abrir a revisão dos cortes** | Abre a tela da Fase 6 no ponto. |
| Qualquer outro | **Refazer o vídeo** | `refazer` do vídeo, uma versão nova (nunca sobrescreve a anterior). |

Depois de um botão, a edição entra na fila e roda até o próximo portão. O texto do problema continua visível para quem prefere resolver na conversa.

## Mudanças no orquestrador (`editar.py`)

Três mudanças pequenas, necessárias para que um ajuste não desfaça outro:

1. **Ganho não refaz tudo.** A assinatura (hash) que as etapas usam para o `cortes.json` passa a ignorar o campo `ganho_db`, exceto na amostra e no vídeo (que precisam dele). Sem isso, aplicar um ganho refaria rosto, elementos (perdendo os ajustes de elementos), câmera e legenda.
2. **`pausas_ok`** vira escolha (lista de segundos) e a etapa de conferir a repassa ao `conferir.py`, entrando no hash dela.
3. **A legenda reaproveita o texto.** Quando só a câmera mudou (os cortes e o estilo são os mesmos), a etapa da legenda roda com `--reaproveitar`: recalcula as posições e **mantém o texto revisado**. Para saber que os cortes não mudaram, o `legendas.py` passa a gravar no `legendas.json` uma assinatura dos cortes (sem o ganho). Sem isso, mexer no zoom apagaria a revisão da legenda da Fase 6.

Também: `conferir.py` grava a lista de correções, e `elementos.py previa` aceita escolher quais elementos desenhar (para a prévia de um só).

## A API (acrescenta à da Fase 6)

Leituras: `GET /api/elementos`, `/api/elementos/previa?pasta&i`, `/api/zoom`, `/api/zoom/previa?pasta&i`, `/api/som`, `/api/som/ouvir?tipo=musica|efeito&nome`, `/api/conferencia`.
Escritas (`POST`, JSON): `/api/elementos/tirar`, `/trocar`, `/rotulo`, `/tempo`, `/modo`, `/adicionar`, `/promover`, `/desfazer`; `/api/zoom/nivel`, `/zoom/desfazer`; `/api/som/nivel`, `/som/efeito`, `/som/desfazer`; `/api/conferencia/aceitar-pausa`, `/conferencia/aplicar-ganho`. Todas seguem as regras da Fase 5 (sessão, cabeçalho, 409 com a edição ocupada, valores fora do limite recusados).

## Arquivos

- Novo: `scripts/ajustes.py`, com toda a lógica (sem servidor), testável sozinha, no mesmo molde do `revisao.py`.
- Mudam: `painel.py` (rotas), `templates/painel.html` (a tela), `editar.py` (as três mudanças acima), `conferir.py` (correções), `legendas.py` (assinatura dos cortes), `elementos.py` (prévia de itens escolhidos).
- Documentação: `referencias/painel.md`, `referencias/elementos-3d.md`, `referencias/som-e-imagem.md`, `referencias/rosto-e-camera.md`, README.

## Testes (`tests/test_fase7.py`)

1. Elementos: tirar, trocar, rótulo, momento, modo e adicionar mudam só o item pedido; valores ruins são recusados sem mexer no arquivo; desfazer devolve exatamente o anterior, várias vezes; cena e imagem recusam troca e rótulo.
2. Zoom: mudar o nível de um bloco; tirar ênfase; recusar mudança de zoom com elemento na tela; desfazer.
3. Som: níveis e efeitos dentro dos limites; trocar o som só por nome do catálogo; ouvir só serve arquivos do catálogo (nome com `..` ou `/` é recusado).
4. Conferência: as correções saem do `conferir.py` com os dados certos; aceitar pausa e aplicar ganho gravam o que devem.
5. Orquestrador: aplicar ganho refaz só amostra e vídeo; mudar a câmera mantém o texto da legenda revisada; mudar os cortes refaz a legenda do zero; `pausas_ok` chega ao `conferir.py`.
6. API: tudo atrás da sessão, 409 com a edição ocupada, nenhum caminho do navegador chega a um arquivo.
7. Prévia de um elemento e de um zoom: imagens do tamanho certo (navegador e ffmpeg de verdade).
8. Na tela, num navegador de verdade: tirar um elemento e desfazer; aceitar uma pausa na conferência.

## Fora desta fase

Arrastar elementos na prévia, desenhar elementos novos pela tela (a Fase 8 faz isso com o Claude), música de fora, mistura final de som ouvida na tela, e escolher onde cada efeito cai no tempo (ele cai junto do elemento).

## Como ficou

- **A escolha e o plano são coisas separadas.** Mudar a intensidade do zoom, a música ou o efeito em cada elemento só grava a **escolha**; o plano novo (`camera.json`, `som.json`) sai quando a edição roda a etapa. As abas de zoom e de som dizem isso e têm **Continuar a edição agora**. Já os ajustes bloco a bloco e efeito a efeito mexem direto no plano, com desfazer.
- **A prévia do elemento é a folha que já existia**, em versão compacta (um instante sobre o fundo da marca e três sobre o quadro do vídeo), uma por elemento, guardada por conteúdo: só é refeita quando o elemento, o rosto, a câmera, o corte ou a marca mudam. Uma por vez, porque cada uma abre um navegador.
- **Dois elementos nunca ficam juntos na tela**, e nenhum passa do fim do vídeo (regra nova, não estava na proposta): o gerador já mantinha esse espaço, e a tela passou a exigir.
- **O zoom do bloco é recusado se mudar com um elemento na tela**, dizendo o momento do elemento. A conferência de elementos só olha os blocos que o ajuste toca, para não bloquear quem já tinha um plano manual.
- **O hash do `cortes.json` ignora o `ganho_db`** nas etapas que não dependem dele. Sem isso, "aplicar o ganho sugerido" refazia o rosto e os elementos e apagava o que a pessoa tinha ajustado.
- **A legenda reaproveita o texto** quando só a câmera mudou. Sem isso, qualquer ajuste de zoom apagava a revisão da legenda da Fase 6.
- **As correções da conferência saem do próprio `conferir.py`**, com os números (início da pausa, trecho e ganho sugerido), e o painel só aceita aquelas que a conferência achou. Um valor diferente do sugerido é recusado.
- **Uma classe do formulário do cartão (`campos`) quase foi sobrescrita** pela tela nova; a tela de ajustes usa a sua (`aj-campos`). Achado olhando a captura da tela, não pelos testes.

## Não coberto

- Arrastar na prévia, e desenhar elementos novos pela tela (Fase 8).
- A mistura final de som na tela. A tela ouve cada som sozinho.
- A prévia da legenda e a renderização completa dependem do filtro de legenda (`libass`) do ffmpeg. Nesta máquina o ffmpeg do Homebrew não o tem: os 3 testes de prévia de legenda da Fase 6 já falhavam antes desta fase e continuam falhando (nenhum teste da Fase 7 depende dele).
- Ajustes manuais de zoom e de som se perdem quando os elementos mudam (o zoom e os efeitos são planejados de novo). É dito na tela, e a ordem recomendada é elementos, zoom, som.
- Falta alguém que não conhece o código usar as telas.
