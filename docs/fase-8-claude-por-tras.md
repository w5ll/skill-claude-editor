# Fase 8. Claude por trás, opcional

> **Status: implementada** (29/10/2026), com 55 testes novos em `tests/test_fase8.py`, **mas nunca rodada contra o Claude Code de verdade**: ele não estava instalado na máquina onde a fase foi feita. Veja [Não coberto](#não-coberto). Quinta e última fase da trilha A. Depende das Fases 6 e 7 (as telas onde as sugestões aparecem) e do protocolo de portões da Fase 4 (`pedidos/` e `respostas/`).

## Objetivo

O painel já edita o vídeo inteiro sem conversa, mas três decisões são de **julgamento** e hoje só se resolvem pedindo na conversa: a primeira revisão dos cortes, a escolha das ideias-chave com o desenho de elementos novos, e a grafia da legenda. A Fase 8 põe um botão **Pedir ao Claude** em cada uma. O painel chama o Claude sem abrir conversa, mostra o que ele sugere e **só aplica o que a pessoa marcar**.

## Regras que não mudam

- **Opcional de verdade.** Sem o Claude Code instalado, ou com o painel aberto com `--sem-claude`, ou com o interruptor desligado na tela, nenhum botão aparece e o painel funciona exatamente como na Fase 7.
- **Nada acontece sozinho.** Cada chamada é um clique, com o aviso de que gasta do plano. O resultado é uma **proposta**; aplicar é outro clique, item a item, e cada item aplicado guarda o arquivo anterior (Desfazer das Fases 6 e 7).
- **Só a entrada mínima.** O pedido leva o texto e as regras daquela tarefa, nunca a pasta, o perfil inteiro, vídeo ou caminho. O Claude roda **sem nenhuma ferramenta** (não lê nem escreve arquivo, não roda comando), numa pasta vazia: o que ele devolve é só texto, que o painel valida antes de mostrar.
- **O que o Claude escreve é dado, nunca instrução.** A fala do vídeo vai dentro do pedido e pode conter qualquer coisa; por isso a resposta só vale se passar pela validação de formato (unidades que existem, valores nos limites, desenho aprovado pelo `validar_svg`), e nada nela vira comando.
- Nunca mexe nos originais nem apaga entrega. O "ok" continua sendo um clique da pessoa.
- Os pedidos que o orquestrador já grava em `pedidos/<portao>.json` (Fase 4) seguem valendo: quem prefere revisar na conversa continua podendo.

## As três tarefas

Cada tarefa tem: a entrada, o formato da resposta (JSON, sem texto em volta), a validação e o que "aplicar" faz.

### 1. Primeira revisão dos cortes (`cortes`)

- **Onde:** na tela de revisão dos cortes (Fase 6).
- **Entrada:** as frases da fala numeradas (`0:12-20`), cada uma marcada como fica ou sai, o motivo do corte automático quando houver, os pontos suspeitos que a tela já marca, a meta de duração (se houver) e os **avisos obrigatórios** do perfil (que nunca podem sair).
- **Resposta:** `{"resumo": "...", "mudancas": [{"unidade": "0:12-20", "acao": "tirar" | "voltar", "motivo": "..."}]}`.
- **Validação:** a unidade existe; a ação muda de fato o estado atual; nada que contenha um aviso obrigatório pode sair; no máximo 40 mudanças; sem repetir a unidade.
- **Aplicar:** cada mudança marcada vira um `tirar` ou `voltar` do `revisao.alternar` (o mesmo clique da tela).

### 2. Ideias-chave e elementos novos (`elementos`)

- **Onde:** na aba Elementos da tela de ajustes (Fase 7).
- **Entrada:** a fala já cortada, com o momento de cada frase no vídeo editado; os elementos que já estão no `elementos.json`; os 12 prontos e os do catálogo; a duração do vídeo; e as regras do desenho (as tags e os limites do `validar_svg`, a receita do volume, as animações).
- **Resposta:** `{"resumo": "...", "itens": [...]}` com três tipos de item: `{"tipo": "usar", "elemento": "alvo", "inicio": 12.3, "duracao": 2.0, "texto": "*3 passos*", "ideia": "..."}` (pronto ou do catálogo), `{"tipo": "novo", "nome": "bussola", "animacao": "girar", "parar": true, "svg": "<g>...</g>", "inicio": ..., "duracao": ..., "ideia": "..."}` (desenho novo) e `{"tipo": "tirar", "id": "funil@3.000", "motivo": "..."}`.
- **Validação:** o elemento pronto existe; o desenho passa no `validar_svg` (tags, forma, animação, limites); o nome é seguro; os momentos cabem no vídeo e não chocam com outro elemento (nem entre as próprias sugestões); no máximo 6 itens; texto de até 40 letras. O que não passa fica de fora e a tela diz por quê.
- **Aplicar:** `usar` e `novo` entram no `elementos.json` (o desenho novo vai para `elementos-gerados/`, sem sobrescrever outro) e `tirar` o remove. Depois a pessoa vê tudo na aba Elementos, **com a prévia**, e pode ajustar, tirar e guardar no catálogo. O desenho novo só é medido na prévia (a margem dentro da caixa); a tela avisa.

### 3. Grafia da legenda (`grafia`)

- **Onde:** na tela de revisão da legenda (Fase 6).
- **Entrada:** o texto de cada bloco numerado e os **termos** do perfil (a grafia certa de marcas e nomes).
- **Resposta:** `{"resumo": "...", "correcoes": [{"bloco": 3, "de": "Insta gran", "para": "Instagram", "motivo": "nome de marca"}]}`.
- **Validação:** o bloco existe; o trecho `de` está no texto do bloco; o resultado cabe nos 80 caracteres; não troca número nem inventa palavra nova (o painel recusa correção que mude os números do bloco); no máximo 60 correções.
- **Aplicar:** `revisao.editar_bloco` em cada bloco marcado, e depois o `legendas.py --reaproveitar` uma vez.

## Como o painel chama o Claude

`claude -p` (modo sem conversa do Claude Code) com a resposta em JSON, **sem ferramentas** (`--tools ""`), um turno só (`--max-turns 1`), sem guardar sessão, sem comandos de barra, sem servidores externos (`--strict-mcp-config`), numa pasta vazia de `.painel/claude/`. O pedido vai pelo fluxo de entrada, não pela linha de comando. O modelo é o `sonnet` (mais barato) e pode ser trocado na tela. Tempo máximo de 3 minutos; **Cancelar** mata o processo.

- **Um pedido por vez** em todo o painel (o segundo recebe 409): é o que limita o gasto.
- **Uso:** cada resposta traz os tokens (as unidades de texto que o Claude conta) de entrada e de saída e o custo estimado que o Claude Code informa. O painel soma por edição e mostra "Claude nesta edição: N pedidos, X de entrada, Y de saída". **O Claude Code não informa a porcentagem do plano** (nem para quem o chama); para ver quanto do plano foi usado, use o próprio Claude Code. A soma fica em `claude/uso.json` da edição.
- **Erros** viram mensagem em português: Claude Code ausente, sem login, limite do plano, resposta que não é JSON ou que não passou na validação (com o motivo). Nenhum erro derruba o painel nem muda a edição.
- Cada proposta fica em `claude/<tarefa>.json` na pasta da edição (com o estado: pendente, aplicada ou descartada), para a conversa também poder ler.

## A API (acrescenta à da Fase 7)

Leitura: `GET /api/claude?pasta` (disponibilidade, interruptor, versão, tarefas com o estado e a proposta, uso). Escrita (`POST`, JSON, mesmas regras da Fase 5): `/api/claude/pedir` (`pasta`, `tarefa`), `/api/claude/cancelar`, `/api/claude/aplicar` (`pasta`, `tarefa`, `itens`: os ids marcados), `/api/claude/descartar` e `/api/claude/ligar` (`ligado`, `modelo`). A tarefa e o modelo são de uma lista; nenhum campo recebe texto livre para o pedido.

## Arquivos

- Novo: `scripts/assistente.py` (tarefas, validação, chamada e uso, sem servidor), testável com um executor de mentira no lugar do `claude`.
- Mudam: `painel.py` (rotas, `--sem-claude`, estado), `templates/painel.html` (o botão e a caixa de sugestões nas três telas e o interruptor).
- Documentação: `referencias/painel.md`, `referencias/orquestrador.md` (o protocolo de portões agora tem quem responda), README.

## Testes (`tests/test_fase8.py`)

1. A resposta do Claude Code: lê o JSON de uma chamada, aceita a resposta com ou sem cerca de código, rejeita o que não é JSON, e transforma `is_error` em mensagem.
2. Validação de cada tarefa com respostas boas, com unidades e blocos que não existem, ações que não mudam nada, avisos obrigatórios, números mudados na legenda, desenho inválido, choque de elementos e excesso de itens.
3. Aplicar: cada item marcado muda só o que diz, deixa histórico, e o que não foi marcado fica como estava.
4. A linha de comando do `claude`: sem ferramentas, um turno, sem sessão, pedido pela entrada e nunca pelos argumentos.
5. Uso somado por edição; um pedido por vez; cancelar; tempo esgotado.
6. API: tudo atrás da sessão, 409 com a edição ocupada ao aplicar, tarefa e modelo fora da lista recusados, e **desligado = nenhum efeito** (com `--sem-claude` ou sem o Claude Code, o painel responde como na Fase 7).
7. Na tela, num navegador de verdade: pedir, ver a sugestão, marcar uma, aplicar e ver a mudança; interruptor desliga os botões.

## Fora desta fase

Aplicar sugestão sem a pessoa marcar, outras tarefas (gancho, fatos), mostrar a resposta aos poucos enquanto chega, a porcentagem do plano (o Claude Code não a informa), e pedir ao Claude coisas livres pelo painel (só as três tarefas fixas).

## Como ficou

- **O uso fica em `claude/uso.json`, não no `trabalho.json`** (a Fase 4 tinha previsto o `trabalho.json`). O painel e a fila já escrevem o `trabalho.json`, e um pedido ao Claude pode rodar enquanto a edição roda: dois escritores sem trava perderiam dados.
- **O gasto conta mesmo quando a resposta não serve.** O uso é gravado assim que o Claude Code responde, antes da conferência: uma resposta que não passou também custou.
- **O "tirar" libera o lugar do elemento** na conferência das sugestões (o Claude pode trocar um elemento por outro no mesmo momento), e a sugestão de elementos inteira é **uma só entrada no histórico**: um Desfazer devolve tudo.
- **Aplicar um corte confere o estado de agora.** Se a pessoa já tirou ou voltou a frase depois do pedido, o item vira "já está assim" em vez de repetir a operação.
- **Desenho novo com o mesmo nome nunca sobrescreve** outro desenho da pasta: vira `nome-2`. Se algo bate na hora de aplicar, nada é gravado e o desenho criado é apagado.
- **O processo do `claude` é sempre esperado depois de morto.** Os testes com um `claude` falso no PATH pegaram o processo morto virando zumbi e os canais abertos (corrigido, e a suíte roda com avisos de recurso tratados como erro).
- De passagem: o servidor imprimia um erro quando a pessoa fechava a aba no meio de uma resposta de erro (o `_json` não tratava a conexão fechada). Corrigido.
- A caixa de sugestões é a mesma nas três telas (um bloco de código), e aparece vazia (sem nenhum botão) com o Claude desligado.

## Não coberto

- **Nunca foi rodada com o Claude Code de verdade.** A linha de comando (`claude -p --output-format json --model ... --tools "" --max-turns 1 --no-session-persistence --disable-slash-commands --strict-mcp-config`) e o formato da resposta foram escritos a partir do que se sabe do Claude Code, e testados só contra um programa `claude` falso. Se uma opção não existir na versão instalada, o painel mostra a mensagem do próprio Claude Code ("o Claude Code recusou o pedido: ...") e **só a função `argumentos()` em `assistente.py` precisa mudar**. **Antes de confiar, rode uma vez com o Claude Code instalado** e confira os três pedidos.
- **A qualidade das sugestões** (cortes, ideias e desenhos, grafia) depende do modelo e não foi avaliada; a conferência só garante que o que chega é válido, não que é bom. Por isso nada é aplicado sem a pessoa marcar, e tudo tem desfazer.
- **O desenho novo só é medido na prévia** (a margem dentro da caixa de 400): a validação antes de aplicar confere as tags, a forma e a animação, não a margem.
- **A porcentagem do plano**: o Claude Code não a informa. A tela mostra os tokens e o custo estimado da edição.
- O modelo `sonnet` é só o padrão por custo; se os desenhos novos saírem fracos, `opus` pode servir melhor (é uma escolha no topo da página).
- Falta alguém que não conhece o código usar as telas.
