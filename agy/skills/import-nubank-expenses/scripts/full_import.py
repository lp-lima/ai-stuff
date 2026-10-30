import csv
import json
import re
import os
import glob
import datetime
import sys
import gspread
from google.oauth2.service_account import Credentials

# Constants
SPREADSHEET_ID = "1-MV-Z_NSi4T8mH8nMPr85Byj0MLXeZfUa83blkA2v9Y"
SHEET_TITLE = "Dump de fatura"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "assets", "credentials.json")
CONFIG_PATH = os.path.join(BASE_DIR, "scripts", "config.json")
DOWNLOADS_DIR = "/mnt/c/Users/lplim/Downloads"

STATIC_FILTERS = ["tokio marine", "come and se", "crunchyroll", "amazonprimebr", "petlove", "meli+", "melimais", "plano nucel", "wellhub", "pagamento recebido"]

def get_target_csv():
    target_date = ""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            try:
                config = json.load(f)
                target_date = config.get("target_date", "")
            except:
                pass
                
        # Reset config
        with open(CONFIG_PATH, 'w') as f:
            json.dump({"target_date": ""}, f)
            
    if target_date:
        pattern = os.path.join(DOWNLOADS_DIR, f"Nubank_{target_date}.csv")
        files = glob.glob(pattern)
        if files:
            return files[0]
        # fallback to partial match
        pattern = os.path.join(DOWNLOADS_DIR, f"*{target_date}*.csv")
        files = glob.glob(pattern)
        if files:
            return files[0]
            
    # Default to latest
    files = glob.glob(os.path.join(DOWNLOADS_DIR, "Nubank*.csv"))
    if not files:
        print("Error: No Nubank CSV files found in Downloads.")
        sys.exit(1)
    
    return max(files, key=os.path.getmtime)

def classify_row(row):
    title = row['title']
    amount = row['amount'].replace('.', '').replace(',', '.').replace(' ', '')
    date = row['date']
    
    title_lower = title.lower()
    if any(f in title_lower for f in STATIC_FILTERS):
        return None
        
    if "paypal *google google" in title_lower and amount == "23.99":
        return None
        
    inst_current = 1
    inst_total = 1
    m = re.search(r'Parcela\s+(\d+)/(\d+)', title, re.IGNORECASE)
    if m:
        inst_current = int(m.group(1))
        inst_total = int(m.group(2))
        
    if inst_current > 1:
        return None
        
    cat, subcat, subgrp = "Outros", "", ""
    
    if title_lower.startswith('ifd*') or 'estorno de "ifd*' in title_lower:
        if 'wms' in title_lower or 'comercial oswaldo' in title_lower or 'sendas' in title_lower or 'atacadao' in title_lower:
            cat, subcat, subgrp = "Alimentação", "Mercado", "Ifood"
        elif 'droga' in title_lower or 'farmac' in title_lower:
            cat, subcat, subgrp = "Saúde", "Farmácia", "Ifood"
        else:
            cat, subcat, subgrp = "Alimentação", "Restaurante", "Ifood"
    elif 'uber' in title_lower:
        cat, subcat, subgrp = "Transporte", "Táxi", "Uber"
    elif '99' in title_lower:
        cat, subcat, subgrp = "Transporte", "Táxi", "99"
    elif 'shellbox' in title_lower or 'shell box' in title_lower:
        cat, subcat, subgrp = "Transporte", "Combustível", "Shell Box"
    elif 'petz' in title_lower:
        cat, subcat, subgrp = "Pet", "Mercado", "Petz"
    elif 'nutag' in title_lower:
        cat, subcat, subgrp = "Transporte", "Pedágio", "NuTag"
    elif 'samsung' in title_lower:
        cat, subcat, subgrp = "Eletrônicos", "", "Samsung"
    elif 'samadi' in title_lower:
        cat, subcat, subgrp = "Cuidados Pessoais", "Gym", ""
    elif 'decolar' in title_lower:
        cat, subcat, subgrp = "Lazer", "Viagem", "Decolar"
    elif 'biteli' in title_lower:
        cat, subcat, subgrp = "Carro", "Manutenção", ""
    elif 'montreal' in title_lower:
        cat, subcat, subgrp = "Vestuário", "Roupas", "Montreal"
    elif 'amazon' in title_lower:
        cat, subcat, subgrp = "Outros", "Amazon", "Amazon"
    elif 'mercado' in title_lower:
        cat, subcat, subgrp = "Outros", "Mercado Livre", "Mercado Livre"
    elif 'shopee' in title_lower:
        cat, subcat, subgrp = "Outros", "Shopee", "Shopee"
    elif 'shein' in title_lower:
        cat, subcat, subgrp = "Vestuário", "Roupas", "Shein"
    elif 'riachuelo' in title_lower or 'kallan' in title_lower or 'chilli beans' in title_lower:
        cat, subcat, subgrp = "Vestuário", "", ""
    elif 'drogasil' in title_lower or 'drogaria' in title_lower or 'farmacia' in title_lower:
        cat, subcat, subgrp = "Saúde", "Farmácia", ""
    elif 'casa racoes' in title_lower:
        cat, subcat, subgrp = "Pet", "Mercado", ""
    elif 'google' in title_lower or 'youtube' in title_lower:
        cat, subcat, subgrp = "Lazer", "Streaming", "Google"
    elif 'superfrete' in title_lower:
        cat, subcat, subgrp = "Outros", "Correios", ""

    return {
        'date': date,
        'title': title,
        'amount': amount,
        'cat': cat,
        'subcat': subcat,
        'subgrp': subgrp,
        'freq': 'Ocasional',
        'imp': 'Normal',
        'installment_current': inst_current,
        'installment_total': inst_total,
        'who': 'Ambos'
    }

def normalize_date_to_first(date_str):
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return dt.replace(day=1).strftime("%Y-%m-%d")

def add_months(date_str, months):
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    month = dt.month - 1 + months
    year = dt.year + month // 12
    month = month % 12 + 1
    return datetime.date(year, month, 1).strftime("%Y-%m-%d")

def process_and_upload(csv_path):
    entries = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed = classify_row(row)
            if parsed:
                entries.append(parsed)

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
                expense_date,
                expense_month,
                entry.get('who', 'Ambos'),
                "Lucas",
                entry['cat'],
                entry['subcat'],
                entry['subgrp'],
                entry['freq'],
                entry['imp'],
                1,
                current_pay_date,
                float(entry['amount']),
                current_idx,
                inst_total,
                description
            ]
            final_rows.append(row)
            
    final_rows.sort(key=lambda x: x[0])
    
    # Upload
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"Error: Credentials file not found at {CREDENTIALS_PATH}")
        sys.exit(1)

    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=scopes)
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_TITLE)
    worksheet.batch_clear(["A2:O"])
    
    if final_rows:
        worksheet.update(values=final_rows, range_name="A2", value_input_option="USER_ENTERED")
        print(f"Successfully uploaded {len(final_rows)} rows to '{SHEET_TITLE}' from {csv_path}")
    else:
        print("No rows to upload.")

if __name__ == "__main__":
    target = get_target_csv()
    process_and_upload(target)
