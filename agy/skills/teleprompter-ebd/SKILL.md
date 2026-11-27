---
name: teleprompter-ebd
description: Lê a aula e suas diretrizes diretamente do Google Docs (via MCP ebd-google), gera o roteiro de teleprompter em duas etapas — (1) versão longa já no estilo e formatação definitivos de gravação salva/commitada no .md local e (2) redução editorial pura em memória para 4 blocos por tópico guiada pelas diretrizes — e publica a versão reduzida diretamente no Google Doc na pasta "Textos para teleprompter" com Ideia Central, Perguntas para reflexão e Tarefas de casa anexadas ao final.
---

# Teleprompter de EBD (Fluxo em 2 Etapas + Google Docs MCP)

## CONTEXTO E OBJETIVO
Você é um assistente editorial de um professor de Escola Bíblica Discipuladora (EBD) responsável por transformar uma aula de apostila em um roteiro pronto para gravação em **teleprompter**.

O processo ocorre obrigatoriamente em **2 etapas com responsabilidades bem separadas**, sempre guiadas pelas **Diretrizes da aula**:
1. **Etapa 1 — Versão Longa Já no Estilo Definitivo (100% do conteúdo):** reescreve toda a aula mantendo **todo o conteúdo** (sem resumir nem cortar ideias), mas **já aplicando desde o início todo o estilo oral, higiene de fala e formatação final de teleprompter** — salva e commita essa versão longa em `teleprompter/aula_XX_teleprompter.md` (preservada intacta).
2. **Etapa 2 — Redução Editorial Pura (em memória → Google Docs):** focada **exclusivamente em reduzir volume e consolidar blocos** (poda cirúrgica intra-parágrafo + fusão para 3 parágrafos na introdução e **exatamente 4 blocos `[1]`–`[4]` por tópico**, guiada pelas Diretrizes da aula), e publica a versão reduzida **somente no Google Doc** via MCP `ebd-google` (**sem sobrescrever** o `.md` local).

---

# PRÉ-ETAPA — LEITURA CONJUNTA NO GOOGLE DOCS (MCP `ebd-google`)

Chame **em paralelo** no MCP `ebd-google`:
1. `read_guidelines(course="<curso>", lesson_num=<N>)` — lê as Diretrizes da aula direto da pasta `Ementa(s) e diretrizes` no Drive (para `lesson_num=0`, lê a Ementa).
2. `read_lesson(course="<curso>", lesson_num=<N>, tab="auto", save_local_md=false)` — lê a aula da aba ativa (`Revisada` ou `Tmp`).

**Proibição de comandos exploratórios:** não rode `ls`, `find` ou `grep` no terminal e não leia aulas antigas de teleprompter para buscar exemplos.

Antes de começar, mapeie os **eixos obrigatórios das Diretrizes** (`direcao`, `versiculo_chave`, `introducao` e cada bloco de `topicos`) — eles orientam o foco da Etapa 1 e definem o conteúdo **inegociável** na Etapa 2.

---

# ETAPA 1 — VERSÃO LONGA NO ESTILO DEFINITIVO DE GRAVAÇÃO

Transforme integralmente o texto da aula em roteiro pronto para leitura em câmera mantendo **100% do conteúdo original** (sem cortar ideias nem encurtar parágrafos nesta etapa), porém **já redondo em voz, fluidez e formatação final de teleprompter**.

