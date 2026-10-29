# Fatos

Erro de fala acontece: dizer "30 mil" querendo dizer "130 mil", citar uma lei pelo número errado, dizer "sempre" quando é "quase sempre". Depois do render, o erro vira legenda e vai para o Instagram. Por isso, **antes do render**, o `fatos.py` marca o que a fala afirma e o Well confirma.

Você marca e pergunta. **Nunca decide se algo é verdadeiro** e não busca nada na internet para "provar".

## O que o script marca

| Tipo | Exemplo | Gravidade |
| --- | --- | --- |
| `numero` | "cinco mil reais", "30%", "cento e vinte mil", "R$ 5.000", "três anos" | alta |
| `data` | "em 2024", "10 de março de 2023" | alta |
| `fonte` | "segundo uma pesquisa", "li num estudo", "os dados mostram" | alta |
| `norma` | "lei 13.709", "artigo 5", "súmula" | alta |
| `comparacao` | "o dobro", "metade" | média |
| `absoluto` | "sempre", "nunca", "todos", "garantido", "certeza" | média |
| `numero` pequeno, `nome` | "três dicas", "Instagram" | baixa (só com `--tudo`) |

**Alta** precisa de resposta e trava o render do vídeo inteiro. **Média** vira uma lista "para olhar" sem resposta obrigatória. Marca que cai num trecho já cortado vira `fora_do_corte` e some do cartão.

## Fluxo

1. Depois de fechar os cortes: `python scripts/fatos.py marcar --pasta saida/...`. O script imprime o bloco 🔎 do cartão.
2. Leia o texto final do corte e procure o que o script não pegou (número por extenso estranho, frase mal transcrita, afirmação forte sem número). Marque com `fatos.py adicionar --video 0 --segundo 12.4 --trecho "..." --motivo "..."`.
3. Mostre o bloco ao Well e espere. Cada ponto tem três respostas: **confirmo**, **corrijo para X**, **corta**.
4. Grave cada resposta: `fatos.py responder ID --pasta ... --status confirmado|corrigir|cortar [--nota "130 mil"]`.
5. `fatos.py pendentes --pasta ...` tem que sair sem erro antes do render do vídeo inteiro.
6. Se mexer nos cortes depois, rode `fatos.py marcar` de novo: as respostas dadas são **conservadas**.

## O que fazer com cada resposta

- **confirmo**: nada. Segue.
- **corrijo para X**: a fala diz uma coisa e o valor certo é outra. Corrija o texto da **legenda** (`legendas.json`, `--reaproveitar`) e **diga ao Well** que a fala continua com o valor errado: ofereça regravar a frase ou cortá-la. Nunca mude o que ele disse sem avisar, e nunca deixe o vídeo com legenda e fala se contradizendo sem ele saber.
- **corta**: a frase sai pelo `cortes.json` (leia `referencias/cortes.md`: cuidado para não deixar a frase vizinha sem sentido). Rode de novo o que vem depois dos cortes.

## Limites

É heurística sobre fala transcrita. Escapa o que a transcrição escreveu de um jeito que o script não reconhece e o que é afirmação sem palavra-gatilho ("a maioria dos advogados faz assim"). Por isso a etapa 2: a leitura do texto final é sua.

Na dúvida se algo é um fato, marque: custa uma pergunta ao Well.
