---
name: edicao-video-well
description: "Edita os vídeos gravados pelo Well para o Instagram (@lunardiwell): corta pausas, respirações, erros e repetições, junta tomadas, coloca legenda no padrão da marca, faz elementos 3D da marca entrarem quando ele fala a palavra certa, iguala o volume e entrega o MP4 pronto para postar. Use quando ele mandar um vídeo bruto, pedir para editar, cortar, legendar, pôr elementos 3D ou ajustar um vídeo já editado."
---

# Edição de vídeo do Well

Edita no próprio computador os vídeos que o Well grava (normalmente no escritório, celular na vertical, a partir de um roteiro da skill `conteudo-well-advogados`). O objetivo é um vídeo com ritmo, sem pausa morta nem erro, com a fala dele intacta e legenda legível.

Sempre em português, com acentuação, sem travessão e sem termo em inglês sem tradução. O Well não lê inglês: nada de comando, caminho interno, código ou registro do ffmpeg na conversa.

## Arquivos de apoio

| Arquivo | O que tem | Quando ler |
| --- | --- | --- |
| `referencias/cortes.md` | Critérios editoriais: tomada certa, o que cortar, o que nunca cortar | Antes de revisar o `cortes.json` |
| `referencias/legendas.md` | Estilo, posição, grafia dos termos, como corrigir | Antes de gerar e revisar a legenda |
| `referencias/elementos-3d.md` | Catálogo dos elementos 3D, modos, quando usar | Ao sugerir e revisar os elementos |
| `referencias/som-e-imagem.md` | Volume, HDR do iPhone, formato, cor, música | Ao montar o cartão e renderizar |
| `referencias/gravacao.md` | Dicas para o Well gravar de um jeito que edita melhor | Quando o bruto vier com problema recorrente |
| `referencias/instalacao.md` | O que precisa estar instalado | Se faltar alguma ferramenta |
| `marca.json` | Cores da marca (as mesmas do carrossel) | Só se for mudar a cor da legenda |

Scripts em `scripts/` (rodar de dentro dessa pasta ou com o caminho completo). Todos aceitam `--help`.

## O fluxo

**Inspecionar → mostrar o cartão de ajustes → esperar o "ok" do Well → editar → amostra → vídeo inteiro → conferir → entregar.**

O "ok" tem que vir numa mensagem dele depois do cartão. Mesmo que o pedido venha detalhado ou diga "decide tudo", o cartão aparece e você espera. Nunca invente a resposta dele.

### 1. Inspecionar (antes do ok, só leitura)

Crie a pasta do trabalho: `saida/<AAAA-MM-DD>_<tema-curto>/` (o tema em poucas palavras, sem acento, com hífen).

```bash
python scripts/inspecionar.py BRUTO1.mov [BRUTO2.mov ...] --pasta saida/2026-10-22_lead-curioso
```

Olhe os três quadros de cada vídeo em `quadros/` (rosto, enquadramento, se já tem texto na tela, se tem algo sensível como tela de computador com dado de cliente). Se o Well mandou o roteiro, leia também: ele confirma grafia e ordem, mas quem manda é o que foi falado.

Não pergunte nada antes de inspecionar, a não ser que ele não tenha dito qual é o vídeo.

### 2. Cartão de ajustes

Mande como texto normal (nunca dentro de bloco de código), neste formato, sempre na mesma ordem:

```markdown
### 🎬 Lead curioso · ajustes para aprovar

Vou juntar os 2 vídeos num Reels vertical, ritmo natural, com legenda.

**⚠️ Preciso que você escolha**

- `IMG_2041.mov` está em HDR (padrão do iPhone). **A)** converter para cor padrão, fica igual em todo celular (recomendado) · **B)** manter HDR

**📋 Ajustes**

- 🎯 **Objetivo**: Reels completo, ritmo natural, cerca de 50 s _(sugerido)_
- 🎞️ **Vídeos**: 1. `IMG_2040.mov` (1:12) · 2. `IMG_2041.mov` (0:40) _(você mandou)_
- ✂️ **Limpeza**: tiro pausas longas, respirações, erros e repetições; mantenho palavras inteiras e pausas de efeito _(sugerido)_
- 💬 **Legenda**: ligada, até 3 palavras por vez, palavra falada em azul, fonte da marca, abaixo do rosto · sem arquivo de legenda separado _(sugerido)_
- ✨ **Elementos 3D**: 4 elementos da marca flutuando no topo quando você fala "WhatsApp", "5 minutos", "funil" e "contrato" · 1 tela cheia no gancho _(sugerido)_
- 🔊 **Som**: voz no volume padrão das redes · sem música, sem efeito, sem redução de ruído _(sugerido)_
- 🎨 **Imagem**: cor original, sem filtro _(sugerido)_
- 📐 **Formato**: vertical 9:16, mesmo tamanho e fluidez do original _(do seu vídeo)_
- 👀 **Revisão**: eu confiro uma amostra de 8 a 15 s antes de fazer o vídeo inteiro _(sugerido)_
- 📁 **Entrega**: `saida/2026-10-22_lead-curioso/2026-10-22_lead-curioso-v001.mp4` _(sugerido)_

⚙️ 1080x1920 · 29,97 quadros/s fixos · MP4 · voz em -14 LUFS, pico até -1 dBTP

👉 Responda **A** para começar, ou diga o que mudar, por exemplo "ritmo mais rápido", "sem legenda", "deixa a pausa do 0:42".
```

Regras do cartão:

- Uma linha por item, dizendo o valor mesmo quando é "desligado" ou "como o original". Marque a origem: _(você pediu)_, _(do seu vídeo)_ ou _(sugerido)_.
- Valores técnicos só na linha ⚙️. Sem caminho interno, sem nome de script, sem JSON.
- Tudo que é desconhecido, conflitante ou não suportado vai em ⚠️, no topo, com opções em letra e uma recomendada. Sem pendência, tire o bloco ⚠️ e peça **ok**.
- "ok", "pode", "manda" só aprovam se responderem todas as pendências. Escolher outra opção ou pedir mudança é mudança: mostre o cartão de novo com ✏️ nas linhas alteradas e espere outro ok.
- Música, efeito sonoro e trilha só entram se o Well pedir com essas palavras. "Deixa dinâmico" não é pedido de música.

Padrões propostos: ritmo natural, legenda ligada, elementos 3D sobrepostos nas palavras que combinam (um a cada 6 s no máximo; liste quais no cartão depois de uma transcrição rápida, ou diga "nos momentos certos" se ainda não transcreveu), voz em -14 LUFS, cor e formato do original, sem música, sem efeito, sem redução de ruído, amostra conferida por você.

### 3. Transcrever e propor os cortes (depois do ok)

```bash
python scripts/transcrever.py BRUTO1.mov BRUTO2.mov --pasta saida/... --termos "Arven, OAB, WhatsApp, CRM"
python scripts/propor_cortes.py --pasta saida/... --ritmo natural      # ou dinamico
```

Leia a lista de trechos que o script mostra e revise seguindo `referencias/cortes.md`. Em especial:

- Tudo em "PARA CONFERIR" precisa de decisão sua: palavra duvidosa, mesma frase gravada duas vezes (fica a melhor tomada, normalmente a mais fluida, não necessariamente a última), som sem palavra.
- Leia o texto final emendado, do primeiro ao último trecho. Ele tem que fazer sentido e dizer exatamente o que o Well disse, sem perder ressalva nem inverter o sentido.
- Para ajustar, edite `cortes.json` à mão: apague o trecho, ou mude `inicio`/`fim` (em segundos do vídeo original). Mantenha a ordem dos trechos.

### 4. Legenda

```bash
python scripts/legendas.py --pasta saida/... [--formato 9:16] [--posicao baixo|meio|alto]
```

Revise `legendas.json` seguindo `referencias/legendas.md` (grafia de marca e termo jurídico, números, nomes). Corrija o campo `texto` de cada bloco e rode de novo com `--reaproveitar`. Use o mesmo `--formato` que vai no renderizar.

### 4b. Elementos 3D

```bash
python scripts/elementos.py sugerir --pasta saida/... [--modo sobreposto|tela]
```

Revise `elementos.json` seguindo `referencias/elementos-3d.md`: o elemento combina com a frase, não cobre o rosto, o rótulo só traz número que o Well falou. Os elementos entram sozinhos no renderizar. Se o Well desligou os elementos no cartão, pule este passo (e apague `elementos.json` se existir).