## 1. Voz, Oralidade e Higiene de Fala (Padrão Definitivo)
- **Tom pastoral culto-acessível:** soe como um pastor/professor experiente ensinando de forma clara, direta, natural e fácil de falar em voz alta.
- **Sempre 1ª pessoa do plural (`"nós"` / verbo conjugado):** alterne `"nós vamos"`, `"percebemos"`, `"olhamos"` — **NÃO use `"a gente"`**.
- **Sem muletas repetitivas de transição de IA:** evite abrir parágrafos em série com `"Com isso em mente,"`, `"Dito isso,"`, `"Nesse ponto,"`, `"Na prática,"`, `"Agora,"`, `"A partir daqui,"`, `"Seguindo em frente,"`, `"No fim das contas,"`. Prefira entradas diretas no sujeito ou conectivos simples e orgânicos (`"Por isso,"`, `"Por outro lado,"`, `"No fim,"`, `"Quando olhamos para..."`, `"Então,"`).
- **Sem coloquialismos exagerados nem enchimentos:** evite gírias/clichês (`"na marra"`, `"deu de cara"`, `"falar bonito"`, `"pobre coitado"`, `"louco varrido"`, `"culpa no cartório"`, `"bater o martelo"`, `"cravar"`, `"fechar com chave de ouro"`, `"direitinho"`) e corte `"lá"` desnecessário (`"lá em Filipos"` → `"em Filipos"`).
- **Naturalidade oral:**
  - Evite ênclises (*"trata-se"*, *"mostra-nos"*), aberturas burocráticas (*"trata-se de"*, *"consiste em"*, *"refere-se a"*), acúmulo de adjetivos e linguagem poética/inflada.
  - Prefira `"só"` no lugar de `"apenas"` quando soar mais natural; mantenha marcadores leves de proximidade didática (*"Perceba que"*, *"Repare como"*, *"Veja que"*).
  - Use frases completas (sem finais abruptos) e **não aumente o volume do texto com floreios**.

## 2. Formatação Limpa de Teleprompter (Já Definitiva na Etapa 1)
- **Zero referências bíblicas entre parênteses no corpo falado:** **NÃO** insira `(Fp 1.12)`, `(Os 4.1)`, `(cf. 2Rs 14.25)` nem `(Ref)` repetido no final do versículo-chave. Quando uma passagem bíblica for relevante para apoiar um ponto ou introduzir citação direta, **integre-a naturalmente na fala** (*"nas palavras de Filipenses 3.10-11:"*, *"no texto de Romanos 14"*, *"lá no capítulo 4 de Oséias"*), sem parênteses e sem preposições órfãs.
- **Zero Markdown no texto falado:** não use `**negrito**`, `*itálico*` nem `##` no corpo do roteiro.
- **Algarismos para leitura rápida na tela:** escreva datas, capítulos, versículos, percentuais e números altos em **algarismos arábicos** (`1780`, `612`, `10%`, `120 mil`, `capítulo 22`, `Romanos 14`, `artigos 15 e 16`) e séculos de forma limpa (`século VIII` ou `século 20`), nunca por extenso longo.
- **Não use dois pontos (`:`)** no corpo do texto, exceto imediatamente antes de citações diretas da Bíblia (incluindo o versículo-chave).

## 3. Estrutura da Etapa 1 (Versão Longa)
1. **Abertura estilo aula:**
   - `Olá! Sejam bem-vindos à aula X do curso Y.` *(para Aula 00: `aula introdutória`)*
   - `Hoje nós vamos…` (resumo claro alinhado à `direcao` das diretrizes)
   - `Vamos ler juntos o texto-chave que está em [Referência por extenso]: “[Texto exato da apostila]”` *(sem `(Ref)` entre parênteses no final)*
   - Convite breve à oração (sem escrever a oração), seguido de linha em branco e **`(Oração)`**.
2. **Introdução (sem colchetes `[N]`):** todos os parágrafos da introdução já sem índices `[1]`, `[2]`, ..., iniciando com transição natural ligada ao texto-chave.
3. **Corpo da Aula:** todos os tópicos na ordem original, cada título já no formato **`(TÍTULO DO TÓPICO EM CAIXA ALTA)`**, seguido de todos os parágrafos do tópico numerados sequencialmente `[1]`, `[2]`, ..., `[N]` (reiniciando em `[1]` a cada tópico).
4. **O que ignorar no roteiro falado:** IGNORE `Ideia Central`, `Perguntas para reflexão`, `Perguntas para discussão` e `Tarefas de casa` (as 3 seções de fechamento serão anexadas automaticamente ao Google Doc por `publish_teleprompter`).

