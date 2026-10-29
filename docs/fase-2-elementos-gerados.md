# Fase 2. Elementos 3D gerados a partir da fala

Especificação para implementar. Quem implementa: o Claude Code no Mac do Well, com os vídeos de verdade para testar. Substitui a lista fixa de 12 elementos de `docs/proximas-fases.md`.

## Objetivo

Hoje a skill só escolhe entre 12 elementos prontos, procurando palavras na fala. A partir desta fase, o Claude lê a transcrição, escolhe as ideias-chave do vídeo e **desenha um elemento novo** para as que nenhum elemento pronto representa. O desenho segue um molde fixo da marca, entra no cartão como prévia para o Well aprovar, e os que ele gostar viram parte do catálogo.

## Regras que não mudam

- Mesma identidade dos 12 atuais: vidro fosco e metal escovado no tom `#7f8caa`, luz de cima, sombra no chão, fundo transparente, caixa de 400 x 400.
- Mesmo tempo: entrada de 0,45 s (cresce e assenta), animação, saída de 0,3 s. Isso já está em `desenhar(t)` de `templates/elementos.html` e não muda.
- Sem texto dentro do desenho. Rótulo só no campo `texto` do item, e só com palavras e números que o Well falou.
- Sem pessoa, rosto, mão, logotipo ou marca de terceiros. Só objetos e símbolos.
- Elemento pronto primeiro: se um dos 12 serve para a ideia, usa ele. Gerado só onde nenhum serve.
- No máximo 1 elemento a cada 6 s (como hoje), e de 3 a 6 por vídeo de até 2:30.
- Nada entra no vídeo sem aparecer na prévia do cartão e ter o "ok" do Well.

## Como fica

### 1. O desenho: um arquivo SVG por elemento

Cada elemento gerado é um pedaço de SVG em `saida/<trabalho>/elementos-gerados/<nome>.svg`, sem a tag `<svg>` em volta. Ele vale para a caixa `viewBox="0 0 400 400"` e pode usar só:

- Os gradientes que o molde já define em `defs(E)`: `url(#met)`, `url(#met2)`, `url(#lado)`, `url(#brilho)`, `url(#esf)`, `url(#vidro)`, `url(#buraco)`, `url(#sombra)`.
- As cores sólidas `#16161f`, `#0a0a12`, `#eaefef`, `#ffffff` (com `opacity` se quiser).
- As tags `g`, `path`, `circle`, `ellipse`, `rect`, `line`, `polyline`, `polygon`.

Receita de volume (é o que dá o "3D" dos atuais):

1. Sombra no chão: `<ellipse cx="200" cy="368" rx="120" ry="18" fill="url(#sombra)"/>`.
2. A silhueta duas vezes: uma com `fill="url(#lado)" transform="translate(0 20)"` (a espessura) e outra por cima com `fill="url(#met)"` (a face).
3. Um contorno de luz: a mesma silhueta com `fill="none" stroke="url(#brilho)" stroke-width="3"`.
4. Detalhes em `url(#met2)`, `url(#vidro)` ou `#16161f` com `opacity=".75"`.

Limites: no máximo 12 formas, margem de 30 dentro da caixa, nada de `text`, `image`, `use`, `foreignObject`, `script`, `style`, atributos `on...`, `href` ou referência a arquivo externo.

Partes que se mexem levam um `id` com o nome da animação (próximo item).

### 2. As animações prontas

O SVG não traz animação própria: ele marca as partes e escolhe uma das animações abaixo no `elementos.json`. Implementar em `animarPartes(u)` de `templates/elementos.html`, valendo para elemento gerado:

| Animação | Parte com o `id` | O que faz |
| --- | --- | --- |
| `girar` | `#gira` | gira em volta do centro da parte, uma volta a cada 3 s (ou de -25° a 0° e para, com `"parar": true`, para agulha de bússola) |
| `subir` | `#sobe` | sobe 40 unidades e volta, devagar |
| `balancar` | `#balanca` | inclina de -6° a 6°, como barco na onda |
| `tracar` | `#traco` (um `path` com `stroke`) | o traço se desenha do começo ao fim em 1 s (`stroke-dasharray`) e fica |
| `encaixar` | `#encaixa` | a parte desce 60 unidades e encaixa com um pequeno quique, aos 0,3 s |
| `pulsar` | `#pulsa` | cresce 8% e volta, a cada 0,8 s |
| `brilhar` | `#reflexo` | o reflexo passa de lado a lado uma vez |
| `aparecer` | `.passo` (várias partes com essa classe) | as partes aparecem uma a uma, a cada 0,15 s (degraus, barras, moedas) |

Cada animação tem um som padrão (vai para `assets/sons/sons.json`, num bloco novo `por_animacao`): `girar` e `balancar` passagem, `subir` e `encaixar` estalo, `tracar` passagem curta, `pulsar` e `brilhar` brilho, `aparecer` clique.

