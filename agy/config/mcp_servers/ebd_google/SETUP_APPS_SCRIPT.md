# Configuração Única do Google Apps Script (Teleprompter `makeCopy`)

Este mini Apps Script permite que o MCP `ebd-google` duplique o arquivo de maior índice na pasta `Textos para teleprompter` usando a cota do seu My Drive pessoal (sem nunca expirar), enquanto a Service Account continua fazendo toda a leitura e edição de conteúdo.

## Passo a passo (~2 minutos)

1. Acesse [script.google.com](https://script.google.com) logado na conta **`lpl1696@gmail.com`** e clique em **Novo projeto**.
2. Renomeie o projeto para **`EBD Teleprompter Copier`**.
3. Substitua todo o conteúdo de `Código.gs` pelo conteúdo de [`apps_script/Code.gs`](./apps_script/Code.gs) e salve (`Ctrl+S`).
4. Configure o segredo:
   - No menu esquerdo, clique em **Configurações do projeto** (ícone de engrenagem).
   - Role até **Propriedades do script** → **Adicionar propriedade de script**:
     - **Propriedade:** `EBD_COPY_SECRET`
     - **Valor:** gere uma senha aleatória longa (ex.: no terminal: `openssl rand -hex 24`).
   - Salve as propriedades.
5. Publique como App da Web:
   - Clique em **Implantar** → **Nova implantação** → ícone de engrenagem → **App da Web**.
   - **Executar como:** `Eu (lpl1696@gmail.com)`
   - **Quem pode acessar:** `Qualquer pessoa` *(a chamada é protegida pelo token `EBD_COPY_SECRET` exigido no corpo JSON).*
   - Clique em **Implantar**, autorize o acesso ao Google Drive na sua própria conta e copie a **URL do App da Web** (termina em `/exec`).
6. Crie o arquivo local de segredo (automaticamente ignorado pelo `sync.sh` e pelo `.gitignore` do `ai-stuff`):
   - Caminho: `/home/lp-lima/.gemini/config/mcp_servers/ebd_google/apps_script_secret.json`
   - Conteúdo (baseado em [`apps_script_secret.example.json`](./apps_script_secret.example.json)):
     ```json
     {
       "webapp_url": "https://script.google.com/macros/s/SEU_ID/exec",
       "secret": "MESMO_VALOR_DE_EBD_COPY_SECRET"
     }
     ```

Pronto! Como a pasta `Textos para teleprompter` já é compartilhada com a Service Account, cada cópia criada dentro dela herda automaticamente permissão de edição para a Service Account preencher o conteúdo logo em seguida.