### 5. Amostra de 8 a 15 s

```bash
python scripts/renderizar.py --pasta saida/... --amostra 0 12 [--formato 9:16] [--hdr sdr]
python scripts/conferir.py --pasta saida/... --video saida/.../amostra-v001.mp4 --retranscrever
```

Escolha a janela da amostra com o trecho mais difícil (emendas próximas, frase regravada, um elemento 3D). Olhe a folha de quadros e alguns quadros soltos (`ffmpeg -ss <segundos> -i video.mp4 -frames:v 1 quadro.jpg`): legenda fora do rosto, legível, palavra certa. Não acrescente nada só para enfeitar a amostra.

Se o Well pediu para aprovar a amostra, mande para ele e espere. Se não, siga.

### 6. Vídeo inteiro e conferência

```bash
python scripts/renderizar.py --pasta saida/... [--formato 9:16] [--hdr sdr]
python scripts/conferir.py --pasta saida/... --video saida/.../<tema>-v001.mp4 --retranscrever
```

Só entregue com tudo "ok". Qualquer "FALHOU" você resolve (ajusta corte, legenda, refaz) ou explica como limite. Uma imagem parada confere enquadramento e legenda, mas não prova sincronia: a retranscrição e a checagem de palavra cortada cobrem a fala.

### 7. Entrega

```markdown
### ✅ Vídeo pronto

- 🎬 **Vídeo**: `saida/2026-10-22_lead-curioso/2026-10-22_lead-curioso-v001.mp4`
- ✂️ **O que mudou**: 1:52 → 0:51 · 23 pausas e 2 frases repetidas tiradas · legenda e 4 elementos 3D colocados
- ✨ **Elementos 3D**: mensagem em 0:04 ("WhatsApp"), relógio em 0:12 ("5 minutos"), ...
- 🔍 **Conferido**: toca do começo ao fim, volume, legenda, elementos, enquadramento, nenhuma palavra cortada
- ⚠️ **Limites**: <só se houver: áudio estourado no original, trecho com ruído, algo que não deu>

👉 Quer mudar algo? Por exemplo "legenda maior", "corta o começo", "mais rápido".
```

Se o vídeo saiu de um roteiro da skill de conteúdo, a legenda do post (o texto que vai embaixo do Reels) é feita lá, não aqui.

## Ajustes depois da entrega

Mudança pontual ("legenda maior", "volta a frase do 0:30") mexe só no que foi pedido: edite `legendas.json` ou `cortes.json` e renderize de novo. A saída nova ganha o próximo número (v002), a anterior fica guardada. Nunca recorte o vídeo inteiro de novo por causa de um ajuste de legenda.

## Regras que não mudam

- Nunca mexa nos arquivos originais. Tudo novo fica na pasta do trabalho.
- Nunca sobrescreva uma entrega anterior.
- A fala é do Well: não corte ressalva, negação ou condição que muda o sentido (cuidado especial com o que a OAB exige, veja `referencias/cortes.md`). Não junte pedaços de frases diferentes para criar uma frase que ele não disse.
- Corte medido no áudio, não estimado pelo roteiro. O roteiro serve para grafia e ordem.
- Sem elemento 3D, música, efeito, filtro de cor, conversão de HDR ou redução de ruído sem o Well escolher no cartão.
- Nada é enviado para fora do computador. A transcrição é local.
- Nunca publique. Postar é com a skill de conteúdo, e só com "pode postar".

## Quando um script falha

Erro de script é problema seu, não do Well. Não mostre a mensagem de erro nem peça para ele consertar. Tente outro caminho (por exemplo, rodar o passo direto no ffmpeg dentro da pasta do trabalho), e conte na entrega, em uma linha simples, o que foi feito diferente. Se não houver caminho, explique o limite em palavras simples e ofereça opções concretas (por exemplo, a versão sem legenda). Nunca desligue um ajuste aprovado em silêncio.

## Inspiração

A forma de trabalhar (cartão de ajustes antes de editar, corte medido na onda sonora, amostra antes do vídeo inteiro, conferência real do arquivo) veio do projeto aberto editonny, de Matheus Gomes (licença MIT). O código aqui é próprio e bem mais enxuto.
