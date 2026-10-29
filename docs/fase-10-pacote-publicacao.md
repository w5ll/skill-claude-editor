# Fase 10. Pacote de publicação e capa

Segunda fase da trilha B. Um script novo, `publicar.py`, e dois arquivos de apoio (`assets/instagram.json` e `templates/capa.html`). **A skill continua não publicando nada**: ela entrega uma pasta pronta para a pessoa postar.

## Objetivo

Hoje a entrega é só o MP4. Falta o que a pessoa precisa na hora de postar: a capa, o texto do post, a legenda em arquivo e a certeza de que o vídeo passa nos limites do Instagram. A fase junta isso numa pasta `publicacao-<nome>/`.

## Regras que não mudam

- Nunca publica. Postar é com a pessoa (ou com a skill de conteúdo, e só com "pode postar").
- Nada entra sem o "ok": a capa (quadro e título) e o texto do post passam pelo cartão, como os elementos gerados.
- Título da capa e texto do post só trazem número, nome e afirmação que a pessoa **falou no vídeo**. O script avisa o que não achou na fala.
- Se o assunto exige aviso obrigatório (por exemplo, o aviso do código de ética da profissão), ele entra no texto do post. O Claude confere com a pessoa; o script não decide isso.
- Nunca sobrescreve: capa, grade e pasta ganham o próximo número.
- Tudo local.

## Os limites do Instagram são um arquivo editável

As fontes que achei **divergem** (duração máxima de 90 s a 3 min, zona segura de 895×980 a 1080×1440, limite de hashtags citado por uma só fonte), e o Instagram muda isso com frequência. Por isso os números ficam em `assets/instagram.json`, com a data da conferência e as fontes, e o script usa dois níveis:

- **falhou**: passa do limite que ninguém discute (4 GB, 2.200 caracteres no texto, mais de 30 hashtags, duração acima do maior valor citado, sem som, proporção que não é 9:16).
- **aviso**: está no limite que depende da versão ou da conta (mais de 90 s, mais de 5 hashtags, arquivo acima de 650 MB, menos de 1080 de largura).

A pessoa confere o arquivo na ajuda oficial do Instagram antes de confiar nele. A data de conferência fica à vista na saída.

## Os cinco comandos

### `capa-opcoes --pasta ... --video V.mp4`

Olha o vídeo pronto a cada 0,5 s e escolhe **4 quadros** para capa. Nota de 0 a 1:

| Critério | Peso | Como mede |
| --- | --- | --- |
| Tamanho do rosto | 0,35 | `rosto.json`: largura do rosto entre 25% e 60% da largura do vídeo é o ideal |
| Rosto centralizado | 0,25 | distância do centro do rosto ao meio da tela |
| Nitidez | 0,30 | variância do laplaciano dentro do rosto, comparada com os outros candidatos (tremida e borrão perdem) |
| Boca fechada | 0,10 | o instante cai numa pausa entre palavras |

Descarta o que está a menos de 0,3 s de uma emenda ou sem rosto achado. Os 4 escolhidos ficam a pelo menos 3 s um do outro. Grava `capa-opcoes.json` e a folha `capa-opcoes.jpg` (quadros numerados de 1 a 4). Os quadros da folha vêm do vídeo pronto (com legenda); a capa em si sai de um quadro limpo.

### `capa --pasta ... --video V.mp4 (--opcao N | --segundo S) --titulo "texto com *destaque*"`

1. Renderiza **um quadro limpo** (sem legenda, sem elementos, sem som) no instante escolhido, pelo próprio `renderizar.py --amostra`, com o mesmo formato e a mesma cor do vídeo pronto (lidos do `.render.json`).
2. Desenha o título sobre ele pelo navegador (`templates/capa.html`): Sora ExtraBold, texto na cor da marca, a palavra entre `*asteriscos*` na cor de destaque, faixa escura atrás para dar contraste. A fonte diminui até caber.
3. Posição do título: abaixo ou acima do rosto (o maior espaço livre), **dentro do corte 3:4 da grade do perfil** (o Instagram mostra a grade em 3:4 desde janeiro de 2025, e uma capa 1080×1920 perde 240 px em cima e 240 embaixo) e das margens de segurança. Se não houver espaço de 260 px, diz para escolher outro quadro.
4. Grava `capa-vNNN.jpg` (1080×1920) e `capa-grade-vNNN.jpg`: a capa com o corte 3:4 marcado, ao lado do corte, para ver como fica no perfil.

### `texto --pasta ... --arquivo texto-do-post.md`

Confere o texto do post que o Claude escreveu (ou veio da skill de conteúdo): vazio, passou de 2.200 caracteres, hashtags (mais de 5 é aviso, mais de 30 falha) e **números que a pessoa não falou**. Grava `texto-do-post.txt` sem formatação, pronto para colar.

### `conferir --pasta ... --video V.mp4 [--texto ...] [--capa ...]`

Confere o vídeo contra `instagram.json` (duração, tamanho do arquivo, proporção, largura, quadros por segundo, som, codecs), a **legenda contra as margens** (nenhum bloco sob os botões do lado, sob a legenda do post ou sob o topo; usa o `legendas.json`) e, se vierem, o texto e o título da capa. Imprime "ok", "aviso" ou "FALHOU" para cada item e grava `publicacao.json`. Elementos 3D não são conferidos nas margens (a posição deles é por nome, não por pixel).

### `pacote --pasta ... --video V.mp4 --capa capa-v001.jpg --texto texto-do-post.md`

Roda a conferência e monta `publicacao-<nome do vídeo>/` com:

- o MP4 (um link para o arquivo, sem duplicar o espaço, ou cópia se o disco não permitir),
- `capa.jpg`,
- `texto-do-post.txt`,
- `legenda.srt` (a mesma legenda do vídeo, para quem quiser subir como arquivo),
- `conferencia.md`, em português, com o resultado de cada item.

Se algo **falhou**, não monta, a não ser com `--mesmo-assim`. Avisos não impedem.

## Mudanças em arquivos que já existem

- `SKILL.md`: linha 📦 no cartão, passo 7 ganha a publicação, regra nova ("nunca publica" já existe), a nota "a legenda do post é feita lá" passa a dizer o que fazer sem a skill de conteúdo.
- `referencias/publicacao.md`: como escolher a capa, como escrever o título e o texto, o que fazer com cada aviso.
- README: marca a Fase 10.
- Nada muda em `renderizar.py`, `legendas.py` nem `rosto.py`.

## Testes

Sem vídeo no repositório, os testes são com dados sintéticos (`tests/test_fase10.py`) e um quadro gerado:

1. `conferir_numeros` falha com 200 s, sem som e em 16:9, e avisa com 120 s; passa com 45 s em 1080×1920.
2. `conferir_texto` conta hashtags, falha acima de 2.200 caracteres e avisa o número que não foi falado ("30 clientes" quando só se falou "cinco").
3. A legenda padrão (rodapé a 24%) passa nas margens; uma em y de 1800 falha.
4. A pontuação da capa prefere rosto grande, centrado, nítido e em pausa, e descarta quadro sem rosto ou colado numa emenda; os 4 escolhidos ficam a 3 s ou mais um do outro.
5. A zona do título fica dentro do corte 3:4, escolhe o lado com mais espaço e recusa quando não há 260 px.
6. A capa é desenhada de verdade no navegador sobre um quadro sintético: 1080×1920, e o corte da grade tem 1080×1440.
7. O pacote não sobrescreve uma pasta que já existe e não monta com item que falhou.

Falta o teste com um vídeo real (a nitidez e a escolha dos quadros só se avaliam olhando a folha).
