# Legendas

## Padrão visual

- Fonte: Sora ExtraBold (a mesma dos títulos do carrossel), em `assets/fontes/`.
- Cor: texto #eaefef com contorno escuro #0a0a12; a palavra que está sendo falada fica em #a8b4d4 (o azul de destaque da marca). Cores em `marca.json`.
- Até 3 palavras por vez, numa linha. O bloco quebra também em pausa, em fim de frase ou quando o texto não cabe na largura (medida com a fonte de verdade).
- Tamanho padrão: 4,6% da altura do vídeo (cerca de 88 px num vídeo de 1920 de altura).
- Sem vírgula e ponto no fim do bloco; interrogação e exclamação ficam.
- Opções: `--maiusculas` (tudo em caixa alta), `--sem-destaque` (sem a palavra azul), `--palavras 2`, `--tamanho 0.05`.

## Posição

- Padrão `auto`: a base do texto fica a 24% da borda de baixo, acima da legenda do post e dos botões do Instagram. Com `rosto.json` (veja `rosto-e-camera.md`), cada bloco que cobriria olhos, boca ou queixo desce para logo abaixo do queixo ou sobe para acima da testa. A lista de blocos mostra onde cada um ficou.
- Posição fixa, sem desviar: `--posicao baixo`, `meio` ou `alto`.
- O texto ocupa no máximo 74% da largura, longe dos botões da direita.
- Rode de novo (`--reaproveitar`) depois de mudar o corte, o rosto ou a câmera: o renderizador avisa quando a legenda ficou velha.
- Texto importante entre 12% e 80% da altura. Não há área segura universal: confira no celular se possível.

## Grafia

A legenda tem que ser fiel ao que foi falado, com a grafia certa. Antes de renderizar, leia todos os blocos de `legendas.json` e corrija o campo `texto`:

- Marcas e ferramentas: WhatsApp, Instagram, Meta, Google, CRM, Kommo, Arven.
- Termos jurídicos: OAB, Código de Ética, Provimento 205/2021, previdenciário, trabalhista, BPC/LOAS.
- Números falados por extenso viram algarismo quando ajuda a leitura: "cinco minutos" → "5 minutos", "trinta por cento" → "30%".
- Nome de cliente ou dado sensível que escapou na fala: avise o Well; não é para estar no vídeo.
- Não "melhore" a fala. Gíria e jeito de falar dele ficam.

Ao corrigir, mantenha o mesmo número de palavras no bloco para a palavra azul continuar acompanhando a fala. Se mudar o número (por exemplo "cinco minutos" → "5min"), o bloco aparece inteiro sem destaque, o que também é aceitável.

Depois de editar: `python scripts/legendas.py --pasta saida/... --reaproveitar`.

Dica: passe os termos já na transcrição (`--termos "Arven, OAB, WhatsApp"`). O Whisper erra menos.

## Arquivo separado

`legendas.srt` é gerado sempre. Só entregue se o Well pedir (por exemplo, para subir a legenda à parte em outra plataforma). Tradução não é feita.
