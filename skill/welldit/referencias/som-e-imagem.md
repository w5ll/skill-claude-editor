# Som e imagem

## Som

- Volume da voz: -14 LUFS (o padrão das redes sociais), pico até -1,5 dBTP no processamento e no máximo -1 dBTP no arquivo final. Feito em duas passadas, sem esmagar a dinâmica.
- Cada emenda ganha uma suavização de 8 ms na entrada e na saída para não estalar.
- `--sem-normalizar` mantém o volume original (por exemplo, se o Well pedir só a legenda).
- Volume diferente entre tomadas: a conferência mede cada trecho e avisa quando um fica mais de 4 dB fora do resto (ou dois vizinhos com mais de 6 dB de diferença). Ela já diz o valor: ponha `"ganho_db": 5.0` naquele trecho do `cortes.json` e renderize de novo.

### Redução de ruído

A inspeção mede a diferença entre a voz e o ruído das pausas (chiado, ar-condicionado, rua):

| Diferença | O que é | Sugestão no cartão |
| --- | --- | --- |
| 30 dB ou mais | gravação limpa | sem redução de ruído |
| 20 a 30 dB | chiado perceptível | redução leve (`--ruido leve`) |
| abaixo de 20 dB | ruído forte | redução forte (`--ruido forte`) |

- O tratamento corta o grave abaixo de 80 Hz e usa uma amostra do próprio ruído, tirada das pausas da gravação. A voz fica no mesmo instante da imagem.
- Só entra com a escolha do Well no cartão. Leve primeiro; forte só com ruído forte (forte demais deixa a voz "metálica").
- Para ouvir antes e depois: `python scripts/ruido.py testar BRUTO.mov --modo leve` (canal esquerdo original, direito tratado).
- Tira chiado constante. Barulho que vai e volta (porta, buzina, cachorro) não sai.

### Estouro e eco

- Estouro: a inspeção procura o topo da onda achatado e diz os momentos ("certo" ou "possível"). Não tem conserto na edição: avise no cartão e sugira regravar aquela frase.
- Eco da sala: a inspeção mede quanto o som demora para morrer no fim das frases. "Pouco" ou "sim" vai no cartão como aviso e na entrega como dica de gravação (`gravacao.md`). Também não sai na edição.

### Música e efeitos sonoros

Só se o Well pedir com essas palavras. "Deixa dinâmico", "ritmo de Reels" ou "estilo daquele vídeo" não são pedido de música nem de efeito.

```bash
python scripts/som.py listar
python scripts/som.py planejar --pasta saida/... --musica batida --efeitos
```

- Músicas da skill (domínio público): `calmo`, `animado`, `batida`. Música que o Well mandar: passe o caminho do arquivo em `--musica`; o direito de uso é dele.
- A música fica 22 dB abaixo da voz enquanto ele fala e sobe 6 dB nas pausas, abaixando sozinha quando ele volta. Mais alta: `--abaixo 18`. Começar de outro ponto da música: `--inicio-musica 8`.
- Efeitos: um para cada elemento 3D, no instante em que ele aparece. Mensagem com som de mensagem, relógio com tique-taque, funil com passagem de ar, furo com bipe de erro, gráfico com sinal de acerto, alvo com estalo, cadeado com clique, lupa com passagem curta, esfera, anel, cubo e cristal com brilho, tela cheia com passagem longa. Pelo menos 1,2 s entre um e outro. Elemento gerado (veja `elementos-3d.md`) segue a animação dele: `girar` e `balancar` passagem, `subir` e `encaixar` estalo, `tracar` passagem curta, `pulsar` e `brilhar` brilho, `aparecer` clique (bloco `por_animacao` de `assets/sons/sons.json`).
- Tudo fica em `som.json`: dá para apagar um efeito, trocar o som (`"som": "estalo"`), mudar o volume (`"ganho_db": -3`) ou o tempo. Sem som: `python scripts/som.py desligar --pasta ...` ou `--sem-som` no renderizar.
- A conferência confere se a música ficou abaixo da voz. Ouça a amostra: número de volume não prova que a fala está clara.
- Origem e licença de cada som: `assets/sons/sons.json`.

## Imagem

- Padrão: cor original, sem filtro, sem "melhorar". Nenhuma correção de cor automática.
- Tamanho e fluidez (quadros por segundo) do original. A saída é sempre em taxa fixa, mesmo que o celular tenha gravado em taxa variável.
- Tamanho: com `@1080` no formato (`original@1080`, `9:16@1080`), o vídeo é reduzido para 1080 de largura (1080x1920 no vertical), que é o máximo que o Instagram mostra. Use sempre que o bruto vier em 4K: a edição fica várias vezes mais rápida e o arquivo final, bem menor. Nunca aumenta um vídeo menor. Passe o mesmo `--formato` para `rosto.py`, `legendas.py`, `elementos.py` e `renderizar.py`.
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
