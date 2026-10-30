import json
import os
import re
import sys
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
CREDENTIALS_PATH = "/home/lp-lima/.gemini/skills/import-nubank-expenses/assets/credentials.json"


def extract_doc_id_and_tab(url_or_id):
    if not url_or_id:
        return "", None
    m_doc = re.search(r"/document/d/([a-zA-Z0-9_-]+)", url_or_id)
    doc_id = m_doc.group(1) if m_doc else url_or_id.strip()
    m_tab = re.search(r"[?&]tab=([a-zA-Z0-9._-]+)", url_or_id)
    tab_id = m_tab.group(1) if m_tab else None
    return doc_id, tab_id


def resolve_tab(doc, tab_id=None, tab_title=None):
    tabs = doc.get("tabs", [])
    if tab_id:
        for t in tabs:
            if t.get("tabProperties", {}).get("tabId") == tab_id:
                return t["tabProperties"]["tabId"], t["documentTab"]["body"]["content"]
    if tab_title:
        for t in tabs:
            if t.get("tabProperties", {}).get("title", "").strip().lower() == tab_title.strip().lower():
                return t["tabProperties"]["tabId"], t["documentTab"]["body"]["content"]
    if tabs:
        t = tabs[0]
        return t["tabProperties"]["tabId"], t["documentTab"]["body"]["content"]
    raise ValueError(f"Nenhuma aba encontrada no documento {doc.get('title')}")


def parse_diretrizes(dir_body):
    aulas = {}
    current_num = None
    current_topico_title = None

    for el in dir_body:
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        style = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        text = "".join(e.get("textRun", {}).get("content", "") for e in p.get("elements", [])).strip()
        if not text:
            continue

        if style == "HEADING_1":
            m = re.match(r"Aula\s+0?(\d+)\s*[–:-]\s*(.*)", text, re.IGNORECASE)
            if m:
                current_num = int(m.group(1))
                aulas[current_num] = {
                    "title": m.group(2).strip(),
                    "direcao": "",
                    "ref": "",
                    "intro": "",
                    "topicos": []
                }
                current_topico_title = None
            else:
                current_num = None
            continue

        if current_num is None:
            continue

        data = aulas[current_num]
        if style == "HEADING_2":
            if text.lower().startswith("versículo-chave:"):
                ref_raw = text.split(":", 1)[1].strip()
                # Garantir separador "." em vez de ":" entre capítulo e versículo
                data["ref"] = ref_raw.replace(":", ".")
            else:
                current_topico_title = text
        elif style == "NORMAL_TEXT":
            if not data["ref"] and not data["direcao"]:
                data["direcao"] = text
            elif data["ref"] and not data["intro"]:
                data["intro"] = re.sub(r"^Introdução:\s*", "", text, flags=re.IGNORECASE)
            elif current_topico_title:
                data["topicos"].append({
                    "title": current_topico_title,
                    "body": text
                })
                current_topico_title = None

    return aulas


