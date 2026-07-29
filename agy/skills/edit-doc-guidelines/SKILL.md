---
name: edit-doc-guidelines
description: Edita uma apostila em formato .docx utilizando um arquivo .md de diretrizes como fonte de verdade, inserindo textos fielmente e buscando versículos na versão NVI.
---

# Editar Apostila (.docx) Baseada em Diretrizes

Esta skill instrui o agente a atuar como um editor de texto preciso e técnico, atualizando um arquivo `.docx` de apostila (considerado o arquivo "Original") usando o conteúdo de um arquivo `.md` (as "Diretrizes") como fonte única de verdade.

## Pré-requisitos
- O usuário deve fornecer o documento `.docx` a ser editado.
- O usuário deve fornecer o documento `.md` com as diretrizes de cada aula.
- Caso o usuário especifique apenas algumas aulas (ex: "apenas aulas 07 e 08"), execute o processo somente para elas.
- Você pode usar a biblioteca `python-docx` para realizar as substituições programaticamente, mantendo o arquivo `.docx` formatado.

## Regras Estritas de Execução

1. **Verbatim (Cópia fiel):** Todo conteúdo extraído das diretrizes deve ser copiado literalmente. Não resuma, não parafraseie e não altere o tom do texto original.
2. **Proibição de Tradução:** O idioma de trabalho é exclusivamente Português do Brasil. É proibida qualquer tradução para inglês ou qualquer outro idioma. Se o texto de destino contiver um texto de preenchimento (como 'Lorem ipsum'), ele deve ser integralmente substituído pelo conteúdo das diretrizes.
3. **Padrão de Formatação:** Todas as seções de conteúdo extraídas das diretrizes devem começar estritamente com `(DIRETRIZES: ` e terminar com `)`.
   *Exemplo correto:* `(DIRETRIZES: O texto extraído da ementa vai aqui sem modificações.)`
4. **Referências Bíblicas:**
   - Sob o título de cada aula e na terceira tarefa de casa, substitua o termo 'Referência' ou 'referência' pelo endereço do versículo-chave indicado nas diretrizes (ex: '2 Timóteo 3.16').
   - Onde houver o marcador 'conteúdo do versículo na versão NVI', substitua pelo texto bíblico completo, especificamente na versão NVI 2011. Pesquise a NVI 2011 na internet usando as ferramentas disponíveis para garantir a versão exata do versículo.
5. **Abrangência:** A menos que o usuário solicite aulas específicas, processe as aulas indicadas integralmente. IGNORE a introdução ao curso ou outras seções que não sejam aulas enumeradas.
6. **Integridade:** Não adicione comentários, explicações ou preâmbulos no texto final. Não reescreva o texto em nenhum sentido. O documento deve ser entregue pronto, substituindo todos os placeholders originais pelo conteúdo exato da fonte da verdade. **NÃO modifique a formatação** de nenhuma seção do documento (para isso, ao alterar o `.docx` usando python, modifique o texto apenas do elemento `run` do parágrafo, ou cuide para manter a formatação inalterada caso reescreva o parágrafo).

## Processo (Passo a passo por aula)

Para cada aula solicitada, realize os seguintes passos no `.docx`:

1. Atualize o título da aula e dos tópicos conforme estabelecido nas diretrizes.
2. Insira o versículo-chave e o texto bíblico pesquisado na NVI 2011 no local indicado.
3. Preencha a seção de Introdução da aula com o conteúdo logo após o texto-chave nas diretrizes, adotando o formato `(DIRETRIZES: [Texto das diretrizes])`.
4. Substitua o título de cada seção (tópicos 1, 2, 3, etc.) pelo título correspondente do documento de diretrizes, mantendo a formatação intacta.
5. Preencha cada bloco de conteúdo (a porção do texto marcada como “Corpo do tópico” ou similar) aplicando a formatação obrigatória: `(DIRETRIZES: [Texto das diretrizes])`.
6. Substitua a referência do versículo-chave na pergunta 3 das tarefas de casa (onde diz "Memorize o versículo-chave: referência").
