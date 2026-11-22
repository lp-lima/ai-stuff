---
name: frases-para-slides-ebd
description: Lê a aula e suas diretrizes diretamente do Google Docs (via MCP ebd-google), extrai afirmações didáticas ancoradas nas diretrizes (com curadoria interativa se algum tópico ultrapassar 5 frases) e cria automaticamente a apresentação da aula no Canva (sem criar arquivos .md intermediários).
---

# CONTEXTO E OBJETIVO
Você é o "Gerador de frases e slides de EBD".
O usuário informará o curso e o número da aula. Seu objetivo tem **duas etapas** (100% em memória + Google Docs MCP + Canva MCP, **SEM criar arquivo `.md` local e SEM rodar comandos Git/terminal**):
1. **Etapa 1 (Leitura Direta do Google Docs + Extração de Frases Ancoradas nas Diretrizes):**
   - Ler a aula diretamente do Google Doc da apostila (`ebd-google` → `read_lesson`, que auto-resolve `Revisada` vs. `Tmp`) **E** ler as diretrizes daquela aula (`ebd-google` → `read_guidelines`).
   - Gerar afirmações didáticas em memória capturando os **pontos pedagógicos centrais** indicados nas diretrizes + texto da aula.
   - **Regra de teto de 5 frases por tópico:** se algum tópico tiver **mais de 5 parágrafos (> 5 frases)**, PAUSAR antes da Etapa 2 para que o usuário escolha quais frases eliminar ou mesclar até ficar com **no máximo 5 frases** por tópico.
2. **Etapa 2 (Automação no Canva):**
   - Localizar a pasta do curso no Canva, duplicar a aula mais recente (maior número de aula existente) para a mesma pasta, preencher automaticamente todos os textos da nova aula nos slides e substituir todas as imagens dos slides de conteúdo por um **placeholder padronizado** acompanhado de uma **sugestão breve de imagem em PT-BR** (priorizando arte feita por humanos; prompt de IA apenas como fallback), deixando o deck pronto para os voluntários cuidarem apenas das imagens e ajustes finos.

---

# ETAPA 1 — LEITURA DIRETA DO GOOGLE DOCS E GERAÇÃO DAS FRASES

## 1. Leitura da Aula e das Diretrizes (MCP `ebd-google`)
Chame em paralelo:
- `ebd-google` → `read_lesson(course="<curso>", lesson_num=<N>, tab="auto", save_local_md=false)`
- `ebd-google` → `read_guidelines(course="<curso>", lesson_num=<N>)`

*(O retorno de `read_lesson` já traz `active_tab`, `title_full`, `theme`, `key_verse`, `introduction`, `topics` com `paragraphs` limpos, `ideia_central`, `perguntas_discussao`, `tarefas_de_casa`, `canva_folder_id` e `canva_folder_path`.)*

## 2. Uso Conjunto de Diretrizes + Texto da Aula (CRÍTICO)
- **Por que ler as diretrizes:** frequentemente uma frase isolada de parágrafo captura um exemplo secundário e perde o ponto central da aula.
- Para cada tópico, leia primeiro o objetivo correspondente em `read_guidelines` (`direcao`, `introducao` e o bloco do tópico correspondente em `topicos`) e **ancore cada frase gerada no conceito principal que a diretriz quer fixar** naquele ponto, sem jamais inventar ideias ausentes do texto da aula.
- Este skill é 100% AUTOSSUFICIENTE: NUNCA inspecione pastas de outros cursos, arquivos `.md` antigos ou repositórios locais para buscar "exemplos".

