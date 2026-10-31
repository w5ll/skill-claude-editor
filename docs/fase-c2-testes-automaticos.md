# Fase C2. Testes automáticos a cada envio no GitHub

Trilha C (infraestrutura). Não muda nada do que a pessoa usa no dia a dia: acrescenta um fluxo de testes do GitHub, alguns testes novos e um jeito de rodar tudo com um comando.

## Objetivo

Hoje existem 282 testes (arquivos `tests/test_fase4.py` a `test_fase12.py`), mas só rodam se alguém lembrar de rodar. Com mais de uma pessoa mexendo em `elementos.py`, `renderizar.py`, `painel.py` e no `SKILL.md`, uma fase pode quebrar a outra sem ninguém ver. A C2 faz o GitHub rodar tudo sozinho a cada envio e a cada pedido de revisão, e mostra um selo verde ou vermelho no README e no pedido.

## O que entra

### 1. Fluxo de testes do GitHub

Arquivo `.github/workflows/testes.yml`:

- **Quando roda:** a cada envio (`push`) na `main` e a cada pedido de revisão (`pull request`) para a `main`. Também dá para disparar à mão.
- **Onde roda:** em duas máquinas, Python 3.12. A **principal é um Mac** do GitHub (`macos-latest`), porque é o computador de todo mundo que usa o projeto; se ela ficar vermelha, o envio fica vermelho. A segunda é Linux (Ubuntu), **informativa**: se falhar, avisa, mas não reprova (serve de teste antecipado para a C1).
- **O que instala:** no Mac, `brew install ffmpeg-full` (o mesmo da instalação do README) e o caminho dele no ambiente; no Linux, `ffmpeg` do Ubuntu. Nos dois, as bibliotecas de `requirements.txt` e o Chromium do Playwright. O modelo de transcrição **não** é baixado: os testes não transcrevem (a conferir na implementação; se algum precisar, ele pula e o motivo aparece).
- **Guarda de pacotes** (cache) para o `pip` e o Chromium, para não baixar tudo a cada vez.
- **Limite de 30 minutos no Mac e 20 no Linux**; um envio novo no mesmo ramo cancela a rodada antiga.
- **Resultado:** se qualquer teste falhar, o envio fica vermelho e o pedido de revisão mostra qual. As imagens que um teste de quadros gerar ficam anexadas à rodada para a pessoa ver a diferença.

### 2. Teste que não pula em silêncio

Hoje um teste sem navegador ou sem ffmpeg completo **pula** sem avisar. Foi o que aconteceu ao rodar tudo no Mac: 3 testes da Fase 6 (prévia da legenda) falham porque o `ffmpeg` do Homebrew é o simples, sem `libass`, e a mensagem não explica isso.

- Um arquivo `tests/ambiente.py` confere o que a máquina tem (ffmpeg com `ass`, `zscale` e `afftdn`, Playwright com Chromium) e dá uma mensagem em português: "este teste precisa do ffmpeg completo (veja a instalação)".
- **Na máquina da pessoa:** o teste pula com essa mensagem.
- **Nos testes automáticos** (variável `WELLDIT_TESTES_AUTOMATICOS=1`, ligada pelo fluxo): faltar ferramenta **reprova** em vez de pular. Assim um teste não vira "verde" só porque a máquina não tinha o navegador.
- Os testes atuais que pulam por conta própria (`skipTest` nas Fases 5 a 8, 10 e 11) passam a usar esse arquivo.

### 3. Testes que faltam (as Fases 1 a 3 não têm nenhum)

Arquivo novo por assunto, todos com dados sintéticos (sem vídeo real e sem transcrição):

- **`tests/test_validar.py`: o `validar` dos desenhos.** Aceita os 12 elementos prontos e os exemplos de `templates/exemplos-gerados`; recusa desenho com texto, pessoa, rosto, mão, logotipo, script externo ou animação que não para.
- **`tests/test_cortes.py`: os cortes.** `propor_cortes.py` com fala sintética: tira pausa longa, respiração e frase repetida; **nunca** tira ressalva ou negação nem o aviso obrigatório do perfil; mantém a tomada certa.
- **`tests/test_legenda.py`: a legenda.** O `legendas.ass` do perfil `arven` sai **igual byte a byte** a uma referência guardada (o mesmo teste que a Fase 3 fez à mão); um perfil de teste com outras cores muda as cores e só elas; a legenda sobe ou desce para não cobrir a boca.
- **`tests/test_elementos_quadros.py`: a comparação de quadros dos elementos** (feita à mão na Fase 2). Desenha cada um dos 12 elementos prontos em 3 instantes e compara com quadros de referência guardados em `tests/referencias/`. A comparação **tem tolerância** (diferença média por pixel abaixo de um limite), porque fonte e serrilhado variam um pouco entre sistemas. Para aceitar uma mudança de visual de propósito, `python tests/atualizar_referencias.py` regrava as referências e a diferença aparece no pedido de revisão.
- **`tests/test_projeto.py`: conferências do projeto inteiro.**
  - todo script em `skill/welldit/scripts/` responde a `--help`;
  - `./empacotar.sh` gera o `.skill` e ele traz `SKILL.md`, os scripts e o perfil `arven`;
  - o `name:` do `SKILL.md` é `welldit` e todo arquivo de `referencias/` citado nele existe;
  - nenhuma menção a nome antigo (`lunardiwell`, `edicao-video-well`) fora dos documentos históricos;
  - nenhum vídeo, `.env` ou perfil pessoal dentro do que o git guarda.

