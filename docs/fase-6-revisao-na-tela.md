# Fase 6. Revisão de cortes e legenda na tela

> **Status: implementada** (29/10/2026) e testada com os dados reais do vídeo de planejamento (dois vídeos 4K HDR de 1 GB, 52 trechos, 230 blocos de legenda), numa tela de navegador de verdade. As decisões que mudaram estão em [Como ficou](#como-ficou).

Terceira fase da trilha A. Os dois portões em que a edição real mais deu trabalho, **cortes** e **legenda**, ganham uma tela de revisão no painel: a pessoa vê o texto da fala com o que fica e o que sai, clica para mudar, ouve o que quiser e aprova, sem abrir um arquivo nem uma conversa. É a tela mais valiosa do painel.

## Objetivo

1. **Cortes**: ver a fala inteira, trecho a trecho, com o que fica e o que sai; tirar ou voltar um trecho com um clique; ouvir qualquer trecho e **qualquer emenda** (o que o espectador vai ouvir no ponto de junção); desfazer.
2. **Suspeitas marcadas**: o painel aponta onde olhar (palavra duvidosa, som sem palavra, fala repetida, fim da gravação, frase que não termina), em vez de a pessoa ler tudo.
3. **Duração ao vivo** contra a meta da pessoa.
4. **Legenda**: editar o texto de cada bloco, ver a **prévia** em cima de um quadro do vídeo, corrigir uma palavra em todos os blocos de uma vez e desfazer.

## Regras que não mudam

- Nada é cortado no meio de uma palavra: os pontos de corte caem no silêncio entre as palavras, como em `propor_cortes.py`. A pessoa nunca escolhe um tempo em segundos.
- A fala é da pessoa: tirar é uma escolha dela, clicada. O painel nunca tira nada sozinho e nunca junta pedaços de frases diferentes.
- Tudo local, só ações conhecidas, tudo atrás da sessão da Fase 5. Nenhum caminho de arquivo vem do navegador: os vídeos são os que estão no `cortes.json`.
- Editar só com a edição parada (nem rodando, nem na fila): a mesma regra do 409.
- Tudo é desfazível, e o arquivo anterior é guardado (`revisao/`).

## Cortes

### A tela
O texto de cada vídeo em **unidades**: pedaços de fala de até uns 14 palavras, que terminam em pontuação ou numa pausa maior que 0,5 s. Cada unidade **fica** (normal) ou **sai** (riscada e apagada); uma unidade nunca está metade em cada estado. Clicar alterna. Cada unidade tem **▶ ouvir**; entre dois trechos que ficam há um botão **emenda ▶**, que toca o fim de um e o começo do outro, como será no vídeo. As palavras de baixa confiança aparecem sublinhadas.

No topo: a **duração final ao vivo** (com a meta, se houver, e quanto passa dela), **Desfazer**, o filtro **só suspeitas** e **Aprovar os cortes e seguir**.

### Suspeitas

| Marca | Como acha |
| --- | --- |
| Palavra duvidosa | transcrição com confiança abaixo de 0,45, ou palavra com mais de 1,5 s |
| Som sem palavra / fala não reconhecida | as marcas "para conferir" do `cortes.json` |
| Fala repetida | unidade que saiu por "frase repetida ou começo errado": confira se ficou a melhor tomada; e mesma frase em dois trechos |
| Fim da gravação | a última unidade de cada vídeo: é onde costuma estar o fecho |
| Frase que não termina | trecho que fica e acaba sem ponto, seguido de um corte, ou terminando em "porque", "que", "e", "mas", "quando", "de", "a"... |

A lista de suspeitas fica no topo; clicar numa leva até a unidade, e cada uma tem **▶ ouvir** com 2 s de folga.

### O que muda no `cortes.json`
- **Tirar** uma unidade: o intervalo (de pausa a pausa, nas bordas das palavras) sai dos trechos do vídeo; o trecho pode se dividir em dois. Entra em `removidos` com o motivo "tirado na revisão".
- **Voltar**: o intervalo é acrescentado e **junta** com o trecho vizinho se estiverem encostados. A ordem de reprodução dos trechos é mantida (inclusive depois de uma frase puxada para o começo pelo `gancho.py`).
- `duracao_final` e o texto de cada trecho são recalculados; o `ganho_db` de um trecho dividido vale para os dois pedaços.
- Antes de cada mudança, o `cortes.json` anterior vai para `revisao/cortes-NNN.json`; **Desfazer** restaura o último e apaga o arquivo.
- Como o `cortes.json` é entrada das etapas seguintes, mudar os cortes depois do portão faz o orquestrador refazer rosto, elementos, legenda e amostra (Fase 4). O portão dos cortes continua aprovado.

### Meta de duração
Uma escolha nova, `meta_duracao` (segundos, opcional, de 10 a 600), definida no painel. Sem meta, a tela mostra os limites de `assets/instagram.json` (aviso e falha) como referência.

### Ouvir
`GET /api/ouvir`: o servidor extrai com o ffmpeg só o áudio do trecho pedido (de um vídeo que está no `cortes.json`, no máximo 6 pedaços e 30 s por pedaço), com a mesma suavização de 8 ms nas emendas que o render usa, e guarda em cache.

## Legenda

### A tela
Uma lista dos blocos (o que aparece de cada vez na tela): tempo, texto editável, a **prévia** (o quadro do vídeo naquele instante, no formato final, com a legenda desenhada pelo mesmo código do render, no lugar que ela vai ficar) e marcas para olhar: **número** (confira), **nome próprio** (maiúscula no meio da frase) e **movida** (a legenda subiu ou desceu para não cobrir o rosto).

### O que dá para fazer
- **Editar o texto de um bloco** (uma linha, até 80 caracteres). Se o número de palavras muda, aquele bloco perde o destaque da palavra falada (como já acontece hoje).
- **Corrigir em todos**: troca uma palavra por outra em todos os blocos de uma vez (palavra inteira, sem diferenciar maiúscula na busca), útil para grafia de marca e termo difícil. Mostra quantos blocos mudaram.
- **Desfazer** (`revisao/legendas-NNN.json`).
- Salvar roda `legendas.py --reaproveitar` com os mesmos parâmetros da edição, que recalcula as posições e grava `legendas.json`, `.ass` e `.srt`. A amostra e o vídeo ficam desatualizados (Fase 4) e são refeitos no próximo passo.

## A API (acrescenta à da Fase 5)

`GET /api/cortes`, `POST /api/cortes/alternar`, `POST /api/cortes/desfazer`, `GET /api/ouvir`, `GET /api/legenda`, `POST /api/legenda/editar`, `POST /api/legenda/substituir`, `POST /api/legenda/desfazer`, `GET /api/legenda/previa`. A meta usa o `ajustar` que já existe. As de escrita seguem as regras da Fase 5 (sessão, cabeçalho, 409 com a edição ocupada); as de leitura exigem a sessão.

## Mudanças em arquivos que já existem

- `editar.py`: a escolha `meta_duracao`.
- `painel.py` e `templates/painel.html`: as rotas e a tela (um painel de revisão que abre por cima da edição, nos portões dos cortes e da legenda e por um botão "Revisar" sempre que houver o que revisar).
- Novo: `scripts/revisao.py`, com toda a lógica (sem servidor), testável sozinha.
- `referencias/painel.md`, `referencias/cortes.md` (o que a tela marca) e README.

## Testes (`tests/test_fase6.py`)

1. Unidades: separam por pontuação, pausa e mudança de estado; nenhuma mistura "fica" e "sai"; palavras de baixa confiança vêm marcadas.
2. Tirar e voltar: sem cortar palavra, dividem e juntam trechos, mantêm a ordem (inclusive trecho puxado para o começo), recalculam duração e textos, e o `ganho_db` vale para os dois pedaços; voltar o que acabou de tirar devolve o mesmo conjunto de palavras.
3. Desfazer: restaura exatamente o arquivo anterior, várias vezes, e não faz nada sem histórico.
4. Suspeitas: acha cada tipo e não marca uma frase boa.
5. Ouvir: só vídeos do `cortes.json`, limites de pedaços e de duração, e o áudio gerado tem a duração pedida (ffmpeg de verdade).
6. Legenda: editar, perder o destaque quando muda o número de palavras, corrigir em todos, desfazer, e as marcas (número, nome, movida); a prévia sai como imagem do tamanho certo, com a legenda desenhada (comparando pixels com e sem texto).
7. API: tudo atrás da sessão, 409 com a edição ocupada, valores fora do limite recusados, e **nenhum caminho do navegador chega a um arquivo**.
8. Na tela, num navegador de verdade: clicar numa unidade a risca e muda a duração ao vivo; desfazer a devolve; editar um bloco da legenda mostra a prévia nova.

## Fora desta fase
Revisão de elementos, zoom e som na tela e os botões de correção da conferência (Fase 7), e Claude por trás, que sugere cortes e grafia (Fase 8). Arrastar para ajustar o tempo de um corte (a escolha é sempre por unidade de fala).

## Como ficou

- **As suspeitas foram afinadas com dados reais.** Na primeira versão, o vídeo real dava 32 pontos, quase todos "palavra duvidosa: E / os / um" (palavras pequenas têm confiança baixa sempre), sem dizer onde nem o trecho, e com instruções de linha de comando ("rode transcrever.py --trecho 54 57"). Agora: palavras pequenas só entram com confiança muito baixa, as duvidosas da mesma frase viram um ponto só, a lista vem **em ordem de tempo**, cada ponto diz o vídeo, o minuto e o trecho, e as mensagens falam em "ouça". Caiu para 25 pontos, todos úteis.
- **▶ fora da área de clique**: o botão de ouvir ficava dentro da frase clicável, e clicar no meio da frase tocava o áudio em vez de tirá-la. Um teste de tela pegou isso.
- **✂ discreto**: com cortes naturais (cada pausa é uma emenda), o vídeo real tinha 50 emendas, e o botão "emenda N ▶" poluía a leitura. Ficou só o ícone, apagado até o mouse chegar.
- **Legenda em grade de duas colunas**, com prévia pequena (clique para ampliar): com a prévia de quadro inteiro, cada linha tinha 290 px e 230 blocos viravam uma rolagem enorme.
- **A prévia usa o código do render**: o ASS é gerado por `legendas.gerar_ass` e desenhado pelo filtro `ass` do ffmpeg, com a fonte do perfil e a conversão de HDR para cor padrão. Um teste compara pixels com e sem legenda.
- **Salvar a legenda roda o `legendas.py --reaproveitar` de verdade** (não uma cópia da lógica), então as posições, o `.ass` e o `.srt` ficam exatamente como o render espera.
- **Tempos no vídeo real**: os cortes (62 KB) em 10 ms, o áudio de qualquer frase em 0,16 s mesmo de um 4K de 1 GB, a prévia de um bloco em 0,65 s com a conversão de HDR.
- **Meta de duração**: `meta_duracao` (10 a 600 s) é uma escolha comum, definida pela tela (`ajustar`). Não faz parte das etapas, então não refaz nada.

## Não coberto
- Arrastar para ajustar o tempo de um corte, refazer (só desfazer) e revisar com dois vídeos lado a lado.
- A prévia da legenda mostra o enquadramento original (sem o zoom da câmera) e não mostra os elementos 3D.
- A pessoa revisando as suspeitas no vídeo de teste foi o autor da fase: falta alguém que não conhece o código usar a tela.
