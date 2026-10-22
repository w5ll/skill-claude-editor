# Elementos 3D no vídeo

Os mesmos elementos do carrossel (vidro fosco e metal escovado no tom #7f8caa, luz de cima), agora animados e entrando no instante em que o Well fala a palavra. É o que amarra o vídeo à identidade do perfil.

## Catálogo e quando usar

| Elemento | Animação | Combina com a fala sobre |
| --- | --- | --- |
| `mensagem` | três pontinhos "digitando" | WhatsApp, mensagem, responder, atendimento, conversa |
| `relogio` | ponteiro correndo | minutos, horas, demora, prazo, tempo de resposta |
| `funil` | bolinhas (leads) caindo no funil | funil, etapas, jornada, leads, contatos |
| `furo` | leads escorrendo pelo buraco | perder, vazamento, furo, desperdício ("o furo" é a tese do Well) |
| `grafico` | barras subindo uma a uma | resultado, crescimento, faturamento, contratos, números |
| `alvo` | onda saindo do centro | público, foco, nicho, cliente certo |
| `cadeado` | a haste desce e tranca | OAB, ética, regras, segurança, sigilo |
| `lupa` | lente procurando | analisar, descobrir, diagnóstico |
| `esfera`, `anel`, `cubo`, `cristal` | só flutuam | abertura, fecho, ideia abstrata, quando nenhum outro serve |

## Dois modos

- **sobreposto** (padrão): o elemento flutua sobre o vídeo, por 2 s, com o rosto do Well na tela. Posição `topo` (padrão), `esquerda`, `direita` ou `meio`. Rótulo opcional embaixo (ex.: "5 minutos").
- **tela**: por 1 a 3 s a tela vira o fundo escuro da marca, com o elemento, um título curto e o @lunardiwell no topo, como um slide do carrossel no meio do vídeo. A voz continua. Use para a ideia principal do vídeo, uma ou duas vezes no máximo.

No título e no rótulo, `*palavra*` fica na cor de destaque, como no carrossel. Uma ou duas palavras, nunca a frase inteira.

## Critério

- Elemento só onde ajuda a entender ou marcar a ideia. Um a cada 6 s no máximo (`--intervalo`); num Reels de 40 s, 3 a 5 elementos bastam.
- O primeiro elemento no gancho (primeiros 3 s) costuma segurar a atenção.
- Nunca em cima do rosto ou da boca. Olhe os quadros de inspeção: se o Well está alto no quadro, use `esquerda` ou `direita`, ou o modo `tela`.
- Número no rótulo só se o Well falou esse número. Não invente dado, resultado nem promessa (regra da OAB vale aqui também).
- No modo tela com título, a legenda continua aparecendo embaixo. Se o título repete exatamente a fala, tudo bem; se ficar poluído, encurte o título.

## Como fazer

```bash
python scripts/elementos.py sugerir --pasta saida/... [--modo sobreposto|tela] [--intervalo 6]
```

Mostra a lista de elementos com o momento e a palavra que chamou cada um. Revise `elementos.json`:

```json
{"elemento": "relogio", "inicio": 7.18, "duracao": 2.0, "modo": "sobreposto",
 "posicao": "topo", "texto": "*5 minutos*", "gatilho": "cinco minutos", "fala_em": 7.30}
```

- `inicio` em segundos do vídeo **já editado**. O padrão é entrar 0,12 s antes da palavra.
- Pode apagar, trocar `elemento`, mudar `modo`, `posicao`, `texto`, `duracao` (1 a 3 s) ou acrescentar um item à mão.
- Se o corte mudar depois, rode `sugerir` de novo (a versão anterior fica em `elementos.anterior.json`).

O `renderizar.py` desenha os elementos que faltam e coloca no vídeo, por baixo da legenda. Para renderizar sem eles: `--sem-elementos`. O `conferir.py` gera um quadro no meio de cada elemento (`.elementoNN.jpg`): olhe todos antes de entregar.

Os desenhos ficam em `templates/elementos.html`. Se um elemento novo entrar no carrossel, copie o desenho para lá também.
