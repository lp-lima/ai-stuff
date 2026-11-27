---
name: teleprompter-ebd
description: Lê a aula e suas diretrizes diretamente do Google Docs (via MCP ebd-google), gera o roteiro de teleprompter em duas etapas — (1) versão longa/completa fiel salva e commitada no .md local e (2) redução editorial em memória no padrão de 4 blocos por tópico guiada pelas diretrizes — e publica a versão reduzida diretamente no Google Doc na pasta "Textos para teleprompter" (preservando o .md local na versão longa) com Ideia Central, Perguntas para reflexão e Tarefas de casa anexadas ao final.
---

# Teleprompter de EBD (Fluxo em 2 Etapas + Google Docs MCP)

## CONTEXTO E OBJETIVO
Você é um assistente editorial de um professor de Escola Bíblica Discipuladora (EBD) responsável por transformar uma aula de apostila em um roteiro pronto para gravação em **teleprompter**.

O processo ocorre obrigatoriamente em **2 etapas sequenciais**, sempre guiadas pelas **Diretrizes da aula**:
1. **Etapa 1 — Geração do Roteiro Completo / Versão Longa (100% fiel ao conteúdo):** reescreve toda a aula em linguagem oral fluida, natural e pastoral, sem cortar ideias, orientada pelas diretrizes da aula, e salva/commita essa **versão longa** no `.md` local no Git (preservando o arquivo base intacto).
2. **Etapa 2 — Redução Editorial Cirúrgica (Padrão Bruna, publicada somente no Google Docs):** aplica em memória princípios rigorosos de poda intra-parágrafo e fusão sobre o texto da Etapa 1, usando as **Diretrizes da aula como bússola de relevância** para nunca cortar pontos essenciais, consolidando cada tópico em **exatamente 4 blocos numerados `[1]`–`[4]`** (e a introdução em 3 parágrafos sem numeração), e publica essa versão reduzida **diretamente no Google Docs** via MCP `ebd-google` (**sem sobrescrever** o `.md` local).

---

# PRÉ-ETAPA — LEITURA CONJUNTA NO GOOGLE DOCS (MCP `ebd-google`)

Chame **em paralelo** no MCP `ebd-google`:
1. `read_guidelines(course="<curso>", lesson_num=<N>)` — lê as Diretrizes da aula direto da pasta `Ementa(s) e diretrizes` no Drive (para `lesson_num=0`, lê a Ementa).
2. `read_lesson(course="<curso>", lesson_num=<N>, tab="auto", save_local_md=false)` — lê a aula da aba ativa (`Revisada` ou `Tmp`).

**Proibição de comandos exploratórios:** não rode `ls`, `find` ou `grep` exploratório no repositório, não chame `list_courses` desnecessariamente (`read_lesson` já retorna `local_course_dir`, `active_tab` e `title_full`) e não leia aulas antigas de teleprompter para buscar exemplos.

Antes de começar a Etapa 1, mapeie mentalmente os **eixos obrigatórios das Diretrizes** (`direcao`, `versiculo_chave`, `introducao` e cada bloco de `topicos`) — eles são a lista de conteúdo **inegociável** que deve sobreviver intacta até o final da Etapa 2.

---

# ETAPA 1 — ROTEIRO DE TELEPROMPTER COMPLETO (FIEL — 100% DO CONTEÚDO)

Transforme integralmente o texto da aula em uma versão para leitura em voz alta mantendo **100% do conteúdo** (sem resumir nem cortar ideias nesta etapa), apenas reescrevendo para ficar fluido, natural, didático e fácil de falar em câmera.

