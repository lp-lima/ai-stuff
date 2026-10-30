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

## Workflow (Zero-Touch Automation)

To guarantee the user does not have to approve multiple shell commands during execution, the classification and upload processes have been fully automated into a single Python script (`scripts/full_import.py`). 

1.  **Configure Target Date (Agent Phase)**:
    -   If the user specifies a particular date or file identifier, use the `replace_file_content` tool to edit `/home/lp-lima/.gemini/skills/import-nubank-expenses/scripts/config.json`.
    -   Update the `target_date` field (e.g., `{"target_date": "2026-09-09"}`).
    -   If the user does not specify a date, you can skip this step. The script will automatically default to the most recently downloaded `Nubank*.csv`.

2.  **Execute Single Static Command (Script Phase)**:
    -   Run the following **EXACT command** using the `run_command` tool. Do not change a single character in this string. This ensures the user can check "Always Allow" to approve this command permanently:
        `/home/lp-lima/.gemini/skills/import-nubank-expenses/venv/bin/python3 /home/lp-lima/.gemini/skills/import-nubank-expenses/scripts/full_import.py`
    -   This script automatically handles:
        -   Resolving the correct file from `~/Downloads`.
        -   Applying all classification logic, filters, and mapping rules (as per `references/mappings.md`).
        -   Normalizing dates, handling installment expansions, and one-month payment offsets.
        -   Uploading the final result directly to the "Dump de fatura" sheet (overwriting `A2:O`).

**Important**: NEVER write helper scripts (e.g., `classify.py`) on the fly, and NEVER run exploratory bash commands (e.g., `find`). Strictly follow the two steps above to maintain a zero-touch experience.

## Reference

-   Detailed classification rules: [mappings.md](references/mappings.md)