### 4. Um comando para rodar tudo

`tests/rodar.sh`: ativa o ambiente (`.venv`), confere o ambiente (item 2) e roda `python -m unittest discover -s tests`. É o mesmo comando do fluxo do GitHub, então "passou aqui" quer dizer "passa lá".

### 5. Documentação

- README: seção curta "Testes" (como rodar, o que cada arquivo cobre, como atualizar as referências) e o selo de resultado no topo.
- `docs/roadmap.md` e o checklist do README: C2 marcada.
- Em `docs/roadmap.md`, nas regras de trabalho em dupla, a regra 4 passa a dizer que o envio só entra na `main` com os testes automáticos verdes.
- Nada muda em `skill/welldit/` (os testes ficam fora da skill), mas rodo o `./empacotar.sh` para conferir que o pacote continua igual.

## O que não entra

- Rodar no Windows a cada envio: depende da C1. Fica para depois dela, como mais uma máquina no mesmo fluxo.
- Teste com vídeo real, transcrição de verdade ou o Claude Code de verdade (Fase 8). Isso continua sendo teste manual e está anotado como "Não coberto" na especificação da Fase 8.
- Proteção do ramo `main` no GitHub (exigir o selo verde para juntar). É uma configuração do site, não do código: explico o passo a passo no README, mas só quem manda no repositório liga.
- Mudar qualquer comportamento dos scripts. Se um teste novo achar um defeito, eu aviso e corrijo só com o seu ok.

## Como saber que ficou pronto

1. `tests/rodar.sh` passa inteiro no Mac com o ffmpeg completo (os 3 testes da prévia da legenda deixam de falhar ou pulam com mensagem clara se o ffmpeg for o simples).
2. O fluxo roda no GitHub, verde, em menos de 20 minutos.
3. Provocar uma quebra de propósito (por exemplo, mudar uma cor de um elemento) deixa o teste de quadros vermelho; desfazer deixa verde.
4. Faltar o navegador na máquina dos testes automáticos reprova em vez de pular.
5. Documentação atualizada, `./empacotar.sh` rodado, checklist do README marcado.

## Riscos e decisões a tomar

- **Quadros de referência feitos no Mac.** A máquina principal também é Mac, então a comparação é a mesma de casa. Um Mac do GitHub pode diferir um pouco do seu (processador, versão do sistema): a tolerância cobre isso, e se passar do limite o primeiro envio fica vermelho e eu ajusto. No Linux a diferença é maior; por ser informativo, ele não trava nada.
- **Tempo.** A rodada local completa leva cerca de 160 segundos; no GitHub, a instalação do `ffmpeg-full` com `brew` é o trecho lento (de 5 a 15 minutos, por isso o limite de 30 e o guarda de pacotes).
- **Envio ao GitHub.** Testar o fluxo de verdade exige enviar o ramo. Só faço isso quando você pedir.

## Passos de implementação

1. `tests/ambiente.py` e troca dos `skipTest` atuais.
2. `tests/rodar.sh`.
3. Testes novos (`test_validar`, `test_cortes`, `test_legenda`, `test_projeto`), um de cada vez, conferindo no Mac.
4. `test_elementos_quadros` com as referências e o `atualizar_referencias.py`.
5. `.github/workflows/testes.yml`.
6. README, roadmap, `./empacotar.sh` e checklist.

## Como ficou

- `.github/workflows/testes.yml`: Mac (principal) e Linux (informativo), com o selo no README.
- `tests/ambiente.py`, `tests/rodar.sh` e `tests/atualizar_referencias.py`.
- Testes novos: `test_validar.py` (8), `test_cortes.py` (14), `test_legenda.py` (13), `test_elementos_quadros.py` (4, com 36 quadros de referência, cerca de 830 KB) e `test_projeto.py` (13). Total: 334 testes, nenhum pulado no Mac com o `ffmpeg-full`, cerca de 160 s.
- Os `skipTest` das Fases 5 a 8, 10, 11 e 12 passaram a usar o `ambiente.py`; os 3 testes de prévia da legenda (Fase 6) agora dizem "precisa do ffmpeg completo" em vez de falhar sem explicação.
- Conferido à mão: trocar a cor do elemento no perfil padrão deixa o teste de quadros vermelho (diferença média 12,7 contra o limite de 1,5) e voltar deixa verde; nos quadros normais a maior diferença medida foi 0,32; faltar o `ffmpeg` completo reprova no modo automático e pula na máquina da pessoa.
- **Não coberto:** o fluxo do GitHub ainda não rodou de verdade (exige enviar o ramo; só com o seu pedido). O tempo da instalação do `ffmpeg-full` com `brew` no Mac do GitHub e a diferença dos quadros entre o seu Mac e o do GitHub só aparecem na primeira rodada.