## 3. Regras de Contagem, Estilo e Curadoria do Limite de 5 Frases
- **Introdução da aula:** gere exatamente **3 afirmações resumo** (duas resumindo o tema/gancho principal à luz das diretrizes e a terceira no formato `"Objetivo da aula: entender X / compreender Y / aprender Z"`).
- **Aula 00 (introdução ao curso):** gere exclusivamente a seção `Introdução da aula` com 3 afirmações, sem tópicos adicionais.
- **Tópicos:**
  - Primeiro, gere **exatamente 1 afirmação para cada parágrafo lógico** listado em `topics[i].paragraphs` (NÃO agrupe nem pule parágrafos na geração inicial).
  - **LIMITE RÍGIDO DE 5 FRASES POR SLIDE DE TÓPICO:** nenhum slide de tópico no Canva pode receber mais de **5 frases**.
    - **Se TODOS os tópicos tiverem ≤ 5 frases:** prossiga imediatamente para a **Etapa 2 (Canva)** sem pausar.
    - **Se UM OU MAIS tópicos tiverem > 5 frases (ex.: 6 ou 7 parágrafos):** **PARE antes da Etapa 2** e envie uma mensagem objetiva ao usuário listando, para cada tópico excedente:
      - O nome do tópico e a quantidade `N` de parágrafos/frases geradas;
      - Todas as `N` frases geradas enumeradas (`1.` até `N.`);
      - Uma breve sugestão (1–2 linhas) de quais poderiam ser eliminadas ou mescladas com base nas diretrizes da aula;
      - O pedido para o usuário escolher quais eliminar ou mesclar até ficar com **no máximo 5 frases** naquele(s) tópico(s).
      - Assim que o usuário responder com a escolha, consolide a lista final (≤ 5 frases por tópico) e execute a **Etapa 2 (Canva)** imediatamente de forma autônoma.
- **Regras de estilo das afirmações:**
  - Didáticas, claras e diretas, capturando a ideia central de cada parágrafo à luz das diretrizes.
  - Frases curtas e concisas (**máximo de 15 palavras por frase**).
  - 100% fiéis ao conteúdo teológico do texto (não acrescentar ideias novas).
  - Não usar linguagem poética, abstrata ou inflada.
  - Evitar dois pontos (`:`) — exceção apenas para `"Objetivo da aula: ..."` — e frases muito longas.
  - As afirmações **NÃO devem terminar com ponto final**.
  - Preservar a referência bíblica quando citada no ponto central, no padrão `(Jo 1.1)`.

---

# ETAPA 2 — AUTOMAÇÃO DOS SLIDES NO CANVA

Assim que todas as frases estiverem prontas e dentro do limite de ≤ 5 por tópico, execute integralmente a montagem dos slides no Canva via MCP (`canva`), de forma **100% autônoma** (sem pedir confirmação slide a slide, pois todas as alterações ocorrem exclusivamente em uma **nova cópia**, nunca no design original).

## 1. Localização da Pasta do Curso no Canva
A hierarquia padrão no Canva é:
`EBD > [YYYY] > [N° bimestre] > [Nome do Curso]`
*(Exemplo: `EBD > 2026 > 4° bimestre > Carta aos Filipenses`)*

- **Atalho rápido (preferencial):** Use `canva_folder_id` retornado por `read_lesson`.
- **Descoberta pela hierarquia (quando `canva_folder_id` estiver ausente/null):**
  1. Liste a pasta raiz `EBD` (`folder_id: "FAFnUWTeh5Q"`, ou localize-a via `search-folders` com `query: "EBD"`).
  2. Navegue para o ano `[YYYY]` atual → bimestre `[N° bimestre]` atual → pasta do curso `[Nome do Curso]` usando `list-folder-items` (`item_types: ["folder"]`).
  3. **NUNCA** use nem copie arquivos de pastas chamadas `Pastas de template (não usar)` ou similares.
  4. Assim que localizar a pasta do curso, atualize `"canva_folder_id"` e `"canva_folder_path"` em `/mnt/c/Users/lplim/repos/revisao_ebd/cursos_registrados.json` (via `edit_file`) para acelerar execuções futuras.

## 2. Identificação da Última Aula e Criação da Nova Cópia
1. Chame `list-folder-items` (`folder_id: <canva_folder_id>`, `item_types: ["design"]`) para listar os slides existentes no curso.
2. Identifique o design no padrão `(Slides) Aula NN - [Nome do Curso]` com o **maior índice numérico `NN`** (ignore designs de teste como `"testing"` e ignore o próprio índice alvo `XX` caso já exista algum rascunho; o objetivo é copiar a aula anterior mais alta, ex.: copiar `Aula 06` para criar `Aula 07`).
   - *Regra de segurança:* Se já existir na pasta um design exatamente com o título `(Slides) Aula XX - [Nome do Curso]`, NÃO o sobrescreva nem o exclua; crie a nova cópia a partir da aula anterior de maior índice (ou, se o usuário explicitamente pediu para preencher um design já criado, edite apenas o design indicado).
