# Fase 9. Gancho e olhar

Especificação da primeira fase da trilha B. Dois scripts novos, `gancho.py` e `olhar.py`, que **só sugerem**: nada muda no vídeo sem o "ok" de quem grava.

## Objetivo

1. **Gancho.** Os 3 primeiros segundos decidem se a pessoa continua assistindo. Hoje a skill corta o silêncio do começo, mas não avalia o que sobra. A fase mede se o começo prende e, quando não prende, propõe puxar do meio uma frase mais forte, ou abrir com um elemento em tela cheia.
2. **Olhar.** Quem grava com roteiro às vezes lê, e o espectador percebe. A fase marca os trechos em que a cabeça abaixa ou vira para o lado por tempo suficiente para parecer leitura, e sugere um zoom para disfarçar ou um corte.

## Regras que não mudam

- Nada é aplicado sem o "ok", e a linha entra no cartão como qualquer outro ajuste.
- Reordenar frases inteiras é permitido (`referencias/cortes.md`); inventar frase, juntar metades de frases diferentes ou tirar ressalva, negação e aviso obrigatório não é.
- Todo trecho de fala movido tem que começar e terminar em fronteira de frase.
- O zoom de disfarce segue as regras da câmera: nunca muda com elemento 3D na tela e nunca passa de 1,3.
- Tudo local, sem enviar nada para fora.

## Parte 1. Gancho (`gancho.py`)

### `gancho.py avaliar --pasta saida/...`

Lê `cortes.json` e as transcrições. Olha os primeiros 3 s do vídeo **já cortado** e dá uma nota de 0 a 5, somando 1 ponto por sinal:

| Sinal | Como mede |
| --- | --- |
| Começa rápido | a primeira palavra sai em até 0,3 s |
| Sem enrolação | a primeira frase não abre com saudação ou muleta ("oi", "olá", "e aí", "então", "bom", "gente", "pessoal", "fala") |
| Fala com a pessoa | tem "você", "vocês", "seu", "sua", "te" ou uma pergunta nos 3 s |
| Promessa ou tensão | tem número, negação forte ("nunca", "nenhum", "não"), "erro", "segredo", "problema", "motivo", "como", "por que" |
| Frase curta | a primeira frase tem de 3 a 14 palavras (e o primeiro bloco falado cabe em 4 s) |

Grava `gancho.json` com a nota, o texto dos 3 s, os sinais que faltaram e as **propostas**, da mais leve à mais forte:

1. `cortar_abertura`: a primeira frase é só saudação ou muleta e a frase seguinte já entra no assunto. Propõe começar na seguinte.
2. `puxar_frase`: nota 2 ou menos. Procura nas frases do resto do vídeo a de maior nota (mesmos sinais, mais 1 ponto se for pergunta). Só entram frases **inteiras** (fecham em ponto, interrogação ou exclamação, e a seguinte começa depois de uma pausa), de 3 a 12 palavras e de 1,5 a 6 s, que não sejam a última frase do vídeo (fecho com chamada fica no fim). Propõe mover essa frase para o começo. A nota da candidata tem que ser pelo menos 2 pontos maior que a do começo atual.
3. `tela_cheia`: sugere abrir com um elemento em tela cheia nos 3 primeiros segundos (usa `elementos.py`, modo tela), quando o começo tem uma palavra-gatilho de elemento.

Cada proposta diz o motivo em português e o que muda na duração. O script mostra tudo na tela.

### `gancho.py aplicar --pasta saida/... --proposta puxar_frase|cortar_abertura [--frase N]`

Aplica **uma** proposta ao `cortes.json`. Antes, guarda a versão atual em `cortes.anterior.json` (nunca sobrescreve um backup: usa `.2`, `.3`...).

- `cortar_abertura`: tira do começo os trechos da saudação, cortando no silêncio entre as palavras.
- `puxar_frase`: divide o trecho em que a frase está, nos silêncios antes e depois dela, e coloca o pedaço dela como primeiro trecho. O texto de cada trecho é recalculado.

Depois de aplicar, `rosto.py`, `elementos.py`, `camera.py` e `legendas.py` precisam rodar de novo (os scripts já avisam quando o corte mudou).