### 3. O item no `elementos.json`

```json
{"elemento": "gerado:bussola", "svg": "elementos-gerados/bussola.svg", "animacao": "girar",
 "ideia": "saber para onde está indo", "inicio": 0.42, "duracao": 2.0, "modo": "sobreposto",
 "posicao": "auto", "texto": "", "gatilho": "para onde você está indo", "fala_em": 0.54}
```

- `elemento` começa com `gerado:` para o gerado; os 12 atuais continuam com o nome simples.
- `ideia`: a ideia-chave em poucas palavras (aparece no cartão).
- O resto é igual ao de hoje (posição automática fora do rosto, modo sobreposto ou tela, rótulo opcional).

### 4. Mudanças em `scripts/elementos.py`

- `desenhar`: aceitar `gerado:`, ler o SVG da pasta do trabalho, validar e mandar para a página em `montar(cfg)` (`cfg.svg` e `cfg.animacao`). A chave do cache (`pasta_do_item`) passa a incluir o hash do SVG.
- Comando novo `validar`: confere as regras do item 1 e diz o que está errado, em português. `desenhar` recusa SVG inválido.
- Comando novo `previa`: desenha cada elemento do `elementos.json` (prontos e gerados) e monta uma folha `elementos-previa.jpg`. Cada linha mostra o elemento aos 0,2 s, 0,6 s e 1,4 s, com a ideia e o tempo do vídeo ao lado, sobre o fundo escuro da marca e também sobre um quadro do próprio vídeo naquele instante, para ver o contraste.
- Comando novo `promover NOME`: copia o SVG aprovado para `templates/gerados/<nome>.svg` e registra em `templates/gerados/catalogo.json` (nome, animação, ideia, palavras que o chamam, som). O `sugerir` passa a procurar também nesse catálogo, como faz com os 12 de hoje.

Em `templates/elementos.html`, `montar(cfg)` usa `cfg.svg` no lugar de `FORMAS[nome]()` quando ele vier, sempre com `defs(E)` antes.

### 5. O fluxo na skill (`SKILL.md` e `referencias/elementos-3d.md`)

Depois dos cortes e antes da câmera:

1. **Ler a história.** O Claude lê o texto final do corte e escolhe de 3 a 6 ideias-chave: a promessa do gancho, os exemplos concretos, a virada, a conclusão. Prefere ideias que viram objeto (bússola para direção, escada para metas, engrenagem para método, trevo para sorte, barco para "à deriva").
2. **Elemento pronto ou gerado.** Para cada ideia, se um dos 12 (ou do catálogo de gerados) serve, usa ele. Se não, escreve o SVG seguindo a receita do item 1 e escolhe a animação.
3. **Validar e mostrar.** Roda `elementos.py validar` e `elementos.py previa`. Olha a folha: desenho legível em tamanho pequeno, parece da mesma família dos atuais, não lembra nada de mau gosto. Refaz o que não passar.
4. **No cartão**, a linha ✨ passa a dizer quais são, por exemplo: "5 elementos: bússola em 0:01 ('para onde está indo'), escada em 0:05 ('objetivos'), barco em 0:24 ('à deriva'), engrenagem em 1:11 ('disciplinados'), trevo em 2:40 ('sorte'). 3 são novos, veja a prévia". E manda a imagem da prévia junto.
5. **Depois da entrega**, pergunta se algum novo deve ficar no catálogo, e roda `promover` nos que o Well aprovar.

## Testes antes de dar por pronto

1. Os 12 elementos atuais continuam iguais (renderizar uma amostra antiga e comparar os quadros).
2. Criar 4 gerados para o vídeo de planejamento: bússola (`girar` com `"parar": true`), escada (`aparecer`), engrenagem (`girar`), trevo (`brilhar`). Rodar `validar`, `previa` e uma amostra com cada um sobre o rosto.
3. `validar` recusa um SVG com `<script>`, um com `<text>` e um com `href`.
4. Um elemento gerado com posição automática foge do rosto como os atuais.
5. Os efeitos sonoros seguem a animação.
6. `promover` coloca o elemento no catálogo e o `sugerir` passa a achar ele pela palavra.

## Prompt para implementar (colar no Claude Code do Mac)

```text
Implemente a Fase 2 da skill seguindo docs/fase-2-elementos-gerados.md, do começo ao fim. Leia antes skill/edicao-video-well/SKILL.md, referencias/elementos-3d.md, scripts/elementos.py e templates/elementos.html. Use o ambiente .venv. Faça os testes da seção "Testes antes de dar por pronto" com o vídeo de planejamento (saida/2026-10-28_img-5127) e me mostre a folha de prévia dos 4 elementos gerados. Não mude o visual dos 12 elementos atuais. Quando tudo passar, atualize README, SKILL.md e referencias, rode ./empacotar.sh, faça commit e push para a main.
```
