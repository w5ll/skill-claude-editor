# O que o editonny tem e a nossa skill ainda não

Comparação feita em 28/10/2026 com a versão do editonny publicada no GitHub ([soumatheusgomes/editonny](https://github.com/soumatheusgomes/editonny), licença MIT). Serve para decidir o que trazer para a `edicao-video-well`. O código continua sendo escrito do nosso jeito, mais enxuto; do editonny vem a ideia e, quando valer a pena, os números que ele já mediu.

## O que já trouxemos na primeira versão

- Cartão de ajustes antes de editar, esperando o "ok".
- Corte medido na onda do som, com limiar calculado para cada gravação.
- Amostra de 8 a 15 segundos antes do vídeo inteiro.
- Volume em -14 LUFS, pico até -1 dBTP.
- Imagem original por padrão, sem filtro; HDR só convertido com escolha no cartão.
- Conferência do arquivo final (toca até o fim, volume, palavra cortada na emenda, retranscrição).
- Nunca sobrescrever entrega anterior.

## O que ele tem e nós não, em ordem de prioridade

### 1. Redução de ruído (recomendado trazer primeiro)

Como ele faz: corta o grave abaixo de 80 Hz e aplica o filtro de ruído do próprio ffmpeg (`afftdn`) usando uma amostra do ruído tirada das pausas da própria gravação. Tem dois níveis, leve e forte. Antes de tratar, mede a diferença entre voz e ruído: 30 dB ou mais é gravação limpa (não mexe), entre 20 e 30 dB pede o leve, abaixo de 20 dB pede o forte. Ele testou outros métodos e esse ganhou.

Por que vale: o Well grava no celular, em sala. Hoje a skill só avisa no cartão que tem ruído. Não precisa instalar nada novo, só ffmpeg.

Custo: baixo. Um script novo (ou uma etapa no `renderizar.py`) e uma linha no cartão ("Ruído: leve, sugerido porque a sala tem chiado").

Arquivos de referência no editonny: `engine/helpers/denoise.py`, `engine/helpers/noise_check.py`.

### 2. Legenda e elementos 3D que desviam do rosto

Como ele faz: um detector de rosto (YuNet, do OpenCV, licença MIT) olha vários quadros de cada trecho e marca onde estão olhos e boca. A legenda e as cenas são colocadas fora dessa área.

Por que vale: a nossa legenda fica numa posição fixa. Se o Well se mexe ou grava mais perto da câmera, a legenda pode passar na boca, e o elemento 3D no topo pode cobrir a testa. Hoje isso só é pego olhando os quadros na conferência.

Custo: médio. Precisa do OpenCV e do arquivo do detector (cerca de 300 KB). Serve de base para o item 3.

Arquivos de referência: `engine/helpers/face_layout.py`.

### 3. Zoom de ênfase e enquadramento que acompanha o rosto

Como ele faz:
- Alterna o zoom a cada frase entre 100% e 112%, dando sensação de corte de câmera num vídeo de uma câmera só.
- Em palavras fortes (negação como "nunca", "nenhum", números, "dobro", "metade") faz uma aproximação rápida de 125% a 130% e segura 0,6 s depois da palavra.
- Não mexe a câmera por baixo de cena em tela cheia.
- Para o zoom não cortar a cabeça, mede o rosto 10 vezes por segundo, suaviza (ignora tremida pequena, segura a posição quando a mão passa na frente) e move o quadro com suavidade.

Por que vale: é o ritmo típico de Reels de quem fala para a câmera. Está na lista do que ainda não fazemos.

Custo: médio a alto. Depende do item 2. Precisa entrar no cartão como escolha ("Câmera: zoom de ênfase, desligado / ligado"), porque mexe na imagem.

Arquivos de referência: `engine/helpers/camera_motion.py`, `engine/helpers/track_faces.py`.

### 4. Conferência mais rígida

O que a conferência dele pega e a nossa não:
- Estalo na emenda (salto brusco na onda bem no ponto do corte).
- Trecho repetido que escapou (a mesma fala tocando duas vezes).
- Silêncio morto que sobrou dentro do vídeo, com o tempo exato para cortar.
- Quadro preto.
- Diferença de volume entre tomadas: um trecho 4 dB abaixo dos outros, ou dois vizinhos com mais de 6 dB de diferença. Ele já diz quanto aumentar naquele trecho.
- Folha de emendas: em cada corte, os 2 últimos quadros do trecho que sai e os 2 primeiros do que entra, para ver pulo de imagem.
- Áudio estourado e eco da sala medidos com mais cuidado (o nosso só conta amostras no máximo).

Por que vale: pega problema antes do Well ver. Usa só o que já temos instalado.

Custo: baixo. Entra no `conferir.py`.

Arquivos de referência: `engine/helpers/verify_cut.py`, `engine/helpers/contact_sheet.py`, `engine/helpers/voice_check.py`.

### 5. Música e efeitos sonoros (só quando o Well pedir)

Como ele faz:
- Biblioteca de músicas por clima (calmo, animado, emocional, batida leve, hip hop e suingado), todas em domínio público (licença CC0, autor HoliznaCC0). São 155 MB.
- Efeitos sonoros também em domínio público (CC0, do site Freesound, com o crédito de cada um): notificação, digitação, passagem rápida, sininho, clique, caixa registradora, relógio, entre outros. São 23 MB.
- A música entra por baixo da voz e abaixa sozinha quando ele fala. Termina com uma saída suave e o volume final é medido de novo.
- O efeito sonoro é colocado no instante exato do movimento que ele acompanha, com espaço mínimo entre um e outro.
- O Well pode ter a biblioteca pessoal dele fora da skill, com o registro de onde veio cada faixa e se pode usar.

Por que vale: o par perfeito para os nossos elementos 3D. O som de notificação entra junto com a mensagem do WhatsApp, a digitação junto com o texto digitando, o tique-taque com o relógio. A regra dele é a mesma nossa: nada de som sem pedido.

Custo: médio. Trazer só alguns efeitos (os que combinam com os 12 elementos) e 2 ou 3 músicas, para o `.skill` não ficar pesado. O resto o Well manda quando quiser.

Arquivos de referência: `engine/helpers/mix_music.py`, `engine/helpers/sound_plan.py`, `engine/helpers/music_library.py`, `visuals/library/effects/CREDITS.md`, `visuals/library/music/catalog.json`.

### 6. Itens menores

- **Texto que já está na tela**: ele mede onde o vídeo bruto já tem texto, para a legenda não ficar por cima. Útil se o Well gravar com texto do próprio Instagram. Prioridade baixa.
- **Duas câmeras ou microfone separado**: ele acerta o tempo entre gravações pela onda do som e troca de câmera no corte. Só vale se o Well passar a gravar assim.
- **Legenda em arquivo VTT** além do SRT. Trivial, se algum lugar pedir.
- **Números falados**: lê "cinco mil reais" como valor em dinheiro. Ajudaria os elementos 3D a escrever o rótulo certo ("R$ 5 mil").

## O que não vale trazer

- **O site guia, o sistema de desenho e as 145 cenas de animação.** O Well já tem a identidade visual dele e os 12 elementos do carrossel.
- **Geração por inteligência artificial paga** (voz, música e imagem por serviço externo). Custa dinheiro e manda o vídeo para fora.
- **Filtros de cor prontos.** O padrão do Well é a cor original.
- **A papelada de controle** (manifesto de entrega com assinatura de arquivo, travas de projeto, revisões com aprovação por diferença). Faz sentido num produto público; para um só usuário, a nossa regra de "nunca sobrescrever, sempre v002" resolve.
- **Os vários idiomas.** O Well grava em português.

## O que nem ele tem

- **Capa do Reels.** O editonny não faz. Tem que ser nossa, e o caminho natural é usar a skill de conteúdo (`w5ll/skill-cards-insta`), que já desenha no padrão da marca.

## Ordem sugerida

1. Redução de ruído e conferência mais rígida (itens 1 e 4): custo baixo, valem para todo vídeo.
2. Testar com um vídeo real do Well antes de seguir.
3. Rosto, depois zoom de ênfase (itens 2 e 3).
4. Efeitos sonoros ligados aos elementos 3D e música (item 5), quando ele quiser.
5. Capa do Reels.

## Licenças

- Código do editonny: MIT. Podemos copiar trechos, mantendo o crédito que já está no README e no SKILL.md.
- Músicas e efeitos sonoros: CC0, domínio público. Crédito não é obrigatório, mas vamos manter a origem de cada arquivo.
- Detector de rosto YuNet: MIT.
- O ajuste de cor dele foi adaptado de outro projeto (video-use, MIT). Não vamos usar.
