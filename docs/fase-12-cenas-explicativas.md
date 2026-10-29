# Fase 12. Cenas explicativas sincronizadas com a fala

Quarta e última fase da trilha B. Um script novo (`cenas.py`), um molde novo (`templates/cenas.html`) e uma mudança pequena em `elementos.py` e `som.py`.

## Objetivo

Os elementos 3D ilustram uma palavra. Falta mostrar a **estrutura** do que a pessoa explica: uma lista de passos que aparecem enquanto ela os fala, um antes e depois, um número que sobe. A fase cria quatro tipos de **cena**, com texto e números animados na marca, cada parte entrando **no instante em que é falada**.

## Os quatro tipos

| Tipo | O que mostra | Quando a fala dispara |
| --- | --- | --- |
| `lista` | título e de 2 a 5 passos numerados | cada passo entra quando a pessoa o fala ("primeiro...", "segundo...") |
| `antes-depois` | o "antes" na tela e, depois, o "depois" com uma seta | o "depois" entra quando é falado |
| `numero` | um número grande que sobe até o valor, com rótulo ("R$ 130 mil", "30%") | o número começa a subir quando é falado |
| `de-para` | um número que vira outro ("de 1 milhão para 130 mil") | o segundo número entra quando é falado |

Dois modos, como nos elementos:

- **`painel`** (padrão): um cartão com a marca, no lugar livre do quadro (acima ou abaixo do rosto, já com o zoom da câmera). A pessoa continua na tela.
- **`tela`**: a tela inteira vira o fundo da marca por no máximo 6 s, como um slide do carrossel. A voz continua.

## Regras que não mudam

- A cena só repete o que a pessoa falou. **Todo número da cena tem que ter sido falado** (o `validar` confere, inclusive "cento e trinta mil"). O texto dos passos é um resumo curto da fala, nunca uma afirmação nova.
- Nada entra sem o "ok" na linha ✨ do cartão, com a folha de prévia.
- Cena é um elemento: entra no `elementos.json`, não se sobrepõe a outro elemento e deixa pelo menos 1,5 s de folga.
- A cena não esconde o rosto: o painel foge dele; a tela é curta e só com o "ok".
- Mesma identidade: fonte Sora ExtraBold, cores de `marca.json`, entrada de 0,45 s e saída de 0,3 s.
- Tudo local, tudo em português.

## O item no `elementos.json`

```json
{"elemento": "cena:lista", "modo": "sobreposto", "inicio": 12.0, "duracao": 9.0, "posicao": "auto",
 "cena": {"titulo": "Três erros no planejamento",
          "passos": [{"texto": "Não ter meta", "gatilho": "primeiro", "fala_em": 12.9},
                     {"texto": "Não medir", "gatilho": "segundo", "fala_em": 15.4},
                     {"texto": "Desistir cedo", "gatilho": "terceiro", "fala_em": 18.0}]}}
```

- `modo` é `sobreposto` (o painel) ou `tela`. O lugar do painel é calculado na hora de desenhar (como a posição `auto` dos elementos), então mudar o texto ou o tempo não deixa a posição velha.
- O momento de cada parte vem de `fala_em` (segundo no vídeo cortado). Mudar `inicio` não desloca a sincronia.
- `antes-depois`: `{"antes": {"texto", ...}, "depois": {"texto", "fala_em"}}`. `numero`: `{"valor", "prefixo", "sufixo", "rotulo", "decimais", "fala_em"}`. `de-para`: `{"de": {"valor", "prefixo", "sufixo"}, "para": {...}, "rotulo", "fala_em"}`.
- Números são mostrados no padrão brasileiro (`1.250`, `2,5`). Para "130 mil", use `valor: 130` e `sufixo: " mil"`, como foi falado.

Limites: título até 6 palavras, passo ou texto até 6 palavras, rótulo até 5. Painel de 3 a 14 s; tela de 2 a 6 s. A duração padrão é até o último gatilho mais 2 s de leitura.

## `cenas.py`

- `sugerir --pasta ...`: lê a fala já cortada e propõe cenas (grava `cenas-sugeridas.json` e imprime):
  - **lista**: duas ou mais ordens seguidas ("primeiro", "segundo", "terceiro"...) em até 40 s; o texto de cada passo são as palavras que vêm depois da ordem, até a pontuação ou 6 palavras;
  - **antes-depois**: "antes" seguido, em até 10 s, de "agora", "hoje", "depois" ou "atualmente";
  - **de-para**: "de <número> para <número>" (ou "a");
  - **numero**: no máximo os 2 números mais fortes (reais, porcentagem, "mil", "milhão") que não estão num de-para.
  O texto sai cru, das próprias palavras da pessoa: o Claude resume e corrige antes de mostrar.
- `aplicar N --pasta ... [--modo painel|tela]`: transforma a proposta N em item do `elementos.json` (recusa se encosta em outro elemento).
- `validar --pasta ...`: confere cada cena (campos, limites, sincronia dentro da duração, **gatilho falado**, **número falado**, folga dos outros elementos) e diz em português o que está errado.
- `previa --pasta ... [--formato ...]`: monta `cenas-previa.jpg`: um quadro em cada momento em que algo entra e no fim, sobre o vídeo, uma linha por cena. É a imagem do cartão.

## Mudanças em arquivos que já existem

- `elementos.py` (compartilhado): reconhece `cena:TIPO` em `desenhar` e `pasta_do_item` (a cena entra na chave do cache); o lugar do painel é resolvido por `cenas.resolver_caixa`. Os 12 elementos e os gerados não mudam.
- `som.py` (compartilhado): a cena tem efeito de passagem curta ao entrar (a tela usa o de tela) e um clique a cada parte que entra, respeitando o espaço mínimo de 1,2 s entre efeitos.
- `assets/sons/sons.json`: `por_elemento.cena`.
- `SKILL.md`, `referencias/cenas.md`, README.

## Testes (`tests/test_fase12.py`)

1. Valores falados: "cento e trinta mil" dá 130000 e 130; "30%" dá 30; "2,5" dá 2,5.
2. `sugerir` acha a lista de três ordens com o tempo de cada passo, o antes e depois, o de-para e o número; não acha lista com uma ordem só; não marca "segundo" como ordem quando é o tempo ("em um segundo").
3. `validar` recusa: número que não foi falado, gatilho que não existe na fala, passo antes do início, duração curta demais para o último passo, mais de 5 passos, tela de 8 s, sobreposição com outro elemento.
4. `aplicar` escreve o item e recusa conflito; o `inicio` movido não muda a sincronia (`em` é calculado de `fala_em`).
5. `resolver_caixa`: o painel fica fora do rosto (acima ou abaixo), dentro das margens, e recusa (e sugere a tela) quando não cabe.
6. Cada tipo é desenhado no navegador nos dois modos, o quadro antes do gatilho não mostra a parte seguinte e o quadro depois mostra (o teste compara os quadros).
7. O efeito sonoro de cada parte entra no plano de som e respeita 1,2 s de espaço.
8. A chave de cache dos 12 elementos continua a mesma.
