# Plano em fases

O projeto deixa de ser a ferramenta do Instagram de uma pessoa e passa a ser **uma ferramenta de edição de vídeo para qualquer pessoa com acesso ao repositório**. Cada pessoa usa a própria marca (cores, fonte, nome) e escolhe como quer editar. O visual que já criamos (fundo escuro, azul acinzentado, fonte Sora) vira o **perfil padrão**, sem nenhum perfil de rede social amarrado.

- **Nome: welldit** (well + edit), para o projeto e para a skill.
- **Visual padrão: ARVEN.** As cores e os elementos 3D atuais ficam como base do projeto, com o aviso **"elementos base ARVEN"** visível. Quem usar o projeto cria o próprio perfil e troca o aviso pelo seu.
- **Repositório público**, como já está no GitHub (sem licença por enquanto).

Este arquivo é o mapa. O checklist resumido fica no [README](../README.md#fases-do-projeto). Cada fase tem a sua especificação em `docs/fase-N-nome.md`, escrita no começo da fase (como a [Fase 2](fase-2-elementos-gerados.md)).

## Como as fases se encaixam

```text
Fase 1 ✅  Fase 2 ✅  Fase 3 ✅  ──►  ──┬──►  Trilha A: painel   4 → 5 → 6 → 7 → 8
                                                              ├──►  Trilha B: conteúdo e entrega   9 · 10 · 11 · 12
                                                              └──►  Trilha C: infraestrutura   C1 · C2
```

- **Fase 3 vem antes de tudo e sozinha**: ela mexe em quase todos os arquivos de texto. Enquanto ela não termina, as outras fases não começam, para não gerar conflito.
- Depois da Fase 3, as três trilhas podem andar **em paralelo**, cada pessoa numa trilha. Dentro da trilha A a ordem é fixa; nas trilhas B e C as fases são independentes.

## As fases

Tamanho é relativo ao esforço da Fase 2 (grande): pequeno, médio ou grande. O gasto real do plano é registrado no fim de cada fase (veja [Gasto do plano](#gasto-do-plano)).

### Fase 1 ✅ Skill de edição e painel de acompanhamento
Inspeção, cartão de ajustes, transcrição local, cortes medidos no áudio, rosto, legenda, zoom, música e efeitos, renderização, conferência, painel que mostra o andamento, tutorial de instalação.

### Fase 2 ✅ Elementos 3D gerados a partir da fala
Elementos novos desenhados para as ideias que nenhum dos 12 prontos representa, com validação, folha de prévia e catálogo. Especificação: [fase-2-elementos-gerados.md](fase-2-elementos-gerados.md).

### Fase 3 ✅ Projeto para qualquer pessoa: perfis de marca · médio
- **Perfil de marca** em `perfis/<nome>/` com `marca.json` (nome, cores, fonte, @ opcional, créditos) e a fonte. Os scripts passam a aceitar `--perfil` (sem ele, usam o perfil padrão). O `marca.json` atual vira o perfil **arven**, o padrão: mesmas cores, fonte e elementos, sem o @ pessoal. Um perfil `_modelo` para a pessoa copiar e preencher.
- **Aviso "elementos base ARVEN"**: aparece no topo e nos créditos do README, no rodapé do painel e no campo `creditos` do perfil. Vale só para a marca (cores e elementos). Continua proibido levar nome de cliente, número real ou método interno da ARVEN para o projeto.
- **Textos neutros**: SKILL.md, referências, README, CLAUDE.md e exemplos falam de "a pessoa que grava", sem o nome do Well, o @ dele nem o nicho jurídico como pressuposto.
- **Regras de nicho viram opcionais**: os gatilhos jurídicos (OAB, ética, cadeado) saem do padrão e viram um pacote que o perfil liga. A regra "nunca cortar o aviso obrigatório" passa a ser uma lista de **avisos obrigatórios** do perfil.
- **Nome welldit**: a pasta `skill/edicao-video-well/` vira `skill/welldit/`, o arquivo gerado vira `welldit.skill` e o `name:` do SKILL.md muda junto. O CLAUDE.md e o README são reescritos para o novo escopo. Renomear o repositório no GitHub (hoje `skill-claude-editor`) é o último passo da fase, com a confirmação de quem manda, porque muda o endereço (o GitHub redireciona o antigo).
- **Pronto quando**: um perfil novo, com outras cores, gera legenda e elementos nas cores dele; o perfil padrão produz quadros **idênticos** aos de hoje (mesmo teste de comparação da Fase 2); não sobra menção ao perfil de ninguém fora de créditos e histórico; o aviso "elementos base ARVEN" aparece nos três lugares.
- Toca: quase tudo. Por isso é a primeira e é feita por uma pessoa só, direto na `main` (as outras fases usam um ramo cada). Especificação e decisões da implementação: [fase-3-perfis-de-marca.md](fase-3-perfis-de-marca.md).

### Fase 4. Orquestrador e estado da edição · médio
- Um `editar.py` que roda a **próxima etapa** de uma edição, para nos portões de aprovação e retoma de onde parou.
- Um arquivo de estado por edição (`trabalho.json`) com as escolhas do cartão, a etapa atual e as aprovações. **O painel e a conversa leem o mesmo estado**: dá para começar num e terminar no outro.
- **Perfis de edição** (modelos prontos de escolhas, em `modelos/`): por exemplo "Reels padrão" (ritmo dinâmico, zoom leve, música calma, 1080x1920 a 60 quadros, ruído leve, cor padrão).
- O **cartão de ajustes gerado por código** a partir da inspeção (pendências e recomendações), além do texto que a conversa já mostra.
- **Pronto quando**: `editar.py` leva um vídeo do bruto até a amostra seguindo um modelo, para nos portões e retoma depois de ser interrompido.

### Fase 5. Painel que executa · grande
- Formulário do cartão já preenchido com o recomendado e botão "Aprovar e começar".
- Fila (um trabalho por vez, vários vídeos), progresso, cancelar e retomar.
- Botões de aprovar a amostra e a entrega; lista de versões; abrir a pasta.
- **Segurança**: como o painel passa a rodar comandos, usa uma **senha de sessão** e confere a origem do pedido, para nenhum site aberto no navegador conseguir acioná-lo. Só roda etapas conhecidas, nunca comando livre. Continua só no computador da pessoa.
- Depende da Fase 4.

### Fase 6. Revisão de cortes e legenda no painel · grande
- O texto da fala com o que fica e o que sai; clique para tirar ou voltar um trecho; ouvir qualquer trecho e qualquer emenda; desfazer.
- **Suspeitas marcadas**: palavra de baixa confiança, som sem palavra, trecho repetido, fim da gravação, frase que não termina.
- Duração total ao vivo contra a meta da pessoa.
- Legenda editável por bloco, com prévia.
- Depende da Fase 5. É a tela mais valiosa: foi onde a edição real deu mais trabalho.

### Fase 7 ✅ Elementos, zoom e som no painel · médio
- Elementos: lista com tempo e prévia, trocar, tirar, mudar o rótulo, catálogo (promover o que gostou).
- Zoom: intensidade e aproximações. Som: música e efeitos com escuta.
- Conferência com **botões de correção** ("aceitar essa pausa", "aplicar o ganho sugerido", "refazer").
- Depende da Fase 5. Especificação e decisões: [fase-7-ajustes-no-painel.md](fase-7-ajustes-no-painel.md).

### Fase 8 ✅ Claude por trás, opcional · médio
- Botões "pedir ao Claude" nas decisões que são de julgamento: primeira revisão dos cortes, escolha das ideias-chave e desenho de elementos novos, correção de grafia da legenda.
- O painel chama o Claude sem abrir conversa e mostra o resultado para a pessoa aprovar. Mostra o gasto (tokens e custo estimado; a porcentagem do plano o Claude Code não informa). Dá para desligar: o painel funciona 100% sem ele.
- Depende das Fases 6 e 7. Precisa do Claude Code instalado. Especificação e decisões: [fase-8-claude-por-tras.md](fase-8-claude-por-tras.md). **Ainda não foi rodada contra o Claude Code de verdade** (veja "Não coberto" na especificação).

### Fase 9. Gancho e olhar · médio (trilha B)
- Avaliar se os 3 primeiros segundos prendem e sugerir trazer uma frase mais forte do meio ou um elemento em tela cheia.
- Detectar quando a pessoa lê ou olha para baixo (pelo `rosto.py`) e sugerir corte ou zoom para disfarçar.

### Fase 10. Pacote de publicação e capa · médio (trilha B)
- Junto com o MP4: texto do post, arquivo de legenda, capa a partir de um quadro com título no visual do perfil, e conferência dos limites do Instagram (duração, tamanho, área segura).

### Fase 11. Direção de arte por série e conferência de fatos · médio (trilha B)
- Um arquivo por série de vídeos com o estilo (elementos, música, ritmo, zoom) que todas as edições da série seguem, ligado aos modelos da Fase 4.
- Antes de editar, marcar números e afirmações para a pessoa confirmar.
- Imagens de apoio de uso livre, com a licença registrada (como os sons).

### Fase 12. Cenas explicativas sincronizadas com a fala · grande (trilha B)
- Telas com texto e números animados (lista de 3 passos, antes e depois) além dos elementos 3D.

### Trilha C. Infraestrutura (independente)
- **C1. Instalação em um comando e outros sistemas** · médio: um `instalar.sh` que cria o ambiente e confere as ferramentas, e o tutorial para Windows e Linux (hoje só há o do Mac).
- **C2. Testes automáticos** · médio: a comparação de quadros dos elementos (feita à mão na Fase 2), o `validar` dos desenhos, os cortes e a legenda, rodando sozinhos a cada envio no GitHub. Com mais de uma pessoa mexendo, é o que impede uma fase de quebrar a outra.

## Quem faz o quê (proposta)

Duas pessoas, duas trilhas, cargas parecidas: **Well** na base e na trilha A (o painel, que é o que mais pesa e tem ordem fixa) e **Lucas** nas trilhas C e B (independentes, boas para andar em paralelo). Quem trabalha numa onda não depende da outra pessoa na mesma onda. A divisão é uma proposta: confirme com o Lucas e troque o nome no checklist do README.

| Onda | Well | Lucas |
| --- | --- | --- |
| **0** | **Fase 3** (base). Decide o nome, a marca e o aviso | Instala o projeto seguindo o tutorial do README numa máquina limpa e **anota tudo que travar** (vira a base da C1). Escreve a especificação da C2 e da Fase 9 em `docs/`, sem mexer em código |
| **1** | **Fase 4** (orquestrador e estado) | **C2** (testes automáticos): primeiro, para proteger todas as fases seguintes |
| **2** | **Fase 5** (painel que executa) | **C1** (instalação em um comando, Windows e Linux) e **Fase 9** (gancho e olhar) |
| **3** | **Fase 6** (revisão de cortes e legenda) | **Fase 10** (pacote de publicação e capa) |
| **4** | **Fases 7 e 8** (elementos, zoom e som no painel; Claude opcional) | **Fases 11 e 12** (direção de arte e fatos; cenas explicativas) |

Por que assim:

- **A Fase 3 é sozinha**, mas o Lucas não fica parado: instalar numa segunda máquina é o melhor teste de instalação que existe, e as especificações são arquivos novos, sem conflito.
- **A C2 vem logo depois da Fase 3** porque, com duas pessoas mexendo, os testes são o que avisa quando uma fase quebra a outra.
- **A trilha A é sequencial** (cada fase usa a anterior), então fica com uma pessoa só. As fases do Lucas são scripts novos, um por fase, e só se encontram com o painel no fim de cada uma (um botão a mais na tela).
- Cada onda é pequena o bastante para fechar numa semana de uso normal do plano, a julgar pelo gasto de referência (veja abaixo). Se uma onda sobrar, adiante a próxima fase da sua trilha.

## Como trabalhamos em dupla

1. **Uma fase, um ramo (branch), um pedido de revisão (pull request).** O ramo se chama `fase-N-nome-curto`. A outra pessoa revisa antes de entrar na `main`.
2. **Quem pega a fase marca o nome** no checklist do README, num commit pequeno, antes de começar. Assim duas pessoas não fazem a mesma coisa.
3. **Cada fase começa pela especificação** (`docs/fase-N-nome.md`): o que entra, o que não entra, os testes. Só depois vem o código.
4. **Cada fase termina com** os testes passando, a documentação atualizada (README, SKILL.md e referências), o `./empacotar.sh` rodado, o checklist marcado e o gasto do plano registrado.
5. **Conflitos**: a trilha A mexe em `painel.py`, `painel.html` e nos arquivos novos do orquestrador; a trilha B cria scripts novos (um por fase); a trilha C mexe em instalação e testes. `elementos.py`, `renderizar.py` e `SKILL.md` são compartilhados: avise no pedido de revisão quando mexer neles.
6. **Mensagem de commit**: em português, no padrão do histórico, uma ideia por commit.
7. **O que nunca entra no repositório**: vídeos, nome de cliente, número real, método interno de empresa. O repositório pode ficar público.
8. **Idioma**: tudo em português, com acentuação, sem travessão e sem termo em inglês sem tradução.

## Gasto do plano

**Referência até agora:** a Fase 2 e este planejamento custaram cerca de **2% do plano semanal** no Sonnet 5.5 com esforço médio (informado pelo Well, a confirmar). Se as fases grandes custarem algo parecido, o roadmap inteiro cabe em poucas semanas, mas só os números reais de cada fase vão dizer.

O Claude Code não deixa o Claude ver quanto do plano foi usado. Por isso, **antes e depois de cada fase, quem trabalhou anota o número que o próprio Claude Code mostra** (o uso do plano), e a diferença entra na tabela do README. Serve para planejar quantas fases cabem por semana e quais compensam o custo.

## Decisões

**Tomadas**

- **Nome:** welldit.
- **Visual padrão:** ARVEN (cores e elementos atuais), com o aviso "elementos base ARVEN".
- **Repositório:** público, por enquanto.
- **Divisão:** Well na Fase 3 e na trilha A; Lucas nas trilhas C e B (proposta acima, falta o Lucas confirmar).

**Em aberto**

- **Onde mais mostrar o aviso ARVEN**: além do README, do painel e do perfil, ele deve aparecer no cartão de ajustes ou na entrega? A proposta é não aparecer no vídeo nem no cartão.
- **Licença**: o repositório é público e não tem licença, o que na prática reserva todos os direitos. Se a ideia é qualquer pessoa usar e adaptar, falta escolher uma (por exemplo MIT, como o editonny que inspirou o projeto). Os elementos base ARVEN poderiam ter uma observação própria.
- **Renomear o repositório** para `welldit` no GitHub (no fim da Fase 3).
- **Escopo do perfil de marca**: o perfil guarda cores, fonte, nome, @ opcional, créditos, termos da transcrição, avisos obrigatórios e o pacote de gatilhos do nicho. Falta alguma coisa?
