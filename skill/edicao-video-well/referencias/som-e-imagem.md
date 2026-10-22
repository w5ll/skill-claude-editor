# Som e imagem

## Som

- Volume da voz: -14 LUFS (o padrão das redes sociais), pico até -1,5 dBTP no processamento e no máximo -1 dBTP no arquivo final. Feito em duas passadas, sem esmagar a dinâmica.
- Cada emenda ganha uma suavização de 8 ms na entrada e na saída para não estalar.
- `--sem-normalizar` mantém o volume original (por exemplo, se o Well pedir só a legenda).
- Música, efeito sonoro, trilha de fundo e "whoosh" de transição: só se o Well pedir com essas palavras. "Deixa dinâmico", "ritmo de Reels" ou "estilo daquele vídeo" não são pedido de música. Ainda não há biblioteca de música nesta skill; se ele pedir, diga que a primeira versão sai sem música e ofereça incluir uma faixa que ele mandar.
- Redução de ruído: ainda não implementada. Se o bruto tiver ruído forte, avise no cartão.
- Áudio estourado (distorcido) não tem conserto: avise e sugira regravar a frase.

## Imagem

- Padrão: cor original, sem filtro, sem "melhorar". Nenhuma correção de cor automática.
- Tamanho e fluidez (quadros por segundo) do original. A saída é sempre em taxa fixa, mesmo que o celular tenha gravado em taxa variável.
- `--formato 9:16` (ou `4:5`, `1:1`, `16:9`) corta o centro da imagem, sem esticar. Use quando o bruto veio em outro formato. Confira nos quadros se o rosto continua dentro.
- Vídeos de tamanhos diferentes são ajustados ao tamanho do primeiro, cortando o centro.

## HDR do iPhone

O iPhone grava em HDR (Dolby Vision ou HLG) por padrão. Legenda queimada em HDR sem conversão fica com cor estranha, e alguns celulares exibem o vídeo lavado ou estourado.

- Quando o bruto é HDR, o cartão sempre pergunta. Recomendado: **converter para cor padrão** (`--hdr sdr`). O renderizador não roda sem essa escolha.
- `--hdr manter` só funciona se todos os vídeos forem HDR; sai em HEVC 10 bits.
- Depois de converter, compare um quadro do original com o do resultado. Se ficar escuro demais, avise o Well.
- Melhor ainda: o Well desliga o HDR na câmera (veja `gravacao.md`).

## Codificação

- Cor padrão: H.264, qualidade alta (CRF 18), 8 bits 4:2:0, BT.709, áudio AAC 192 kbps, arquivo pronto para internet (começa a tocar antes de baixar tudo).
- HDR mantido: HEVC 10 bits com as marcações de cor do original.