## Parte 2. Olhar (`olhar.py`)

### O que dá e o que não dá para medir

O detector de rosto (YuNet) devolve 5 pontos: os dois olhos, o nariz e as duas pontas da boca. Dá para saber para onde a **cabeça** aponta, não para onde os **olhos** olham. Então:

- **Cabeça para baixo** (olhando papel ou celular): o nariz se afasta da linha dos olhos em direção à boca. Medida: `inclinação = (nariz_y - olhos_y) / (boca_y - olhos_y)`.
- **Cabeça virada para o lado** (olhando outra tela): o nariz sai do meio dos olhos. Medida: `giro = (nariz_x - meio_dos_olhos_x) / distância_entre_os_olhos`.
- **Só os olhos se mexendo com a cabeça parada** não é detectado. Está dito na documentação.

As duas medidas são comparadas com a **mediana do próprio vídeo** (a pessoa olhando para a câmera é a maior parte do tempo), porque cada pessoa e cada ângulo de celular têm o seu valor normal.

### `olhar.py medir --pasta saida/... [--formato 9:16]`

1. Mede os pontos do rosto 10 vezes por segundo nos trechos que ficam (a mesma passada do `rosto.py`).
2. Suaviza com a mediana de 5 medidas.
3. Marca como desvio quando a inclinação passa da mediana em **mais de 0,07 e mais de 3 vezes o desvio típico** (isso é cerca de 12 graus), ou o giro passa de **0,25**, que é cerca de 15 graus.
4. Junta desvios separados por até 0,3 s e **só guarda os que duram 1,2 s ou mais**.
5. Grava `olhar.json` com cada trecho (início, fim, tipo `baixo` ou `lado`, intensidade, as palavras ditas), e uma folha `olhar-quadros.jpg` com um quadro do meio de cada trecho marcado e um quadro normal ao lado para comparar. **Quem revisa olha a folha antes de aceitar**: pensar olhando para baixo também é desvio.

### `olhar.py zoom --pasta saida/... [--zoom 1.15]`

Escreve em `camera.json` um bloco de zoom (padrão 1,15) sobre cada trecho marcado, com o motivo `disfarçar leitura`. Pula o trecho que cruza um elemento 3D e diz qual pulou. Se não houver `camera.json`, cria um só com esses blocos (câmera parada no resto). Só roda com o "ok" do zoom no cartão.

Cortar o trecho é decisão do Claude e da pessoa, no `cortes.json`, como já é hoje: o `olhar.json` mostra as palavras do trecho para saber se a mesma frase tem outra tomada.

## Mudanças em arquivos que já existem

- `rosto.py`: `medir_video` passa a guardar também o nariz e os olhos (`nariz_x`, `nariz_y`, `olho_d_x`, `olho_e_x`) em cada medida. O `rosto.json` não muda.
- `SKILL.md`: passo 3c (gancho e olhar) depois do rosto, linha 🪝 no cartão, regras novas.
- `referencias/gancho-e-olhar.md`: critérios e como ler as propostas.
- `referencias/rosto-e-camera.md`: remete para o `olhar.py`.
- README: marca a Fase 9.

## Testes

Não há vídeo no repositório, então os testes são com dados sintéticos e rodam sem o ffmpeg:

1. `avaliar` dá nota baixa a um começo com "oi pessoal, então hoje eu vou falar" e nota alta a "você nunca perde 5 clientes por mês?".
2. `puxar_frase` só escolhe frase inteira, nunca a última, e a nota da candidata é pelo menos 2 pontos maior.
3. `aplicar puxar_frase` num `cortes.json` de exemplo: o total de tempo é o mesmo, a ordem das palavras só muda no trecho puxado, os cortes caem em silêncio, e o backup existe.
4. `olhar` marca uma sequência sintética com 2 s de inclinação alta, ignora 0,8 s, junta dois desvios separados por 0,2 s e ignora ruído de uma medida só.
5. `zoom` pula o trecho que cruza um elemento e respeita o limite de 1,3.

E um teste com um vídeo de verdade assim que houver um bruto à mão. **Os limiares de 0,07 e 0,25 foram calculados na teoria e precisam ser ajustados com vídeo real.**
