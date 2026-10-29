# Imagens de apoio

Imagens de uso livre que entram no vídeo como os elementos 3D: um cartão sobreposto (fora do rosto) ou a tela cheia por 1 a 3 s. A biblioteca fica em `imagens/` na raiz do projeto, com o `registro.json`.

## Regras

- **Só entra imagem registrada**, com licença aceita, origem e crédito. O `elementos.py` recusa imagem que não está no registro ou cujo arquivo mudou depois (SHA-256 diferente).
- **Só se registra o que a pessoa trouxe.** Baixar imagem da internet é com o pedido da pessoa. Nunca use imagem de busca sem origem, de cliente, ou de terceiros com direitos reservados.
- **Nada de cliente**: foto de cliente, tela com dado de cliente ou imagem de caso real não entram na biblioteca (o repositório pode ser público).
- Imagem com **pessoa reconhecível** precisa da autorização dela para uso comercial: a biblioteca avisa, e o vídeo que promove um trabalho é uso comercial. Imagem com **marca de terceiros** também avisa.

## Licenças

| Licença | Pode? | Observação |
| --- | --- | --- |
| `cc0`, `dominio-publico` | sim | sem crédito |
| `pexels`, `pixabay`, `unsplash` | sim | licenças próprias dos sites: uso comercial sem crédito, **com restrições** (não vender a imagem sem alterar, não sugerir apoio de quem aparece, cuidado com pessoas e marcas). Guarde o endereço da página em `origem` e releia a licença do site na hora de registrar |
| `cc-by` | sim, **com crédito** | o texto do crédito é obrigatório no registro e vai para o texto do post |
| `propria` | sim | foto da própria pessoa; sem origem |
| `cc-by-sa` | **não** | obriga a licenciar o vídeo inteiro igual |
| `cc-by-nc` | **não** | proíbe uso comercial |
| `cc-by-nd` | **não** | proíbe alterar, e a imagem é recortada e recebe película e rótulo |
| direitos reservados | **não** | sem licença de uso |

Essas são as regras gerais de cada licença, não aconselhamento jurídico. Na dúvida sobre uma imagem, não registre.

## Registrar

```bash
python scripts/imagens.py adicionar foto.jpg --titulo "Café na mesa" --palavras cafe,reuniao \
    --autor "Nome do autor" --licenca cc0 --origem https://pagina-da-imagem --pessoa nao --marca nao
```

- `--palavras`: o começo das palavras que chamam a imagem na fala (como em `elementos.py promover`). Poucas e específicas: uma palavra comum demais chama a imagem o tempo todo.
- `--pessoa` e `--marca`: respostas obrigatórias, `sim` ou `nao`. Olhe a imagem antes.
- A imagem é reduzida para no máximo 1920 px e guardada em `imagens/`. O arquivo que a pessoa deu não é tocado.
- `imagens.py verificar` confere tudo (arquivo, SHA-256, licença, crédito, origem) e avisa pessoas e marcas.

## Usar num vídeo

1. `imagens.py sugerir --pasta saida/...`: propõe imagens para as palavras da fala (no máximo uma a cada 6 s, nunca em cima de outro elemento). Escolha as que combinam; imagem de apoio não é enfeite: se não explica a frase, não use.
2. `imagens.py usar ID --pasta ... --inicio 12.5 --duracao 2 [--modo tela] [--texto "Seu *café* da manhã"]`. O `sobreposto` fica de 1 a 4 s; a `tela`, de 1 a 3 s. O rótulo usa `*asteriscos*` para o destaque, como nos elementos, e só leva palavras e números que a pessoa falou.
3. `elementos.py previa --pasta ...`: olhe a folha. Cartão fora do rosto, imagem legível em tamanho pequeno, nada de mau gosto.
4. Mostre à pessoa (linha 🖼️ do cartão) e espere o "ok".
5. `imagens.py creditos --pasta ...`: lista as imagens usadas, com autor, licença e origem (grava `creditos-imagens.txt`), e o crédito obrigatório (`cc-by`) que o texto do post precisa levar.

O efeito sonoro de uma imagem é o de passagem curta (`sons.json`, `por_elemento.imagem`), só se a pessoa pediu efeitos.
