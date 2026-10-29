# Fase 3. Projeto para qualquer pessoa: perfis de marca

Especificação. Quem implementa: o Claude Code de quem pegou a fase (Well). Faz parte do [roadmap](roadmap.md) e é a **base**: as outras fases só começam depois dela.

> **Status: implementada** e testada. As decisões que a especificação deixava em aberto estão em [Como ficou](#como-ficou). Falta só renomear o repositório no GitHub, que depende da confirmação de quem manda.

## Objetivo

Hoje a skill é a ferramenta de uma pessoa: o nome, o @, as cores, o nicho e até a forma de falar com o usuário são dela. Depois desta fase, qualquer pessoa com acesso ao repositório cria o **próprio perfil de marca** (cores, fonte, nome, @ opcional, créditos) e edita nas cores dela. O visual que já existe vira o perfil padrão, **arven**, com o aviso "elementos base ARVEN". O projeto passa a se chamar **welldit**.

## Regras que não mudam

- O perfil padrão produz **o mesmo vídeo de hoje**, quadro a quadro. A única diferença é o @ que aparecia no alto da tela cheia dos elementos: o perfil padrão não tem @.
- Nada de vídeo, nome de cliente, número real ou método interno de empresa no repositório (ele é público). A marca ARVEN (cores e elementos base) é a exceção declarada, sempre com o aviso.
- Tudo em português, com acentuação, sem travessão e sem termo em inglês sem tradução.

## Como fica

### 1. O perfil

Uma pasta por perfil, dentro da skill (para ir junto no `.skill`):

```text
skill/welldit/perfis/
  arven/marca.json        o perfil padrão (o visual de hoje)
  _modelo/marca.json      para copiar e preencher
  <nome>/marca.json       o de cada pessoa
```

`marca.json` (os campos novos estão marcados com *):

```json
{
  "nome": "ARVEN",
  "arroba": "",
  "creditos": "elementos base ARVEN",
  "cores": {"fundo": "#16161f", "fundo_profundo": "#0a0a12", "cartao": "#1a1a24", "linha": "#333446",
            "elemento_3d": "#7f8caa", "destaque": "#a8b4d4", "texto": "#eaefef", "apoio": "#b4bccd", "rotulo": "#8f97ab"},
  "legenda": {"fonte": "Sora ExtraBold", "arquivo_fonte": "assets/fontes/Sora-ExtraBold.ttf",
              "cor_texto": "texto", "cor_palavra_falada": "destaque", "cor_contorno": "fundo_profundo"},
  "gatilhos": ["geral", "marketing", "juridico"],
  "avisos_obrigatorios": [],
  "termos": []
}
```

- `nome`: aparece no título do painel. `arroba`: aparece no alto da tela cheia dos elementos; vazio, não aparece nada. `creditos`: aviso fixo mostrado no rodapé do painel.
- `cores` e `legenda`: como hoje. `arquivo_fonte` é procurado primeiro na pasta do perfil e depois na pasta da skill (por isso o `arven` aponta para `assets/fontes/`). `fonte` é o nome da família, que o ffmpeg e a página usam.
- `gatilhos`: quais **pacotes de palavras** o `elementos.py sugerir` usa (item 3).
- `avisos_obrigatorios`: frases que nunca podem ser cortadas (item 4).
- `termos`: grafia certa de marcas e termos (por exemplo `["WhatsApp", "CRM"]`). A legenda corrige sozinha só a caixa e a acentuação de palavras soltas que batem com um termo. Nunca é passado ao transcritor, porque termo que não aparece na fala faz o Whisper inventar palavra.

O `arven` fica com `avisos_obrigatorios` e `termos` vazios, para o resultado continuar idêntico ao de hoje.

### 2. Qual perfil vale

Ordem de escolha, da mais forte para a mais fraca:

1. `--perfil NOME` no script;
2. o perfil gravado na pasta do trabalho (`perfil.json`, criado pelo `inspecionar.py --perfil NOME`);
3. a variável `WELLDIT_PERFIL`;
4. `arven`.

Assim a pessoa escolhe o perfil uma vez, na inspeção, e o resto da edição segue sozinho. (Na Fase 4 esse arquivo é absorvido pelo `trabalho.json`.)

Passam a ler o perfil: `legendas.py` (cores, fonte e medida do texto), `elementos.py` (cores, @, fonte, chave do cache, prévia), `renderizar.py` (pasta da fonte da legenda) e o painel (título, cores, fonte, créditos). A legenda grava o perfil na assinatura: o `renderizar.py` recusa legenda feita com outro perfil, como já faz com outra câmera.

Comandos de apoio, num script novo `perfil.py`: `listar`, `novo NOME` (copia o `_modelo`), `validar NOME` (confere campos, cores em `#rrggbb` e a fonte).

Perfis pessoais não vão para o git por padrão (`.gitignore` guarda só `arven` e `_modelo`); quem quiser compartilhar um perfil usa `git add -f`.

### 3. Gatilhos por pacote

A lista de palavras do `elementos.py` ganha um pacote em cada linha. A ordem não muda (a primeira regra que bate continua valendo), só se ignoram as de pacotes desligados.

| Pacote | O que chama (começo da palavra) |
| --- | --- |
| `geral` | tempo (minuto, hora, demora, prazo...), resultado e crescimento, alvo e foco, análise, perda e vazamento, e todo o bloco de gestão (objetivo, meta, planejamento, rotina, decisão, disciplina...) |
| `marketing` | mensagem (WhatsApp, responder, atendimento...), funil (etapa, jornada, lead, contato) e público (nicho, qualificado) |
| `juridico` | OAB, ética, sigilo e contrato |

`arven`: os três ligados, igual a hoje. `_modelo`: só `geral`. O catálogo de elementos gerados (Fase 2) vale para todos.

### 4. Avisos obrigatórios

O `propor_cortes.py` procura cada aviso do perfil na transcrição (palavras normalizadas, com tolerância a erro de reconhecimento). Se qualquer palavra dele ficar fora dos trechos que sobram, o aviso entra em "PARA CONFERIR" com o motivo e o tempo. Se ficar inteiro, o script diz que foi mantido. A regra de `referencias/cortes.md` deixa de falar da OAB e passa a falar dos avisos do perfil.

### 5. O aviso "elementos base ARVEN"

Aparece no topo e nos créditos do README, no rodapé do painel (vindo do campo `creditos`) e no próprio `marca.json`. Não aparece no vídeo nem no cartão. Quem usar outro perfil troca o texto no campo `creditos`.

### 6. O nome welldit e os textos

- A pasta `skill/edicao-video-well/` vira `skill/welldit/` (com `git mv`, para manter o histórico), o arquivo gerado vira `dist/welldit.skill` e o `name:` do SKILL.md vira `welldit`. Todos os caminhos nos scripts, no README, nos documentos, no `.gitignore` e no `empacotar.sh` acompanham.
- O texto deixa de falar "o Well" e de supor o nicho jurídico: a pessoa que edita é "a pessoa" (ou "você", nos diálogos), os exemplos são neutros e a skill de conteúdo vira uma integração opcional.
- O CLAUDE.md é reescrito para o novo escopo, com a exceção da marca ARVEN.
- Documentos históricos (`comparacao-editonny.md`, `proximas-fases.md`, as especificações antigas) mantêm o texto original, só com os caminhos atualizados.
- Renomear o repositório no GitHub fica **fora desta fase de código**: só depois, com a confirmação do Well.

## Testes antes de dar por pronto

1. **Perfil padrão idêntico.** Uma amostra renderizada com o `arven` tem os mesmos quadros da referência anterior à fase (660 de 660), e o `.ass` da legenda sai igual byte a byte.
2. **Perfil novo.** Um perfil de teste com cores e fonte diferentes gera legenda e elementos (e a folha de prévia) nas cores dele, e o painel mostra o nome, as cores e os créditos dele.
3. **Pacotes.** Com o `arven`, o `sugerir` devolve a mesma lista de antes. Com o `_modelo`, "OAB" e "WhatsApp" não chamam elemento nenhum e "planejamento" continua chamando.
4. **Aviso obrigatório.** Com um aviso no perfil, o `propor_cortes` o marca quando um corte o atinge e confirma quando ele fica inteiro.
5. **Legenda com termo.** Com `termos: ["WhatsApp"]`, "whatsapp" sai "WhatsApp"; sem termo, a legenda não muda.
6. **Troca de perfil no meio.** Gerar a legenda com um perfil e renderizar com outro é recusado com uma mensagem clara.
7. **Renomeação.** `./empacotar.sh` gera `dist/welldit.skill`; todos os scripts respondem a `--help`; o painel sobe e responde; uma busca no repositório não acha `lunardiwell`, `welldit` nem "o Well" fora dos documentos históricos e dos créditos.

## Fora desta fase

- O `trabalho.json`, o orquestrador e os modelos de edição (Fase 4).
- Escolher o perfil pelo painel (Fase 5).
- Licença do repositório e renomeação no GitHub.

## Como ficou

- **`--perfil` e `perfil.json`**: `inspecionar.py`, `legendas.py`, `elementos.py`, `renderizar.py`, `propor_cortes.py` e `painel.py` aceitam `--perfil`. O `inspecionar.py` grava o perfil na pasta do trabalho. Um perfil que não existe é recusado na hora, com a lista dos que existem. Escolher o perfil pelo painel fica na Fase 5: por enquanto o painel usa o perfil com que foi aberto.
- **Pacote `geral` sempre ligado**: o campo `gatilhos` escolhe os pacotes extras; `geral` entra mesmo que o perfil não o liste.
- **Legenda de edições antigas**: a legenda feita antes dos perfis não tem o campo `perfil` e continua valendo (o `renderizar.py` só recusa quando o campo existe e é de outro perfil).
- **Cache dos elementos**: a chave de cada elemento desenhado passa a incluir cores, fonte e @ do perfil. Pastas de trabalho antigas redesenham os elementos uma vez; o resultado é o mesmo.
- **Cores da legenda**: `legenda.cor_texto`, `cor_palavra_falada` e `cor_contorno` do perfil passam a valer (antes o código usava as cores fixas).
- **Fonte**: a página dos elementos e a legenda usam o arquivo da fonte do perfil (procurado na pasta do perfil e depois em `assets/fontes/`). O nome interno da família na página é só um rótulo.
- **Avisos obrigatórios**: o `propor_cortes.py` considera todas as vezes que a frase é dita. Se alguma delas ficar inteira, o aviso está mantido; só é marcado quando nenhuma ficar.
- **Termos**: corrigem a caixa e a acentuação de palavras soltas na legenda, nunca vão para o transcritor.
- **Perfis pessoais** ficam fora do git (`.gitignore`); `perfil.py novo` cria a partir do modelo.

Testes (todos passaram): o perfil padrão gera `legendas.ass` idêntico byte a byte, a mesma lista do `sugerir` e 660 de 660 quadros iguais à referência anterior à fase; um perfil de teste com outras cores, fonte própria, @ e termo gerou legenda, elementos, folha de prévia e painel nas cores dele; o `_modelo` não chama elemento por "OAB" nem "WhatsApp" e continua chamando por "planejamento"; o aviso obrigatório foi marcado como mantido e como não encontrado (o caso "cortado" tem teste de unidade); trocar de perfil entre a legenda e o render é recusado; `./empacotar.sh` gera `dist/welldit.skill`, todos os scripts respondem a `--help` e uma busca no repositório não acha `lunardiwell` nem `edicao-video-well` fora dos documentos históricos.

## Ordem dos commits

1. Esta especificação.
2. O código dos perfis (carregamento, `--perfil`, `perfil.py`, pacotes de gatilhos, avisos obrigatórios, termos, créditos no painel), ainda com a pasta antiga, e a comparação com a referência.
3. A renomeação da pasta para `skill/welldit/` e dos caminhos.
4. Os textos neutros (SKILL.md, referências, README, CLAUDE.md, comentários dos scripts).
5. O checklist marcado e o gasto do plano.
