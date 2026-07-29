import csv
import json
import os
import re

import sys
csv_path = sys.argv[1]
output_path = "/home/lp-lima/.gemini/skills/import-nubank-expenses/scripts/classified_data.json"

ignored_keywords = [
    "Tokio Marine", "Come And Se", "Crunchyroll", "Amazonprimebr",
    "PetLove", "Melimais", "Plano NuCel", "Wellhub", "Pagamento recebido"
]

def parse_installment(title):
    match = re.search(r" - Parcela (\d+)/(\d+)$", title)
    if match:
        return int(match.group(1)), int(match.group(2)), title[:match.start()]
    return 1, 1, title

def classify(title):
    t = title.lower()
    who = "Ambos"
    cat = "Outros"
    subcat = "Outros"
    subgrp = ""
    
    if "ri happy" in t or "kids" in t or "raritybaby" in t or "nawafestas" in t or "magnofestas" in t or "fabuletasperso" in t or "tudodasmarias" in t or "ryoliconjuntom" in t:
        who = "Filhos"

    if t.startswith("ifd*"):
        if "coop" in t or "wms" in t:
            cat, subcat, subgrp = "Alimentação", "Mercado", "Ifood"
        elif "farma" in t or "raia" in t or "drogasil" in t:
            cat, subcat, subgrp = "Saúde", "Farmácia", "Ifood"
        else:
            cat, subcat, subgrp = "Alimentação", "Restaurante", "Ifood"
    elif "uber" in t:
        cat, subcat, subgrp = "Transporte", "Táxi", "Uber"
    elif "99 ride" in t:
        cat, subcat, subgrp = "Transporte", "Táxi", "99"
    elif "shell box" in t:
        cat, subcat, subgrp = "Transporte", "Combustível", "Shell Box"
    elif "petz" in t or "racoes" in t:
        cat, subcat, subgrp = "Pet", "Mercado", "Petz" if "petz" in t else ""
    elif "nutag" in t:
        cat, subcat, subgrp = "Transporte", "Pedágio", "NuTag"
    elif "samsung" in t:
        cat, subcat, subgrp = "Eletrônicos", "Outros", "Samsung"
    elif "samadi" in t:
        cat, subcat, subgrp = "Cuidados Pessoais", "Gym", ""
    elif "decolar" in t:
        cat, subcat, subgrp = "Lazer", "Viagem", "Decolar"
    elif "biteli" in t:
        cat, subcat, subgrp = "Carro", "Manutenção", ""
    elif "montreal" in t:
        cat, subcat, subgrp = "Vestuário", "Roupas", "Montreal"
    elif "extra" in t or "ben-hur" in t or "joanin" in t or "carrefour" in t or "sonda" in t or "comercial oswaldo" in t or "spemporio" in t:
        cat, subcat, subgrp = "Alimentação", "Mercado", ""
    elif "drogasil" in t:
        cat, subcat, subgrp = "Saúde", "Farmácia", "Drogasil"
    elif "sorveteri" in t or "pasteis" in t or "doceamor" in t or "pamonha" in t:
        cat, subcat, subgrp = "Alimentação", "Restaurante", ""
    elif "shopee" in t:
        if "tecnologia" in t:
            cat, subcat, subgrp = "Eletrônicos", "Acessórios", "Shopee"
        elif who == "Filhos" and ("festas" in t or "fabuleta" in t):
            cat, subcat, subgrp = "Lazer", "Festas", "Shopee"
        elif who == "Filhos" and ("baby" in t or "kids" in t or "marias" in t or "ryoli" in t):
            cat, subcat, subgrp = "Vestuário", "Roupas", "Shopee"
        elif "ferragens" in t or "util" in t:
            cat, subcat, subgrp = "Casa", "Manutenção" if "ferragens" in t else "Utilidades", "Shopee"
        elif "enxovi" in t:
            cat, subcat, subgrp = "Casa", "Cama, Mesa e Banho", "Shopee"
        else:
            cat, subcat, subgrp = "Outros", "Compras", "Shopee"
    elif "amazon" in t:
        cat, subcat, subgrp = "Outros", "Compras", "Amazon"
    elif "mercadolivre" in t:
        cat, subcat, subgrp = "Outros", "Compras", "Mercado Livre"
    elif "casasbahia" in t or "dois irmaos" in t:
        cat, subcat, subgrp = "Casa", "Móveis/Eletrodomésticos", "Casas Bahia" if "casasbahia" in t else ""
    elif "estante" in t:
        cat, subcat, subgrp = "Educação", "Livros", "Estante Virtual"
    elif "superfrete" in t:
        cat, subcat, subgrp = "Outros", "Correios", "Superfrete"
    elif "paddle.net" in t:
        cat, subcat, subgrp = "Eletrônicos", "Software", "AltTab Pro"
    elif "iof" in t:
        cat, subcat, subgrp = "Impostos", "IOF", ""
        
    return cat, subcat, subgrp, who

classified_data = []

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row:
            continue
        date, title, amount = row
        
        # Check ignored keywords
        skip = False
        for kw in ignored_keywords:
            if kw.lower() in title.lower():
                skip = True
                break
        if skip:
            continue
            
        cur, tot, clean_title = parse_installment(title)
        
        if cur > 1:
            continue
            
        cat, subcat, subgrp, who = classify(clean_title)
        
        amt = float(amount.replace('.', '').replace(',', '.').replace('- ', '-'))
        
        classified_data.append({
            "date": date,
            "title": clean_title,
            "amount": amt,
            "installment_current": cur,
            "installment_total": tot,
            "who": who,
            "cat": cat,
            "subcat": subcat,
            "subgrp": subgrp,
            "freq": "Ocasional",
            "imp": "Normal"
        })

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(classified_data, f, ensure_ascii=False, indent=2)

print(f"Classified {len(classified_data)} items.")