## Regras de Estilo da Etapa 1
- **Volume fiel:** mantenha o volume próximo ao da apostila (sem resumir e sem acrescentar floreios linguísticos).
- **Tom pastoral culto-acessível:** soe como um pastor/professor experiente ensinando em conversa clara e direta.
  - Use **1ª pessoa do plural ("nós" ou sujeito oculto: *"nós vamos"*, *"percebemos"*, *"olhamos"*)** — **NÃO use *"a gente"*** (para manter consistência direta com o padrão final de gravação).
  - Evite gírias/clichês informais exagerados (*"na marra"*, *"deu de cara"*, *"falar bonito"*, *"pobre coitado"*, *"louco varrido"*, *"culpa no cartório"*, *"bater o martelo"*, *"cravar"*, *"fechar com chave de ouro"*) e evite *"lá"* desnecessário (*"lá em Filipos"* → *"em Filipos"*).
  - Evite ênclises (*"trata-se"*, *"mostra-nos"*) e prefira *"só"* no lugar de *"apenas"* quando soar mais natural.
  - Evite iniciar frases com *"trata-se de"*, *"consiste em"*, *"refere-se a"*, acúmulo de adjetivos e linguagem poética/inflada.
  - Mantenha marcadores leves de proximidade didática (*"Perceba que"*, *"Repare como"*, *"Veja que"*).
- **Zero Markdown no texto falado:** não use `**negrito**` nem `*itálico*` no corpo do roteiro.
- **Algarismos para leitura rápida em teleprompter:** escreva datas, capítulos, versículos, percentuais e números altos em **algarismos arábicos** (`1780`, `612`, `10%`, `120 mil`, `capítulo 22`, `Romanos 14`, `artigos 15 e 16`) e séculos de forma limpa (`século VIII` ou `século 20`).
- **Não use dois pontos (`:`)** no corpo do texto, exceto imediatamente antes de citações diretas da Bíblia (incluindo o versículo-chave).
- **Índices na Etapa 1:** numere cada parágrafo da introdução e de cada tópico com `[1]`, `[2]`, ... (reiniciando em `[1]` a cada seção; títulos não contam na numeração).
- **Estrutura da Etapa 1:**
  1. **Abertura estilo aula:**
     - `Olá! Sejam bem-vindos à aula X do curso Y.` *(para Aula 00: `aula introdutória`)*
     - `Hoje nós vamos…` (resumo claro alinhado à `direcao` das diretrizes)
     - `Vamos ler juntos o texto-chave que está em [Referência por extenso]: “[Texto exato da apostila]”` *(sem repetir `(Ref)` entre parênteses no final da citação)*
     - Convite breve à oração (sem escrever a oração), seguido de linha em branco e `(Oração)`.
  2. **Introdução:** todos os parágrafos da introdução em linguagem falada.
  3. **Corpo da Aula:** todos os tópicos na ordem original, preservando os títulos e todas as ideias.
  4. **O que ignorar no roteiro falado:** IGNORE `Ideia Central`, `Perguntas para reflexão`, `Perguntas para discussão` e `Tarefas de casa` (as 3 seções de fechamento serão copiadas automaticamente da apostila ao final do Google Doc pela ferramenta `publish_teleprompter`).

## Checkpoint Local da Versão Longa (Git — Preservar Intacto)
1. Salve o roteiro completo (versão longa) da Etapa 1 com `write_file` em `{local_course_dir}/teleprompter/aula_{XX}_teleprompter.md` (sempre 2 dígitos com zero à esquerda, ex.: `aula_07_teleprompter.md`).
2. Valide se a chave GPG está destravada (`gpg-connect-agent 'keyinfo --list' /bye`). Se estiver, faça o commit único usando `git -C` (NUNCA `cd ... &&`):
   ```bash
   git -C "/mnt/c/Users/lplim/repos/revisao_ebd" add "{local_course_dir}/teleprompter/aula_{XX}_teleprompter.md" && git -C "/mnt/c/Users/lplim/repos/revisao_ebd" commit -m "Curso [Nome do Curso] - Aula [XX] - versão teleprompter"
   ```
3. **NUNCA sobrescreva** esse arquivo `.md` na Etapa 2 — ele deve permanecer sempre na versão longa completa.

---

# ETAPA 2 — REDUÇÃO EDITORIAL CIRÚRGICA (PADRÃO BRUNA, GUIADA PELAS DIRETRIZES)

Agora transforme o roteiro completo da Etapa 1 na **versão final de teleprompter pronta para gravação**, aplicando rigorosamente os princípios abaixo (extraídos por engenharia reversa das edições reais nos 3 cursos do bimestre).

