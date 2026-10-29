# O painel que executa

`python scripts/painel.py [--porta 8765] [--sem-abrir] [--perfil NOME]`. Abre o navegador num endereço com um código de sessão. É a mesma edição do `editar.py`, com cliques no lugar de comandos: o painel não tem etapas próprias.

## O que a pessoa faz

1. **Nova edição**: marca os vídeos brutos, escolhe a série e o perfil (opcionais) e clica **Começar**. A inspeção roda sozinha.
2. **Cartão**: formulário com o recomendado marcado e "Ajustes rápidos" (ritmo, zoom, música, efeito, legenda, elementos, amostra). **Aprovar e começar**.
3. **Portões**: cortes, elementos, legenda, fatos, gancho e leitura, problemas da conferência e amostra. **Aprovar e seguir**, ou **Copiar pedido para o Claude** para revisar na conversa.
4. **Fila**: uma edição por vez; as outras ficam "na fila, posição N". **Cancelar** para o processo e deixa a etapa interrompida; **Retomar** continua de onde parou.
5. **Entrega**: versões, folhas de quadros, conferência, **Aprovar entrega** (grava qual versão está aprovada em `trabalho.json`, campo `entrega_aprovada`) e **Abrir a pasta**.

## Revisão de cortes e legenda (os dois portões que mais dão trabalho)

Nos portões `cortes` e `legenda` (e pelo botão **Revisar cortes** / **Revisar legenda** sempre que houver o que revisar), o painel abre uma tela de revisão por cima da edição. Só funciona com a edição parada (nem rodando, nem na fila).

**Cortes.** A fala de cada vídeo em frases clicáveis: normal = fica, riscada = sai. Um clique alterna; nada é cortado no meio de uma palavra (o corte cai no silêncio entre as palavras). **▶** toca a frase e **✂** toca a emenda, ou seja, o fim de um trecho seguido do começo do próximo, como o espectador vai ouvir. No topo: a duração final ao vivo (com a **meta** em segundos, se a pessoa pôs uma), **Desfazer** (quantas vezes quiser), **só suspeitas** e **Aprovar os cortes e seguir**.

A lista **"pontos para olhar"** diz o vídeo, o minuto, o motivo e o trecho, em ordem. Os motivos são: palavra duvidosa (palavras pequenas como "e" e "um" não entram, porque a confiança delas é sempre baixa), palavra longa demais, fala que a transcrição não reconheceu, frase que saiu por repetição, a mesma frase em dois trechos, frase que pode ter sido cortada ao meio e o fim da gravação (onde costuma estar o fecho).

Tirar e voltar mexem no `cortes.json` e guardam o anterior em `revisao/cortes-NNN.json`. Como o `cortes.json` é entrada das etapas seguintes, mudar os cortes depois do portão faz o orquestrador refazer rosto, elementos, legenda e amostra.

**Legenda.** Um cartão por bloco, com a **prévia** (o quadro do vídeo, no formato final, com a legenda desenhada pelo mesmo código do render, no lugar em que ela vai ficar; clique para ampliar) e o texto editável. Marcas para olhar: **número**, **nome próprio** e **movida** (subiu ou desceu para não cobrir o rosto). **Corrigir em todos** troca uma palavra inteira em todos os blocos (grafia de marca, termo difícil). Salvar roda o `legendas.py --reaproveitar`, que recalcula as posições e grava `legendas.json`, `.ass` e `.srt`. Se o número de palavras de um bloco muda, ele perde o destaque da palavra falada.

Na conversa, o mesmo é editar `cortes.json` e `legendas.json` à mão (veja `cortes.md` e `legendas.md`).

## Ajustes de elementos, zoom, som e conferência

Uma tela de **ajustes** com quatro abas abre pelo portão `elementos` (**Revisar os elementos**), pelo portão `problemas` (**Ver os problemas e corrigir**) e pelos botões **Ajustar elementos / zoom / som** e **Ver a conferência** do cartão da edição. Como a revisão da Fase 6, só mexe com a edição parada, e cada mudança guarda a versão anterior em `revisao/` (**Desfazer**). Um pedido recusado não muda nada. Na conversa, o equivalente é editar `elementos.json`, `camera.json` e `som.json` à mão (veja `elementos-3d.md`, `rosto-e-camera.md` e `som-e-imagem.md`).

- **Elementos.** Uma linha por elemento, com a **prévia** (sobre o fundo da marca e sobre o quadro do vídeo), o momento, a duração, o rótulo (até 40 letras, `*asteriscos*` destacam), o modo (sobreposto ou tela cheia), a posição, **Trocar por** (os 12 prontos e o catálogo), **Tirar** e **Adicionar**. Dois elementos não ficam juntos na tela, e nenhum passa do fim do vídeo. Cena e imagem de apoio só mudam de momento ou saem (o texto vem da fala). Elemento desenhado na hora mostra o problema do desenho, se houver, e tem **Guardar no catálogo** (pede as palavras que o chamam).
- **Zoom.** A intensidade (parado, leve, normal, forte) e, bloco a bloco, o nível (aberto, mais perto, ênfase) com a prévia do enquadramento já ancorado no rosto. **Tirar a ênfase** devolve o enquadramento do bloco vizinho. O painel recusa qualquer ajuste que faria o zoom mudar com um elemento na tela.
- **Som.** A música (**ouvir 30 s**), um efeito em cada elemento (liga ou desliga), o quanto a música fica abaixo da voz (10 a 30 dB) e sobe nas pausas (0 a 12 dB), e cada efeito: trocar o som, o volume (−12 a +6 dB) e tirar. Só os sons e músicas da skill; música de fora continua sendo pedido na conversa. A mistura final se confere na amostra.
- **Conferência.** Cada problema com conserto automático ganha um botão: **Aceitar essa pausa** (vira `pausas_ok` nas escolhas e a conferência é refeita), **Aplicar o ganho sugerido** (grava `ganho_db` no trecho do `cortes.json`; refaz só a amostra e o vídeo) e **Abrir a revisão dos cortes** (palavra cortada ou trecho repetido). **Refazer o vídeo** gera uma versão nova e nunca apaga a anterior.

