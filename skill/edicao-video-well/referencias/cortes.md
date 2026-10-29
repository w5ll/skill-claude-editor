# Critérios de corte

O script propõe, você decide. Depois de rodar `propor_cortes.py`, leia os trechos como se fosse o Well assistindo: o texto emendado tem que soar como uma fala só, natural, com o sentido que ele quis.

## O que sai

- Pausa longa entre frases. No ritmo natural, fica uma respiração curta (cerca de 0,3 s no fim de frase, 0,2 s no meio). No dinâmico, quase colado.
- Respiração audível e barulho sem fala (clique de boca, cadeira, tosse).
- Começo errado e frase regravada: fica a versão completa e mais fluida.
- Palavra repetida em seguida ("perde no WhatsApp, perde no WhatsApp").
- Hesitação: "ahn", "hum", "é..." arrastado.
- Silêncio do começo (antes da primeira palavra) e do fim.

## O que nunca sai

- Ressalva, condição e negação: "não", "nem sempre", "depende do caso", "em regra". Tirar isso muda o que o Well disse.
- Qualquer aviso que a OAB exige ou que deixa o conteúdo informativo em vez de promessa de resultado. Na dúvida, mantenha.
- Pausa de efeito: a pausa antes de um número, de uma virada ou do fecho. Se o roteiro marca pausa, ou a fala claramente espera o espectador, mantenha.
- O final da última palavra. A folga depois da fala existe para isso.

## Escolhendo a tomada

Quando a mesma frase aparece mais de uma vez:

1. Fica a que está inteira (sem tropeço no meio).
2. Entre as inteiras, a mais fluida e com a entonação mais firme.
3. A última não é automaticamente a melhor.
4. Se for preciso juntar metade de uma tomada com metade de outra, só faça se o corte cair numa pausa natural e o tom for o mesmo. Nunca emende no meio de uma palavra.

Sem ouvir, você decide pelo texto e pela confiança da transcrição (`conf` em `transcricoes/`): tomada com palavra de confiança baixa ou palavra longa demais costuma ter tropeço. Na dúvida entre duas tomadas, mantenha a mais completa e avise o Well na entrega.

## Estrutura do vídeo

Os vídeos do Well seguem o roteiro da skill de conteúdo: gancho nos primeiros segundos, desenvolvimento, fecho com chamada. Se o bruto tiver o gancho gravado depois (ele refez no fim), mova o trecho do gancho para o começo no `cortes.json`. Reordenar é permitido; inventar frase não.

Duração: a que o material pede. Não estique nem corte conteúdo para caber num tempo, a não ser que o Well peça.

## Mexendo no cortes.json

```json
{"video": 0, "inicio": 12.34, "fim": 18.90, "texto": "..."}
```

- `video` é a posição do arquivo na lista (0 é o primeiro).
- `inicio` e `fim` em segundos do arquivo original.
- O vídeo final segue a ordem da lista `trechos`.
- Para tirar um trecho, apague o objeto. Para tirar o meio de um trecho, divida em dois.
- Ao mexer numa borda, deixe pelo menos 0,07 s antes da primeira sílaba e 0,06 s depois da última.
- `"ganho_db": 5.0` aumenta (ou, negativo, abaixa) o volume só daquele trecho. Use o valor que a conferência sugerir quando uma tomada sai mais baixa que as outras.
- Depois de mexer, rode de novo `rosto.py`, `camera.py planejar` (se tiver câmera) e `legendas.py`, porque os tempos mudaram.

## Conferência

`conferir.py` avisa se alguma palavra ficou cortada no meio numa emenda e, com `--retranscrever`, compara a fala do resultado com o texto esperado. Abaixo de 85% de semelhança, algo sumiu ou foi engolido: procure a emenda culpada.

Também falha quando:

- um trecho toca de novo o pedaço do anterior (mesmo tempo do vídeo, ou começa com as mesmas 3 palavras em que o outro termina);
- sobra silêncio sem fala acima de 0,7 s (`--pausa-max`). Pausa de efeito que fica de propósito: passe o segundo dela em `--pausas-ok 12.3`;
- há estalo numa emenda, quadro preto, ou um trecho com volume fora do resto (ela diz o `ganho_db`).

Olhe sempre as folhas de emendas (`.emendasNN.jpg`): cada linha mostra os 2 últimos quadros do trecho que sai e os 2 primeiros do que entra. Pulo de imagem grande entre a 2ª e a 3ª coluna é emenda que aparece.