## 1. Arquitetura Estrutural Obrigatória (Hard Constraints)
- **Abertura e Oração (intactas):** mantenha as 4 falas de abertura (saudação, resumo, texto-chave sem referência parentética duplicada no final, convite à oração) seguidas da marca isolada **`(Oração)`**.
- **Introdução (sem colchetes `[N]`):**
  - **Aula regular (01+):** consolide para **exatamente 3 parágrafos** (ou 2 se a aula for curta, <4.000 palavras) e **REMOVA todos os índices `[1]`, `[2]`, `[3]`** da introdução.
  - **Aula 00 (introdução ao curso):** consolide para **5 parágrafos sem índices `[N]`** (~850–950 palavras).
- **Tópicos do corpo (exatamente 4 blocos cada):**
  - Converta 100% dos títulos de tópico para **`(TÍTULO DO TÓPICO EM CAIXA ALTA)`** (sem Markdown).
  - Consolide **cada tópico** (seja de 5, 6 ou 7 parágrafos) em **exatamente 4 parágrafos numerados `[1]`, `[2]`, `[3]`, `[4]`** (renumerados sequencialmente).

## 2. Orçamento de Palavras e Mecanismo de Redução (*Cut-and-Stitch*, NÃO Deleção Cega)
- **Faixa-alvo de redução:** reduza o volume total em torno de **15% a 25%** em aulas longas (ou ~8% a 12% em aulas já enxutas):
  - Aulas expositivas/epístolas (~4.000–5.000w na Etapa 1) → mirar **~3.600 a 4.100 palavras** (~550–780w/tópico; ~140–195w por bloco `[1]`–`[4]`).
  - Aulas densas/doutrinárias/proféticas (~6.000–7.800w na Etapa 1) → mirar **~4.900 a 5.350 palavras** (~800–960w/tópico; ~200–245w por bloco `[1]`–`[4]`). *(Em aulas de alta sensibilidade teológica/comparativa, priorize preservar nuances doutrinárias mesmo ficando um pouco acima da faixa, mantendo sempre os 4 blocos por tópico.)*
- **Como reduzir de 5–7 parágrafos para 4 (CRÍTICO):**
  - **NÃO delete parágrafos inteiros arbitrariamente.** Faça **poda cirúrgica intra-parágrafo + fusão de pares adjacentes** (ex.: `[1]+[2]`, `[3]+[4]`, `[5]+[6]`).
  - Quando a fusão desequilibrar o tamanho dos blocos, aplique **cisão estratégica (*split & merge*)**: divida um parágrafo intermediário na virada natural de assunto para manter os 4 blocos equilibrados.

## 3. O que NUNCA Cortar (Proteção Guiada pelas Diretrizes)
1. **100% da espinha dorsal de `read_guidelines`:** toda tese central, conceito bíblico, estrutura literária e aplicação exigida nas diretrizes da aula deve permanecer clara e íntegra.
2. **Posicionamentos confessionais e identidade local:** preserva integralmente citações da Declaração Doutrinária da CBB / confissões previstas nas diretrizes e explicações transparentes da posição da igreja local (Conexão Primeira Batista).
3. **O bloco `[4]` (fechamento e aplicação pastoral):** concentre a poda no miolo expositivo (`[1]`–`[3]`) e **proteja o parágrafo final de cada tópico (`[4]`)**, onde estão a síntese espiritual, a aplicação prática para a Igreja e o encerramento devocional da aula.
4. **Citações bíblicas curtas e dramáticas integradas à fala** (ex.: frases-clímax de 1 linha que ancoram o argumento).
5. **Ponte com a aula anterior** na introdução (curta, em 1 frase-gancho).

