---
name: edicao-video-well
description: "Edita os vídeos gravados pelo Well para o Instagram (@lunardiwell): corta pausas, respirações, erros e repetições, junta tomadas, coloca legenda no padrão da marca fora do rosto, faz elementos 3D da marca entrarem quando ele fala a palavra certa, dá zoom de ênfase, tira ruído, põe música e efeitos quando pedido, iguala o volume e entrega o MP4 pronto para postar. Use quando ele mandar um vídeo bruto, pedir para editar, cortar, legendar, pôr elementos 3D, zoom, música ou ajustar um vídeo já editado."
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
| `referencias/rosto-e-camera.md` | Rosto (legenda e elementos fora dele) e zoom de ênfase | Ao rodar `rosto.py` e `camera.py` |
| `referencias/som-e-imagem.md` | Volume, ruído, estouro, eco, música, efeitos, HDR, formato, cor | Ao montar o cartão e renderizar |
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

Olhe os três quadros de cada vídeo em `quadros/` (rosto, enquadramento, se já tem texto na tela, se tem algo sensível como tela de computador com dado de cliente). Leia as pendências de som: ruído (com a sugestão leve ou forte), estouro (com os momentos) e eco. Se o Well mandou o roteiro, leia também: ele confirma grafia e ordem, mas quem manda é o que foi falado.

Não pergunte nada antes de inspecionar, a não ser que ele não tenha dito qual é o vídeo.

### 2. Cartão de ajustes

Mande como texto normal (nunca dentro de bloco de código), neste formato, sempre na mesma ordem:

```markdown
### 🎬 Lead curioso · ajustes para aprovar

Vou juntar os 2 vídeos num Reels vertical, ritmo natural, com legenda.

**⚠️ Preciso que você escolha**

- `IMG_2041.mov` está em HDR (padrão do iPhone). **A)** converter para cor padrão, fica igual em todo celular (recomendado) · **B)** manter HDR
- `IMG_2040.mov` tem chiado de fundo (24 dB abaixo da voz). **C)** redução de ruído leve (recomendado) · **D)** deixar como está

**📋 Ajustes**

- 🎯 **Objetivo**: Reels completo, ritmo natural, cerca de 50 s _(sugerido)_
- 🎞️ **Vídeos**: 1. `IMG_2040.mov` (1:12) · 2. `IMG_2041.mov` (0:40) _(você mandou)_
- ✂️ **Limpeza**: tiro pausas longas, respirações, erros e repetições; mantenho palavras inteiras e pausas de efeito _(sugerido)_
- 💬 **Legenda**: ligada, até 3 palavras por vez, palavra falada em azul, fonte da marca, abaixo do rosto · sem arquivo de legenda separado _(sugerido)_
- ✨ **Elementos 3D**: 4 elementos da marca quando você fala "WhatsApp", "5 minutos", "funil" e "contrato", sempre fora do rosto · 1 tela cheia no gancho _(sugerido)_
- 🎥 **Câmera**: parada, sem zoom _(sugerido)_
- 🔊 **Som**: voz no volume padrão das redes, com redução de ruído leve · sem música, sem efeito _(sugerido)_
- 🎨 **Imagem**: cor original, sem filtro _(sugerido)_
- 📐 **Formato**: vertical 9:16, mesma fluidez do original _(do seu vídeo)_ · reduzido de 4K para 1080x1920, o tamanho do Instagram _(sugerido)_
- 👀 **Revisão**: eu confiro uma amostra de 8 a 15 s antes de fazer o vídeo inteiro _(sugerido)_
- 📁 **Entrega**: `saida/2026-10-22_lead-curioso/2026-10-22_lead-curioso-v001.mp4` _(sugerido)_

⚙️ 2160x3840 → 1080x1920 · 29,97 quadros/s fixos · MP4 · voz em -14 LUFS, pico até -1 dBTP

👉 Responda **A** e **C** para começar, ou diga o que mudar, por exemplo "ritmo mais rápido", "com zoom", "põe uma música calma", "deixa a pausa do 0:42".
```

Regras do cartão:

- Uma linha por item, dizendo o valor mesmo quando é "desligado" ou "como o original". Marque a origem: _(você pediu)_, _(do seu vídeo)_ ou _(sugerido)_.
- Valores técnicos só na linha ⚙️. Sem caminho interno, sem nome de script, sem JSON.
- Tudo que é desconhecido, conflitante ou não suportado vai em ⚠️, no topo, com opções em letra e uma recomendada. Sem pendência, tire o bloco ⚠️ e peça **ok**.
- "ok", "pode", "manda" só aprovam se responderem todas as pendências. Escolher outra opção ou pedir mudança é mudança: mostre o cartão de novo com ✏️ nas linhas alteradas e espere outro ok.
- Música, efeito sonoro e trilha só entram se o Well pedir com essas palavras. "Deixa dinâmico" não é pedido de música. Quando pedir, a linha 🔊 diz qual música (calma, animada ou batida leve, ou a que ele mandou) e "efeito em cada elemento 3D".
- Zoom de ênfase só entra se o Well pedir ("com zoom", "dá uns cortes de câmera", "aproxima nas partes fortes") ou aceitar quando você oferecer. "Deixa dinâmico" pode virar uma oferta no cartão, nunca um zoom ligado por conta própria.
- Redução de ruído: com chiado medido (diferença de 30 dB ou menos), vai como pendência ⚠️ com a sugestão da inspeção (leve ou forte). Gravação limpa: "sem redução de ruído (gravação limpa)".
- Áudio estourado ou sala com eco: vão em ⚠️ como aviso (não têm conserto na edição), com a opção de seguir assim ou regravar a frase.

- Tamanho: o Instagram mostra no máximo 1080x1920. Bruto maior que isso (4K do iPhone): proponha "reduzido para 1080x1920, o tamanho do Instagram" e use `--formato original@1080` (ou `9:16@1080`) em todos os scripts que recebem `--formato`. Fica bem mais rápido e o arquivo final, bem menor. Mantenha os quadros por segundo do original.

Padrões propostos: ritmo natural, legenda ligada fora do rosto, elementos 3D nas palavras que combinam (um a cada 6 s no máximo; liste quais no cartão depois de uma transcrição rápida, ou diga "nos momentos certos" se ainda não transcreveu), câmera parada, voz em -14 LUFS, redução de ruído só com chiado medido, cor e formato do original, sem música, sem efeito, amostra conferida por você.

### 3. Transcrever e propor os cortes (depois do ok)

```bash
python scripts/transcrever.py BRUTO1.mov BRUTO2.mov --pasta saida/... --termos "Arven, OAB, WhatsApp, CRM"
python scripts/propor_cortes.py --pasta saida/... --ritmo natural      # ou dinamico
```

Leia a lista de trechos que o script mostra e revise seguindo `referencias/cortes.md`. Em especial:

- Tudo em "PARA CONFERIR" precisa de decisão sua: palavra duvidosa, mesma frase gravada duas vezes (fica a melhor tomada, normalmente a mais fluida, não necessariamente a última), som sem palavra.
- Leia o texto final emendado, do primeiro ao último trecho. Ele tem que fazer sentido e dizer exatamente o que o Well disse, sem perder ressalva nem inverter o sentido.
- Para ajustar, edite `cortes.json` à mão: apague o trecho, ou mude `inicio`/`fim` (em segundos do vídeo original). Mantenha a ordem dos trechos.

### 3b. Rosto

```bash
python scripts/rosto.py --pasta saida/... [--formato 9:16]
```

Sempre que tiver legenda, elemento 3D ou zoom. Rode depois de fechar o `cortes.json` (e de novo se ele mudar). Veja `referencias/rosto-e-camera.md`.

### 4. Elementos 3D, câmera e legenda (nesta ordem)

```bash
python scripts/elementos.py sugerir --pasta saida/... [--modo sobreposto|tela]
python scripts/camera.py planejar --pasta saida/... [--intensidade leve|normal|forte]   # só com zoom aprovado
python scripts/legendas.py --pasta saida/... [--formato 9:16]
python scripts/som.py planejar --pasta saida/... [--musica calmo|animado|batida|ARQUIVO] [--efeitos]   # só com música ou efeito pedido
```

A ordem importa: a câmera não muda o zoom com elemento na tela, a legenda desvia do rosto já com o zoom, e os efeitos sonoros seguem os elementos. Mexeu num deles, rode de novo os que vêm depois.

**Legenda.**

Revise `legendas.json` seguindo `referencias/legendas.md` (grafia de marca e termo jurídico, números, nomes). Corrija o campo `texto` de cada bloco e rode de novo com `--reaproveitar`. Use o mesmo `--formato` que vai no renderizar. A lista mostra os blocos que mudaram de lugar para não cobrir o rosto.

