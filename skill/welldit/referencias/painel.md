# O painel que executa

`python scripts/painel.py [--porta 8765] [--sem-abrir] [--perfil NOME]`. Abre o navegador num endereço com um código de sessão. É a mesma edição do `editar.py`, com cliques no lugar de comandos: o painel não tem etapas próprias.

## O que a pessoa faz

1. **Nova edição**: marca os vídeos brutos, escolhe a série e o perfil (opcionais) e clica **Começar**. A inspeção roda sozinha.
2. **Cartão**: formulário com o recomendado marcado e "Ajustes rápidos" (ritmo, zoom, música, efeito, legenda, elementos, amostra). **Aprovar e começar**.
3. **Portões**: cortes, elementos, legenda, fatos, gancho e leitura, problemas da conferência e amostra. **Aprovar e seguir**, ou **Copiar pedido para o Claude** para revisar na conversa.
4. **Fila**: uma edição por vez; as outras ficam "na fila, posição N". **Cancelar** para o processo e deixa a etapa interrompida; **Retomar** continua de onde parou.
5. **Entrega**: versões, folhas de quadros, conferência, **Aprovar entrega** (grava qual versão está aprovada em `trabalho.json`, campo `entrega_aprovada`) e **Abrir a pasta**.

## Conversa e painel juntos

Os dois leem e escrevem o `trabalho.json`. Se a pessoa pedir para revisar um portão na conversa, o orquestrador já gravou `pedidos/<portao>.json`: leia, faça a revisão (`referencias/cortes.md`, `legendas.md`, `elementos-3d.md`...) e aprove com `editar.py aprovar --pasta ... PORTAO --seguir`. Enquanto uma edição está rodando ou na fila no painel, **não** rode `editar.py` nela por fora (o painel recusa o contrário com 409): espere terminar ou cancele.

## Segurança

Como o painel executa, tem defesas:

- **Código de sessão** novo a cada abertura, no endereço do terminal. Vira um cookie `HttpOnly` e `SameSite=Strict` e sai do endereço. Sem ele, a API e os arquivos respondem 401. Se a pessoa abrir `http://localhost:8765` sem o código, a página pede para colá-lo.
- **Host e origem**: o cabeçalho `Host` tem que ser `localhost` ou `127.0.0.1` com a porta do painel (contra o truque de trocar o nome da máquina), a `Origin`, se vier, tem que ser a do painel, e todo pedido que muda algo leva `X-Painel: 1`. Não há CORS.
- **Só ações conhecidas**: `novo`, `aprovar`, `iniciar`, `cancelar`, `ajustar`, `refazer`, `aprovar-entrega` e `abrir-pasta`. Não existe campo que receba um comando. Vídeos só de `material-bruto/`, edições só de `saida/` (nome simples, com `trabalho.json`), escolhas só da lista permitida.
- Ouve só em `127.0.0.1`. Nada sai do computador.

## Limites

- A fila e o processo de uma etapa não sobrevivem a fechar o painel; a edição, sim (`trabalho.json`): abra o painel de novo e clique em **Retomar**.
- A revisão detalhada de cortes e legenda na tela é da Fase 6; elementos, zoom e som na tela e os botões de correção, da Fase 7.
- O painel não substitui a conversa para o que exige julgamento: ele grava o "ok" da pessoa, não decide.
