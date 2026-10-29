# Rosto e câmera

## Rosto (sempre que tiver legenda, elemento 3D ou zoom)

```bash
python scripts/rosto.py --pasta saida/... [--formato 9:16]
```

Procura o rosto do Well 10 vezes por segundo em cada trecho que fica e grava `rosto.json`: onde estão os olhos, a boca e o tamanho do rosto, já no enquadramento final. Rode depois de fechar o `cortes.json` e de novo sempre que o corte mudar (os outros scripts avisam se o `rosto.json` ficou velho).

Com ele:

- a **legenda** confere, bloco por bloco, se cobre olhos, boca ou queixo. Se cobrir, desce para logo abaixo do queixo; se não couber na área segura, sobe para acima da testa; se nem assim couber (rosto ocupando quase a tela toda), fica embaixo e o script avisa o momento;
- o **elemento 3D** procura o primeiro lugar livre: topo, topo menor, esquerda, direita, cada vez menor. Se não houver lugar, avisa: use o modo tela ou tire o elemento;
- o **zoom** cresce em volta do rosto.

O caminho do rosto é suavizado: uma detecção errada não mexe em nada, mão na frente do rosto segura a última posição, tremida pequena é ignorada e cada mudança vira um movimento suave de meio segundo. Trecho em que o rosto não aparece (menos de 30% das medidas) fica com as posições padrão: confira esses quadros.

Detector: YuNet, do OpenCV (licença MIT), em `assets/modelos/`.

O mesmo detector alimenta o `olhar.py`, que marca os trechos de leitura (cabeça abaixada ou virada). Veja `referencias/gancho-e-olhar.md`.

## Câmera: zoom de ênfase (só com escolha do Well no cartão)

```bash
python scripts/camera.py planejar --pasta saida/... [--intensidade leve|normal|forte]
python scripts/camera.py desligar --pasta saida/...
```

Dá ritmo de corte de câmera num vídeo gravado com uma câmera só:

| Intensidade | Frase sim, frase não | Aproximação de ênfase |
| --- | --- | --- |
| leve | 100% e 106% | 115% |
| normal (padrão) | 100% e 112% | 125% |
| forte | 100% e 115% | 130% |

- A cada frase o enquadramento alterna entre aberto e um pouco mais perto. Frase longa (mais de 4,5 s) vira duas; frase curta (menos de 1,2 s) junta com a seguinte; mudança perto de um corte (até 0,25 s) vai para o corte.
- Nas palavras fortes (negação como "nunca", "nenhum", "não", "nada"; números; "dobro", "metade") a câmera aproxima rápido e segura 0,6 s depois da palavra. No máximo uma a cada 4 s, a mesma palavra no máximo 2 vezes, e nunca duas ênfases seguidas na mesma palavra. Se as ênfases ficarem em palavras fracas, troque à mão no `camera.json` para o momento que pede força (o número, a virada, a conclusão).
- Nunca muda o zoom com elemento 3D na tela: a troca espera o elemento sair. Nunca menos de 2,5 s entre uma mudança e outra.
- O zoom cresce em volta do rosto: o rosto fica no mesmo lugar da tela e só aumenta, então não sai do quadro. A legenda e os elementos ficam por cima e não crescem junto.

Revise `camera.json` lendo os motivos ("frase", "ênfase: nunca"). Dá para apagar um bloco, mudar o `zoom` (1.0 a 1.3) ou os tempos. Zoom acima de 1,3 começa a mostrar a perda de nitidez.

**Depois de mexer na câmera, gere a legenda de novo** (`legendas.py --reaproveitar`): ela desvia do rosto já com o zoom. O renderizador recusa legenda feita com outra câmera.

Limites:

- Não funciona com `--hdr manter` (use `--hdr sdr`).
- Ênfase demais cansa. Num Reels de 40 s, 3 a 5 aproximações bastam; se o script sugerir mais, apague as mais fracas.
- Olhe a folha de emendas da conferência: zoom que muda junto com um corte deve parecer troca de câmera, não pulo.