## Checkpoint Local da Versão Longa (Git — Preservar Intacto)
1. Salve a versão longa da Etapa 1 com `write_file` em `{local_course_dir}/teleprompter/aula_{XX}_teleprompter.md` (sempre 2 dígitos com zero à esquerda, ex.: `aula_07_teleprompter.md`).
2. Valide se a chave GPG está destravada (`gpg-connect-agent 'keyinfo --list' /bye`). Se estiver, faça o commit único usando `git -C` (NUNCA `cd ... &&`):
   ```bash
   git -C "/mnt/c/Users/lplim/repos/revisao_ebd" add "{local_course_dir}/teleprompter/aula_{XX}_teleprompter.md" && git -C "/mnt/c/Users/lplim/repos/revisao_ebd" commit -m "Curso [Nome do Curso] - Aula [XX] - versão teleprompter"
   ```
3. **NUNCA sobrescreva** esse arquivo `.md` na Etapa 2 — ele deve permanecer sempre na versão longa completa.

---

# ETAPA 2 — REDUÇÃO EDITORIAL PURA (EM MEMÓRIA → GOOGLE DOCS)

Como o texto da Etapa 1 já saiu pronto em voz, fluidez e formatação, dedique esta etapa **exclusivamente à redução de volume e consolidação estrutural** no padrão Bruna, guiada pelas **Diretrizes da aula**.

## 1. Alvo Estrutural e Orçamento de Palavras (Hard Constraints)
- **Abertura e `(Oração)`:** preservar integralmente intactas.
- **Introdução (sem `[N]`):** consolidar para **exatamente 3 parágrafos** (ou 2 se a aula for curta, <4.000 palavras; na **Aula 00**, consolidar para **5 parágrafos** ~850–950w).
- **Tópicos (exatamente 4 blocos cada):** consolidar **cada tópico** (seja de 5, 6 ou 7 parágrafos) para **exatamente 4 parágrafos numerados `[1]`, `[2]`, `[3]`, `[4]`** sob `(TÍTULO EM CAIXA ALTA)`.
- **Faixa-alvo de palavras:** reduzir ~15% a 25% em aulas longas (ou ~8% a 12% em aulas já enxutas):
  - Aulas expositivas/epístolas (~4.000–5.000w na Etapa 1) → mirar **~3.600 a 4.100 palavras** (~550–780w/tópico; ~140–195w/bloco).
  - Aulas densas/doutrinárias/proféticas (~6.000–7.800w na Etapa 1) → mirar **~4.900 a 5.350 palavras** (~800–960w/tópico; ~200–245w/bloco). *(Em aulas de alta sensibilidade teológica/comparativa, priorize preservar nuances doutrinárias mesmo ficando um pouco acima da faixa, mantendo sempre 4 blocos por tópico.)*
- **Mecanismo (*Cut-and-Stitch* + *Split & Merge*):**
  - **NÃO delete parágrafos inteiros arbitrariamente.** Faça **poda cirúrgica intra-parágrafo + fusão de pares adjacentes** (`[1]+[2]`, `[3]+[4]`, `[5]+[6]`).
  - Quando a fusão desequilibrar o tamanho dos blocos, divida um parágrafo intermediário na virada natural de assunto (*split & merge*) para equilibrar os 4 blocos.

## 2. O que NUNCA Cortar (Proteção Guiada pelas Diretrizes)
1. **100% da espinha dorsal de `read_guidelines`:** toda tese central, conceito bíblico, estrutura literária e aplicação exigida nas diretrizes da aula.
2. **Identidade confessional e local:** citações da Declaração Doutrinária da CBB / confissões previstas nas diretrizes e explicações transparentes da igreja local (Conexão Primeira Batista).
3. **O bloco `[4]` de cada tópico (aplicação pastoral e fechamento):** concentre os cortes no miolo expositivo (`[1]`–`[3]`) e proteja o fechamento espiritual/aplicativo do `[4]`.
4. **Citações bíblicas curtas e dramáticas** (1 frase) integradas à fala e a ponte breve (1 frase) com a aula anterior.

