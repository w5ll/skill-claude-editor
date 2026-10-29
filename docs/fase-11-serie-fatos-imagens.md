# Fase 11. Direção de arte por série, conferência de fatos e imagens de apoio

Terceira fase da trilha B. Três scripts novos (`serie.py`, `fatos.py`, `imagens.py`) e uma mudança pequena em `elementos.py` para a imagem entrar no vídeo.

## Objetivo

1. **Série.** Quem grava costuma ter séries de vídeos (por exemplo, "planejamento", "bastidores") com o mesmo jeito de editar. Um arquivo por série guarda esse jeito (ritmo, legenda, elementos, zoom, música, formato, avisos e hashtags da publicação) e toda edição da série o segue, sem a pessoa repetir as escolhas no cartão.
2. **Fatos.** Antes de renderizar, a skill marca no que foi falado os números, datas, fontes e afirmações fortes, para a pessoa **confirmar, corrigir ou cortar**. É a rede de proteção para erro de fala (dizer "30 mil" querendo dizer "130 mil").
3. **Imagens de apoio.** Uma biblioteca local de imagens de uso livre, com a licença registrada (como os sons), e um modo de a imagem entrar no vídeo no lugar de um elemento 3D.

## Regras que não mudam

- Nada é aplicado sem o "ok": a série aparece no cartão com a origem "_(da série X)_", e a pessoa pode mudar qualquer linha. Corte por causa de fato só com a resposta da pessoa.
- A skill nunca decide se um fato é verdadeiro: ela só marca e pergunta. Não consulta a internet para "provar" nada.
- Só entra imagem com licença registrada e aceita. Nada de imagem de busca sem origem, de cliente ou de terceiros com direitos reservados. Baixar imagem da internet só quando a pessoa pedir, e a skill só registra o que a pessoa trouxe.
- Nenhum nome de cliente, número real ou método interno vai para um arquivo de série, de fatos ou de imagem que entre no repositório.
- Tudo local, tudo em português.

## Parte 1. Série (`serie.py`)

Os arquivos ficam em `series/<nome>.json`, **na raiz do projeto, fora da skill** (são da pessoa, não vão para o `.skill`). `series/_modelo.json` é o exemplo comentado para copiar. O formato é o mesmo que os **modelos de edição** da Fase 4 vão usar.

```json
{
  "nome": "Planejamento",
  "descricao": "Vídeos de gestão e rotina, tom calmo",
  "ritmo": "natural",
  "formato": "9:16@1080",
  "legenda": {"ligada": true, "palavras": 3, "posicao": "auto", "tamanho": 0.046, "maiusculas": false, "destaque": true},
  "elementos": {"ligado": true, "modo": "sobreposto", "intervalo": 6, "permitidos": [], "proibidos": ["cadeado"], "gerados": true},
  "camera": {"zoom": "leve"},
  "som": {"musica": "calmo", "efeitos": false, "volume": -14},
  "ruido": "auto",
  "termos": ["Fulano"],
  "publicacao": {"hashtags_fixas": ["#planejamento"], "avisos_obrigatorios": [], "chamada": "Siga para mais"}
}
```

Todo campo é opcional: o que não está no arquivo segue o padrão da skill. `permitidos` vazio quer dizer "todos"; `proibidos` ganha de `permitidos`.

Comandos:

- `serie.py listar`: as séries da pasta e a descrição de cada uma.
- `serie.py validar NOME`: confere cada campo (nomes de música e elementos existem, números dentro do limite, nada fora da lista) e diz em português o que está errado.
- `serie.py cartao NOME`: as linhas do cartão de ajustes que a série preenche, já com "_(da série Planejamento)_", e o que ela deixa em aberto.
- `serie.py aplicar NOME --pasta saida/...`: copia a série para `serie.json` na pasta do trabalho (uma **cópia**: mudar a série depois não altera uma edição antiga) e imprime os **comandos** de cada etapa com os parâmetros certos.
- `serie.py elementos --pasta saida/...`: tira do `elementos.json` o que a série proíbe ou não permite (guarda `elementos.anterior.json`).
- `serie.py texto --pasta ... --arquivo texto-do-post.md`: confere se o texto do post traz as hashtags fixas e todos os avisos obrigatórios da série.

## Parte 2. Fatos (`fatos.py`)

`fatos.py marcar --pasta ...` lê as transcrições (e o `cortes.json`, se existir) e marca, por frase:

| Tipo | O que acha | Gravidade |
| --- | --- | --- |
| `numero` | valor em reais, porcentagem, "mil", "milhão", quantidade com unidade (anos, meses, dias, vezes, clientes, pessoas, processos), número a partir de 10 | **alta** |
| `data` | ano (19xx, 20xx), mês com dia | **alta** |
| `fonte` | "segundo...", "pesquisa", "estudo", "dados", "estatística", "levantamento": afirmação apoiada em fonte que a fala não nomeia | **alta** |
| `norma` | "lei", "artigo", "decreto", "resolução", "súmula", "portaria", "regulamento": referência que precisa estar exata | **alta** |
| `comparacao` | "dobro", "triplo", "metade", "X vezes mais" | média |
| `absoluto` | "sempre", "nunca", "todos", "ninguém", "garantido", "garantia", "certeza", "impossível" | média |
| `numero` (pequeno) e `nome` (marca ou pessoa citada) | contagem como "três dicas"; nome próprio | baixa (só com `--tudo`) |

