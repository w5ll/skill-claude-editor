# Fase 4. Orquestrador e estado da edição

Primeira fase da trilha A. Um script novo, `editar.py`, que leva uma edição de uma etapa à seguinte, e um arquivo de estado, `trabalho.json`, que a conversa e o painel (Fase 5) leem e escrevem. **Nenhuma etapa existente muda**: o orquestrador só chama os scripts de hoje.

## Objetivo

1. **Menos chamadas e menos texto por edição.** Hoje cada vídeo exige uns 12 scripts, e cada um é uma chamada de Claude com o contexto inteiro reenviado, mais uma saída longa para ler. A Fase 4 move o que é **determinístico** para o código e deixa para Claude (ou para a pessoa) só o que é **julgamento**.
2. **Um estado só.** A conversa, o painel e, na Fase 8, um motor de Claude por trás leem o mesmo `trabalho.json`: dá para começar num e terminar noutro, e retomar depois de uma interrupção.
3. **Modelos de edição.** Um conjunto de escolhas prontas ("Reels padrão") para o cartão já sair preenchido.

## Regras que não mudam

- A pessoa aprova o cartão antes de qualquer edição. O "ok" é gravado no estado, nunca presumido.
- Nunca mexe nos originais, nunca sobrescreve uma entrega, tudo local, tudo em português.
- O orquestrador **não decide nada editorial**: portão de aprovação é portão.

## As etapas e os portões

Cada etapa tem: o comando que roda, o que precisa existir antes, o que produz e se é seguida de um portão.

| # | Etapa | Roda | Portão depois |
| --- | --- | --- | --- |
| 1 | `inspecionar` | `inspecionar.py` | **cartão**: a pessoa aprova (ou muda) as escolhas |
| 2 | `transcrever` | `transcrever.py` | |
| 3 | `cortes` | `propor_cortes.py` | **revisar cortes** (julgamento) |
| 4 | `fatos` | `fatos.py marcar` | **confirmar fatos**, só se houver ponto alto pendente |
| 5 | `rosto` | `rosto.py` | |
| 6 | `gancho_olhar` | `gancho.py avaliar`, `olhar.py medir` | **aprovar sugestões**, só se houver proposta |
| 7 | `elementos` | `elementos.py sugerir`, `cenas.py sugerir`, `imagens.py sugerir` | **aprovar elementos** (julgamento, com a prévia) |
| 8 | `camera` | `camera.py planejar` | |
| 9 | `legenda` | `legendas.py` | **revisar legenda** (grafia) |
| 10 | `som` | `som.py planejar` | |
| 11 | `amostra` | `renderizar.py --amostra` | **aprovar a amostra**, se a pessoa pediu |
| 12 | `video` | `renderizar.py` | |
| 13 | `conferir` | `conferir.py` | **problemas** (corrigir ou aceitar), só se houver falha |
| 14 | `entrega` | resumo final | |

Etapas desligadas pelas escolhas (sem música, sem zoom, sem elementos) são marcadas `pulada` e não rodam. A Fase 4 **vai até a amostra** (etapa 11); as etapas 12 a 14 entram no mesmo mecanismo, mas o critério de pronto para na amostra.

Uma etapa só roda quando as anteriores estão `feita`. Cada etapa guarda um **hash das entradas** (arquivos e escolhas de que depende): se nada mudou, `proximo` pula; se mudou, refaz essa etapa e **invalida as seguintes** (por exemplo, mexer nos cortes invalida rosto, elementos, câmera, legenda, som e amostra).

## O arquivo de estado (`trabalho.json`)

Na pasta do trabalho. Escrito só por `editar.py` (e, depois, pelo painel, pelas mesmas funções).

```json
{
  "versao": 1,
  "perfil": "arven", "serie": "planejamento",
  "videos": ["material-bruto/IMG_5127.MOV", "material-bruto/IMG_5128.MOV"],
  "escolhas": {"formato": "9:16@1080", "ritmo": "natural", "hdr": "sdr", "ruido": "leve", "legenda": {...},
               "elementos": {...}, "camera": "leve", "som": {...}, "amostra": true},
  "etapas": {"inspecionar": {"estado": "feita", "hash": "ab12", "fim": "2026-10-29T12:00:00", "resumo": "2 vídeos, 5:43, HDR"},
             "transcrever": {"estado": "rodando", "inicio": "...", "pid": 4321}},
  "portao": {"nome": "cartao", "tipo": "aprovacao", "aberto_em": "...", "pergunta": "...", "opcoes": ["A", "B"]},
  "aprovacoes": [{"portao": "cartao", "resposta": "A,C", "quando": "...", "quem": "pessoa"}]
}
```

Estados de uma etapa: `pendente`, `rodando`, `feita`, `pulada`, `falhou`, `aguardando` (portão aberto). Uma etapa `rodando` cujo processo não existe mais vira `interrompida` na leitura, e `proximo` a refaz.

## Os comandos

```
editar.py novo VIDEO... [--serie NOME] [--perfil NOME] [--tema curto]   cria a pasta e o trabalho.json
editar.py proximo --pasta ...        roda etapas até o próximo portão (ou o fim); nunca passa de um portão aberto
editar.py estado  --pasta ... [--json]   uma linha por etapa e o portão aberto (curto, para ler sem gastar contexto)
editar.py cartao  --pasta ...        o cartão de ajustes, gerado por código, com pendências e recomendações
editar.py aprovar --pasta ... [PORTAO] [--resposta "A,C"]   grava o "ok" e abre o caminho
editar.py ajustar --pasta ... --escolha chave=valor   muda uma escolha e invalida o que depende dela
editar.py refazer --pasta ... ETAPA  força uma etapa e invalida as seguintes
```

