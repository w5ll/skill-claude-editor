# Projeto: welldit (edição de vídeo)

Repositório da skill `skill/welldit/`, que edita vídeos gravados com o celular para o Instagram: corta pausas e erros, coloca legenda no padrão do perfil de marca, iguala o volume e entrega o MP4. O projeto é para qualquer pessoa com acesso ao repositório: o visual (cores, fonte, nome) vem de um perfil de marca em `skill/welldit/perfis/NOME/`. Leia `skill/welldit/SKILL.md` e os arquivos de `referencias/` antes de qualquer trabalho. O plano em fases e o checklist estão em `docs/roadmap.md` e no README.

- Sempre em português, com acentuação, sem travessão, sem termo em inglês sem tradução. A pessoa que edita pode não ler inglês.
- Pedido de edição: siga o SKILL.md. Inspecionar, cartão de ajustes, esperar o "ok" da pessoa, só então editar.
- Trabalho em `saida/<AAAA-MM-DD>_<tema-curto>/`. Vídeos brutos em `material-bruto/`. Vídeos não vão para o git.
- Nunca mexa nos originais e nunca sobrescreva uma entrega.
- Nunca leve nome de cliente, número real ou método interno de nenhuma empresa para o projeto. O repositório é público. Exceção declarada: a marca ARVEN (cores e elementos base) é o visual padrão, sempre com o aviso "elementos base ARVEN".
- Perfil de marca: o padrão é o `arven`; perfis pessoais ficam fora do git. Se as cores base mudarem, atualize `skill/welldit/perfis/arven/marca.json`. Nada no código nem nos textos pressupõe uma pessoa, um @ ou um nicho: isso é do perfil.
- Trabalho em fases: cada fase tem uma especificação em `docs/fase-N-nome.md` e termina com os testes passando, a documentação atualizada, o `./empacotar.sh` rodado, o checklist do README marcado e o gasto do plano anotado. Quem pega uma fase escreve o nome no checklist antes de começar. Regras de trabalho em dupla em `docs/roadmap.md`.
- Depois de mudar a skill, rode `./empacotar.sh` para gerar o `.skill` atualizado.