**Elementos 3D.** Revise `elementos.json` seguindo `referencias/elementos-3d.md`: o elemento combina com a frase, o rótulo só traz número que o Well falou. A posição `auto` foge do rosto sozinha. Os elementos entram sozinhos no renderizar. Se o Well desligou os elementos no cartão, pule este passo (e apague `elementos.json` se existir).

**Câmera.** Revise `camera.json` seguindo `referencias/rosto-e-camera.md`: poucas aproximações, nas palavras que pedem força. Sem zoom aprovado, não rode (e use `camera.py desligar` se existir).

**Som.** Revise `som.json` seguindo `referencias/som-e-imagem.md`. Sem música nem efeito pedido, não rode (e use `som.py desligar` se existir).

### 5. Amostra de 8 a 15 s

```bash
python scripts/renderizar.py --pasta saida/... --amostra 0 12 [--formato 9:16] [--hdr sdr] [--ruido leve|forte]
python scripts/conferir.py --pasta saida/... --video saida/.../amostra-v001.mp4 --retranscrever
```

Escolha a janela da amostra com o trecho mais difícil (emendas próximas, frase regravada, um elemento 3D, uma aproximação de zoom). Olhe a folha de quadros, a folha de emendas e alguns quadros soltos (`ffmpeg -ss <segundos> -i video.mp4 -frames:v 1 quadro.jpg`): legenda fora do rosto, legível, palavra certa; zoom sem cortar a cabeça. Não acrescente nada só para enfeitar a amostra.

Se o Well pediu para aprovar a amostra, mande para ele e espere. Se não, siga.

### 6. Vídeo inteiro e conferência

```bash
python scripts/renderizar.py --pasta saida/... [--formato 9:16] [--hdr sdr] [--ruido leve|forte]
python scripts/conferir.py --pasta saida/... --video saida/.../<tema>-v001.mp4 --retranscrever
```

Só entregue com tudo "ok". Qualquer "FALHOU" você resolve (ajusta corte, põe o `ganho_db` sugerido, refaz) ou explica como limite. Pausa de efeito que o Well quer manter passa com `--pausas-ok <segundo>`. Uma imagem parada confere enquadramento e legenda, mas não prova sincronia: a retranscrição e a checagem de palavra cortada cobrem a fala. Olhe todas as folhas de emendas antes de entregar.

### 7. Entrega

```markdown
### ✅ Vídeo pronto

- 🎬 **Vídeo**: `saida/2026-10-22_lead-curioso/2026-10-22_lead-curioso-v001.mp4`
- ✂️ **O que mudou**: 1:52 → 0:51 · 23 pausas e 2 frases repetidas tiradas · legenda e 4 elementos 3D colocados · chiado reduzido
- ✨ **Elementos 3D**: mensagem em 0:04 ("WhatsApp"), relógio em 0:12 ("5 minutos"), ...
- 🎥 **Câmera**: <só se tiver zoom: "zoom a cada frase e 3 aproximações: 'nunca' em 0:09, ...">
- 🔊 **Som**: <só se tiver música ou efeito: "música batida leve por baixo, efeito em cada elemento">
- 🔍 **Conferido**: toca do começo ao fim, volume igual entre trechos, legenda fora do rosto, elementos, emendas sem estalo nem pulo, nenhuma palavra cortada, nenhum silêncio sobrando
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
- Sem elemento 3D, zoom, música, efeito, filtro de cor, conversão de HDR ou redução de ruído sem o Well escolher no cartão.
- Música e efeitos só da biblioteca da skill (domínio público) ou que o Well mandar. Nunca baixe música da internet.
- Nada é enviado para fora do computador. A transcrição é local.
- Nunca publique. Postar é com a skill de conteúdo, e só com "pode postar".

## Quando um script falha

Erro de script é problema seu, não do Well. Não mostre a mensagem de erro nem peça para ele consertar. Tente outro caminho (por exemplo, rodar o passo direto no ffmpeg dentro da pasta do trabalho), e conte na entrega, em uma linha simples, o que foi feito diferente. Se não houver caminho, explique o limite em palavras simples e ofereça opções concretas (por exemplo, a versão sem legenda). Nunca desligue um ajuste aprovado em silêncio.

## Inspiração

A forma de trabalhar (cartão de ajustes antes de editar, corte medido na onda sonora, amostra antes do vídeo inteiro, conferência real do arquivo) e as ideias da redução de ruído, do rosto, do zoom de ênfase, da mistura de música e das checagens de emenda vieram do projeto aberto editonny, de Matheus Gomes (licença MIT). O código aqui é próprio e bem mais enxuto. Os sons da skill foram escolhidos da biblioteca de domínio público reunida por ele.