def collect_replacements(orig_body, target_aulas, diretrizes_aulas, nvi_verses):
    replacements = []
    current_num = None
    topico_idx = 0

    for i, el in enumerate(orig_body):
        if "paragraph" not in el:
            continue
        p = el["paragraph"]
        style = p.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        p_start = el["startIndex"]
        p_end = el["endIndex"]
        full_text = "".join(e.get("textRun", {}).get("content", "") for e in p.get("elements", []))
        stripped = full_text.strip()
        if not stripped:
            continue

        if style == "HEADING_1":
            m = re.match(r"(Aula\s+0?(\d+)\s*:\s*)(.*)", stripped, re.IGNORECASE)
            if m:
                num = int(m.group(2))
                if num in target_aulas and num in diretrizes_aulas:
                    current_num = num
                    topico_idx = 0
                    prefix = m.group(1)
                    old_title = m.group(3)
                    if old_title != diretrizes_aulas[num]["title"]:
                        s = p_start + len(prefix)
                        e = s + len(old_title)
                        replacements.append((s, e, old_title, diretrizes_aulas[num]["title"], f"Aula {num:02d} - Título da aula"))
                else:
                    current_num = None
            else:
                current_num = None
            continue

        if current_num is None:
            continue

        aula_data = diretrizes_aulas[current_num]
        verse_text = nvi_verses.get(str(current_num), "")

        # 2. Versículo-chave e Referência sob o título
        if "conteúdo do versículo na versão nvi" in stripped.lower():
            for elem in p.get("elements", []):
                run_content = elem.get("textRun", {}).get("content", "")
                r_start = elem.get("startIndex", 0)
                idx_v = run_content.find("conteúdo do versículo na versão NVI")
                if idx_v != -1:
                    target_str = "conteúdo do versículo na versão NVI"
                    s = r_start + idx_v
                    e = s + len(target_str)
                    replacements.append((s, e, target_str, verse_text, f"Aula {current_num:02d} - Texto do versículo (NVI 2011)"))
                idx_r = run_content.find("Referência")
                if idx_r != -1:
                    target_str = "Referência"
                    s = r_start + idx_r
                    e = s + len(target_str)
                    replacements.append((s, e, target_str, aula_data["ref"], f"Aula {current_num:02d} - Referência do versículo-chave"))
            continue

        # 3 & 4. Direção da aula + Diretrizes da Introdução
        if stripped.lower() == "(texto da introdução)" or "lorem ipsum" in stripped.lower() and topico_idx == 0:
            s = p_start
            e = p_end - 1
            new_intro_block = (
                f"(DIREÇÃO DA AULA: {aula_data['direcao']})\n"
                f"(DIRETRIZES DA INTRODUÇÃO: {aula_data['intro']})"
            )
            replacements.append((s, e, stripped, new_intro_block, f"Aula {current_num:02d} - Direção + Introdução"))
            continue

        # 5 & 6. Títulos e Corpos dos tópicos
        if stripped.lower() == "(corpo do tópico)":
            if topico_idx < len(aula_data["topicos"]):
                t_info = aula_data["topicos"][topico_idx]
                prev_el = orig_body[i - 1]
                prev_p = prev_el["paragraph"]
                prev_text = "".join(e.get("textRun", {}).get("content", "") for e in prev_p.get("elements", [])).strip()
                t_s = prev_el["startIndex"]
                t_e = prev_el["endIndex"] - 1
                replacements.append((t_s, t_e, prev_text, t_info["title"], f"Aula {current_num:02d} - Título do tópico {topico_idx + 1}"))

                b_s = p_start
                b_e = p_end - 1
                replacements.append((b_s, b_e, stripped, f"(DIRETRIZES: {t_info['body']})", f"Aula {current_num:02d} - Corpo do tópico {topico_idx + 1}"))
                topico_idx += 1
            continue

        # 7. Terceira tarefa de casa
        if "memorize o versículo-chave:" in stripped.lower():
            idx_ref = full_text.lower().find("referência")
            if idx_ref != -1:
                old_ref = full_text[idx_ref:idx_ref + len("referência")]
                s = p_start + idx_ref
                e = s + len("referência")
                replacements.append((s, e, old_ref, aula_data["ref"], f"Aula {current_num:02d} - Referência na tarefa de casa 3"))
            continue

    return replacements


