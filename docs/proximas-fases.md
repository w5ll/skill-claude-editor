# Próximas fases

> **Substituído:** o plano em fases, com o checklist e as regras de trabalho em dupla, está em [roadmap.md](roadmap.md). Este arquivo fica como histórico das ideias de origem.

Mapeado em 29/10/2026, depois da primeira edição real (vídeo de planejamento, IMG_5127 + IMG_5128) e do painel no navegador.

## Fase 2. Elementos 3D novos

> **Atualizado:** a Fase 2 passou a ser elementos gerados a partir da fala de cada vídeo. A especificação está em [fase-2-elementos-gerados.md](fase-2-elementos-gerados.md) e **já está implementada**. Bússola, escada, engrenagem e trevo foram feitos como exemplos (`skill/welldit/templates/exemplos-gerados/`). A lista abaixo fica como ideias de desenho para os próximos.

Hoje são 12 elementos, quase todos ligados a marketing jurídico (mensagem, funil, furo, cadeado...). O vídeo de planejamento mostrou o buraco: ele fala de direção, objetivos, disciplina, decisões e sorte, e quase nada disso tinha elemento.

### Os elementos, em ordem de prioridade

| # | Elemento | Animação | Entra quando ele fala | Som |
| --- | --- | --- | --- | --- |
| 1 | `bussola` | agulha gira e para apontando para cima | para onde você está indo, direção, rumo, caminho | passagem curta |
| 2 | `escada` | degraus aparecem de baixo para cima, uma bolinha sobe | objetivo, meta, chegar lá, passo a passo, degrau | estalo |
| 3 | `engrenagem` | duas engrenagens girando encaixadas | método, metódico, rotina, disciplina, processo, sistema | clique |
| 4 | `trevo` | trevo de quatro folhas gira e brilha | sorte, sortudo, acaso | brilho |
| 5 | `mapa` | rota pontilhada se desenha até um marcador | planejamento, plano, traçar, estratégia | passagem |
| 6 | `barco` | barquinho balançando na onda | à deriva, à margem, sem rumo, reativo | passagem longa |
| 7 | `trofeu` | brilho atravessa o troféu | conquista, atingir, esportista, campeão, vencer | acerto |
| 8 | `foguete` | sobe deixando rastro | lançamento, crescer rápido, startup, empreendedor | passagem longa |
| 9 | `calendario` | folhas virando, um dia marcado | agenda, horário, prazo, mês, ano | clique |
| 10 | `casa` | telhado encaixa e a luz da janela acende | casa, comprar uma casa, família | estalo |
| 11 | `moedas` | moedas caindo e empilhando | dinheiro, caixa, reais, custo, economia, reduzir de X para Y | acerto |
| 12 | `seta-queda` | seta desce de um número grande para um pequeno, com os dois números | reduzir, cortar custo, de 1 milhão para 130 mil | passagem |

O 12 veio do vídeo novo ("AD 26: é possível reduzir de 1M para 130K"): número caindo é um padrão forte de anúncio. Ele usa o rótulo com os dois números falados ("*R$ 1 mi* → *R$ 130 mil*"), e só números que ele falou.

### Padrão de cada elemento (igual aos 12 atuais)

- Vidro fosco e metal escovado no tom `#7f8caa`, luz de cima, fundo transparente. Mesmo traço do carrossel (`w5ll/skill-cards-insta`); se um elemento novo entrar no carrossel, o desenho é o mesmo.
- Entrada de 0,45 s (cresce e assenta), animação própria em loop curto, saída de 0,3 s.
- Funciona nos dois modos: sobreposto (com rótulo opcional) e tela cheia.

### Como fazer cada um

1. Desenho e animação em `templates/elementos.html` (SVG, como os atuais).
2. Nome em `ELEMENTOS` e as palavras em `GATILHOS` (`scripts/elementos.py`). Palavra curta que pega outras ("meta" e "metade") vai em `INTEIRAS`.
3. Som em `assets/sons/sons.json`, em `por_elemento`.
4. Linha no catálogo de `referencias/elementos-3d.md`.
5. Teste: desenhar os quadros, ver o início, o meio e o fim, e renderizar uma amostra com o elemento sobre um rosto.

Custo estimado: 4 elementos por rodada de trabalho. Começar pelos 4 primeiros (bússola, escada, engrenagem, trevo), que cobrem o vídeo de planejamento inteiro.

## Fase 4. Ideias do crIAbr

O [crIAbr](https://www.criabr.com/explorar) é um catálogo pago de "skills", agentes e direções de arte para vídeo. Não copiamos nada de lá (é conteúdo pago e de terceiros); são ideias que valem para a nossa skill, feitas do nosso jeito:

| Ideia | Como ficaria aqui | Valor |
| --- | --- | --- |
| **Gancho nos 3 primeiros segundos** | a skill avalia se o começo do corte prende (frase forte, pergunta, número) e sugere trazer uma frase mais forte do meio para o início, ou um elemento em tela cheia no gancho | alto |
| **Detectar quando ele lê ou olha para baixo** | com o `rosto.py`, medir a direção do olhar; trecho lendo o roteiro vira sugestão de corte ou de zoom para disfarçar | alto (no 5127 ele lia em 0:55) |
| **Pacote de publicação** | junto com o MP4: legenda do post, capa, arquivo de legenda e conferência dos limites do Instagram (duração, tamanho, área segura) | alto |
| **Direção de arte do projeto** | um arquivo por série de vídeos com o estilo (elementos, música, ritmo, zoom), que todas as edições seguem | médio |
| **Imagens de apoio gratuitas com licença** | buscar imagem ou vídeo de apoio de uso livre e registrar a licença, como fizemos com os sons | médio |
| **Conferir os fatos** | antes de editar, marcar números e afirmações para o Well confirmar (útil em anúncio: "reduzir de 1M para 130K") | médio |
| **Cenas explicativas sincronizadas com a fala** | telas com texto e números animados (lista de 3 passos, antes e depois), além dos elementos 3D | médio, caro |

Já temos, e o crIAbr também oferece: transcrição palavra por palavra, limpeza do bruto com conferência, legenda em arquivo, efeitos e música em -14 LUFS.

## Capa do Reels (continua em aberto)

Gerar a capa a partir de um quadro do vídeo com o título no padrão do carrossel, usando a skill de conteúdo.
