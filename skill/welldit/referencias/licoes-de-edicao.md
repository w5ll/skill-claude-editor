# Lições de edição de outro repositório (ideias para melhorar a welldit)

Vieram de um guia de processo de edição de vídeo de uma pessoa parceira. Aqui ficam só as ideias gerais, escritas de novo com as nossas palavras. Nada de cliente, número real ou código de terceiros. Cada item é uma ideia a testar, não uma regra.

## Problemas de gravação e de corte que já apareceram lá

- **Erros e repetições escondidos pela transcrição.** O reconhecimento de fala "limpa" gaguejos e palavras repetidas. Para achar o que sobrou: transcrever de novo de forma literal (pedindo para manter "é…", "eu, eu…", sem usar o texto anterior como contexto) e medir o volume a cada 20 a 50 ms para achar as pausas entre palavras.
- **Tempos das palavras atrasam cerca de 0,2 s.** Cortar sempre no silêncio entre palavras, nunca no tempo bruto.
- **Conferir cada emenda** transcrevendo só o trecho emendado, para ver se alguma palavra foi cortada.
- **Falso começo de palavra repetida** ("essa… essa lista"): cortar o começo falso e manter a versão certa inteira. Nunca cortar a última palavra do vídeo: deixar cerca de 0,25 s depois dela.
- **Respirações a partir de 0,25 s** podem reprovar numa conferência rígida. Deixar cerca de 0,12 s.

## Imagem e som

- **Gravação do celular em HDR** (com duas faixas de áudio) trava algumas ferramentas. Preparar uma cópia com cor padrão (BT.709), quadros por segundo exatos e só a faixa de áudio normal. Dica para quem grava: desligar o HDR no celular.
- A conversão automática de HDR pode deixar a imagem **amarelada**. Se a pessoa preferir a cor igual à do original, reinterpretar a cor em vez de converter.
- **Pico de áudio:** o normalizador de volume pode errar o pico em cerca de 0,8 dB. Um limitador no fim da cadeia resolve (já adicionado em `renderizar.py`).
- **Duração depois do áudio comprimido:** o áudio pode sobrar alguns centésimos de segundo e reprovar uma checagem de duração exata. Ajustar o corte em quadros inteiros.

## Legenda e cenas

- Falas rápidas estouram a largura com 2 ou 3 palavras por vez. Se acontecer, usar 1 palavra por vez (ou 2 curtas, com no máximo cerca de 17 letras).
- Respeitar a **área segura** nas laterais (por volta de 13% de cada lado) para legendas e cenas, e conferir com leitura do texto na imagem.
- Texto das cenas fora da faixa do rosto; títulos no alto, destaques embaixo.
- **Cena que cobre a gravação** (por exemplo, refazer uma tela cortada) pede a aprovação visual da pessoa com o vídeo completo.
- Elementos só quando ligados ao que foi falado. Elemento sem relação com a fala (como um ponto de interrogação solto) foi rejeitado.

## Processo

- **Prévia curta antes do vídeo inteiro**, conferindo a imagem em cada corte da prévia.
- **Revisor crítico:** um segundo olhar (outro agente) vê a prévia e o pedido e devolve um veredito e as 5 primeiras correções, em no máximo 3 rodadas de correção, antes de mostrar à pessoa.
- **Todo retorno que vale para os próximos vídeos vira regra do perfil**, numa seção "Aprendizados" com data. Hoje a welldit guarda o perfil de marca; falta um lugar para esses aprendizados.
- **Variações de gancho:** o mesmo corpo aprovado com várias aberturas diferentes, gerando um vídeo por abertura, com conferência de duração, emenda e volume em cada um. Uma gravação com várias aberturas pode ser dividida em uma por abertura.
- **Nome de arquivo de entrega** num padrão fixo (marca, tema, gancho, formato) para facilitar o gerenciador de anúncios.
- **Limpeza depois de exportar:** ferramentas de desenho de cenas deixam muitos gigabytes em pastas temporárias. Apagar depois da entrega.
- **Roteiro duplo:** um roteiro da fala e outro do que aparece na tela em cada fala; nomes e números ditos viram elementos.
- Não transcrever o mesmo bruto duas vezes.

## O que ficou de fora de propósito

- Regras, cores, nomes de arquivo e registros de trabalho de clientes reais.
- A transcrição e a análise de um vídeo de terceiros usado como método de origem.
- Um repositório citado no guia que não tem licença: não se copia código dele.
- Caminhos e preferências pessoais da máquina de quem escreveu o guia.
