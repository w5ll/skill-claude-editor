# Edição de vídeo do Well

Skill do Claude que **edita os vídeos** que o Well ([@lunardiwell](https://instagram.com/lunardiwell)) grava para o Instagram. Par da skill de conteúdo ([skill-cards-insta](https://github.com/w5ll/skill-cards-insta)): lá nasce o roteiro, aqui o vídeo gravado vira Reels pronto.

## Como funciona

1. Você manda o vídeo bruto (e o roteiro, se tiver): *"edita esse vídeo do lead curioso"*.
2. A skill olha o vídeo e mostra um **cartão com todos os ajustes** (ritmo, legenda, som, formato, cor). Nada é editado antes do seu "ok".
3. Transcreve a fala no próprio computador, palavra por palavra.
4. Corta pausas longas, respirações, erros, frases repetidas e começos errados. O corte é medido na onda do som, para não comer sílaba.
5. Acha o seu rosto em cada trecho, 10 vezes por segundo.
6. Coloca a legenda no padrão da marca: Sora ExtraBold, até 3 palavras por vez, palavra falada em azul. Se ela fosse cobrir a boca ou o queixo, desce ou sobe sozinha.
7. Faz os **elementos 3D do carrossel** entrarem animados quando você fala a palavra certa: "WhatsApp" chama a mensagem digitando, "cinco minutos" o relógio com o rótulo "5 minutos", "funil" o funil com leads caindo. Eles procuram um lugar que não cubra o rosto. Também tem o modo tela cheia, que vira um slide do carrossel por um instante.
8. Se você pedir, dá **zoom de ênfase**: alterna o enquadramento a cada frase, como se fossem duas câmeras, e aproxima nas palavras fortes ("nunca", números, "dobro").
9. Tira o **chiado de fundo** (leve ou forte, conforme a medição) e avisa áudio estourado e eco da sala.
10. Se você pedir, põe **música** por baixo (abaixa sozinha quando você fala) e um **efeito sonoro** em cada elemento 3D. Tudo de domínio público.
11. Iguala o volume da voz ao padrão das redes, e o volume entre uma tomada e outra.
12. Confere uma amostra de 8 a 15 segundos, depois faz o vídeo inteiro e confere de novo: toca até o fim, volume, nenhuma palavra cortada, nenhum estalo, trecho repetido, silêncio sobrando ou quadro preto, fala completa, e uma folha com os quadros de cada emenda.
13. Entrega o MP4, sem nunca apagar os originais nem as versões anteriores.

## Estrutura

```
skill/edicao-video-well/         ← a skill (é isso que vira o arquivo .skill)
  SKILL.md                       fluxo, cartão de ajustes, entrega, regras
  referencias/
    cortes.md                    o que cortar, o que nunca cortar, tomada certa
    legendas.md                  estilo, posição, grafia dos termos
    elementos-3d.md              catálogo dos elementos 3D, modos e critério
    rosto-e-camera.md            rosto (legenda e elementos fora dele) e zoom de ênfase
    som-e-imagem.md              volume, ruído, estouro, eco, música, efeitos, HDR, formato, cor
    gravacao.md                  dicas para gravar de um jeito que edita melhor
    instalacao.md                o que precisa estar instalado
  marca.json                     cores da marca (as mesmas do carrossel)
  assets/fontes/                 Sora ExtraBold (licença OFL)
  assets/modelos/                detector de rosto YuNet (licença MIT)
  assets/sons/                   3 músicas e 10 efeitos sonoros (domínio público), com a origem em sons.json
  templates/elementos.html       desenho e animação dos elementos 3D
  scripts/
    inspecionar.py               lê o vídeo bruto: duração, formato, HDR, volume, quadros
    transcrever.py               transcrição local palavra por palavra (faster-whisper)
    fala.py                      mede fala e silêncio no áudio
    ruido.py                     mede ruído, estouro e eco; tira o chiado
    propor_cortes.py             propõe os cortes (cortes.json)
    rosto.py                     acha o rosto em cada trecho (rosto.json)
    camera.py                    planeja o zoom de ênfase (camera.json)
    legendas.py                  monta a legenda no tempo do corte, fora do rosto (.ass e .srt)
    elementos.py                 sugere e desenha os elementos 3D
    som.py                       música e efeitos sonoros (som.json)
    renderizar.py                monta o vídeo: amostra ou inteiro
    conferir.py                  confere o arquivo final
material-bruto/                  vídeos brutos (fora do git)
saida/                           trabalhos editados (vídeos fora do git)
```

## Rodando na mão

```bash
pip install -r skill/edicao-video-well/scripts/requirements.txt   # uma vez (precisa do ffmpeg)
python -m playwright install chromium                              # uma vez (desenha os elementos 3D)
cd skill/edicao-video-well/scripts
P=../../../saida/2026-10-22_lead-curioso
python inspecionar.py ../../../material-bruto/2026-10-22_lead-curioso/IMG_2040.mov --pasta $P
python transcrever.py ../../../material-bruto/2026-10-22_lead-curioso/IMG_2040.mov --pasta $P --termos "Arven, OAB, WhatsApp"
python propor_cortes.py --pasta $P --ritmo natural
python rosto.py --pasta $P
python elementos.py sugerir --pasta $P
python camera.py planejar --pasta $P                  # só se quiser zoom
python legendas.py --pasta $P
python som.py planejar --pasta $P --musica batida --efeitos   # só se quiser música ou efeito
python renderizar.py --pasta $P --amostra 0 12 --ruido leve
python renderizar.py --pasta $P --ruido leve
python conferir.py --pasta $P --video $P/2026-10-22_lead-curioso-v001.mp4 --retranscrever
```

## Empacotando a skill

```bash
./empacotar.sh        # gera dist/edicao-video-well.skill
```

## O que ainda não faz

- Capa do Reels.
- Tirar eco da sala ou consertar áudio estourado (a skill só avisa).
- Duas câmeras ou microfone separado.

O que veio do editonny e o que ficou de fora está em [docs/comparacao-editonny.md](docs/comparacao-editonny.md).

## Créditos

A forma de trabalhar (cartão de ajustes antes de editar, corte medido na onda sonora, amostra antes do vídeo inteiro, conferência real do arquivo) veio do projeto aberto [editonny](https://github.com/soumatheusgomes/editonny), de Matheus Gomes (licença MIT). O código daqui é próprio e bem mais enxuto. Detector de rosto YuNet: OpenCV Zoo, licença MIT. Músicas (HoliznaCC0) e efeitos sonoros (vários autores do Freesound): domínio público (CC0), escolhidos da biblioteca do editonny, com a origem em `skill/edicao-video-well/assets/sons/sons.json`. Fonte Sora: The Sora Project Authors, licença SIL Open Font License 1.1 (`skill/edicao-video-well/assets/fontes/OFL.txt`).
