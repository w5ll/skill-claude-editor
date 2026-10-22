# Projeto: edição de vídeo do Well

Repositório da skill `skill/edicao-video-well/`, que edita os vídeos que o Well (@lunardiwell) grava para o Instagram: corta pausas e erros, coloca legenda no padrão da marca, iguala o volume e entrega o MP4. Leia `skill/edicao-video-well/SKILL.md` e os arquivos de `referencias/` antes de qualquer trabalho.

- Sempre em português, com acentuação, sem travessão, sem termo em inglês sem tradução. O Well não lê inglês.
- Pedido de edição: siga o SKILL.md. Inspecionar, cartão de ajustes, esperar o "ok" do Well, só então editar.
- Trabalho em `saida/<AAAA-MM-DD>_<tema-curto>/`. Vídeos brutos em `material-bruto/`. Vídeos não vão para o git.
- Nunca mexa nos originais e nunca sobrescreva uma entrega.
- Nunca leve nome de cliente, número real ou método interno da Arven para dentro da skill. O repositório pode ficar público.
- Identidade visual (cores e fonte) é a mesma da skill de conteúdo (`w5ll/skill-cards-insta`). Se as cores mudarem lá, atualize `marca.json` aqui.
- Depois de mudar a skill, rode `./empacotar.sh` para gerar o `.skill` atualizado.