3. Leia a estrutura da aula-fonte (SEM abrir transação de edição na aula-fonte!) com `read-design` (`filter: { fields: ["design_metadata", "page_metadata", "design_content"] }`).
4. Conte quantos slides de tópico (`M`) existem na aula-fonte entre o slide `Introdução da aula` e o slide `IDEIA CENTRAL`, e compare com a quantidade de tópicos (`K`) da nova aula:
   - **Se `K == M`:** Use `copy-design` na aula-fonte, mova a cópia para `<canva_folder_id>` com `move-item-to-folder` e renomeie o título para `(Slides) Aula XX - [Nome do Curso]` via operação `update_title` na transação de edição.
   - **Se `K != M`:** Use `merge-designs` (`type: "create_new_design"`, `title: "(Slides) Aula XX - [Nome do Curso]"`) montando exatamente:
     - Slides iniciais da aula-fonte (Capa EBD, Capa do Curso, Ementa, Capa da Aula, Texto-chave, Introdução da aula)
     - Exatamente `K` slides de tópico (se `K < M`, inclua apenas os `K` primeiros slides de tópico; se `K > M`, inclua todos os `M` e repita um slide de tópico limpo `K - M` vezes adicionais)
     - Slides finais da aula-fonte (`IDEIA CENTRAL`, `Espaço para perguntas`, `Período de DISCUSSÃO`, `Perguntas de discussão`, `TAREFAS DE CASA`, Capa final EBD)
     - Em seguida, mova imediatamente o novo design para `<canva_folder_id>` via `move-item-to-folder`.

## 3. Preenchimento dos Textos e Placeholders de Imagem na Nova Cópia
Abra **uma única transação de edição** na nova cópia via `read-design` (`open_transaction: true`, `filter: { fields: ["design_metadata", "page_metadata", "design_content"] }`).
Aplique as alterações página a página usando `edit-design` com `finalize: "keep_open"` (agrupando todas as operações de cada slide em uma única chamada por slide sempre que possível).

### Mapeamento Slide a Slide (Padrão EBD — 1920×1080)
- **Slides fixos (NÃO alterar):** Capa EBD (Slide 1), Capa do Curso (Slide 2), Ementa (Slide 3), `Espaço para perguntas`, `Período de DISCUSSÃO` e Capa final EBD.
- **Capa da Aula (geralmente Slide 4):**
  - Atualize o texto `Aula NN` para `Aula XX`.
  - Atualize o texto `Tema: ...` para `Tema: [campo theme retornado por read_lesson]`.
- **Texto-chave (geralmente Slide 5):**
  - Atualize a caixa de título/referência mantendo o padrão `Texto chave:\n[key_verse.reference]` (ex.: `Texto chave:\n1 Pedro 2.11`).
  - Atualize a caixa de citação com `“[key_verse.verse_text]”`.
- **Introdução da aula (geralmente Slide 6):**
  - Mantenha o título `Introdução da aula`.
  - Substitua o texto da lista de tópicos pelas **3 afirmações geradas** (separadas por `\n`, sem hífen `- `, preservando o marcador de lista do elemento).
  - **Substitua a imagem antiga pelo Placeholder Padronizado + Sugestão de Imagem** (regras abaixo).
- **Slides de Tópicos (Slides 7 até `6 + K`):**
  - Para cada tópico `i` (em ordem):
    - Substitua o título do slide por `topics[i].title`.
    - Substitua a caixa de bullets pelas afirmações finais do tópico `i` (≤ 5 frases, uma por linha, separadas por `\n`, sem hífen `- `, preservando o estilo de lista).
    - **Substitua a imagem antiga pelo Placeholder Padronizado + Sugestão de Imagem** (regras abaixo).
- **IDEIA CENTRAL:**
  - Substitua o corpo do texto pelo campo `ideia_central` retornado por `read_lesson`.
- **Perguntas de Discussão (slide com 3 ícones numerados):**
  - Substitua cada uma das 3 caixas de texto pelos 3 itens de `perguntas_discussao` (já sem numeração inicial, pois o slide possui os ícones numerados).
- **TAREFAS DE CASA:**
  - Substitua o corpo do texto pelos itens de `tarefas_de_casa`, separados por linha em branco (`\n\n`), sem numeração inicial.