def build_batch_requests(replacements, tab_id):
    sorted_reps = sorted(replacements, key=lambda x: x[0], reverse=True)
    requests = []
    for s, e, old_text, new_text, desc in sorted_reps:
        requests.append({
            "insertText": {
                "location": {"index": s + 1, "tabId": tab_id},
                "text": new_text
            }
        })
        if e > s + 1:
            requests.append({
                "deleteContentRange": {
                    "range": {
                        "startIndex": s + 1 + len(new_text),
                        "endIndex": e + len(new_text),
                        "tabId": tab_id
                    }
                }
            })
        requests.append({
            "deleteContentRange": {
                "range": {
                    "startIndex": s,
                    "endIndex": s + 1,
                    "tabId": tab_id
                }
            }
        })
    return requests


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    orig_id, orig_url_tab = extract_doc_id_and_tab(config.get("original_doc", ""))
    dir_id, dir_url_tab = extract_doc_id_and_tab(config.get("diretrizes_doc", ""))
    orig_tab_title = config.get("original_tab_title", "Original")
    dir_tab_title = config.get("diretrizes_tab_title", "Diretrizes")
    target_aulas = [int(a) for a in config.get("aulas", [])]
    nvi_verses = config.get("nvi_verses", {})
    mode = config.get("mode", "inspect")

    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=["https://www.googleapis.com/auth/documents"]
    )
    session = AuthorizedSession(creds)

    dir_resp = session.get(f"https://docs.googleapis.com/v1/documents/{dir_id}?includeTabsContent=true")
    if dir_resp.status_code != 200:
        print(f"Erro ao acessar documento de Diretrizes ({dir_resp.status_code}): {dir_resp.text}")
        sys.exit(1)
    dir_doc = dir_resp.json()
    _, dir_body = resolve_tab(dir_doc, tab_id=dir_url_tab, tab_title=dir_tab_title)

    diretrizes_aulas = parse_diretrizes(dir_body)
    if not target_aulas:
        target_aulas = sorted(diretrizes_aulas.keys())

    if mode == "inspect":
        print("=== AULAS EXTRAÍDAS DAS DIRETRIZES ===")
        for num in target_aulas:
            if num in diretrizes_aulas:
                d = diretrizes_aulas[num]
                print(f"Aula {num:02d}: {d['title']}")
                print(f"  Versículo-chave: {d['ref']}")
                print(f"  Direção: {d['direcao'][:100]}...")
                print(f"  Introdução: {d['intro'][:100]}...")
                print(f"  Tópicos ({len(d['topicos'])}): {[t['title'] for t in d['topicos']]}")
        return

    missing_verses = [num for num in target_aulas if not nvi_verses.get(str(num))]
    if missing_verses:
        print(f"Erro: Faltam os textos na NVI 2011 em 'nvi_verses' no config.json para as aulas: {missing_verses}")
        for num in missing_verses:
            if num in diretrizes_aulas:
                print(f"  Aula {num:02d} requer referência: {diretrizes_aulas[num]['ref']}")
        sys.exit(1)

    orig_resp = session.get(f"https://docs.googleapis.com/v1/documents/{orig_id}?includeTabsContent=true")
    if orig_resp.status_code != 200:
        print(f"Erro ao acessar documento Original ({orig_resp.status_code}): {orig_resp.text}")
        sys.exit(1)
    orig_doc = orig_resp.json()
    orig_tab_id, orig_body = resolve_tab(orig_doc, tab_id=orig_url_tab, tab_title=orig_tab_title)

    replacements = collect_replacements(orig_body, target_aulas, diretrizes_aulas, nvi_verses)
    print(f"Total de substituições preparadas: {len(replacements)}")
    for s, e, old_t, new_t, desc in replacements:
        print(f"  [{s}:{e}] {desc}: {repr(old_t)} -> {repr(new_t[:80])}...")

    if not replacements:
        print("Nenhuma substituição encontrada para as aulas selecionadas.")
        return

    reqs = build_batch_requests(replacements, orig_tab_id)
    update_resp = session.post(
        f"https://docs.googleapis.com/v1/documents/{orig_id}:batchUpdate",
        json={"requests": reqs}
    )
    if update_resp.status_code != 200:
        print(f"Erro no batchUpdate ({update_resp.status_code}): {update_resp.text}")
        sys.exit(1)

    print("Sucesso! Documento atualizado no Google Docs preservando 100% da formatação.")


if __name__ == "__main__":
    main()