### Saídas curtas (requisito de economia)

- Cada etapa mostra **no máximo 10 linhas**: o resultado e o que precisa de decisão. O resto vai para `etapas/<nome>.log` na pasta do trabalho.
- `estado` cabe em menos de 20 linhas; com `--json`, é um objeto compacto para o painel.
- Lista longa (os trechos do corte, os blocos da legenda) **não é impressa**: fica em arquivo, e o resumo diz quantos há e quais pedem olhar (as marcas "para conferir").
- Imagens (folhas de quadros) só são citadas quando houver alerta; o orquestrador diz qual abrir, não abre sozinho.

### O cartão gerado por código

`editar.py cartao` monta, do `inspecao.json`, da série e das escolhas, as mesmas linhas do cartão de hoje (⚠️ pendências com opções, 📋 ajustes com a origem _(você pediu)_, _(do seu vídeo)_, _(sugerido)_ ou _(da série X)_). A conversa mostra esse texto; o painel (Fase 5) o transforma em formulário. A regra do SKILL.md de que "ok" só vale se responder todas as pendências passa a ser **verificada pelo código**: `aprovar` recusa enquanto houver pendência sem resposta.

## Modelos de edição

A **série** da Fase 11 já é o modelo: mesmo formato, mesmos campos. A Fase 4 acrescenta `series/_reels-padrao.json` (ritmo dinâmico, zoom leve, música calma, 1080x1920 a 60 quadros, ruído conforme a inspeção, cor padrão, amostra ligada) e faz o `novo` aceitar `--serie reels-padrao`. Sem série, valem os padrões da skill. Não se cria uma segunda pasta `modelos/`.

## Os portões de julgamento e a Fase 8

Um portão de **julgamento** (revisar cortes, escolher elementos, corrigir a grafia da legenda) é uma pergunta com entrada e saída bem definidas. A Fase 4 define o protocolo, e a Fase 8 só implementa quem responde:

- `editar.py` grava `pedidos/<portao>.json`: a tarefa em português, **só a entrada mínima** (a transcrição ou o trecho, as regras que valem, o formato da resposta) e o esquema da resposta.
- Quem responde escreve `respostas/<portao>.json`, que `editar.py aprovar` lê e valida contra o esquema.
- Quem responde pode ser: a pessoa (no painel ou na conversa), o Claude Code que está conversando, o `claude -p` ou a API (Fase 8). **O orquestrador não sabe qual.**

Isso mantém cada chamada de Claude pequena e sem laço de ferramentas, e dá um lugar único para gravar o uso (`uso` no `trabalho.json`) quando a Fase 8 existir.

## Mudanças em arquivos que já existem

- `SKILL.md`: o fluxo passa a ser "`editar.py proximo`, leia o resumo, resolva o portão". O texto longo de cada etapa vai para as referências, lidas só quando a etapa pede (meta: o SKILL.md cai de cerca de 26 KB para menos de 10 KB).
- `painel.py`: nada muda nesta fase (a Fase 5 passa a usar o `trabalho.json`).
- `comum.py`: funções pequenas para ler e gravar o estado com escrita atômica.
- README, `series/_reels-padrao.json`, `referencias/orquestrador.md`.

## Testes (`tests/test_fase4.py`)

1. O grafo de etapas: dependências, pular o que está desligado, ordem.
2. `proximo` para no primeiro portão aberto e não passa dele; `aprovar` abre o caminho; `aprovar` recusa com pendência sem resposta.
3. Retomada: etapa `rodando` com processo morto vira `interrompida` e é refeita; etapa `feita` com o mesmo hash é pulada.
4. Invalidação: `ajustar` e `refazer` marcam as etapas seguintes como `pendente`, e só elas.
5. `estado` cabe em 20 linhas e a saída de cada etapa em 10, mesmo com muita coisa a mostrar.
6. O cartão gerado traz pendências com opções, a origem de cada linha e as escolhas da série.
7. Fluxo real em vídeo sintético de 10 s (sem a transcrição, com um comando de teste no lugar): do `novo` à amostra, passando pelos portões, e retomando depois de uma interrupção.
8. Os scripts existentes continuam funcionando sozinhos, sem o orquestrador.

## Pronto quando

`editar.py` leva um vídeo do bruto até a amostra seguindo uma série, para em cada portão, e retoma depois de ser interrompido; a conversa e o `estado --json` mostram o mesmo; uma edição até a amostra imprime pouco o bastante para caber em poucas telas (a meta é medida contando linhas e caracteres impressos, antes e depois).

## Fora desta fase
O painel que executa (Fase 5), a revisão dos cortes e da legenda na tela (Fase 6), os botões de correção (Fase 7) e o motor de Claude por trás (Fase 8). O aparar de silêncios e o ajuste de ganho a partir da conferência, que hoje foram feitos com um script avulso, entram na Fase 7 como botões, reaproveitando essa lógica.

## Decisões em aberto
- **Quem responde os portões de julgamento** na Fase 8: `claude -p`, API com chave, ou os dois (recomendação: os dois atrás do mesmo protocolo, começando pelo `claude -p`). Confirmar nos termos de uso se o plano pode ser automatizado dessa forma.
- **Quais portões ficam ligados por padrão** (a proposta acima liga o cartão, os cortes, os elementos e a legenda).
- **Onde guardar o estado de quem usa o painel sem pasta de trabalho** (a Fase 5 decide).
