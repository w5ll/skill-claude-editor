# Fase 5. Painel que executa

> **Status: implementada** (29/10/2026) e testada com o painel real, os scripts reais e um trecho de 25 s do vídeo de planejamento (do bruto à entrega aprovada, só pela API e vista numa tela de navegador). As decisões que mudaram estão em [Como ficou](#como-ficou).

Segunda fase da trilha A. O painel (`painel.py`) deixa de só mostrar e passa a **rodar a edição inteira sem abrir uma conversa**: a pessoa envia os vídeos, preenche o cartão num formulário, aprova os portões e acompanha o progresso. Usa o `editar.py` e o `trabalho.json` da Fase 4; nenhuma etapa nova de edição.

## Objetivo

1. **Editar sem conversa**: do bruto à entrega só com cliques (e sem gastar token de Claude nas decisões que são da pessoa).
2. **Segurança primeiro**: hoje qualquer página aberta no navegador poderia falar com o painel (até o envio de arquivos é aberto). Como agora ele **executa**, ganha senha de sessão e confere de onde vem cada pedido.
3. **Conversa e painel juntos**: começar num e terminar no outro, porque os dois leem o mesmo `trabalho.json`.

## Regras que não mudam

- O painel só roda **ações conhecidas** (as do `editar.py`), nunca um comando livre. Não existe campo que receba um comando, caminho de script ou argumento solto.
- Só no computador da pessoa (`127.0.0.1`). Nada sai.
- Nunca mexe nos originais, nunca sobrescreve uma entrega, nunca apaga nada.
- O "ok" é um clique da pessoa, gravado no estado. Nenhuma aprovação é presumida.

## Segurança

| Risco | Defesa |
| --- | --- |
| Outro site aberto no navegador aciona o painel | **Senha de sessão**: um código aleatório novo a cada vez que o painel abre. O endereço com o código aparece no terminal e abre sozinho; ele vira um cookie `HttpOnly` e `SameSite=Strict`, e o código sai do endereço. Sem o cookie, toda a API e os arquivos respondem 401. |
| Pedido forjado de outra origem | Todo pedido que muda algo (`POST`, `PUT`) tem que trazer o cabeçalho `X-Painel` e, se vier `Origin`, ela tem que ser a do próprio painel. |
| Nome de máquina trocado (DNS rebinding) | O cabeçalho `Host` tem que ser `localhost` ou `127.0.0.1` com a porta do painel; qualquer outro é recusado. |
| Caminho fora das pastas | Vídeos só de `material-bruto/`, edições só de `saida/` (nome simples, com `trabalho.json`), arquivos só dessas pastas. |
| Comando livre | Não existe. Cada ação é uma função fixa; escolhas passam por uma lista de valores permitidos. |
| Duas ações ao mesmo tempo na mesma edição | Recusada (409) enquanto a edição está na fila ou rodando. |

## O que a pessoa faz na tela

1. **Nova edição**: marca um ou mais vídeos brutos, escolhe a série e o perfil (opcionais), dá um nome curto e clica **Começar**. A inspeção roda sozinha.
2. **Cartão**: formulário já preenchido com o recomendado (as perguntas do HDR e do ruído com a opção recomendada marcada) e ajustes rápidos (ritmo, zoom, música, efeitos, legenda, elementos, amostra). **Aprovar e começar** grava as escolhas e o "ok" e roda até o próximo portão.
3. **Portões de julgamento** (cortes, elementos, legenda, fatos, gancho e leitura, problemas): mostra a pergunta e os arquivos, com **Aprovar e seguir** e **Copiar pedido para o Claude** (para quem quer a revisão detalhada na conversa; a revisão na tela é a Fase 6).
4. **Amostra**: assistir e **Aprovar a amostra** (quando ela pediu para aprovar).
5. **Fila e progresso**: uma edição por vez, as outras esperam ("na fila, posição 2"). Barra de progresso das etapas longas, **Cancelar** (para o processo em andamento) e **Retomar** (continua de onde parou).
6. **Entrega**: lista de versões com assistir, quadros, emendas e conferência, **Aprovar entrega** (grava qual versão está aprovada para postar) e **Abrir a pasta**.

## A API (tudo `POST` em JSON, exceto onde dito)

`/api/novo`, `/api/aprovar`, `/api/iniciar` (e retomar), `/api/cancelar`, `/api/ajustar`, `/api/refazer`, `/api/aprovar-entrega`, `/api/abrir-pasta`; `GET /api/estado` (inclui a fila, o portão aberto, o cartão e as séries e perfis) e o envio de vídeos (`PUT /api/enviar`, que passa a exigir a sessão). Qualquer outro caminho é 404.

## A fila

Um trabalhador único, fora do servidor HTTP, roda `editar.proximo` de uma edição por vez, na ordem de chegada. Cancelar mata o grupo de processos da etapa e marca a etapa como interrompida (não como falha); retomar a refaz. Se o painel fechar no meio, a etapa fica interrompida e **Retomar** a continua. A fila não sobrevive a um reinício (as edições, sim, pelo `trabalho.json`).

## Mudanças em arquivos que já existem

- `editar.py`: uma exceção de cancelamento que `proximo` trata (etapa vira `interrompida`, sem erro).
- `painel.py` e `templates/painel.html`: ações, sessão e a tela nova. O que já existia (envio, brutos, versões, conferência) continua.
- Novos: `scripts/painel_seguranca.py` e `scripts/fila.py`.
- `SKILL.md`, README (`Painel no navegador`) e `referencias/painel.md`.

## Testes (`tests/test_fase5.py`)

1. Segurança: o código certo vira cookie e o errado não; `Host` de outro nome, `Origin` de outro site e falta do `X-Painel` são recusados; sem sessão, API e arquivos dão 401; o envio de vídeo também.
2. Rotas: um caminho que não existe, um campo desconhecido, uma escolha fora da lista, `..` em nome de vídeo ou de edição, e um pedido de "executar" qualquer coisa são recusados.
3. Fila: uma edição por vez, na ordem; recusa ação na edição ocupada (409); cancelar mata um processo de verdade (grupo inteiro) e deixa a etapa interrompida; retomar continua.
4. Fluxo completo pela API, com um executor de mentira: novo → cartão com o recomendado → aprovar → portões → fim, e **Aprovar entrega** grava a versão.
5. Na tela, num navegador de verdade: o formulário do cartão aparece com o recomendado marcado e **Aprovar e começar** faz o pedido certo.
6. O painel antigo (edições sem `trabalho.json`) continua sendo mostrado.

## Fora desta fase
Revisar cortes e legenda na tela (Fase 6), elementos, zoom e som na tela e os botões de correção (Fase 7), e Claude por trás (Fase 8). Acesso de outro computador da rede (não é objetivo: o painel é só local).

## Como ficou

- **Código de sessão no cookie, não no endereço**: o painel abre em `/?s=CODIGO`, troca por um cookie `HttpOnly`/`SameSite=Strict` e redireciona para `/`. A página sem sessão responde 401 e pede o código.
- **Ações como funções fixas** (`Acoes`), separadas do servidor HTTP e do `editar.py`. O painel nunca monta uma linha de comando: o que roda é `editar.proximo`, numa fila de um trabalhador só.
- **Erros de negócio viram mensagem**: o `editar.py` passou a levantar `PedidoRecusado` (e `Cancelado`) em vez de encerrar o processo, para o painel mostrar o motivo ("faltam respostas: ...") em vez de um erro mudo. A linha de comando continua igual.
- **Cancelar**: cada script roda como processo próprio (`start_new_session`), e cancelar mata o grupo inteiro (um teste confirma que o processo filho também morre). A etapa fica `interrompida`, não `falhou`.
- **Estado em cache** por arquivo: a cada 2 s o painel lê o estado de todas as edições, e calcular o hash das etapas toda vez custaria megabytes. O estado só é recalculado quando algum `.json` da pasta muda.
- **Defeito achado nos testes e corrigido**: com a pasta do projeto num caminho com link simbólico (o `/var` do macOS), o painel quebrava (erro 500). Agora resolve o caminho ao abrir.
- **Defeitos de tela achados olhando a captura**: link azul padrão ilegível no tema escuro, resumos cortados no meio da palavra nas pastilhas, e o caminho inteiro na linha de entrega do cartão.
- **Antes não havia nenhuma autenticação**, nem no envio de arquivos; agora tudo exige a sessão.

## Não coberto
- Revisar cortes e legenda na tela (Fase 6) e elementos, zoom e som (Fase 7): os portões de julgamento só têm **Aprovar** e **Copiar pedido para o Claude**.
- Acesso de outro computador, vários usuários ao mesmo tempo, e fila que sobrevive a fechar o painel.
