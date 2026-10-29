# welldit

Skill do Claude que **edita vídeos gravados com o celular** para o Instagram (well + edit): corta pausas e erros, coloca legenda, elementos 3D e zoom no padrão da sua marca, iguala o volume e entrega o MP4 pronto. Qualquer pessoa com acesso ao repositório pode usar, com o próprio perfil de marca.

> **Elementos base ARVEN.** O visual padrão (cores, fonte e elementos 3D) é o do perfil `arven`. Para usar as suas cores, crie um perfil: veja [Marca e perfis](#marca-e-perfis).

Combina com uma skill de conteúdo, se você usar uma (por exemplo a [skill-cards-insta](https://github.com/w5ll/skill-cards-insta)): lá nasce o roteiro, aqui o vídeo gravado vira Reels pronto.

Para instalar no seu Mac, veja [Instalar no seu Mac, com o VS Code](#instalar-no-seu-mac-com-o-vs-code).

## Como funciona

**Em uma linha por etapa:** o `editar.py` roda as etapas da lista abaixo na ordem, para nos pontos em que é preciso a sua decisão (o cartão de ajustes, os cortes, os elementos, a legenda) e retoma de onde parou se for interrompido. Cada etapa imprime uma linha, e o detalhe fica num arquivo de registro. Veja `referencias/orquestrador.md`.

1. Você manda o vídeo bruto (e o roteiro, se tiver): *"edita esse vídeo da dica rápida"*.
2. A skill olha o vídeo e mostra um **cartão com todos os ajustes** (ritmo, legenda, som, formato, cor). Nada é editado antes do seu "ok".
3. Transcreve a fala no próprio computador, palavra por palavra.
4. Corta pausas longas, respirações, erros, frases repetidas e começos errados. O corte é medido na onda do som, para não comer sílaba.
5. Acha o seu rosto em cada trecho, 10 vezes por segundo. Com isso, **avalia o gancho** (os 3 primeiros segundos, nota de 0 a 5) e propõe cortar a saudação ou puxar do meio uma frase mais forte, e **marca os trechos em que você lê** (cabeça abaixada ou virada) para você decidir entre outra tomada, corte ou zoom. Só sugere; nada muda sem o seu "ok".
6. Coloca a legenda no padrão da marca: Sora ExtraBold, até 3 palavras por vez, palavra falada em azul. Se ela fosse cobrir a boca ou o queixo, desce ou sobe sozinha.
7. Faz os **elementos 3D da marca** entrarem animados quando você fala a palavra certa: "WhatsApp" chama a mensagem digitando, "cinco minutos" o relógio com o rótulo "5 minutos", "funil" o funil com leads caindo. Eles procuram um lugar que não cubra o rosto. Também tem o modo tela cheia, que vira um slide do carrossel por um instante. Quando você fala de uma ideia que nenhum dos 12 elementos prontos representa (direção, método, sorte, estar à deriva), a skill **desenha um elemento novo** só para ela: bússola, escada, engrenagem, trevo. Você vê uma **folha de prévia** (cada elemento em três instantes, sobre o fundo da marca e sobre o seu próprio vídeo) e só entra o que você aprovar. Os que você gostar podem ficar no catálogo para os próximos vídeos.
8. Se você pedir, dá **zoom de ênfase**: alterna o enquadramento a cada frase, como se fossem duas câmeras, e aproxima nas palavras fortes ("nunca", números, "dobro").
9. Tira o **chiado de fundo** (leve ou forte, conforme a medição) e avisa áudio estourado e eco da sala.
10. Se você pedir, põe **música** por baixo (abaixa sozinha quando você fala) e um **efeito sonoro** em cada elemento 3D. Tudo de domínio público.
11. Iguala o volume da voz ao padrão das redes, e o volume entre uma tomada e outra.
12. Confere uma amostra de 8 a 15 segundos, depois faz o vídeo inteiro e confere de novo: toca até o fim, volume, nenhuma palavra cortada, nenhum estalo, trecho repetido, silêncio sobrando ou quadro preto, fala completa, e uma folha com os quadros de cada emenda.
13. Entrega o MP4, sem nunca apagar os originais nem as versões anteriores.
14. Se você pedir, monta o **pacote de publicação**: escolhe 4 quadros para a capa (rosto grande, centrado, nítido), põe o título no padrão da marca fora do rosto e dentro do corte da grade do perfil, confere o texto do post (tamanho, hashtags, números que você não falou) e os limites do Instagram, e entrega tudo numa pasta pronta para postar. Nada é publicado.

Também, quando você pedir:

- **Série**: um arquivo em `series/` guarda o jeito de editar de um conjunto de vídeos (ritmo, legenda, elementos, zoom, música, avisos e hashtags do post), e todo vídeo da série o segue. O cartão mostra cada escolha com "(da série ...)".
- **Conferência de fatos**: antes do render, a skill marca na sua fala os números, datas, fontes e referências de lei, e pergunta se estão certos. Ela nunca decide o que é verdade: só marca e pergunta.
- **Imagens de apoio**: uma biblioteca local de imagens de uso livre, com a licença, a origem e o crédito registrados, que entram no vídeo como os elementos 3D (cartão ou tela cheia).

Também, quando você pedir: **cenas explicativas**, com texto e números animados na marca, cada parte entrando quando você a fala. Há quatro tipos: lista de passos ("primeiro, segundo, terceiro"), antes e depois, um número que sobe ("30%", "R$ 130 mil") e de-para ("de 1 milhão para 130 mil"). Entram como um cartão fora do rosto ou em tela cheia por poucos segundos, e todo número da cena tem que ter sido falado por você.

## Fases do projeto

O projeto está crescendo de ferramenta de uma pessoa para **ferramenta de edição para qualquer pessoa com acesso ao repositório**, com a marca configurável e um painel que roda a edição inteira sem abrir uma conversa. O nome novo é **welldit**, e o visual padrão segue a marca ARVEN (**elementos base ARVEN**). O plano completo, as dependências, a divisão entre as duas pessoas e as regras de trabalho em dupla estão em [docs/roadmap.md](docs/roadmap.md).

**Como usar este checklist:** quem pega uma fase escreve o próprio nome no lugar de "livre", num commit pequeno, antes de começar. Ao terminar, marca a caixa e preenche o gasto do plano na tabela abaixo. A fase 3 é feita primeiro e por uma pessoa só; depois dela, as trilhas A, B e C andam em paralelo.

**Feito**

- [x] **Fase 1.** Skill de edição e painel de acompanhamento
- [x] **Fase 2.** Elementos 3D gerados a partir da fala ([especificação](docs/fase-2-elementos-gerados.md))

**Base (primeiro e sozinha)**

- [x] **Fase 3.** Projeto para qualquer pessoa: perfis de marca, textos neutros, regras de nicho opcionais, nome welldit, aviso "elementos base ARVEN" ([especificação](docs/fase-3-perfis-de-marca.md)) · _Well_

**Trilha A: painel que roda a edição** (nesta ordem)

- [x] **Fase 4.** Orquestrador e estado da edição (`editar.py`, `trabalho.json`, modelos de edição) · _Lucas_ ([especificação](docs/fase-4-orquestrador.md))
- [x] **Fase 5.** Painel que executa: formulário do cartão, fila, aprovações, senha de sessão · _Lucas_ ([especificação](docs/fase-5-painel-executa.md))
- [x] **Fase 6.** Revisão de cortes e legenda no painel · _Lucas_ ([especificação](docs/fase-6-revisao-na-tela.md))
- [ ] **Fase 7.** Elementos, zoom e som no painel, conferência com botões de correção · _Well (proposta)_
- [ ] **Fase 8.** Claude por trás, opcional: revisar cortes e desenhar elementos pelo painel · _Well (proposta)_

**Trilha B: conteúdo e entrega** (independentes entre si)

- [x] **Fase 9.** Gancho dos 3 primeiros segundos e detecção de leitura e olhar · _Lucas_ ([especificação](docs/fase-9-gancho-olhar.md))
- [x] **Fase 10.** Pacote de publicação e capa do Reels · _Lucas_ ([especificação](docs/fase-10-pacote-publicacao.md))
- [x] **Fase 11.** Direção de arte por série, conferência de fatos e imagens de apoio · _Lucas_ ([especificação](docs/fase-11-serie-fatos-imagens.md))
- [x] **Fase 12.** Cenas explicativas sincronizadas com a fala · _Lucas_ ([especificação](docs/fase-12-cenas-explicativas.md))

**Trilha C: infraestrutura** (independentes)

- [ ] **C1.** Instalação em um comando e tutorial para Windows e Linux · _Lucas (proposta)_
- [ ] **C2.** Testes automáticos a cada envio no GitHub · _Lucas (proposta)_

**Gasto do plano** (o número que o Claude Code mostra, antes e depois de cada fase)

| Fase | Quem | Antes | Depois | Commit |
| --- | --- | --- | --- | --- |
| 1 | | | | |
| 2 | Well | 0% | 2% (inclui o planejamento das fases) | `402c088` |
| 3 | Well | 2% | 5% (cerca de 3 pontos) | `09a07de` a `f61ed7a` |
| 9 | Lucas | a anotar | a anotar | PR #1 |
| 10 | Lucas | a anotar | a anotar | PR #2 |
| 11 | Lucas | a anotar | a anotar | PR #3 |
| 12 | Lucas | a anotar | a anotar | PR #4 |
| 4 | Lucas | a anotar | a anotar | PR #6 |
| 5 | Lucas | a anotar | a anotar | PR #7 |
| 6 | Lucas | a anotar | a anotar | PR #8 |

Referência informada (Sonnet 5.5, esforço médio): a Fase 2 e o planejamento custaram cerca de **2% do plano semanal**, e a Fase 3 mais cerca de **3 pontos**, indo a 5%. Números lidos no Claude Code por quem rodou a fase, sem casa decimal.

## Marca e perfis

O visual de cada edição (cores, fonte, nome, @ e créditos) vem de um **perfil de marca**: uma pasta em `skill/welldit/perfis/`. O perfil padrão é o `arven` (elementos base ARVEN). Para usar a sua marca:

```bash
source .venv/bin/activate
python skill/welldit/scripts/perfil.py novo minha-marca      # copia o modelo para skill/welldit/perfis/minha-marca/
python skill/welldit/scripts/perfil.py validar minha-marca   # confere campos, cores e fonte
```

Edite `skill/welldit/perfis/minha-marca/marca.json` (os campos estão em [perfis/LEIA.md](skill/welldit/perfis/LEIA.md)) e, ao pedir a edição, diga *"use o perfil minha-marca"*. A escolha fica gravada na pasta do trabalho e vale até o fim da edição. Além das cores e da fonte, o perfil guarda os **pacotes de palavras** que chamam elementos 3D (marketing, jurídico...), os **avisos obrigatórios** que nunca podem ser cortados e os **termos** com a grafia certa de marcas. Perfis pessoais não vão para o git.

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
pip install -r skill/welldit/scripts/requirements.txt
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
Edita o vídeo material-bruto/IMG_0000.MOV para o Instagram, seguindo a skill em skill/welldit/SKILL.md. Use o ambiente .venv do projeto (source .venv/bin/activate). Antes de tudo, confere se está instalado o que a skill precisa (referencias/instalacao.md); se faltar algo, me explica o que vai instalar e espera meu ok. Depois inspeciona o vídeo e me mostra o cartão de ajustes antes de editar.
```

Troque `IMG_0000.MOV` pelo nome do seu arquivo. Para usar um perfil seu, acrescente "Use o perfil minha-marca." Se forem dois vídeos que se completam, cite os dois, na ordem.

O que acontece depois:

- Ele mostra o **cartão de ajustes** e espera. Responda com as letras das escolhas e o que quiser mudar, por exemplo "A e C, com zoom leve e música calma".
- Na primeira transcrição ele baixa o modelo de transcrição, de cerca de 1,6 GB. Depois disso, tudo roda sem internet.
- Ele faz uma amostra de 8 a 15 segundos, confere, e depois o vídeo inteiro.
- O vídeo pronto fica em `saida/<data>_<tema>/`, com o nome terminando em `-v001.mp4`. Cada ajuste gera uma versão nova (v002, v003) e as anteriores ficam guardadas.

Vídeo do iPhone em 4K: peça para sair em 1080x1920 (`--formato original@1080`). É o tamanho que o Instagram usa, a edição fica bem mais rápida e o arquivo final, bem menor.

### 7. Painel no navegador (opcional)

Uma página para **editar sem abrir uma conversa**: você envia os vídeos, preenche o cartão de ajustes e aprova cada etapa com cliques. Em outro terminal do VS Code (menu Terminal, Novo Terminal), na pasta do projeto:

```bash
source .venv/bin/activate
```

```bash
python skill/welldit/scripts/painel.py
```

(Para o painel nas cores de um perfil seu: `python skill/welldit/scripts/painel.py --perfil minha-marca`.)

O navegador abre sozinho num endereço com um **código de sessão** (`http://localhost:8765/?s=...`), que muda toda vez que o painel é aberto. Se abrir a página sem o código, ela pede para colar o que aparece no terminal. Isso impede que outro site aberto no navegador use o painel. Lá você:

- **Envia vídeos:** arraste os brutos para a página. Eles vão para `material-bruto` e nunca sobrescrevem um arquivo com o mesmo nome.
- **Começa uma edição:** marque os vídeos, escolha a série e o perfil (se tiver) e clique em **Começar a edição**.
- **Preenche o cartão:** o formulário já vem com o recomendado marcado (cor padrão, redução de ruído) e uma área de "Ajustes rápidos". Clique em **Aprovar e começar**.
- **Revisa os cortes na tela:** a fala inteira em frases, com o que fica e o que sai. Um clique tira ou volta uma frase, a duração final muda ao vivo (com a sua meta, se tiver), você ouve qualquer frase e qualquer **emenda**, o painel aponta os pontos para olhar (palavra duvidosa, fala não reconhecida, repetição, fim da gravação) e dá para desfazer.
- **Revisa a legenda na tela:** o texto de cada bloco, com a prévia sobre o quadro do vídeo, e **Corrigir em todos** para trocar uma palavra em todas as legendas.
- **Aprova as etapas:** quando a edição precisa da sua decisão (elementos, amostra e o resto), ela para e mostra o que decidir, com **Aprovar e seguir** ou **Copiar pedido para o Claude**, se você preferir revisar na conversa.
- **Acompanha:** as etapas, a porcentagem das longas e a fila (uma edição por vez; as outras esperam). Dá para **Cancelar** e **Retomar** de onde parou.
- **Recebe a entrega:** assiste às versões, vê as folhas de quadros e a conferência, clica em **Aprovar entrega** e em **Abrir a pasta**.

O painel só funciona no seu computador: ninguém na rede vê. Para fechar o painel: Ctrl+C no terminal dele. As edições feitas só pela conversa continuam aparecendo (só sem os botões de execução). Detalhes e segurança em `skill/welldit/referencias/painel.md`.

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
| A transcrição mostra palavras sem sentido repetidas ("Amém", "Obrigado", "Tchau") | É fala que o transcritor não reconheceu. Peça para transcrever aquele trecho de novo com `--trecho INICIO FIM`, sem termos |
| O vídeo terminou antes do fecho | Peça para transcrever os últimos 20 segundos com `--trecho` e conferir antes de cortar |
| Mac dormiu no meio | Mantenha a tampa aberta e o carregador ligado durante a edição |

## Estrutura

```
skill/welldit/         ← a skill (é isso que vira o arquivo .skill)
  SKILL.md                       fluxo, cartão de ajustes, entrega, regras
  referencias/
    cortes.md                    o que cortar, o que nunca cortar, tomada certa
    legendas.md                  estilo, posição, grafia dos termos
    elementos-3d.md              catálogo dos elementos 3D, modos, critério e como desenhar elementos novos
    rosto-e-camera.md            rosto (legenda e elementos fora dele) e zoom de ênfase
    gancho-e-olhar.md            nota do começo, propostas de gancho, leitura e olhar para baixo
    som-e-imagem.md              volume, ruído, estouro, eco, música, efeitos, HDR, formato, cor
    publicacao.md                capa, texto do post, limites do Instagram e a pasta de publicação
    series.md                    séries: o jeito de editar de um conjunto de vídeos
    fatos.md                     números, datas, fontes e afirmações a confirmar
    imagens.md                   imagens de apoio: licenças, registro e créditos
    cenas.md                     cenas explicativas: lista, antes e depois, número, de-para
    orquestrador.md              o editar.py por dentro: etapas, portões, retomada, saída curta
    painel.md                    o painel que executa: o que faz, segurança, fila, API
    fluxo-manual.md              o passo a passo completo de cada etapa (o SKILL.md só aponta para ele)
    gravacao.md                  dicas para gravar de um jeito que edita melhor
    instalacao.md                o que precisa estar instalado
  perfis/                        perfis de marca: arven (o padrão, elementos base ARVEN) e _modelo para copiar
  assets/fontes/                 Sora ExtraBold (licença OFL)
  assets/modelos/                detector de rosto YuNet (licença MIT)
  assets/sons/                   3 músicas e 10 efeitos sonoros (domínio público), com a origem em sons.json
  templates/elementos.html       desenho e animação dos 12 elementos 3D prontos e das 8 animações dos gerados
  templates/exemplos-gerados/    4 elementos gerados de modelo: bússola, escada, engrenagem, trevo
  templates/gerados/             catálogo dos elementos gerados aprovados (catalogo.json e os desenhos)
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
    perfil.py                    lista, cria e confere os perfis de marca
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
pip install -r skill/welldit/scripts/requirements.txt   # uma vez (precisa do ffmpeg)
python -m playwright install chromium                              # uma vez (desenha os elementos 3D)
cd skill/welldit/scripts
P=../../../saida/2026-10-22_dica-rapida
python inspecionar.py ../../../material-bruto/2026-10-22_dica-rapida/IMG_2040.mov --pasta $P --perfil arven   # o perfil fica gravado na pasta
python transcrever.py ../../../material-bruto/2026-10-22_dica-rapida/IMG_2040.mov --pasta $P --termos "NomeDaMarca, WhatsApp"
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
python conferir.py --pasta $P --video $P/2026-10-22_dica-rapida-v001.mp4 --retranscrever
python elementos.py promover bussola --pasta $P --palavras "bussol,rumo"   # guarda um gerado aprovado no catálogo
```

## Empacotando a skill

```bash
./empacotar.sh        # gera dist/welldit.skill
```

## O que ainda não faz

- Capa do Reels.
- Tirar eco da sala ou consertar áudio estourado (a skill só avisa).
- Duas câmeras ou microfone separado.

O que veio do editonny e o que ficou de fora está em [docs/comparacao-editonny.md](docs/comparacao-editonny.md).

## Créditos

A forma de trabalhar (cartão de ajustes antes de editar, corte medido na onda sonora, amostra antes do vídeo inteiro, conferência real do arquivo) veio do projeto aberto [editonny](https://github.com/soumatheusgomes/editonny), de Matheus Gomes (licença MIT). O código daqui é próprio e bem mais enxuto. Detector de rosto YuNet: OpenCV Zoo, licença MIT. Músicas (HoliznaCC0) e efeitos sonoros (vários autores do Freesound): domínio público (CC0), escolhidos da biblioteca do editonny, com a origem em `skill/welldit/assets/sons/sons.json`. Elementos base ARVEN: o visual padrão (cores e elementos 3D) é da marca ARVEN. Fonte Sora: The Sora Project Authors, licença SIL Open Font License 1.1 (`skill/welldit/assets/fontes/OFL.txt`).
