# Fase C1. Instalação em um comando, Windows e Linux

> **Status: implementada** (30/10/2026), com o ok do Well às decisões abaixo. Resultados na seção [Resultado](#resultado). Trilha C (infraestrutura). Depende da C2 (pedido nº 9), porque o fluxo de testes do GitHub é o que prova o Linux e o Mac.

## Objetivo

Hoje instalar o projeto são 4 passos de Terminal com comandos colados à mão, só no Mac (README, "Instalar no seu Mac, com o VS Code"). A C1 faz três coisas:

1. Um **`instalar.sh`** que prepara tudo com um comando, no Mac primeiro e no Linux em seguida, e que dá para rodar de novo sem estragar nada.
2. Um **tutorial para Windows** e um para **Linux**, no mesmo estilo do do Mac.
3. **Provas**: o `instalar.sh` roda do zero, a cada envio, num Mac e num Linux limpos do GitHub.

## Estado de partida (o que existe)

- Tutorial do Mac no README (seção "Instalar no seu Mac, com o VS Code") e tabela de ferramentas em `skill/welldit/referencias/instalacao.md`. Foi escrito a partir de uma primeira instalação num MacBook M1 Pro, e os problemas dela já estão na tabela "Quando der problema".
- A onda 0 do roadmap pediu ao Lucas que instalasse numa máquina limpa e anotasse o que travou. **Não achei essas anotações** no git (nenhum ramo, nenhum commit) nem em `docs/`. Se ele as tem, me passe antes da implementação; sem elas, a base é a tabela "Quando der problema" e o que o fluxo de testes já mostrou.
- O fluxo de testes (C2) já instala do zero num Mac (`brew install ffmpeg-full`) e num Linux (`apt install ffmpeg`) e passa nos dois. É a prova de que as ferramentas e as bibliotecas servem nos dois sistemas. Ainda não prova o *procedimento* de instalar, que é o que a C1 acrescenta.
- Hoje o caminho do Homebrew está escrito à mão (`/opt/homebrew`) no README e em `tests/rodar.sh`. Em Mac com processador Intel o Homebrew fica em `/usr/local`; o `instalar.sh` usa `brew --prefix` e corrijo os dois lugares.

## O que o `instalar.sh` faz

Fica na raiz do projeto (ao lado do `empacotar.sh`; fora da skill, então não entra no `.skill`). Uso: `./instalar.sh`. Opções: `--so-conferir` (não instala nada, só diz o que falta) e `--sim` (não pergunta, para os testes automáticos).

Passos, nesta ordem, cada um dizendo em uma linha o que está fazendo e o resultado:

1. **Sistema.** Reconhece Mac, Linux com `apt` (Ubuntu e Debian, inclusive dentro do WSL) ou outro. Outro sistema: explica que não é coberto e aponta o tutorial.
2. **Python.** Procura um Python de 3.10 a 3.13 (prefere 3.12). Se não houver (ou só houver o 3.9 do Mac ou o 3.14), instala o `python@3.12` pelo Homebrew (Mac) ou o `python3` e o `python3-venv` pelo `apt` (Linux), **depois de perguntar**.
3. **ffmpeg completo.** Confere `ffmpeg` e `ffprobe` com os filtros `ass`, `zscale` e `afftdn`. Mac: instala o `ffmpeg-full`. Linux: instala o `ffmpeg` do `apt`. Se o ffmpeg que já existe serve, não mexe.
4. **Ambiente da skill (`.venv`).** Cria com o Python do passo 2. Se já existe e está bom, reaproveita. Se existe com Python fora da faixa, **não apaga**: avisa e pergunta se pode guardar como `.venv-antigo` e refazer.
5. **Caminho do ffmpeg-full no Mac.** Acrescenta a linha em `.venv/bin/activate` só se ainda não estiver lá.
6. **Bibliotecas.** `pip install -r skill/welldit/scripts/requirements.txt` (o pip sozinho pula o que já está).
7. **Navegador dos elementos 3D.** `playwright install chromium` (no Linux, com as dependências do sistema, que pedem a senha).
8. **Conferência final.** Roda `tests/ambiente.py` e um `--help` de cada script. Termina com "Tudo pronto" e o que fazer agora (abrir a pasta no VS Code), ou com a lista do que falta em palavras simples.

Regras do script:

- **Pode rodar de novo.** Cada passo confere antes de agir; segunda rodada não muda nada e diz "já estava pronto".
- **Nunca mexe em `material-bruto/` nem em `saida/`**, nem em perfis, nem no git do projeto. O único que ele escreve é `.venv`, `.venv-antigo` (se a pessoa aceitar) e `instalacao.log`.
- **Português simples na tela.** Nada de comando, caminho interno ou erro técnico na conversa. Os comandos e a saída deles vão para `instalacao.log` (que entra no `.gitignore`). Se algo falhar, a tela diz o que não deu certo em uma frase e pede para mandar o `instalacao.log` ao Well.
- **Não instala sem perguntar** o que mexe no sistema (Python, ffmpeg, dependências do `apt`) e avisa que pode pedir a senha do computador. Com `--sim` não pergunta.
- **O modelo de transcrição (1,6 GB) não é baixado agora**; o aviso continua sendo "na primeira transcrição".
- Funciona em `bash` e no `zsh` do Mac (o `/bin/bash` 3.2 do Mac: sem recursos novos do bash).

## Tutorial para Linux e Windows

- **Linux (Ubuntu e Debian):** o mesmo comando, `./instalar.sh`. Passo a passo no README: instalar `git`, baixar o projeto, rodar o comando, abrir no VS Code. Outras distribuições (Fedora, Arch): a tabela de ferramentas diz o que instalar à mão; **não coberto**.
- **Windows: pelo WSL** (Linux dentro do Windows, com o Ubuntu). O tutorial: ligar o WSL com um comando no PowerShell, abrir o Ubuntu, instalar o VS Code com a extensão "WSL" e rodar o mesmo `./instalar.sh` do Linux. Os vídeos ficam em uma pasta do Windows que o Ubuntu enxerga (`/mnt/c/...`), ou dentro do próprio Ubuntu (mais rápido).
- **README:** a seção "Instalar" ganha, no alto, "Em um comando" e três subseções (Mac, Linux, Windows). Os passos manuais do Mac atuais ficam como "Se o comando não funcionar: instalar à mão", e valem também de referência para o que o script faz.
- **`referencias/instalacao.md`** e a tabela de ferramentas passam a incluir Linux e Windows (WSL), e o `SKILL.md` ganha uma linha apontando o `instalar.sh` (arquivo compartilhado: aviso no pedido de revisão).

## Provas e testes

| O que | Como | Resultado esperado |
| --- | --- | --- |
| `instalar.sh` num **Mac limpo** | novo trabalho no fluxo do GitHub (`macos-latest`, sem nada do projeto instalado): `./instalar.sh --sim`, depois uma **segunda rodada** (tem que dizer "já estava pronto" e não alterar nada), depois os testes dentro do `.venv` que ele criou | Mac é a máquina principal: se falhar, fica vermelho |
| `instalar.sh` num **Linux limpo** | o mesmo, no `ubuntu-latest` | informativo, como hoje |
| `instalar.sh --so-conferir` | teste novo `tests/test_instalar.py` com um `PATH` falso (ferramentas de mentira em uma pasta temporária): sem ffmpeg, com ffmpeg sem `libass`, com Python 3.9, com `.venv` ruim | diz o que falta em português, sem instalar, sem apagar |
| Texto da tela | o mesmo teste: nenhuma palavra em inglês fora de uma lista de nomes próprios (`ffmpeg`, `Python`, `Homebrew`...), nenhum travessão, tudo com acentuação | passa |
| Não mexe no que não pode | o mesmo teste: antes e depois, `material-bruto/` e `saida/` de uma pasta de teste ficam byte a byte iguais; o script não tem nenhuma escrita nesses caminhos | passa |
| Na minha máquina | rodo o `instalar.sh` num clone limpo, numa pasta nova do Mac (sem tocar no `.venv` atual do projeto), e a segunda vez em cima | anoto o resultado aqui |

### Não coberto (será dito assim na entrega)

- **Windows direto (sem WSL) e o próprio WSL.** Não tenho máquina Windows aqui. O Linux dentro do WSL é o Ubuntu que o GitHub testa, então a parte do Linux está provada; o que **não** está provado é o passo de ligar o WSL, a extensão do VS Code e a pasta `/mnt/c`. O tutorial do Windows sai marcado "ainda não testado num Windows de verdade".
- **Linux que não é Ubuntu ou Debian** e **Mac antigo** (Intel, macOS antigo): o script usa `brew --prefix`, mas só o Mac com processador Apple (o `macos-latest` do GitHub e o do Well) é provado.
- **Claude Code e VS Code:** o script não instala (pedem a conta da pessoa); o tutorial continua mandando baixar.

## O que não entra

- Instalar o Homebrew pelo script (veja a primeira pergunta).
- Windows direto, sem WSL: o painel usa `os.killpg` e `start_new_session` (`fila.py`, `assistente.py`), que não existem no Windows, e abrir a pasta usa `open`/`xdg-open` (`painel.py`). Portar isso é uma fase à parte, com máquina Windows para testar.
- Atualizar a skill (`git pull`) pelo script. Continua sendo o passo 8 do tutorial.

## Decisões do Well (30/10/2026)

1. Homebrew: o script **não instala**; mostra o link do brew.sh e pede para rodar de novo.
2. Windows: **só pelo WSL**. Windows direto fica para uma fase futura.
3. Sem `instalar-windows.ps1`: só o tutorial.
4. Sem máquina Windows no fluxo do GitHub.
5. Fluxo novo à parte: `.github/workflows/instalacao.yml`.
6. Sem anotações do Lucas da máquina limpa.
7. **Aviso no README** (pedido do Well, porque o repositório é público) de que o projeto não é otimizado para o Windows e o que isso significa. Está no alto da seção "Instalar, com o VS Code".

## Resultado

- `instalar.sh` na raiz; `tests/test_instalar.py` (13 testes, ferramentas de mentira); `.github/workflows/instalacao.yml`; README, `referencias/instalacao.md`, `SKILL.md` (uma linha), `tests/rodar.sh` (agora com `brew --prefix`) e `.gitignore` (`instalacao.log`, `.venv-antigo*`).
- **Provado no Mac do Well** (pasta limpa, sem o `.venv`): `--so-conferir` lista o que falta e sai com erro; a instalação completa leva cerca de 45 s com o cache do pip e termina em "Tudo pronto"; a **segunda rodada** diz "Tudo já estava pronto" e a pasta fica byte a byte igual; `material-bruto/` e `saida/` de teste não mudaram; o `.venv` criado enxerga `ass`, `zscale` e `afftdn`.
- **Ainda não provado** (só depois do primeiro envio ao GitHub): o fluxo `instalacao.yml` no Mac e no Linux limpos. Python ausente, `apt` e `sudo` do Linux só são exercitados lá.
- **Não coberto:** Windows e o próprio WSL; Linux que não é Ubuntu ou Debian; Mac com processador Intel; o ramo de instalar o Python quando falta (no Mac, o `python@3.12` do Homebrew já existia).
- `tests/rodar.sh`: 347 testes. Um deles, `test_fase7.TestTela.test_zoom_e_som_pela_tela` (painel, escolha da música), **falha de vez em quando na suíte inteira neste Mac e passa isolado e no módulo**. Acontece igual na base sem a C1 (334 testes), então é anterior; fica anotado para olhar à parte.

## Pedido nº 9 e ramo

O pedido nº 9 (C2) segue **aberto**, sem conflito e com os dois testes verdes (Mac e Linux). Este trabalho está no ramo `fase-c1-instalacao`, criado a partir do ramo da C2 (a `main` do GitHub ainda não tem os testes automáticos). Quando o nº 9 entrar, o ramo da C1 se ajusta à `main` sem retrabalho.
