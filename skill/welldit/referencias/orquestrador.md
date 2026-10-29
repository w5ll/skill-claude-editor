# O orquestrador (`editar.py`)

Roda as etapas de uma edição na ordem certa, para nos portões e retoma de onde parou. Não decide nada editorial: cada etapa chama os scripts de sempre. O que Claude (ou a pessoa) decide está nos **portões**.

## Uso rápido

```bash
python scripts/editar.py novo VIDEO... [--serie NOME] [--perfil NOME] [--tema curto]
python scripts/editar.py proximo --pasta saida/AAAA-MM-DD_tema
python scripts/editar.py estado  --pasta ... [--json]
python scripts/editar.py cartao  --pasta ...
python scripts/editar.py aprovar --pasta ... [PORTAO] [--resposta "A,C"] [--seguir]   # aprova e já roda até o próximo portão
python scripts/editar.py ajustar --pasta ... --escolha chave=valor
python scripts/editar.py refazer --pasta ... ETAPA
```

`novo` cria `saida/<data>_<tema>/` (nunca sobrescreve: a segunda vez ganha `-2`) e o `trabalho.json`. Sem `--serie`, valem os padrões; `--serie reels-padrao` é um ponto de partida (veja `series.md`).

## As etapas

`inspecionar` → **cartão** → `transcrever` → `cortes` → **cortes** → `fatos` → `rosto` → `gancho_olhar` → `elementos` → **elementos** → `camera` → `legenda` → **legenda** → `som` → `amostra` → `video` → `conferir` → `entrega`. Em negrito, os portões. Etapas desligadas pelas escolhas (sem zoom, sem música, sem elementos, sem legenda) ficam `pulada`. Os portões de fatos, gancho e olhar e problemas da conferência só abrem se houver o que decidir; o da amostra só se a pessoa pediu para aprová-la.

## Como decide o que rodar

Cada etapa guarda um hash de: as escolhas que a afetam, o conteúdo dos arquivos de que depende (por exemplo, o `cortes.json` que você revisou) e a execução das etapas anteriores. Mudou algo, a etapa é refeita e as seguintes também; não mudou nada, é pulada. Por isso:

- Mexer no `cortes.json` depois da revisão refaz rosto, elementos, legenda e a amostra, mas **não** a etapa `cortes` (a revisão é entrada das seguintes).
- `ajustar legenda.palavras=2` refaz só legenda e amostra (e depois o vídeo e a conferência).
- Refazer uma etapa reabre o portão dela, porque a aprovação vale para o hash que foi aprovado.
- Uma etapa `rodando` cujo processo sumiu vira `interrompida` e é refeita no próximo `proximo`.

## O cartão

`cartao` gera o cartão por código: pendências com opções em letra (HDR, ruído) e as linhas de ajuste com a origem (_da série_, _você pediu_, _do seu vídeo_, _sugerido_). `aprovar --resposta "A,C"` exige **uma letra por pendência**; resposta incompleta não grava nada, então as letras não mudam entre uma tentativa e outra. O zoom não combina com HDR mantido, e o `aprovar` recusa essa combinação.

## Portões de julgamento (para a Fase 8)

Ao abrir um portão de julgamento, o orquestrador grava `pedidos/<portao>.json` (a tarefa, os arquivos relevantes e o formato da resposta). Quem responde escreve `respostas/<portao>.json` com `{"aprovado": true, "notas": "..."}`; `aprovar` recusa se `aprovado` não for `true`. Sem arquivo de resposta, o "ok" da pessoa basta. Quem responde (a pessoa no painel, o Claude Code na conversa, `claude -p` ou a API) o orquestrador não sabe.

## Saída curta

Cada etapa imprime **uma linha**, com o que ela produziu (lido dos arquivos dela, sem caminhos nem listas). O texto completo vai para `etapas/<nome>.log`. Só abra o log se uma etapa falhar (`✗`). `estado` cabe em 20 linhas; `estado --json` é para o painel.

## Acrescentar uma etapa

Uma etapa é uma entrada de `ETAPAS` em `editar.py`: nome, de quem depende, quais escolhas e arquivos mudam o resultado, o que precisa existir quando termina, os comandos e (opcional) o portão. Depois acrescente a linha em `resumo_da_etapa` e um teste em `tests/test_fase4.py`.
