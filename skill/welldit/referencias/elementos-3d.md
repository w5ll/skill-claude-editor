# Elementos 3D no vídeo

Elementos base ARVEN (vidro fosco e metal escovado no tom #7f8caa, luz de cima; as cores seguem o perfil de marca), animados e entrando no instante em que a pessoa fala a palavra. É o que amarra o vídeo à identidade do perfil.

São 12 elementos prontos. Para as ideias que nenhum deles representa, o Claude desenha um elemento novo, mostra a prévia à pessoa e só usa se for aprovado: veja [Elementos gerados](#elementos-gerados).

## Catálogo e quando usar

| Elemento | Animação | Combina com a fala sobre |
| --- | --- | --- |
| `mensagem` | três pontinhos "digitando" | WhatsApp, mensagem, responder, atendimento, conversa |
| `relogio` | ponteiro correndo | minutos, horas, demora, prazo, tempo de resposta |
| `funil` | bolinhas (leads) caindo no funil | funil, etapas, jornada, leads, contatos |
| `furo` | leads escorrendo pelo buraco | perder, vazamento, furo, desperdício (o "furo" é uma ideia forte para quem fala de atendimento e captação) |
| `grafico` | barras subindo uma a uma | resultado, crescimento, faturamento, contratos, números |
| `alvo` | onda saindo do centro | público, foco, nicho, cliente certo |
| `cadeado` | a haste desce e tranca | regras, segurança, disciplina, método (e OAB, ética e sigilo, com o pacote `juridico`) |
| `lupa` | lente procurando | analisar, descobrir, diagnóstico |
| `esfera`, `anel`, `cubo`, `cristal` | só flutuam | abertura, fecho, ideia abstrata, quando nenhum outro serve |

Os gatilhos são organizados em **pacotes**, ligados pelo campo `gatilhos` do perfil: `geral` (sempre), `marketing` (mensagem, funil, público) e `juridico` (OAB, ética, sigilo, contrato). O pacote `geral` reconhece assuntos de gestão e rotina: objetivo, meta, estratégia, sonho (alvo); planejamento, lançamento, caixa, lucro, vendas (gráfico); rotina, agenda, horário (relógio); problema, erro, prejuízo (furo); decisão, enxergar, entender, clareza (lupa); disciplina, método, rigor (cadeado). Se o vídeo for de um assunto que quase não aciona nada, escolha à mão 2 ou 3 momentos fortes e use `esfera`, `cristal` ou o modo tela com um título curto.

## Dois modos

- **sobreposto** (padrão): o elemento flutua sobre o vídeo, por 2 s, com o rosto da pessoa na tela. Posição `auto` (padrão): com `rosto.json`, procura o primeiro lugar que não cobre o rosto (topo, topo menor, esquerda, direita, cada vez menor), já com o zoom da câmera; sem `rosto.json`, fica no topo. Também aceita `topo`, `esquerda`, `direita` ou `meio` fixos, e `"escala": 0.8` para diminuir. Rótulo opcional embaixo (ex.: "5 minutos").
- **tela**: por 1 a 3 s a tela vira o fundo escuro da marca, com o elemento, um título curto e o @ do perfil no topo (se o perfil tiver um), como um slide no meio do vídeo. A voz continua. Use para a ideia principal do vídeo, uma ou duas vezes no máximo.

No título e no rótulo, `*palavra*` fica na cor de destaque do perfil. Uma ou duas palavras, nunca a frase inteira.

## Critério

- Elemento só onde ajuda a entender ou marcar a ideia. Um a cada 6 s no máximo (`--intervalo`); num Reels de 40 s, 3 a 5 elementos bastam.
- O primeiro elemento no gancho (primeiros 3 s) costuma segurar a atenção.
- Nunca em cima do rosto ou da boca. A posição `auto` cuida disso; o `elementos.py desenhar` mostra onde cada um ficou, e se avisar que não achou lugar, use o modo `tela` ou tire o elemento.
- Com efeitos sonoros pedidos, cada elemento ganha o seu som (`som-e-imagem.md`).
- Número no rótulo só se a pessoa falou esse número. Não invente dado, resultado nem promessa (os avisos obrigatórios do perfil valem aqui também).
- No modo tela com título, a legenda continua aparecendo embaixo. Se o título repete exatamente a fala, tudo bem; se ficar poluído, encurte o título.

## Como fazer

```bash
python scripts/elementos.py sugerir --pasta saida/... [--modo sobreposto|tela] [--intervalo 6]
```

Mostra a lista de elementos com o momento e a palavra que chamou cada um. Revise `elementos.json`:

```json
{"elemento": "relogio", "inicio": 7.18, "duracao": 2.0, "modo": "sobreposto",
 "posicao": "auto", "texto": "*5 minutos*", "gatilho": "cinco minutos", "fala_em": 7.30}
```

- `inicio` em segundos do vídeo **já editado**. O padrão é entrar 0,12 s antes da palavra.
- Pode apagar, trocar `elemento`, mudar `modo`, `posicao`, `texto`, `duracao` (1 a 3 s) ou acrescentar um item à mão.
- Se o corte mudar depois, rode `sugerir` de novo (a versão anterior fica em `elementos.anterior.json`).

O `renderizar.py` desenha os elementos que faltam e coloca no vídeo, por baixo da legenda. Para renderizar sem eles: `--sem-elementos`. O `conferir.py` gera um quadro no meio de cada elemento (`.elementoNN.jpg`): olhe todos antes de entregar.

Os desenhos dos 12 prontos ficam em `templates/elementos.html`. Os gerados ficam na pasta do trabalho e, se a pessoa aprovar, no catálogo (`templates/gerados/`).

## Elementos gerados

Os 12 prontos cobrem marketing, atendimento e gestão, e pouco mais. Quando o vídeo fala de outra coisa (direção, método, sorte, estar à deriva), o Claude **desenha um elemento novo** para cada ideia que nenhum pronto representa. O desenho segue um molde fixo da marca, aparece numa prévia para a pessoa aprovar e, se ela gostar, pode ficar no catálogo para os próximos vídeos.

### O fluxo (depois dos cortes, antes da câmera)

1. **Ler a história.** Leia o texto final do corte e escolha de 3 a 6 ideias-chave (para um vídeo de até 2:30): a promessa do gancho, os exemplos concretos, a virada, a conclusão. Prefira ideia que vira objeto: bússola para direção, escada para metas, engrenagem para método, trevo para sorte, barco para "à deriva".
2. **Pronto ou gerado.** Se um dos 12 (ou um do catálogo) serve para a ideia, use ele. Só desenhe onde nenhum serve. No máximo 1 elemento a cada 6 s, como sempre.
3. **Escrever o desenho** em `saida/<trabalho>/elementos-gerados/<nome>.svg` e o item no `elementos.json` (campos abaixo).
4. **Validar e olhar.** Rode `elementos.py validar` e `elementos.py previa` e abra `elementos-previa.jpg`: o desenho é legível em tamanho pequeno, parece da mesma família dos atuais, tem contraste sobre o vídeo e não lembra nada de mau gosto? Refaça o que não passar.
5. **Mostrar à pessoa.** A linha ✨ do cartão diz quais são, com o momento e a palavra de cada um e quantos são novos, e a folha da prévia vai junto. Sem o "ok", os gerados não entram (use só os prontos).
6. **Depois da entrega**, pergunte se algum novo deve ficar no catálogo e rode `promover` nos que ele aprovar.

Valem as mesmas regras dos 12: vidro fosco e metal escovado no tom `#7f8caa`, luz de cima, sombra no chão, fundo transparente; entrada de 0,45 s e saída de 0,3 s (já no molde); sem texto dentro do desenho (rótulo só no campo `texto`, com palavras e números que a pessoa falou); sem pessoa, rosto, mão, logotipo ou marca de terceiros, só objetos e símbolos.

### O desenho

Um arquivo por elemento, só o miolo (sem a tag `<svg>` em volta), valendo para a caixa de 400 x 400. Os quatro modelos estão em `templates/exemplos-gerados/` (bússola, escada, engrenagem, trevo): copie o estilo deles.

Pode usar:

- Os gradientes da marca, que o molde já define: `url(#met)`, `url(#met2)`, `url(#lado)`, `url(#brilho)`, `url(#esf)`, `url(#vidro)`, `url(#buraco)`, `url(#sombra)`.
- As cores sólidas `#16161f`, `#0a0a12`, `#eaefef` e `#ffffff` (com `opacity`, se quiser).
- As tags `g`, `path`, `circle`, `ellipse`, `rect`, `line`, `polyline` e `polygon`.

Receita do volume (é o que dá o "3D" dos atuais):

1. Sombra no chão: `<ellipse cx="200" cy="368" rx="120" ry="18" fill="url(#sombra)"/>`.
2. A silhueta duas vezes: uma com `fill="url(#lado)"` e `transform="translate(0 20)"` (a espessura) e outra por cima com `fill="url(#met)"` (a face).
3. O contorno de luz: `stroke="url(#brilho)" stroke-width="3"` na própria face (ou a mesma silhueta com `fill="none"`).
4. Detalhes em `url(#met2)`, `url(#vidro)` ou `#16161f` com `opacity=".75"`.

Limites: no máximo 12 formas (a sombra conta), margem de 30 dentro da caixa (a sombra não conta), e nada de `text`, `image`, `use`, `foreignObject`, `script`, `style`, `defs`, atributos `on...` (como `onclick`), `href` ou referência a arquivo externo. O `validar` confere tudo isso.

Peça que gira, como a engrenagem, não leva espessura dentro da parte que gira (a espessura giraria junto e o desenho tremeria): deixe o `lado` parado por baixo.

### As animações

O desenho não traz animação própria: ele marca as partes que se mexem e o item escolhe uma das animações abaixo (campo `animacao`). O som segue a animação, quando a pessoa pedir efeitos (`som-e-imagem.md`).

| Animação | Parte marcada | O que faz | Som |
| --- | --- | --- | --- |
| `girar` | `id="gira"` | gira em volta do centro da parte, uma volta a cada 3 s. Com `"parar": true`, vai de -25° até a posição em que a parte foi desenhada e para (agulha de bússola) | passagem |
| `balancar` | `id="balanca"` | inclina de -6° a 6°, como barco na onda | passagem |
| `subir` | `id="sobe"` | sobe 40 e volta, devagar | estalo |
| `encaixar` | `id="encaixa"` | a parte desce 60 e encaixa aos 0,3 s, com um pequeno quique | estalo |
| `tracar` | `id="traco"`, um `path` com `stroke` | o traço se desenha do começo ao fim em 1 s e fica | passagem curta |
| `pulsar` | `id="pulsa"` | cresce 8% e volta, a cada 0,8 s | brilho |
| `brilhar` | `id="reflexo"` | o reflexo passa de lado a lado uma vez. Desenhe uma faixa inclinada, `#ffffff` com `opacity`, no meio do elemento: ela só aparece dentro das faces de metal | brilho |
| `aparecer` | `class="passo"`, em várias partes | as partes aparecem uma a uma, a cada 0,15 s (degraus, barras, moedas) | clique |

O `id` não pode repetir nem ser o nome de um gradiente da marca. A classe `passo` é a única permitida.

### O item no `elementos.json`

```json
{"elemento": "gerado:bussola", "svg": "elementos-gerados/bussola.svg", "animacao": "girar", "parar": true,
 "ideia": "saber para onde está indo", "inicio": 0.42, "duracao": 2.0, "modo": "sobreposto",
 "posicao": "auto", "texto": "", "gatilho": "para onde você está indo", "fala_em": 0.54}
```

- `elemento` começa com `gerado:`; os 12 prontos continuam com o nome simples.
- `ideia` é a ideia-chave em poucas palavras (aparece na prévia e no cartão).
- O resto é igual ao dos prontos: posição `auto` foge do rosto sozinha, modos sobreposto e tela, rótulo opcional.

### Os comandos

```bash
python scripts/elementos.py validar --pasta saida/...                          # confere cada gerado
python scripts/elementos.py validar --arquivo desenho.svg --animacao girar     # um desenho avulso
python scripts/elementos.py previa --pasta saida/... [--formato 9:16]          # gera elementos-previa.jpg
python scripts/elementos.py promover bussola --pasta saida/... --palavras "bussol,rumo"
```

- **validar** diz o que está errado, em português. O `desenhar` e o `renderizar` recusam desenho que não passa.
- **previa** desenha cada elemento do `elementos.json` (prontos e gerados) e monta `elementos-previa.jpg`: uma linha por elemento, com a ideia, o tempo no vídeo e a palavra que chamou, mostrando-o aos 0,2 s, 0,6 s e 1,4 s sobre o fundo escuro da marca e sobre um quadro do próprio vídeo naquele instante (na posição em que ele vai entrar, sem o zoom da câmera). Use o `--formato` do renderizar.
- **promover** copia o desenho aprovado para `templates/gerados/` e registra em `templates/gerados/catalogo.json` o nome, a animação, a ideia, as palavras que o chamam e o som. `--palavras` é o começo das palavras, sem acento ("bussol" pega bússola). Escolha palavras que não chamam um elemento pronto: o `promover` avisa quando chamam.
- O `sugerir` procura primeiro no catálogo e depois nos 12 prontos. Elemento do catálogo entra no `elementos.json` já com `svg`, `animacao` e `ideia`, e o desenho é copiado para a pasta do trabalho.
