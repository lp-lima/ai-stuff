---
name: import-nubank-expenses
description: Import and classify Nubank credit card entries from CSV into the "Custos" Google Spreadsheet. Use when a user provides a Nubank CSV file (e.g., from Downloads) and wants it added to the "Dump de fatura" sheet with automated classification, installment expansion, and date normalization.
---

# Import Nubank Expenses

This skill automates the process of importing Nubank credit card transactions into the "Custos" spreadsheet (ID: `1-MV-Z_NSi4T8mH8nMPr85Byj0MLXeZfUa83blkA2v9Y`). It uses a hybrid architecture: the Agent handles classification (fuzzy logic), and a Python script handles deterministic processing and direct upload to Google Sheets.

## Setup Requirements (One-time)

1.  **Google Cloud Credentials**:
    -   Use the existing GCP project `gemini-workspace-mcp-497221`.
    -   A **Service Account** (`spreadsheets-editor@gemini-workspace-mcp-497221.iam.gserviceaccount.com`) is already configured.
    -   Its JSON key is stored at `assets/credentials.json` within the skill directory.
    -   Only the **Google Sheets API** needs to be enabled (no Drive API required).
2.  **Spreadsheet Sharing**:
    -   The "Custos" spreadsheet must be shared with the service account's `client_email` (give it "Editor" access).
3.  **Python Dependencies**:
    -   A virtual environment at `venv/` contains `gspread` and `google-auth`.

## Workflow

1.  **Resolve File Path**: Identify the credit card bill file (CSV) based on the user's description. Fall back to the latest `Nubank*.csv` in `Downloads/`.
2.  **Classification (Agent Phase)**:
    -   **Filter**: 
        -   **IGNORE** any entry that is marked as a second installment or later (e.g., "Parcela 2/3").
        -   **IGNORE** static recurring/non-purchase entries: `Tokio Marine`, `Come And Se`, `Crunchyroll`, `Amazonprimebr`, `PetLove`, `Meli+`, `Plano NuCel`, `Wellhub`, and `Pagamento recebido`.
    -   **Map & Classify**: Use [mappings.md](references/mappings.md) to assign `Categoria`, `Subcategoria`, and `Subgrupo`. Set `Quem gastou?` to "Ambos", `Pago por quem?` to "Lucas", and `Adiamento de pagamento` to `1`.
    -   **Staging**: Save the classified data to `scripts/classified_data.json`.
3. **Processing & Upload (Script Phase)**:
    -   Execute the script using the virtual environment: `venv/bin/python3 scripts/process_import.py scripts/classified_data.json`.
    -   The script authenticates via the service account key at `assets/credentials.json`.
    -   The script will:

        -   Normalize dates to the 1st of the month.
        -   Apply a one-month payment offset.
        -   Expand installments into multiple rows.
        -   **Directly upload** the data to the "Dump de fatura" sheet, overwriting range `A2:O`.

## Reference

-   Detailed classification rules: [mappings.md](references/mappings.md)
