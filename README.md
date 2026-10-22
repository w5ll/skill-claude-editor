# Edição de vídeo do Well

Skill do Claude que **edita os vídeos** que o Well ([@lunardiwell](https://instagram.com/lunardiwell)) grava para o Instagram. Par da skill de conteúdo ([skill-cards-insta](https://github.com/w5ll/skill-cards-insta)): lá nasce o roteiro, aqui o vídeo gravado vira Reels pronto.

## Como funciona

1. Você manda o vídeo bruto (e o roteiro, se tiver): *"edita esse vídeo do lead curioso"*.
2. A skill olha o vídeo e mostra um **cartão com todos os ajustes** (ritmo, legenda, som, formato, cor). Nada é editado antes do seu "ok".
3. Transcreve a fala no próprio computador, palavra por palavra.
4. Corta pausas longas, respirações, erros, frases repetidas e começos errados. O corte é medido na onda do som, para não comer sílaba.
5. Coloca a legenda no padrão da marca: Sora ExtraBold, até 3 palavras por vez, palavra falada em azul.
6. Faz os **elementos 3D do carrossel** entrarem animados quando você fala a palavra certa: "WhatsApp" chama a mensagem digitando, "cinco minutos" o relógio com o rótulo "5 minutos", "funil" o funil com leads caindo. Também tem o modo tela cheia, que vira um slide do carrossel por um instante.
7. Iguala o volume da voz ao padrão das redes.
8. Confere uma amostra de 8 a 15 segundos, depois faz o vídeo inteiro e confere de novo (toca até o fim, volume, nenhuma palavra cortada, fala completa).
9. Entrega o MP4, sem nunca apagar os originais nem as versões anteriores.

## Estrutura

```
skill/edicao-video-well/         ← a skill (é isso que vira o arquivo .skill)
  SKILL.md                       fluxo, cartão de ajustes, entrega, regras
  referencias/
    cortes.md                    o que cortar, o que nunca cortar, tomada certa
    legendas.md                  estilo, posição, grafia dos termos
    elementos-3d.md              catálogo dos elementos 3D, modos e critério
    som-e-imagem.md              volume, HDR do iPhone, formato, cor
    gravacao.md                  dicas para gravar de um jeito que edita melhor
    instalacao.md                o que precisa estar instalado
  marca.json                     cores da marca (as mesmas do carrossel)
  assets/fontes/                 Sora ExtraBold (licença OFL)
  templates/elementos.html       desenho e animação dos elementos 3D
  scripts/
    inspecionar.py               lê o vídeo bruto: duração, formato, HDR, volume, quadros
    transcrever.py               transcrição local palavra por palavra (faster-whisper)
    fala.py                      mede fala e silêncio no áudio
    propor_cortes.py             propõe os cortes (cortes.json)
    legendas.py                  monta a legenda no tempo do corte (.ass e .srt)
    elementos.py                 sugere e desenha os elementos 3D
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
python legendas.py --pasta $P
python elementos.py sugerir --pasta $P
python renderizar.py --pasta $P --amostra 0 12
python renderizar.py --pasta $P
python conferir.py --pasta $P --video $P/2026-10-22_lead-curioso-v001.mp4 --retranscrever
```

## Empacotando a skill

```bash
./empacotar.sh        # gera dist/edicao-video-well.skill
```

## O que ainda não faz

- Música e efeitos sonoros (só entram quando pedido; ainda sem biblioteca).
- Redução de ruído.
- Zoom e reenquadramento que acompanha o rosto.
- Capa do Reels.

## Créditos

A forma de trabalhar (cartão de ajustes antes de editar, corte medido na onda sonora, amostra antes do vídeo inteiro, conferência real do arquivo) veio do projeto aberto [editonny](https://github.com/soumatheusgomes/editonny), de Matheus Gomes (licença MIT). O código daqui é próprio e bem mais enxuto. Fonte Sora: The Sora Project Authors, licença SIL Open Font License 1.1 (`skill/edicao-video-well/assets/fontes/OFL.txt`).