- Só **alta** bloqueia: o `renderizar` do vídeo inteiro só deve rodar quando `fatos.py pendentes` não tiver nada. **Média** vira uma lista para olhar, sem resposta obrigatória.
- O que cai num trecho já cortado entra como `fora_do_corte` e não precisa de resposta.
- `fatos.py mostrar` imprime o bloco do cartão, em português: a frase, o trecho marcado, o que perguntar e as respostas possíveis (**confirmo**, **corrijo para X**, **corta**).
- `fatos.py responder ID --status confirmado|corrigir|cortar [--nota "130 mil"]` grava a resposta. `corrigir` pede o valor certo e o Claude corrige a legenda (e, se a fala está errada, propõe regravar ou cortar a frase: nunca muda o que a pessoa disse sem avisar). `cortar` é decisão para o `cortes.json`.
- `fatos.py adicionar --video N --segundo S --trecho "texto" --motivo "..."` para o que o Claude achar e o script não.
- `fatos.py marcar` de novo (depois de mexer nos cortes) **conserva as respostas** já dadas.
- **Limite**: é heurística sobre fala transcrita. Número escrito por extenso e frase mal transcrita podem escapar: por isso o Claude lê o texto final e usa `adicionar`.

## Parte 3. Imagens de apoio (`imagens.py`)

A biblioteca fica em `imagens/` na raiz do projeto (arquivos e `registro.json`). Cada imagem tem id, arquivo, título, palavras que a chamam, autor, **licença**, **origem** (endereço), data do registro, SHA-256 e duas respostas obrigatórias: aparece pessoa reconhecível? aparece marca de terceiros?

Licenças aceitas: `cc0`, `dominio-publico`, `pexels`, `pixabay`, `unsplash` (licenças próprias dos sites, que liberam o uso comercial sem crédito e têm restrições, por isso a página da imagem fica registrada em `origem`), `cc-by` (**exige crédito**: o texto do crédito é obrigatório no registro) e `propria` (foto da própria pessoa). **Recusadas**, com o motivo: `cc-by-sa` (obriga a licenciar o vídeo igual), `cc-by-nc` (proíbe uso comercial) e qualquer "todos os direitos reservados".

Comandos:

- `imagens.py adicionar ARQUIVO --titulo ... --palavras a,b --autor ... --licenca cc0 --origem URL --pessoa nao --marca nao [--credito "..."]`: confere os campos e a licença, **reduz para no máximo 1920 px** e guarda uma cópia em `imagens/`. O arquivo original não é tocado.
- `imagens.py listar` e `imagens.py buscar PALAVRA...`.
- `imagens.py verificar`: arquivo existe, o SHA-256 bate, licença aceita, `cc-by` com crédito, e avisa as imagens com pessoa ou marca.
- `imagens.py sugerir --pasta ...`: procura, na fala já cortada, as palavras que chamam uma imagem da biblioteca e imprime a proposta (não aplica). No máximo uma a cada 6 s e nunca em cima de outro elemento.
- `imagens.py usar ID --pasta ... --inicio S --duracao D [--modo sobreposto|tela] [--texto "..."]`: coloca a imagem no `elementos.json` como `imagem:ID`.
- `imagens.py creditos --pasta ...`: lista as imagens usadas no vídeo, com autor, licença e origem, e o texto de crédito que o post precisa levar (as `cc-by`). Grava `creditos-imagens.txt` na pasta do trabalho.

**Como a imagem entra no vídeo.** `elementos.py` passa a aceitar `"elemento": "imagem:ID"`, desenhado por `templates/imagem.html` com a mesma entrada de 0,45 s e saída de 0,3 s dos elementos 3D:

- `sobreposto`: cartão com cantos arredondados no tamanho e na posição automática de um elemento (fora do rosto), com rótulo opcional;
- `tela`: a imagem ocupa a tela por 1 a 3 s, com uma película escura da marca por cima e o rótulo embaixo. A voz continua.

A imagem entra no mesmo limite de "um elemento a cada 6 s", usa o mesmo cache e o mesmo efeito sonoro de passagem (`sons.json`, `por_elemento.imagem`).

## Mudanças em arquivos que já existem

- `elementos.py` (compartilhado): reconhece `imagem:ID` em `desenhar`, `previa` e `pasta_do_item` (o hash da imagem entra na chave do cache). Os 12 elementos e os gerados não mudam.
- `som.py` (compartilhado): o item `imagem:` usa o som `por_elemento.imagem`.
- `assets/sons/sons.json`: `por_elemento.imagem`.
- `SKILL.md`: passo 3d (fatos) antes do render, linha 🔎 e 🖼️ no cartão, regras novas; passo 1 lê a série.
- `referencias/series.md`, `referencias/fatos.md`, `referencias/imagens.md`.
- `.gitignore`, README, `series/_modelo.json`.

## Testes

Com dados sintéticos (`tests/test_fase11.py`):

1. Série: `validar` aceita o modelo e recusa música inexistente, zoom fora da lista e elemento desconhecido; `aplicar` faz cópia e os comandos trazem os parâmetros; `elementos` tira o proibido e guarda o anterior; `texto` acha hashtag e aviso faltando.
2. Fatos: acha "cinco mil reais", "30%", "em 2024", "segundo uma pesquisa", "a lei 13.709", "sempre" e "o dobro"; não marca "o segundo passo" como fonte; não marca "três dicas" sem `--tudo`; `fora_do_corte`; `marcar` de novo conserva a resposta; `pendentes` só conta altas sem resposta.
3. Imagens: `adicionar` recusa `cc-by-sa`, `cc-by-nc` e licença desconhecida, exige crédito no `cc-by` e as respostas de pessoa e marca, reduz a imagem grande, não toca o original, e registra o SHA-256; `verificar` pega arquivo trocado; `sugerir` respeita 6 s e outros elementos; `usar` escreve o item certo; `creditos` lista só as usadas.
4. Desenho: uma imagem sintética vira um `elemento.mov` nos dois modos (se houver navegador), e o cache muda quando a imagem muda.
5. Os 12 elementos e os gerados continuam com a mesma chave de cache de antes.
