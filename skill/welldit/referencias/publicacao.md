# Publicação: capa, texto do post e limites do Instagram

Tudo aqui acontece **depois** que a pessoa aprovou o vídeo. A skill nunca publica: entrega uma pasta pronta (`publicacao-<nome>/`) com o vídeo, a capa, o texto do post, a legenda em arquivo e o resultado da conferência.

## Capa

`publicar.py capa-opcoes` escolhe 4 quadros do vídeo pronto. O critério é o de uma boa miniatura: rosto grande (25% a 60% da largura), no meio, nítido (sem tremida) e com a boca fechada (instante entre palavras). Descarta quadro colado numa emenda.

Olhe a folha `capa-opcoes.jpg` antes de mostrar. A nota é só um filtro: boca torta, olho fechado, mão na frente e expressão estranha o script não vê. Se nenhum dos 4 servir, use `--segundo` com um instante que você escolheu olhando o vídeo.

### O título

- Curto: até 8 palavras (acima de 8 o script avisa, acima de 14 recusa). Uma promessa, uma pergunta ou o número que prende, como o gancho.
- Uma palavra ou número em destaque, entre asteriscos: `"Você perde *5 clientes* por mês"`. Na cor de destaque da marca.
- **Só o que a pessoa falou.** Número, nome e promessa que não estão na fala o script avisa, e você confirma com ela. Não prometa resultado que ela não prometeu.
- Sem aviso obrigatório na capa: ele vai no texto do post.

### Onde o título fica

O script põe o título abaixo ou acima do rosto, onde houver mais espaço, e dentro do **corte 3:4 da grade do perfil**: o Instagram mostra a grade em 3:4, então uma capa 1080×1920 perde 240 px em cima e 240 embaixo. Também respeita as margens de segurança dos botões. Olhe `capa-grade-vNNN.jpg`: à esquerda a capa com o corte marcado, à direita como fica no perfil. Se o rosto ocupa a tela toda e não há faixa livre de 260 px, o script diz para escolher outro quadro.

As cores e a fonte do título são as do **perfil de marca** (`--perfil NOME`; sem ele, o perfil da pasta do trabalho). A capa sai de um **quadro limpo**: o script renderiza o instante escolhido sem legenda, sem elementos 3D e sem som, com o mesmo formato e a mesma cor do vídeo.

## Texto do post

1. Se o vídeo saiu de um roteiro da skill de conteúdo, o texto do post vem de lá. Use esse.
2. Senão, escreva um rascunho curto: uma primeira linha que prende (a promessa do vídeo, com as palavras da pessoa), duas ou três linhas do que ela explicou, a chamada que ela fez no fim, e as hashtags.
3. **Nada que ela não disse.** Número, nome, resultado e garantia só entram se estiverem na fala. O `publicar.py texto` avisa os números que não achou.
4. Aviso obrigatório do assunto (por exemplo, o aviso que a profissão exige em publicidade) entra no texto. Se a pessoa tem uma lista deles, confira se todos estão.
5. Mostre à pessoa e espere o "ok". Sem o "ok", o pacote sai sem texto de verdade: não finja que está aprovado.

Limites que o script confere: 2.200 caracteres (falha acima), hashtags (aviso acima de 5, falha acima de 30).

## Limites do Instagram

Ficam em `assets/instagram.json`, com a data da conferência e as fontes. **Os números vieram de blogs e ferramentas de terceiros, que divergem entre si**, e o Instagram muda isso com frequência. Cada item tem dois níveis:

- **FALHOU**: o que ninguém discute (mais de 4 GB, sem som, fora de 9:16, abaixo de 720 px, texto acima de 2.200 caracteres, mais de 30 hashtags, duração acima do maior valor citado).
- **aviso**: o que depende da conta e da versão (mais de 90 s, mais de 5 hashtags, arquivo acima de 650 MB, menos de 1080 de largura).

Quando a pessoa tiver uma conta com regra diferente (Reels de até 3 min liberados, por exemplo), ajuste o arquivo e atualize a data. Diga a ela, na entrega, que os limites devem ser conferidos na ajuda oficial.

### Margens de segurança

A legenda é conferida contra as margens em 1080×1920: 250 px em cima, 400 px embaixo (legenda do post e botões) e 120 px à direita (curtir, comentar, compartilhar). A legenda padrão da skill já respeita. Elementos 3D não são conferidos nas margens, porque a posição deles é por nome (topo, esquerda...) e não por pixel: olhe a folha de quadros da conferência.

## O pacote

`publicar.py pacote` roda a conferência e monta a pasta. Se algo **falhou**, não monta (a não ser com `--mesmo-assim`, e diga à pessoa por quê). Avisos entram no `conferencia.md` e na sua mensagem. A pasta nunca sobrescreve outra: a segunda vez ganha `-2`.

O vídeo dentro da pasta é um link para o arquivo original (não duplica o espaço); se o disco não permitir link, é uma cópia.

## O que ainda não foi testado com vídeo de verdade

A escolha dos 4 quadros (nitidez e posição do rosto) e o quadro limpo vindo do `renderizar.py` só se avaliam com um vídeo real. Na primeira edição, olhe `capa-opcoes.jpg` e anote aqui se os pesos pedem ajuste (`nota_geometrica` e `escolher` em `publicar.py`).
