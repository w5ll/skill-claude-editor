# Cenas explicativas

Os elementos 3D ilustram uma palavra. A cena mostra a **estrutura** do que a pessoa explica, com texto e números animados na marca, cada parte entrando quando é falada. É um item do `elementos.json` (`"elemento": "cena:lista"` etc.), desenhado pelo `elementos.py` com `templates/cenas.html`.

## Os quatro tipos

| Tipo | Quando usar | Entra quando |
| --- | --- | --- |
| `lista` | a pessoa enumera ("primeiro... segundo... terceiro...") | cada passo é falado |
| `antes-depois` | "antes eu... agora eu..." | o "depois" é falado |
| `numero` | um número que sustenta o argumento ("30%", "R$ 130 mil") | o número é falado, e ele sobe até o valor |
| `de-para` | "de 1 milhão para 130 mil" | o segundo número é falado |

Dois modos: **painel** (cartão no lugar livre do quadro, acima ou abaixo do rosto, de 3 a 14 s) e **tela** (tela inteira por 2 a 6 s). Prefira o painel: o rosto continua na tela. Use a tela para a virada do vídeo, no máximo uma vez.

## Fluxo

1. `python scripts/cenas.py sugerir --pasta saida/...` depois de fechar os cortes. Ele propõe e grava `cenas-sugeridas.json`.
2. **Escolha pouco.** Uma cena a cada 15 s no máximo, e só onde a estrutura é o conteúdo. Lista de dois passos pode ser só fala; número que a pessoa só citou de passagem não precisa de cena.
3. `cenas.py aplicar N --pasta ... [--modo tela]` põe a proposta no `elementos.json`.
4. **Resuma os textos.** A proposta traz as palavras cruas da fala; deixe cada passo com 2 a 5 palavras ("Defina uma meta clara", não a frase inteira). Preencha o `titulo` da lista se ajudar ("Três passos"), sem inventar nada.
5. `cenas.py validar --pasta ...` e `cenas.py previa --pasta ...`. Olhe `cenas-previa.jpg`: o painel fica fora do rosto, o texto cabe e lê em tamanho pequeno, cada parte entra no momento certo.
6. Mostre à pessoa a linha ✨ com a folha e espere o "ok".

## Regras

- **Todo número da cena foi falado.** O `validar` confere, inclusive "cento e trinta mil" e "30%". Para "130 mil" use `valor: 130` e `sufixo: " mil"`, como foi falado.
- O texto só resume o que a pessoa disse. Nada de promessa, número ou nome novos. Número ou afirmação que a pessoa quer confirmar também passa por `referencias/fatos.md`, se essa fase estiver no projeto.
- Limites: título até 6 palavras, passo ou texto até 6, rótulo até 5. Lista de 2 a 5 passos.
- A cena não encosta em outro elemento (1,5 s de folga). Se o `sugerir` de elementos já pôs um elemento ali, escolha um dos dois.
- Nunca em cima do rosto. Se o painel não couber fora dele, o script avisa: use a tela, encurte ou tire um passo.
- O efeito sonoro (só se a pessoa pediu efeitos): passagem ao entrar e um clique a cada parte, com 1,2 s no mínimo entre efeitos.

## Ajustar

Os textos e os tempos ficam no `elementos.json`. O tempo de cada parte é `fala_em` (segundo no vídeo cortado); mudar `inicio` não desloca a sincronia. Se mexer nos cortes depois, as cenas precisam de `cenas.py sugerir` de novo (o `fala_em` mudou) e o `elementos.py sugerir` reescreve o arquivo: aplique as cenas por último, ou guarde uma cópia.

## O que ainda não foi testado com vídeo de verdade

O detector de estrutura é heurística sobre a fala transcrita (ordinais, "antes/agora", "de X para Y"). Ele foi testado com frases escritas à mão. Na primeira edição real, anote aqui o que ele deixou passar ou propôs demais.
