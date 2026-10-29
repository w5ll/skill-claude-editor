# Gancho e olhar

Os dois scripts **só sugerem**. Nada muda no vídeo sem o "ok" de quem grava.

## Gancho (`gancho.py`)

Os 3 primeiros segundos do vídeo **já cortado** ganham uma nota de 0 a 5, um ponto por sinal:

| Sinal | O que pede |
| --- | --- |
| Começa rápido | primeira palavra em até 0,3 s |
| Sem enrolação | a primeira frase não abre com "oi", "olá", "então", "bom", "gente", "pessoal", "fala" |
| Fala com a pessoa | "você", "seu", "sua", "te" ou uma pergunta |
| Promessa ou tensão | número, "nunca", "nenhum", "ninguém", "erro", "segredo", "problema", "motivo", "como", "porque" |
| Frase curta | a primeira frase tem de 3 a 14 palavras e até 5 s |

Nota 4 ou 5: deixe como está. Nota 3: diga a nota e mantenha, a não ser que haja uma saudação a cortar. Nota 2 ou menos: o script propõe.

### Propostas

- **`cortar_abertura`**: a primeira frase é só saudação ("Oi, pessoal", "Fala, gente, tudo bem?") e a seguinte entra no assunto. É a mais segura: tira palavra que não carrega conteúdo. Mesmo assim, saudação de marca ou de série que a pessoa quer manter fica, é escolha dela.
- **`puxar_frase`**: leva uma frase inteira do meio para o começo. Troca a ordem do que foi dito, então confira se a frase **faz sentido sem o que vinha antes**: uma frase que começa com "isso", "então" ou "por causa disso" depende do contexto e não deve ser puxada, mesmo com nota alta. Se a frase ficar no começo e o resto do vídeo continuar fazendo sentido, aceite; senão, descarte. Só frases inteiras, que fecham em ponto, interrogação ou exclamação, dentro de um único trecho e nunca a última (o fecho com chamada fica no fim).
- **`tela_cheia`**: abrir com um elemento em tela cheia no momento em que a palavra-gatilho é falada. Não muda a fala; entra pelo `elementos.py sugerir --modo tela`. Veja `referencias/elementos-3d.md`.

### Regras

- Nunca puxe uma frase que carrega ressalva, condição, negação que muda o sentido ou aviso obrigatório (`referencias/cortes.md`): fora do lugar, ela perde a ressalva que vinha junto.
- Nunca puxe e também deixe no lugar: a mesma frase duas vezes é repetição e a conferência reclama.
- O roteiro, se houver, diz qual era o gancho planejado. Se o gancho do roteiro está gravado depois, mova-o no `cortes.json` à mão (veja `referencias/cortes.md`) em vez de usar o `gancho.py`.
- Depois de `aplicar`, rode de novo `rosto.py`, `elementos.py sugerir`, `camera.py` e `legendas.py`. A versão anterior do corte fica em `cortes.anterior.json`; para desfazer, copie-a de volta.

## Olhar (`olhar.py`)

Marca os trechos em que a **cabeça** fica abaixada (olhando papel ou celular) ou virada para o lado (olhando outra tela) por 1,2 s ou mais. É a medida do nariz em relação aos olhos e à boca, comparada com o normal do próprio vídeo.

**O que não dá para saber:** para onde os olhos olham com a cabeça parada. Quem lê só mexendo os olhos não é marcado.

**Falso alarme:** pensar olhando para baixo, olhar o teclado, coçar a testa. Por isso o script faz a folha `olhar-quadros.jpg`: um quadro normal ao lado de um quadro de cada trecho marcado. Olhe a folha e descarte o que não for leitura antes de propor.

### O que fazer com um trecho de leitura

1. **Existe outra tomada da mesma frase em que a pessoa olha para a câmera?** Use ela (`referencias/cortes.md`, "Escolhendo a tomada"). É a melhor solução.
2. **Dá para cortar sem perder conteúdo?** Pausa, muleta ou frase repetida dentro do trecho podem sair.
3. **Senão, `olhar.py zoom`**: um zoom de 115% sobre o trecho, com margem de 0,2 s para cada lado e no mínimo 2,5 s. Muda o enquadramento, o que distrai o olho de quem assiste, mas não esconde o fato de que a pessoa está lendo. Diga isso à pessoa: o remédio de verdade é gravar de novo olhando para a câmera ou usar um aplicativo de texto rolante perto da lente (`referencias/gravacao.md`).

O zoom nunca entra em trecho que tem elemento 3D na tela (o script avisa qual pulou).

## Limiares e ajustes

Os números (inclinação 0,05 acima do normal, giro 0,12) foram calibrados na primeira edição real (29/10/2026): um vídeo de 3:26 sem leitura, 2.083 medidas, a pessoa falando para a câmera e olhando para o lado algumas vezes.

- Normal do vídeo: inclinação 0,561 (desvio típico 0,02; 95% das medidas até 0,035 acima); giro entre -0,09 e +0,12 em 90% das medidas.
- Os limiares que a teoria sugeria (0,07 e 0,25) não marcaram nada. Com giro 0,10 saíram 4 trechos, e a folha mostrou que os 2 mais fracos eram falso alarme (olhando para a câmera, com a cabeça levemente inclinada) e os 2 mais fortes eram olhar para o lado de verdade.
- Com 0,05 e 0,12 saiu 1 trecho (olhar para o lado em 3:12, por 2,8 s), sem falso alarme. Um olhar para o lado de cerca de 1 s (em 2:44) ficou de fora por não passar de 1,2 s.

**Ainda não calibrado:** leitura com a cabeça para baixo. Esse vídeo não tinha. O limiar de inclinação (0,05) vem da dispersão do próprio vídeo, não de um caso de leitura. Na primeira edição de um vídeo lido do roteiro, confira a folha: se marcou demais, suba `LIMIAR_INCLINACAO`; se deixou passar leitura clara, desça. Anote aqui.
