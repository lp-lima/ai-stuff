import json
import datetime
import sys
import os
import gspread
from google.oauth2.service_account import Credentials

# Constants
SPREADSHEET_ID = "1-MV-Z_NSi4T8mH8nMPr85Byj0MLXeZfUa83blkA2v9Y"
SHEET_TITLE = "Dump de fatura"
CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "../assets/credentials.json")

def normalize_date_to_first(date_str):
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return dt.replace(day=1).strftime("%Y-%m-%d")

def add_months(date_str, months):
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    return datetime.date(year, month, 1).strftime("%Y-%m-%d")

def process_import(input_json_path):
    with open(input_json_path, 'r', encoding='utf-8') as f:
        entries = json.load(f)
    
    final_rows = []
    
    for entry in entries:
        expense_date = entry['date']
        expense_month = normalize_date_to_first(expense_date)
        base_payment_date = add_months(expense_month, 1)
        
        inst_current = int(entry['installment_current'])
        inst_total = int(entry['installment_total'])
        
        iterations = inst_total if inst_current == 1 else 1
        
        for i in range(iterations):
            current_idx = inst_current + i
            current_pay_date = add_months(base_payment_date, i)
            
            description = entry['title']
            if i > 0:
                description = f"{description} (Expansão {current_idx}/{inst_total})"

            row = [
                expense_date,              # A
                expense_month,             # B
                entry.get('who', 'Ambos'), # C - Quem gastou?
                "Lucas",                   # D
                entry['cat'],              # E
                entry['subcat'],           # F
                entry['subgrp'],           # G
                entry['freq'],             # H
                entry['imp'],              # I
                1,                         # J
                current_pay_date,          # K
                float(entry['amount']),    # L
                current_idx,               # M
                inst_total,                # N
                description                # O
            ]
            final_rows.append(row)
            
    final_rows.sort(key=lambda x: x[0])
    return final_rows

def upload_to_sheets(rows):
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]

    if not os.path.exists(CREDENTIALS_PATH):
        print(f"Error: Credentials file not found at {CREDENTIALS_PATH}")
        print("       Place the service account JSON key at assets/credentials.json")
        sys.exit(1)

    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=scopes)
    client = gspread.authorize(creds)

    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(SHEET_TITLE)

    # Clear A2:O (assuming A1 is header)
    worksheet.batch_clear(["A2:O"])

    # Update A2 with new rows
    if rows:
        worksheet.update(values=rows, range_name="A2")
        print(f"Successfully uploaded {len(rows)} rows to '{SHEET_TITLE}'.")
    else:
        print("No rows to upload.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 process_import.py <input_json_path>")
        sys.exit(1)

    processed_rows = process_import(sys.argv[1])
    upload_to_sheets(processed_rows)