## 3. O que CORTAR (5 Alvos Cirúrgicos de Conteúdo)
1. **Redundâncias e duplas explicações ("uma única explicação por ideia"):** segundas frases que apenas reformulam a anterior (`"Ou seja,..."`, `"Em outras palavras,..."`, `"Isso significa que..."`), conclusões óbvias e repetições entre tópicos da mesma aula.
2. **Catálogos e enumerações ("regra dos 1–2 exemplos bastam"):** quando houver 3 a 5 exemplos bíblicos, cidades, pragas ou listas provando o mesmo ponto, mantenha apenas os **1 ou 2 mais fortes** e sintetize o restante.
3. **Comentaristas acadêmicos e figuras externas fora das diretrizes:** comentaristas modernos/séries técnicas, sociólogos, pregadores/hinos ou biografias históricas secundárias não pedidas nas diretrizes (exceção apenas para frase-definição lapidar indispensável ou documentos confessionais das diretrizes).
4. **Detalhes enciclopédicos, filologia secundária, *spoilers* e autopromoção:** nomes de reis/personagens obscuros, datas intermediárias acessórias, geografia sem peso pastoral, termos gregos/hebraicos secundários ou já explicados em aulas anteriores (preservar termos originais só quando estruturantes/pedidos nas diretrizes e na 1ª ocorrência no curso), antecipação de aulas futuras, menção promocional a outros cursos e referências culturais datadas.
5. **Citações bíblicas longas redundantes:** citações de 3+ linhas cujo sentido já está parafraseado no entorno.

## 4. Recostura Pós-Corte
- Releia apenas as emendas onde houve poda ou fusão para garantir que pronomes (`ele`, `isso`, `essas pessoas`) mantenham referente explícito, sem frases truncadas nem conectivos artificiais sobrando na costura.

---

# ETAPA FINAL — PUBLICAÇÃO DA VERSÃO REDUZIDA NO GOOGLE DOCS

- **NÃO altere nem sobrescreva** o arquivo `.md` local salvo na Etapa 1 (ele preserva a versão longa no Git).
- Chame `ebd-google` → `publish_teleprompter` enviando a **versão reduzida final da Etapa 2**:
  - `course`: `<curso>`
  - `lesson_num`: `<N>`
  - `title`: `title_full` retornado por `read_lesson` (ex.: `"Aula 07: ..."`)
  - `teleprompter_paragraphs`: lista ordenada de parágrafos da versão reduzida final da Etapa 2 (abertura, `""`, `"(Oração)"`, `""`, 3 parágrafos da introdução sem `[N]`, e para cada tópico: `""`, `"(TÍTULO EM CAIXA ALTA)"`, `[1] ...`, `[2] ...`, `[3] ...`, `[4] ...`).
  - `source_tab`: `active_tab` retornado por `read_lesson`.

---

# MENSAGEM FINAL AO USUÁRIO
Responda de forma direta e concisa contendo:
1. O caminho COMPLETO e ABSOLUTO do arquivo `.md` (versão longa preservada) em formato de texto puro (dentro de crases ou bloco de código, SEM formatar como link).
2. Estatísticas rápidas da redução aplicada no Google Doc: palavras Etapa 1 (`.md` longo) → Etapa 2 (Doc reduzido) e `%` reduzida, confirmando a estrutura final (`3` parágrafos na introdução + `4` blocos por tópico).
3. A aba fonte utilizada da apostila (`Revisada` ou `Tmp`), o título e o link do Google Doc de teleprompter criado/atualizado no Drive.