**Ordem recomendada: elementos, depois zoom, depois som.** Mudar os elementos faz o zoom e os efeitos serem planejados de novo na próxima rodada (o zoom nunca muda no meio de um elemento, e cada efeito cai junto do seu elemento); os ajustes manuais de zoom e de som feitos antes se perdem. Mudar o zoom refaz as posições da legenda, mas **mantém o texto revisado** (os cortes e o estilo são os mesmos).

## Claude por trás (opcional)

Com o Claude Code instalado, três telas ganham o botão **Pedir ao Claude**: a **revisão dos cortes** (primeira revisão: tirar tomadas repetidas e erros, voltar o que faz falta), os **elementos** (ideias-chave e desenhos novos) e a **revisão da legenda** (grafia de marcas, nomes e acentos). O painel chama o Claude sem abrir conversa e mostra uma **sugestão** com uma caixa de marcar em cada item; **só o que a pessoa marca é aplicado**, e cada aplicação guarda o arquivo anterior (o **Desfazer** da própria tela desfaz).

- **Desligável.** O interruptor **Claude por trás** no topo liga e desliga (e escolhe o modelo: sonnet, que é o mais barato, opus ou haiku). `painel.py --sem-claude` abre o painel sem nenhum botão. Sem o Claude Code instalado o interruptor nem aparece. Desligado, o painel funciona exatamente como sem a Fase 8.
- **Só a entrada mínima, sem ferramentas.** O pedido leva a fala e as regras daquela tarefa, nada de pasta, perfil ou caminho. O `claude -p` roda sem nenhuma ferramenta (não lê nem escreve arquivo, não roda comando), um turno só, numa pasta vazia (`.painel/claude/`). O que volta é texto, e o painel só mostra o que passa na conferência: a frase existe, a ação muda de fato o estado, o desenho passa no `validar_svg`, o momento cabe sem bater em outro elemento, a correção não troca um número.
- **Um pedido por vez** em todo o painel. **Cancelar** para o processo. Tempo máximo de 3 minutos.
- **Quanto foi usado.** A caixa mostra, por edição, o número de pedidos, os tokens (unidades de texto) de entrada e de saída e o custo estimado que o Claude Code informa (`claude/uso.json` na pasta da edição). **A porcentagem do plano semanal o Claude Code não informa**: veja no próprio Claude Code.
- **Na conversa.** Cada sugestão fica em `claude/<tarefa>.json` (estado: pendente, aplicada ou descartada). O protocolo de portões da Fase 4 continua valendo: quem prefere revisar na conversa lê `pedidos/<portao>.json` como sempre.

## Conversa e painel juntos

Os dois leem e escrevem o `trabalho.json`. Se a pessoa pedir para revisar um portão na conversa, o orquestrador já gravou `pedidos/<portao>.json`: leia, faça a revisão (`referencias/cortes.md`, `legendas.md`, `elementos-3d.md`...) e aprove com `editar.py aprovar --pasta ... PORTAO --seguir`. Enquanto uma edição está rodando ou na fila no painel, **não** rode `editar.py` nela por fora (o painel recusa o contrário com 409): espere terminar ou cancele.

## Segurança

Como o painel executa, tem defesas:

- **Código de sessão** novo a cada abertura, no endereço do terminal. Vira um cookie `HttpOnly` e `SameSite=Strict` e sai do endereço. Sem ele, a API e os arquivos respondem 401. Se a pessoa abrir `http://localhost:8765` sem o código, a página pede para colá-lo.
- **Host e origem**: o cabeçalho `Host` tem que ser `localhost` ou `127.0.0.1` com a porta do painel (contra o truque de trocar o nome da máquina), a `Origin`, se vier, tem que ser a do painel, e todo pedido que muda algo leva `X-Painel: 1`. Não há CORS.
- **Só ações conhecidas**: `novo`, `aprovar`, `iniciar`, `cancelar`, `ajustar`, `refazer`, `aprovar-entrega`, `abrir-pasta`, as de revisão (cortes e legenda) e as de ajuste (elementos, zoom, som e conferência) e as do Claude por trás (`pedir`, `cancelar`, `aplicar`, `descartar`, `ligar`), cada uma com valores de uma lista ou dentro de um limite. Não existe campo que receba um comando. Vídeos só de `material-bruto/`, edições só de `saida/` (nome simples, com `trabalho.json`), escolhas só da lista permitida.
- Ouve só em `127.0.0.1`. Nada sai do computador.

## Limites

- A fila e o processo de uma etapa não sobrevivem a fechar o painel; a edição, sim (`trabalho.json`): abra o painel de novo e clique em **Retomar**.
- Na tela de cortes não há "refazer" (só desfazer) nem arrastar para ajustar o tempo: a escolha é sempre por frase. Nos elementos também não se arrasta: o momento é um número.
- A tela de som não monta a mistura (voz, música e efeitos juntos): ouve cada som sozinho. A mistura se confere na amostra.
- A prévia da legenda mostra o enquadramento original (sem o zoom da câmera) e não mostra os elementos 3D.
- O painel não decide: o "ok" é sempre um clique da pessoa. O Claude por trás só **sugere**, e a sugestão é conferida e aplicada item a item, com desfazer.