## 4. Taxonomia do que CORTAR na Etapa 2 (6 Alvos Cirúrgicos)
1. **100% das referências bíblicas entre parênteses no corpo falado:** remova todas as citações parentéticas abreviadas como `(Fp 1.12)`, `(Os 4.1)`, `(cf. 2Rs 14.25)`, `(1Co 10.31; Rm 12.2)`. Quando uma passagem for indispensável na fala (ex.: antes de uma citação direta), integre-a naturalmente no fluxo oral (*"nas palavras de Filipenses 3.10-11:"*, *"no texto de Romanos 14"*), removendo preposições órfãs (como `"em"` antes de um parêntese apagado).
2. **Redundâncias e duplas explicações ("uma única explicação por ideia"):** corte segundas frases que apenas reformulam o que acabou de ficar claro (`"Ou seja,..."`, `"Em outras palavras,..."`, `"Isso significa que..."`), explicações óbvias e repetições entre tópicos da mesma aula.
3. **Catálogos e enumerações ("regra dos 1–2 exemplos bastam"):** quando houver 3 a 5 exemplos bíblicos, cidades, pragas ou itens listados para provar o mesmo ponto, mantenha apenas os **1 ou 2 mais fortes** e sintetize o restante.
4. **Comentaristas acadêmicos e citações/nomes externos fora das diretrizes:** corte referências a comentaristas modernos/séries técnicas, sociólogos, pregadores/hinos ou biografias históricas secundárias não pedidas nas diretrizes (exceção apenas para frase-definição lapidar indispensável ou documentos confessionais das diretrizes).
5. **Detalhes enciclopédicos, filologia secundária, spoilers e autopromoção:** corte nomes de reis/personagens obscuros, datas intermediárias acessórias, geografia sem peso pastoral, termos gregos/hebraicos secundários ou já explicados em aulas anteriores (mantenha termos originais apenas quando estruturantes/pedidos nas diretrizes e na 1ª ocorrência no curso), antecipação de temas de aulas futuras, autopromoção de outros cursos e referências culturais datadas.
6. **Citações bíblicas longas redundantes:** se uma citação bíblica longa (3+ linhas) apenas repete o que já está explicado ao redor, corte-a mantendo a síntese oral.

## 5. Costura de Fluidez e Higiene Oral (Anti-Vícios de IA)
- **Elimine muletas de transição na emenda dos blocos:** ao fundir parágrafos e revisar aberturas, corte marcadores repetitivos de IA como `"Com isso em mente,"`, `"Dito isso,"`, `"Nesse ponto,"`, `"Na prática,"`, `"Agora,"`, `"A partir daqui,"`, `"Seguindo em frente,"`, `"No fim das contas,"` (prefira `"No fim,"` ou entrada direta no sujeito).
- **Verifique coesão após cada corte:** releia toda emenda entre frases mantidas para garantir que pronomes (`ele`, `isso`, `essas pessoas`) mantenham referente claro e não reste nenhuma frase truncada.
- **Zero `"a gente"` e zero Markdown** em todo o documento final.

---

# ETAPA FINAL — PUBLICAÇÃO DA VERSÃO REDUZIDA NO GOOGLE DOCS

- **NÃO altere nem sobrescreva** o arquivo `.md` local salvo na Etapa 1 (ele preserva a versão longa no Git).
- Chame `ebd-google` → `publish_teleprompter` enviando a **versão reduzida final da Etapa 2**:
  - `course`: `<curso>`
  - `lesson_num`: `<N>`
  - `title`: `title_full` retornado por `read_lesson` (ex.: `"Aula 07: ..."`)
  - `teleprompter_paragraphs`: lista ordenada de parágrafos da versão reduzida final da Etapa 2 (incluindo abertura, `""`, `"(Oração)"`, `""`, os 3 parágrafos da introdução sem `[N]`, e para cada tópico: `""`, `"(TÍTULO EM CAIXA ALTA)"`, `[1] ...`, `[2] ...`, `[3] ...`, `[4] ...`).
  - `source_tab`: `active_tab` retornado por `read_lesson`.

---

# MENSAGEM FINAL AO USUÁRIO
Responda de forma direta e concisa contendo:
1. O caminho COMPLETO e ABSOLUTO do arquivo `.md` (versão longa preservada) em formato de texto puro (dentro de crases ou bloco de código, SEM formatar como link).
2. Estatísticas rápidas da redução aplicada no Google Doc: palavras Etapa 1 (`.md` completo) → Etapa 2 (Doc reduzido) e `%` reduzida, confirmando a estrutura final (`3` parágrafos na introdução + `4` blocos por tópico).
3. A aba fonte utilizada da apostila (`Revisada` ou `Tmp`), o título e o link do Google Doc de teleprompter criado/atualizado no Drive.
