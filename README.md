# Edição de vídeo do Well

Skill do Claude que **edita os vídeos** que o Well ([@lunardiwell](https://instagram.com/lunardiwell)) grava para o Instagram. Par da skill de conteúdo ([skill-cards-insta](https://github.com/w5ll/skill-cards-insta)): lá nasce o roteiro, aqui o vídeo gravado vira Reels pronto.

Para instalar no seu Mac, veja [Instalar no seu Mac, com o VS Code](#instalar-no-seu-mac-com-o-vs-code).

## Como funciona

1. Você manda o vídeo bruto (e o roteiro, se tiver): *"edita esse vídeo do lead curioso"*.
2. A skill olha o vídeo e mostra um **cartão com todos os ajustes** (ritmo, legenda, som, formato, cor). Nada é editado antes do seu "ok".
3. Transcreve a fala no próprio computador, palavra por palavra.
4. Corta pausas longas, respirações, erros, frases repetidas e começos errados. O corte é medido na onda do som, para não comer sílaba.
5. Acha o seu rosto em cada trecho, 10 vezes por segundo.
6. Coloca a legenda no padrão da marca: Sora ExtraBold, até 3 palavras por vez, palavra falada em azul. Se ela fosse cobrir a boca ou o queixo, desce ou sobe sozinha.
7. Faz os **elementos 3D do carrossel** entrarem animados quando você fala a palavra certa: "WhatsApp" chama a mensagem digitando, "cinco minutos" o relógio com o rótulo "5 minutos", "funil" o funil com leads caindo. Eles procuram um lugar que não cubra o rosto. Também tem o modo tela cheia, que vira um slide do carrossel por um instante. Quando você fala de uma ideia que nenhum dos 12 elementos prontos representa (direção, método, sorte, estar à deriva), a skill **desenha um elemento novo** só para ela: bússola, escada, engrenagem, trevo. Você vê uma **folha de prévia** (cada elemento em três instantes, sobre o fundo da marca e sobre o seu próprio vídeo) e só entra o que você aprovar. Os que você gostar podem ficar no catálogo para os próximos vídeos.
8. Se você pedir, dá **zoom de ênfase**: alterna o enquadramento a cada frase, como se fossem duas câmeras, e aproxima nas palavras fortes ("nunca", números, "dobro").
9. Tira o **chiado de fundo** (leve ou forte, conforme a medição) e avisa áudio estourado e eco da sala.
10. Se você pedir, põe **música** por baixo (abaixa sozinha quando você fala) e um **efeito sonoro** em cada elemento 3D. Tudo de domínio público.
11. Iguala o volume da voz ao padrão das redes, e o volume entre uma tomada e outra.
12. Confere uma amostra de 8 a 15 segundos, depois faz o vídeo inteiro e confere de novo: toca até o fim, volume, nenhuma palavra cortada, nenhum estalo, trecho repetido, silêncio sobrando ou quadro preto, fala completa, e uma folha com os quadros de cada emenda.
13. Entrega o MP4, sem nunca apagar os originais nem as versões anteriores.

## Fases do projeto

O projeto está crescendo de ferramenta de uma pessoa para **ferramenta de edição para qualquer pessoa com acesso ao repositório**, com a marca configurável e um painel que roda a edição inteira sem abrir uma conversa. O nome novo é **welldit**, e o visual padrão segue a marca ARVEN (**elementos base ARVEN**). O plano completo, as dependências, a divisão entre as duas pessoas e as regras de trabalho em dupla estão em [docs/roadmap.md](docs/roadmap.md).

**Como usar este checklist:** quem pega uma fase escreve o próprio nome no lugar de "livre", num commit pequeno, antes de começar. Ao terminar, marca a caixa e preenche o gasto do plano na tabela abaixo. A fase 3 é feita primeiro e por uma pessoa só; depois dela, as trilhas A, B e C andam em paralelo.

**Feito**

- [x] **Fase 1.** Skill de edição e painel de acompanhamento
- [x] **Fase 2.** Elementos 3D gerados a partir da fala ([especificação](docs/fase-2-elementos-gerados.md))

**Base (primeiro e sozinha)**

- [ ] **Fase 3.** Projeto para qualquer pessoa: perfis de marca, textos neutros, regras de nicho opcionais, nome welldit, aviso "elementos base ARVEN" · _Well_

**Trilha A: painel que roda a edição** (nesta ordem)

- [ ] **Fase 4.** Orquestrador e estado da edição (`editar.py`, `trabalho.json`, modelos de edição) · _Well (proposta)_
- [ ] **Fase 5.** Painel que executa: formulário do cartão, fila, aprovações, senha de sessão · _Well (proposta)_
- [ ] **Fase 6.** Revisão de cortes e legenda no painel · _Well (proposta)_
- [ ] **Fase 7.** Elementos, zoom e som no painel, conferência com botões de correção · _Well (proposta)_
- [ ] **Fase 8.** Claude por trás, opcional: revisar cortes e desenhar elementos pelo painel · _Well (proposta)_

**Trilha B: conteúdo e entrega** (independentes entre si)

- [ ] **Fase 9.** Gancho dos 3 primeiros segundos e detecção de leitura e olhar · _Lucas (proposta)_
- [ ] **Fase 10.** Pacote de publicação e capa do Reels · _Lucas (proposta)_
- [ ] **Fase 11.** Direção de arte por série, conferência de fatos e imagens de apoio · _Lucas (proposta)_
- [ ] **Fase 12.** Cenas explicativas sincronizadas com a fala · _Lucas, em andamento_ ([especificação](docs/fase-12-cenas-explicativas.md))

**Trilha C: infraestrutura** (independentes)

- [ ] **C1.** Instalação em um comando e tutorial para Windows e Linux · _Lucas (proposta)_
- [ ] **C2.** Testes automáticos a cada envio no GitHub · _Lucas (proposta)_

**Gasto do plano** (o número que o Claude Code mostra, antes e depois de cada fase)

| Fase | Quem | Antes | Depois | Commit |
| --- | --- | --- | --- | --- |
| 1 | | | | |
| 2 | Well | | | `402c088` |

Referência informada: a Fase 2 e o planejamento custaram cerca de **2% do plano semanal** (Sonnet 5.5, esforço médio).

## Instalar no seu Mac, com o VS Code

Passo a passo para editar no seu computador. É o jeito recomendado: o vídeo não sai da sua máquina e não tem limite de tamanho. Leva uns 20 minutos na primeira vez, e depois disso é só usar.

Escrito a partir da primeira instalação de verdade, num MacBook M1 Pro. Os problemas que apareceram nela já estão resolvidos aqui.

### 1. Programas que você precisa

1. **VS Code**: baixe em [code.visualstudio.com](https://code.visualstudio.com) e arraste para a pasta Aplicativos.
2. **Extensão do Claude Code**: no VS Code, clique no ícone de quadradinhos da barra da esquerda (Extensões), busque "Claude Code" e instale a da Anthropic. Entre com a sua conta do Claude.
3. **Homebrew**, o instalador de programas do Mac: abra o Terminal (Cmd + espaço, digite "Terminal") e cole o comando que aparece em [brew.sh](https://brew.sh). Ele pede a senha do Mac. No fim, ele mostra dois comandos em "Next steps": rode os dois.

### 2. Baixar o projeto

No Terminal, um comando por vez:

```bash
cd ~
```

```bash
git clone https://github.com/w5ll/skill-claude-editor.git
```

```bash
cd skill-claude-editor
```

```bash
git checkout main
```

O último comando garante que você está na versão principal da skill, a `main`.

### 3. Instalar as ferramentas de vídeo e o Python

```bash
brew install ffmpeg-full python@3.12
```

Use o `ffmpeg-full`, e não o `ffmpeg` simples. O simples vem sem a parte da legenda e sem a conversão de cor do iPhone, e a skill não consegue terminar o vídeo.

Use o Python 3.12. O 3.14, mais novo, ainda não funciona com as bibliotecas de transcrição.

### 4. Criar o ambiente da skill

Ainda na pasta do projeto:

```bash
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
```

```bash
echo 'export PATH="/opt/homebrew/opt/ffmpeg-full/bin:$PATH"' >> .venv/bin/activate
```

```bash
source .venv/bin/activate
```

```bash
pip install -r skill/edicao-video-well/scripts/requirements.txt
```

O segundo comando faz a skill sempre usar o ffmpeg completo, mesmo que o Mac tenha outro instalado. O último baixa as bibliotecas de transcrição, rosto e desenho, e leva alguns minutos.

Para conferir se ficou tudo certo:

```bash
ffmpeg -hide_banner -filters | grep -E " (ass|zscale|afftdn) "
```

Tem que aparecer três linhas: `ass`, `zscale` e `afftdn`. Se faltar alguma, o ffmpeg certo não está sendo usado: rode de novo o `source .venv/bin/activate`.

Para desenhar os elementos 3D a skill usa o Google Chrome. Se você não tiver o Chrome, instale-o ou rode `python -m playwright install chromium`.

### 5. Abrir no VS Code

1. No VS Code: menu Arquivo, Abrir Pasta, e escolha `skill-claude-editor` (fica na sua pasta de usuário).
2. Se aparecer o aviso **"Modo Restrito"** no topo, clique nele e escolha **Confiar**. Sem isso, o Claude não consegue rodar os scripts.
3. Abra o Claude Code pelo ícone do asterisco laranja na barra da esquerda.

### 6. Editar o primeiro vídeo

1. Passe o vídeo do iPhone para o Mac por AirDrop ou cabo. Não mande pelo WhatsApp, que piora a qualidade.
2. Coloque o arquivo na pasta `material-bruto` do projeto. Pode arrastar direto para a pasta no VS Code.
3. No Claude Code, cole:

```text
Edita o vídeo material-bruto/IMG_0000.MOV para o Instagram, seguindo a skill em skill/edicao-video-well/SKILL.md. Use o ambiente .venv do projeto (source .venv/bin/activate). Antes de tudo, confere se está instalado o que a skill precisa (referencias/instalacao.md); se faltar algo, me explica o que vai instalar e espera meu ok. Depois inspeciona o vídeo e me mostra o cartão de ajustes antes de editar.
```

Troque `IMG_0000.MOV` pelo nome do seu arquivo. Se forem dois vídeos que se completam, cite os dois, na ordem.

O que acontece depois:

- Ele mostra o **cartão de ajustes** e espera. Responda com as letras das escolhas e o que quiser mudar, por exemplo "A e C, com zoom leve e música calma".
- Na primeira transcrição ele baixa o modelo de transcrição, de cerca de 1,6 GB. Depois disso, tudo roda sem internet.
- Ele faz uma amostra de 8 a 15 segundos, confere, e depois o vídeo inteiro.
- O vídeo pronto fica em `saida/<data>_<tema>/`, com o nome terminando em `-v001.mp4`. Cada ajuste gera uma versão nova (v002, v003) e as anteriores ficam guardadas.

Vídeo do iPhone em 4K: peça para sair em 1080x1920 (`--formato original@1080`). É o tamanho que o Instagram usa, a edição fica bem mais rápida e o arquivo final, bem menor.

### 7. Painel no navegador (opcional)

Uma página para enviar os vídeos e acompanhar a edição sem abrir pastas. Em outro terminal do VS Code (menu Terminal, Novo Terminal), na pasta do projeto:

```bash
source .venv/bin/activate
```

```bash
python skill/edicao-video-well/scripts/painel.py
```

O navegador abre em `http://localhost:8765`. Lá você:

- **Envia vídeos:** arraste os brutos para a página. Eles vão para `material-bruto` e nunca sobrescrevem um arquivo com o mesmo nome. Depois do envio, o botão "copiar pedido de edição" copia o prompt pronto para colar no Claude Code.
- **Acompanha cada edição:** as etapas feitas (inspeção, transcrição, cortes, rosto, legenda, amostra, vídeo, conferência) e o que está rodando agora, com a porcentagem na transcrição, no rosto, no desenho dos elementos e no render. Se um passo parar no meio (erro ou fim do limite de uso), o painel avisa.
- **Vê o resultado:** assiste à amostra e às versões, abre as folhas de quadros e de emendas, e vê a lista da conferência.

O painel só funciona no seu computador: ninguém na rede vê. Quem edita e aprova continua sendo a conversa no Claude Code. Para fechar o painel: Ctrl+C no terminal dele.

### 8. Atualizar a skill

Quando houver melhoria nova, no terminal do VS Code (menu Terminal, Novo Terminal):

```bash
git pull
```

Pode rodar com uma edição em andamento: o que já foi feito fica salvo na pasta `saida`.

### Quando der problema

| O que aparece | O que fazer |
| --- | --- |
| "Modo Restrito" no topo do VS Code | Clique no aviso e escolha Confiar |
| Ele diz que o ffmpeg não tem `libass` ou `zscale` | Faça o passo 3 com `ffmpeg-full` e o segundo comando do passo 4 |
| Erro ao instalar o faster-whisper | O ambiente foi criado com o Python errado: apague a pasta `.venv` e refaça o passo 4 |
| "Approaching limit" no Claude Code | Seu limite de uso está acabando. Se ele parar, nada se perde: depois que o limite zerar, mande "continua a edição de onde parou, sem refazer a transcrição" |
| A transcrição mostra palavras sem sentido repetidas ("OAB, OAB", "Obrigado", "Tchau") | É fala que ele não reconheceu. Peça para transcrever aquele trecho de novo com `--trecho INICIO FIM`, sem termos |
| O vídeo terminou antes do fecho | Peça para ele transcrever os últimos 20 segundos com `--trecho` e conferir antes de cortar |
| Mac dormiu no meio | Mantenha a tampa aberta e o carregador ligado durante a edição |

## Estrutura

```
skill/edicao-video-well/         ← a skill (é isso que vira o arquivo .skill)
  SKILL.md                       fluxo, cartão de ajustes, entrega, regras
  referencias/
    cortes.md                    o que cortar, o que nunca cortar, tomada certa
    legendas.md                  estilo, posição, grafia dos termos
    elementos-3d.md              catálogo dos elementos 3D, modos, critério e como desenhar elementos novos
    rosto-e-camera.md            rosto (legenda e elementos fora dele) e zoom de ênfase
    som-e-imagem.md              volume, ruído, estouro, eco, música, efeitos, HDR, formato, cor
    gravacao.md                  dicas para gravar de um jeito que edita melhor
    instalacao.md                o que precisa estar instalado
  marca.json                     cores da marca (as mesmas do carrossel)
  assets/fontes/                 Sora ExtraBold (licença OFL)
  assets/modelos/                detector de rosto YuNet (licença MIT)
  assets/sons/                   3 músicas e 10 efeitos sonoros (domínio público), com a origem em sons.json
  templates/elementos.html       desenho e animação dos 12 elementos 3D prontos e das 8 animações dos gerados
  templates/exemplos-gerados/    4 elementos gerados de modelo: bússola, escada, engrenagem, trevo
  templates/gerados/             catálogo dos elementos gerados que o Well aprovou (catalogo.json e os desenhos)
  templates/painel.html          página do painel
  scripts/
    inspecionar.py               lê o vídeo bruto: duração, formato, HDR, volume, quadros
    transcrever.py               transcrição local palavra por palavra (faster-whisper)
    fala.py                      mede fala e silêncio no áudio
    ruido.py                     mede ruído, estouro e eco; tira o chiado
    propor_cortes.py             propõe os cortes (cortes.json)
    rosto.py                     acha o rosto em cada trecho (rosto.json)
    camera.py                    planeja o zoom de ênfase (camera.json)
    legendas.py                  monta a legenda no tempo do corte, fora do rosto (.ass e .srt)
    elementos.py                 sugere, desenha, valida, mostra a prévia e guarda no catálogo os elementos 3D
    som.py                       música e efeitos sonoros (som.json)
    renderizar.py                monta o vídeo: amostra ou inteiro
    conferir.py                  confere o arquivo final
    painel.py                    painel no navegador: enviar vídeos e acompanhar a edição
material-bruto/                  vídeos brutos (fora do git)
saida/                           trabalhos editados (vídeos fora do git)
```

## Rodando na mão

```bash
pip install -r skill/edicao-video-well/scripts/requirements.txt   # uma vez (precisa do ffmpeg)
python -m playwright install chromium                              # uma vez (desenha os elementos 3D)
cd skill/edicao-video-well/scripts
P=../../../saida/2026-10-22_lead-curioso
python inspecionar.py ../../../material-bruto/2026-10-22_lead-curioso/IMG_2040.mov --pasta $P
python transcrever.py ../../../material-bruto/2026-10-22_lead-curioso/IMG_2040.mov --pasta $P --termos "Arven, WhatsApp"
python propor_cortes.py --pasta $P --ritmo natural
python rosto.py --pasta $P
python elementos.py sugerir --pasta $P
python elementos.py validar --pasta $P                # só com elemento gerado
python elementos.py previa --pasta $P                 # só com elemento gerado: folha elementos-previa.jpg
python camera.py planejar --pasta $P                  # só se quiser zoom
python legendas.py --pasta $P
python som.py planejar --pasta $P --musica batida --efeitos   # só se quiser música ou efeito
python renderizar.py --pasta $P --amostra 0 12 --ruido leve
python renderizar.py --pasta $P --ruido leve
python conferir.py --pasta $P --video $P/2026-10-22_lead-curioso-v001.mp4 --retranscrever
python elementos.py promover bussola --pasta $P --palavras "bussol,rumo"   # guarda um gerado aprovado no catálogo
```

## Empacotando a skill

```bash
./empacotar.sh        # gera dist/edicao-video-well.skill
```

## O que ainda não faz

- Capa do Reels.
- Tirar eco da sala ou consertar áudio estourado (a skill só avisa).
- Duas câmeras ou microfone separado.

O que veio do editonny e o que ficou de fora está em [docs/comparacao-editonny.md](docs/comparacao-editonny.md).

## Créditos

A forma de trabalhar (cartão de ajustes antes de editar, corte medido na onda sonora, amostra antes do vídeo inteiro, conferência real do arquivo) veio do projeto aberto [editonny](https://github.com/soumatheusgomes/editonny), de Matheus Gomes (licença MIT). O código daqui é próprio e bem mais enxuto. Detector de rosto YuNet: OpenCV Zoo, licença MIT. Músicas (HoliznaCC0) e efeitos sonoros (vários autores do Freesound): domínio público (CC0), escolhidos da biblioteca do editonny, com a origem em `skill/edicao-video-well/assets/sons/sons.json`. Fonte Sora: The Sora Project Authors, licença SIL Open Font License 1.1 (`skill/edicao-video-well/assets/fontes/OFL.txt`).
