# Publicidade: gancho e roteiro

Quando a pessoa diz que o vídeo é **anúncio, propaganda ou publicidade**, o gancho (o começo) decide se a pessoa continua assistindo. O fluxo muda em três pontos: a série `publicidade`, o gancho puxado de qualquer lugar do vídeo e a legenda limpa.

## Como começar

- Use a série pronta: `editar.py novo VIDEO --serie publicidade`. Ela liga o modo anúncio, deixa os elementos 3D desligados e usa a legenda sem borda escura. O cartão mostra a linha "Anúncio".
- Num trabalho que já existe: `editar.py ajustar --pasta ... --escolha publicidade=true`.

## O que o modo anúncio faz

1. Depois dos cortes, olha **todas as frases inteiras** do vídeo, inclusive a última. A frase vai até o ponto, a interrogação ou a exclamação, mesmo que tenha pausa no meio.
2. Dá uma nota a cada frase (`publicidade.py listar`): fala com a pessoa, diz para quem é, traz resultado ou prova, faz pergunta, abre sem enrolação, é curta. Desconta frase longa, frase que só se entende com a anterior ("Mas…", "Então…") e chamada para ação ("me segue", "comente", "clique"). Chamada para ação não é gancho: fica no fim.
3. Puxa a escolhida para o começo (`publicidade.py aplicar`), sem repetir a frase onde ela estava.
4. Acerta o roteiro: tira "e", "então", "aí" e "de fato" soltos no começo da frase puxada, tira a saudação solta que abria o vídeo e deixa o resto na ordem em que foi falado, com a chamada para ação no fim.

Só frases inteiras mudam de lugar, cortadas no silêncio. Nunca se inventa frase nem se junta metade de uma com metade de outra. A versão anterior fica em `cortes.anterior.json`.

## Quem escolhe

- Com a série `publicidade` ou `publicidade=true`, o `editar.py` já puxa a melhor frase sozinho (`--auto`), só se ela for pelo menos 2 pontos melhor que o começo. Esse é o piso.
- **Faça melhor com julgamento:** rode `publicidade.py listar`, leia as 5 primeiras e escolha a que prende de verdade (para quem é, o que a pessoa ganha, prova). A nota é um guia: ela pode premiar uma pergunta do meio da explicação que não serve de abertura. Aplique com `publicidade.py aplicar --unidade N`. Quando a pessoa pede anúncio, essa escolha é autorizada de antemão: não precisa de novo "ok", mas conte na entrega qual frase abriu e o que saiu do lugar.
- Depois de aplicar, rode de novo rosto, elementos, câmera e legenda. A grafia que você já corrigiu na legenda é refeita, então confira de novo.

## Legenda limpa

`legenda.borda=limpa` tira a borda escura e deixa só um brilho escuro suave e translúcido. Sem nenhum contorno a letra some em fundo claro (camisa branca, parede clara), por isso o brilho fica. Para voltar ao padrão: `legenda.borda=escura`.

## Cuidados de anúncio

- Resultado e número ditos ("20% ao mês") passam pelo portão de fatos: só a pessoa confirma.
- Regras de publicidade do setor da pessoa (por exemplo, o que um órgão de classe permite) são dela. Os `avisos_obrigatorios` do perfil continuam valendo e nunca saem no corte.