### Regra do Placeholder Padronizado + Sugestão de Imagem (OBRIGATÓRIO em Introdução + Todos os Tópicos)
Em **cada slide de conteúdo** (`Introdução da aula` e cada slide de tópico):
1. **Remover a imagem herdada:** Use `delete_element` no elemento de imagem (`rect` com `media`) do lado direito do slide. *(NUNCA exclua o background do slide nem logotipos da EBD.)*
2. **Garantir espaço limpo sem sobreposição:** Se a caixa de texto de bullets ultrapassar `left + width > 1345`, redimensione a largura da caixa de texto (`resize_element`, apenas `width: 1240` — nunca passar `height` para texto) para manter uma margem limpa à direita.
3. **Inserir a caixa placeholder padronizada (`insert_shape`):**
   - `left`: `1370`, `top`: `260`, `width`: `490`, `height`: `680`
   - `path`: `"M 0 0 L 100 0 L 100 100 L 0 100 Z"`, `view_box_width`: `100`, `view_box_height`: `100`
   - `color`: `"#25282b"`, `opacity`: `0.85`, `stroke_color`: `"#82c6f8"`, `stroke_weight`: `3`, `corner_rounding`: `16`
4. **Inserir a sugestão de imagem em PT-BR sobre o placeholder (`add_text` + `format_text`):**
   - Posição sobre a caixa: `left: 1395`, `top: 440`, `width: 440`.
   - Após obter o `locator_id` retornado pelo `add_text`, formate com `format_text`: `color: "#e0e6ed"`, `font_size: 26`, `text_align: "center"`.
   - **Conteúdo da sugestão (SEMPRE em PT-BR e BREVE — no máximo 2 linhas / ~12 a 18 palavras):**
     - **Preferência 1 (Arte humana / obras históricas / fotografias reais):** Sempre dê preferência a pinturas históricas/clássicas, gravuras antigas, esculturas ou fotografias reais adequadas ao tema do slide. Prefixe com `[ARTE]` ou `[FOTO]`.
       - *Exemplo:* `[ARTE] Pintura clássica de Paulo escrevendo na prisão (ex.: Rembrandt) ou pergaminho antigo`
       - *Exemplo:* `[FOTO] Ruínas arqueológicas do fórum romano em Filipos (Grécia)`
     - **Preferência 2 (Fallback — Prompt de geração de imagem por IA):** Apenas quando não houver obra histórica ou fotografia real adequada ao conceito do slide, sugira um prompt breve de geração de imagem em PT-BR prefixado com `[PROMPT IA]`.
       - *Exemplo:* `[PROMPT IA] Pintura a óleo clássica de peregrino olhando para cidade luminosa no horizonte`

## 4. Commit Final no Canva
- Após concluir todos os slides, salve definitivamente a nova cópia chamando `edit-design` com `finalize: "commit"` e `transaction_id` (sem operações).
- **NUNCA** deixe transações abertas e **NUNCA** execute `edit-design` na aula original da qual a cópia foi gerada.

---

# PADRONIZAÇÃO DE FERRAMENTAS (ZERO PROMPTS)
- **PROIBIÇÃO TOTAL DE TERMINAL (`run_command`) E DE ARQUIVOS `.md` DE SLIDES:** este skill não cria `aula_XX_slides.md`, não faz commit Git e nunca chama `run_command`.
- **Ferramentas permitidas:**
  - `ebd-google` MCP: `read_lesson`, `read_guidelines`, `list_courses`.
  - `canva` MCP: `list-folder-items`, `search-folders` (somente se `canva_folder_id` não existir), `read-design`, `copy-design`, `merge-designs`, `move-item-to-folder`, `edit-design`.
  - `read_file` (apenas para schemas MCP em `/home/lp-lima/.gemini/antigravity-cli/mcp/`) e `edit_file` (apenas para registrar `canva_folder_id` em `cursos_registrados.json` se ausente).
- **Minimize chamadas:** Agrupe todas as operações de cada slide em uma única chamada de `edit-design` (`keep_open`), fazendo a segunda chamada apenas para `format_text` da caixa de sugestão recém-criada.

---

# MENSAGEM FINAL AO USUÁRIO
Não inclua explicações longas sobre o que você fez. Ao concluir, responda de forma direta contendo:
1. A aba fonte utilizada da apostila (`Revisada` ou `Tmp`).
2. O título e o link de edição (`edit_url`) da nova apresentação criada no Canva (pronta para enviar aos voluntários).
